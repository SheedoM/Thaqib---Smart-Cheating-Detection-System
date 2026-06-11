"""
Tenant isolation tests — cross-tenant access must return 404, not 403.
Ensures College A cannot see College B's resources.
"""
import pytest


# ── Exam isolation ────────────────────────────────────────────────────────────

class TestExamIsolation:
    def test_college_a_cannot_see_college_b_exam(
        self,
        client,
        college_a_admin_headers,
        college_b_exam_id,
    ):
        """College A admin must get 404 when fetching College B's exam."""
        resp = client.get(
            f"/api/sessions/{college_b_exam_id}",
            headers=college_a_admin_headers,
        )
        assert resp.status_code == 404

    def test_college_a_exam_list_excludes_college_b_exams(
        self,
        client,
        college_a_admin_headers,
        college_b_exam_id,
    ):
        resp = client.get("/api/sessions", headers=college_a_admin_headers)
        assert resp.status_code == 200
        ids = [e["id"] for e in resp.json()]
        assert str(college_b_exam_id) not in ids

    def test_university_super_admin_sees_all_exams(
        self,
        client,
        university_super_admin_headers,
        college_a_exam_id,
        college_b_exam_id,
    ):
        resp = client.get("/api/sessions", headers=university_super_admin_headers)
        assert resp.status_code == 200
        ids = [e["id"] for e in resp.json()]
        assert str(college_a_exam_id) in ids
        assert str(college_b_exam_id) in ids


# ── Hall isolation ────────────────────────────────────────────────────────────

class TestHallIsolation:
    def test_college_a_cannot_see_college_b_hall(
        self,
        client,
        college_a_admin_headers,
        college_b_hall_id,
    ):
        resp = client.get(
            f"/api/halls/{college_b_hall_id}",
            headers=college_a_admin_headers,
        )
        assert resp.status_code == 404

    def test_college_a_hall_list_excludes_college_b_halls(
        self,
        client,
        college_a_admin_headers,
        college_b_hall_id,
    ):
        resp = client.get("/api/halls", headers=college_a_admin_headers)
        assert resp.status_code == 200
        ids = [h["id"] for h in resp.json()]
        assert str(college_b_hall_id) not in ids


# ── User isolation ────────────────────────────────────────────────────────────

class TestUserIsolation:
    def test_college_a_cannot_see_college_b_user(
        self,
        client,
        college_a_admin_headers,
        college_b_user_id,
    ):
        resp = client.get(
            f"/api/users/{college_b_user_id}",
            headers=college_a_admin_headers,
        )
        assert resp.status_code == 404

    def test_college_a_user_list_excludes_college_b_users(
        self,
        client,
        college_a_admin_headers,
        college_b_user_id,
    ):
        resp = client.get("/api/users", headers=college_a_admin_headers)
        assert resp.status_code == 200
        ids = [u["id"] for u in resp.json()]
        assert str(college_b_user_id) not in ids


# ── Cross-college exam creation blocked ──────────────────────────────────────

class TestCrossTenantCreation:
    def test_college_a_cannot_create_hall_in_college_b(
        self,
        client,
        college_a_admin_headers,
        college_b_id,
    ):
        # admin role cannot create halls (super_admin only) → 403
        # super_admin of college_a would get 404 (college_b out of scope)
        # either way the operation is blocked
        resp = client.post(
            "/api/halls",
            json={"name": "Intruder Hall", "institution_id": str(college_b_id), "capacity": 30},
            headers=college_a_admin_headers,
        )
        assert resp.status_code in (403, 404)

    def test_exam_with_cross_institution_halls_rejected(
        self,
        client,
        college_a_admin_headers,
        college_a_hall_id,
        college_b_hall_id,
    ):
        """Mixing halls from different institutions in a single exam must return 400."""
        resp = client.post(
            "/api/sessions/",
            json={
                "exam_name": "Mixed Exam",
                "hall_ids": [str(college_a_hall_id), str(college_b_hall_id)],
                "scheduled_start": "2026-06-10T09:00:00Z",
                "scheduled_end": "2026-06-10T11:00:00Z",
            },
            headers=college_a_admin_headers,
        )
        assert resp.status_code in (400, 404)
