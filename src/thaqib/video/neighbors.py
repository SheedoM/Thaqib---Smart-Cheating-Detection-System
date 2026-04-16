"""
Neighbor computation for spatial awareness system.

Responsible ONLY for neighbor computation based on Euclidean distance.
"""

import numpy as np

from thaqib.video.registry import GlobalStudentRegistry, StudentSpatialState


class NeighborComputer:
    """Computes k-nearest neighbors for all students in the registry using vectorized numpy operations."""

    def __init__(self) -> None:
        # Cache for skip-if-stable optimization
        self._prev_centers: np.ndarray | None = None
        self._prev_track_ids: list[int] | None = None
        self._stability_threshold: float = 20.0  # pixels

    def compute_neighbors(self, registry: GlobalStudentRegistry, k: int = 4) -> None:
        """
        Compute neighbors for all students in the registry.
        Adds 'neighbors' and 'neighbor_distances' fields dynamically to StudentSpatialState.
        Uses vectorized NumPy broadcasting for O(1) loop speed.

        Skips recomputation if all student centers moved < 20px since last call
        (common in a stable exam hall).
        """
        all_states = [s for s in registry.get_all() if getattr(s, "is_active", True)]
        n_students = len(all_states)

        if n_students <= 1:
            for state in all_states:
                state.neighbors = []
                state.neighbor_distances = {}
                state.neighbor_papers = {}
            self._prev_centers = None
            self._prev_track_ids = None
            return

        # Extract centers into a (N, 2) numpy array
        centers = np.array([state.center for state in all_states], dtype=float)
        track_ids = [state.track_id for state in all_states]

        # Skip-if-stable: if same students and barely moved, reuse previous result
        if (self._prev_centers is not None
            and self._prev_track_ids is not None
            and self._prev_track_ids == track_ids
            and len(self._prev_centers) == len(centers)):
            max_movement = np.max(np.linalg.norm(centers - self._prev_centers, axis=1))
            if max_movement < self._stability_threshold:
                return  # Skip recomputation — positions are stable

        self._prev_centers = centers.copy()
        self._prev_track_ids = list(track_ids)

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
        paper_centers = [state.paper_center for state in all_states]
        
        for i, state in enumerate(all_states):
            # Sort the nearest ones by distance for this specific student
            row_indices = nearest_indices[i]
            sorted_row_indices = row_indices[np.argsort(dist_matrix[i, row_indices])]
            
            state.neighbors = [track_ids[idx] for idx in sorted_row_indices]
            state.neighbor_distances = {track_ids[idx]: float(dist_matrix[i, idx]) for idx in sorted_row_indices}
            state.neighbor_papers = {track_ids[idx]: paper_centers[idx] for idx in sorted_row_indices}

    def compute_paper_neighbors(
        self, registry: GlobalStudentRegistry, all_papers: list[tuple[int, int]]
    ) -> None:
        """
        Compute surrounding papers using exclusive greedy ownership assignment.

        Each detected paper is assigned to its single closest student (1-to-1).
        Students without a YOLO-detected paper fall back to their `paper_center`
        (bottom-center of bbox), since in an exam setting every student has a paper.

        A student's `surrounding_papers` list is then populated from the papers
        owned by their spatial neighbors.
        """
        all_states = [s for s in registry.get_all() if getattr(s, "is_active", True)]
        
        # Step A: Clear previous paper data
        if not all_states:
            return
            
        for state in all_states:
            state.detected_paper = None
            state.is_heuristic_paper = False
            state.surrounding_papers = []

        # Step B: Assign YOLO-detected papers to nearest students (exclusive greedy)
        if all_papers:
            student_centers = np.array([state.center for state in all_states], dtype=float)
            paper_centers_arr = np.array(all_papers, dtype=float)

            # Distance Matrix (M papers × N students)
            diff = paper_centers_arr[:, np.newaxis, :] - student_centers[np.newaxis, :, :]
            dist_matrix = np.linalg.norm(diff, axis=2)

            # Greedy exclusive assignment: sort all (paper, student) pairs by distance,
            # then assign each paper to the closest student that doesn't already have one.
            n_papers = len(all_papers)
            n_students = len(all_states)
            
            # Build flat list of (distance, paper_idx, student_idx)
            pairs = []
            for p_idx in range(n_papers):
                for s_idx in range(n_students):
                    # Only consider assignments within a reasonable threshold
                    bbox_width = all_states[s_idx].bbox[2] - all_states[s_idx].bbox[0]
                    threshold = max(300, bbox_width * 2)
                    if dist_matrix[p_idx, s_idx] < threshold:
                        pairs.append((dist_matrix[p_idx, s_idx], p_idx, s_idx))
            
            # Sort by distance (closest first) and assign greedily
            pairs.sort(key=lambda x: x[0])
            assigned_papers: set[int] = set()
            assigned_students: set[int] = set()
            
            for _, p_idx, s_idx in pairs:
                if p_idx in assigned_papers or s_idx in assigned_students:
                    continue
                all_states[s_idx].detected_paper = all_papers[p_idx]
                all_states[s_idx].is_heuristic_paper = False
                assigned_papers.add(p_idx)
                assigned_students.add(s_idx)

        # Step C: Fallback — if no YOLO paper detected, use paper_center estimate
        for state in all_states:
            if state.detected_paper is None:
                state.detected_paper = state.paper_center
                state.is_heuristic_paper = True

        # Step D: Extract Neighbor Papers — each student gets papers owned by neighbors
        for state in all_states:
            if not state.neighbors:
                continue
                
            for neighbor_id in state.neighbors:
                neighbor_state = registry.get(neighbor_id)
                
                if (neighbor_state is not None and 
                    getattr(neighbor_state, "is_active", True) and
                    neighbor_state.detected_paper is not None):
                    
                    state.surrounding_papers.append(neighbor_state.detected_paper)

