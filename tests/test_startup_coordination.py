"""
Unit tests for Repair D: Startup Synchronization & Fail-Fast Mechanics.
"""

import sys
import threading
import time
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from thaqib.startup import StartupCoordinator


class TestStartupCoordination(unittest.TestCase):
    def test_happy_path_synchronization(self):
        """All components preloading models and signaling ready should unblock the barrier cleanly."""
        components = ["cam0", "cam1", "audio"]
        coord = StartupCoordinator(components)

        results = []

        def worker(cid, delay):
            time.sleep(delay)
            coord.signal_ready(cid)
            res = coord.wait_barrier(timeout=2.0)
            results.append((cid, res))

        threads = [
            threading.Thread(target=worker, args=("cam0", 0.05)),
            threading.Thread(target=worker, args=("cam1", 0.1)),
            threading.Thread(target=worker, args=("audio", 0.15)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 3)
        for cid, res in results:
            self.assertTrue(res, f"Component {cid} barrier failed unexpectedly")
        self.assertFalse(coord.abort_event.is_set())

    def test_fail_fast_on_component_failure(self):
        """When one component fails startup, abort_event is set immediately and others don't hang."""
        components = ["cam0", "cam1", "audio"]
        coord = StartupCoordinator(components)

        results = []

        def worker(cid, should_fail):
            if should_fail:
                time.sleep(0.05)
                coord.signal_failed(cid, "Simulated device init error")
                results.append((cid, False))
            else:
                coord.signal_ready(cid)
                res = coord.wait_barrier(timeout=0.5)
                results.append((cid, res))

        threads = [
            threading.Thread(target=worker, args=("cam0", False)),
            threading.Thread(target=worker, args=("cam1", True)),  # Failing worker
            threading.Thread(target=worker, args=("audio", False)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertTrue(coord.abort_event.is_set())
        self.assertTrue(coord.failed_events["cam1"].is_set())

    def test_timeout_unready_components(self):
        """wait_for_all_ready should return False and abort if a component never signals ready."""
        components = ["cam0", "cam1"]
        coord = StartupCoordinator(components)

        coord.signal_ready("cam0")
        # cam1 never signals ready

        success = coord.wait_for_all_ready(timeout=0.1)
        self.assertFalse(success)
        self.assertTrue(coord.abort_event.is_set())


if __name__ == "__main__":
    unittest.main()
