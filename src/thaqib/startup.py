"""
Centralized startup coordination and barrier synchronization.
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)


class StartupCoordinator:
    """Coordinates multi-pipeline startup, model preloading, and synchronized barrier release."""

    def __init__(self, component_ids: list[str]):
        self.component_ids = list(component_ids)
        self.ready_events = {cid: threading.Event() for cid in self.component_ids}
        self.failed_events = {cid: threading.Event() for cid in self.component_ids}
        self.start_barrier = threading.Barrier(len(self.component_ids)) if self.component_ids else None
        self.abort_event = threading.Event()

    def signal_ready(self, cid: str) -> None:
        """Signal that a component has finished preloading models and is ready to run."""
        if cid in self.ready_events:
            self.ready_events[cid].set()
            logger.info(f"Component [{cid}] is READY.")

    def signal_failed(self, cid: str, reason: str = "") -> None:
        """Signal that a component encountered a fatal error during initialization."""
        if cid in self.failed_events:
            self.failed_events[cid].set()
        self.abort_event.set()
        logger.error(f"Component [{cid}] FAILED startup: {reason}")

    def wait_for_all_ready(self, timeout: float = 30.0) -> bool:
        """Blocks until all components signal ready, or abort is triggered, or timeout expires."""
        start_t = time.time()
        while time.time() - start_t < timeout:
            if self.abort_event.is_set():
                return False
            if all(evt.is_set() for evt in self.ready_events.values()):
                return True
            time.sleep(0.02)

        # Timeout expired
        unready = [cid for cid, evt in self.ready_events.items() if not evt.is_set()]
        logger.error(f"Startup timed out after {timeout}s waiting for: {unready}")
        self.abort_event.set()
        return False

    def wait_barrier(self, timeout: float = 10.0) -> bool:
        """Synchronized release of all ready workers to begin processing simultaneously."""
        if self.abort_event.is_set() or self.start_barrier is None:
            return False
        try:
            self.start_barrier.wait(timeout=timeout)
            return True
        except threading.BrokenBarrierError:
            self.abort_event.set()
            return False
