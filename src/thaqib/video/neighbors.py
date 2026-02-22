"""
Neighbor computation for spatial awareness system.

Responsible ONLY for neighbor computation based on Euclidean distance.
"""

import numpy as np

from thaqib.video.registry import GlobalStudentRegistry, StudentSpatialState


class NeighborComputer:
    """Computes k-nearest neighbors for all students in the registry."""

    def compute_neighbors(self, registry: GlobalStudentRegistry, k: int = 4) -> None:
        """
        Compute neighbors for all students in the registry.
        Adds 'neighbors' and 'neighbor_distances' fields dynamically to StudentSpatialState.
        """
        all_states = registry.get_all()

        if not all_states:
            return

        for state in all_states:
            distances: list[tuple[int, float]] = []

            for other_state in all_states:
                if state.track_id == other_state.track_id:
                    continue

                # Compute Euclidean distance using numpy
                p1 = np.array(state.center)
                p2 = np.array(other_state.center)
                distance = float(np.linalg.norm(p1 - p2))

                distances.append((other_state.track_id, distance))

            # Sort ascending by distance
            distances.sort(key=lambda x: x[1])

            # Select nearest k
            nearest_k = distances[:k]

            # Store results
            state.neighbors = [n[0] for n in nearest_k]
            state.neighbor_distances = {n[0]: n[1] for n in nearest_k}
