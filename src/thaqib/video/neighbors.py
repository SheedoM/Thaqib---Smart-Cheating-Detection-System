"""
Neighbor computation for spatial awareness system.

Responsible ONLY for neighbor computation based on Euclidean distance.
"""

import numpy as np

from thaqib.video.registry import GlobalStudentRegistry, StudentSpatialState


class NeighborComputer:
    """Computes k-nearest neighbors for all students in the registry using vectorized numpy operations."""

    def compute_neighbors(self, registry: GlobalStudentRegistry, k: int = 4) -> None:
        """
        Compute neighbors for all students in the registry.
        Adds 'neighbors' and 'neighbor_distances' fields dynamically to StudentSpatialState.
        Uses vectorized NumPy broadcasting for O(1) loop speed.
        """
        all_states = [s for s in registry.get_all() if getattr(s, "is_active", True)]
        n_students = len(all_states)

        if n_students <= 1:
            for state in all_states:
                state.neighbors = []
                state.neighbor_distances = {}
                state.neighbor_papers = {}
            return

        # Extract centers into a (N, 2) numpy array
        centers = np.array([state.center for state in all_states], dtype=float)
        
        # Calculate pairwise Euclidean distance matrix using broadcasting
        # Shape: (N, 1, 2) - (1, N, 2) -> (N, N, 2)
        diff = centers[:, np.newaxis, :] - centers[np.newaxis, :, :]
        dist_matrix = np.linalg.norm(diff, axis=2)

        # Set diagonal to infinity so a student is not their own neighbor
        np.fill_diagonal(dist_matrix, np.inf)

        # Ensure k is not larger than the available neighbors
        actual_k = min(k, n_students - 1)

        # Find the indices of the top k nearest neighbors for each student
        # argpartition is O(N) compared to argsort which is O(N log N)
        nearest_indices = np.argpartition(dist_matrix, actual_k - 1, axis=1)[:, :actual_k]

        # Map back to track IDs and distances
        track_ids = [state.track_id for state in all_states]
        paper_centers = [state.paper_center for state in all_states]
        
        for i, state in enumerate(all_states):
            # Sort the nearest ones by distance for this specific student
            row_indices = nearest_indices[i]
            sorted_row_indices = row_indices[np.argsort(dist_matrix[i, row_indices])]
            
            state.neighbors = [track_ids[idx] for idx in sorted_row_indices]
            state.neighbor_distances = {track_ids[idx]: float(dist_matrix[i, idx]) for idx in sorted_row_indices}
            state.neighbor_papers = {track_ids[idx]: paper_centers[idx] for idx in sorted_row_indices}
