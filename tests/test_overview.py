"""
Integration tests for GET /api/overview/* endpoints (university super admin view).
"""
from datetime import datetime, timedelta, timezone

import pytest

from src.thaqib.db.models.exams import ExamSession


# ── /api/overview/summary ─────────────────────────────────────────────────────

class TestOverviewSummary:
    def test_university_super_admin_sees_summary(self, client, university_super_admin_headers):
        resp = client.get("/api/overview/summary", headers=university_super_admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "is_multi_college" in data
        assert data["is_multi_college"] is True
        assert "running_exams" in data
        assert "active_alerts" in data
        assert "active_colleges" in data

    def test_college_admin_forbidden(self, client, college_admin_headers):
        resp = client.get("/api/overview/summary", headers=college_admin_headers)
        assert resp.status_code == 403

    def test_invigilator_forbidden(self, client, invigilator_token_headers):
        resp = client.get("/api/overview/summary", headers=invigilator_token_headers)
        assert resp.status_code == 403

    def test_unauthenticated_rejected(self, client):
        resp = client.get("/api/overview/summary")
        assert resp.status_code == 401

    def test_active_colleges_excludes_university_root(
        self,
        client,
        db_session,
        university_super_admin_headers,
        university_institution,
        college_a,
    ):
        now = datetime.now(timezone.utc)
        db_session.add_all([
            ExamSession(
                institution_id=university_institution.id,
                exam_name="Root Active Exam",
                scheduled_start=now,
                scheduled_end=now + timedelta(hours=2),
                status="active",
            ),
            ExamSession(
                institution_id=college_a.id,
                exam_name="College Active Exam",
                scheduled_start=now,
                scheduled_end=now + timedelta(hours=2),
                status="active",
            ),
        ])
        db_session.commit()

        resp = client.get("/api/overview/summary", headers=university_super_admin_headers)

        assert resp.status_code == 200
        assert resp.json()["active_colleges"] == 1


# ── /api/overview/colleges ────────────────────────────────────────────────────

class TestOverviewColleges:
    def test_returns_college_list(self, client, university_super_admin_headers):
        resp = client.get("/api/overview/colleges", headers=university_super_admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "colleges" in data
        assert isinstance(data["colleges"], list)

    def test_college_cards_have_required_fields(self, client, university_super_admin_headers):
        resp = client.get("/api/overview/colleges", headers=university_super_admin_headers)
        assert resp.status_code == 200
        for card in resp.json()["colleges"]:
            assert "id" in card
            assert "name" in card
            assert "running_exams" in card
            assert "active_alerts" in card

    def test_non_super_admin_forbidden(self, client, college_admin_headers):
        resp = client.get("/api/overview/colleges", headers=college_admin_headers)
        assert resp.status_code == 403

    def test_university_super_admin_sees_child_colleges_not_root(
        self,
        client,
        university_super_admin_headers,
        university_institution,
        college_a,
        college_b,
    ):
        resp = client.get("/api/overview/colleges", headers=university_super_admin_headers)

        assert resp.status_code == 200
        college_ids = {card["id"] for card in resp.json()["colleges"]}
        assert college_ids == {str(college_a.id), str(college_b.id)}
        assert str(university_institution.id) not in college_ids

    def test_standalone_super_admin_sees_own_institution_card(
        self,
        client,
        super_admin_token_headers,
        test_institution,
    ):
        resp = client.get("/api/overview/colleges", headers=super_admin_token_headers)

        assert resp.status_code == 200
        colleges = resp.json()["colleges"]
        assert len(colleges) == 1
        assert colleges[0]["id"] == str(test_institution.id)


# ── /api/overview/exams ───────────────────────────────────────────────────────

class TestOverviewExams:
    def test_returns_exam_list(self, client, university_super_admin_headers):
        resp = client.get("/api/overview/exams", headers=university_super_admin_headers)
        assert resp.status_code == 200
        assert "exams" in resp.json()

    def test_status_filter_accepted(self, client, university_super_admin_headers):
        resp = client.get("/api/overview/exams?status=active", headers=university_super_admin_headers)
        assert resp.status_code == 200

    def test_college_id_filter_accepted(self, client, university_super_admin_headers, child_college_id):
        resp = client.get(
            f"/api/overview/exams?college_id={child_college_id}",
            headers=university_super_admin_headers,
        )
        assert resp.status_code == 200

    def test_forbidden_for_non_super_admin(self, client, college_admin_headers):
        resp = client.get("/api/overview/exams", headers=college_admin_headers)
        assert resp.status_code == 403


# ── /api/overview/alerts ─────────────────────────────────────────────────────

class TestOverviewAlerts:
    def test_returns_alert_list(self, client, university_super_admin_headers):
        resp = client.get("/api/overview/alerts", headers=university_super_admin_headers)
        assert resp.status_code == 200
        assert "alerts" in resp.json()

    def test_alerts_have_required_fields(self, client, university_super_admin_headers):
        resp = client.get("/api/overview/alerts", headers=university_super_admin_headers)
        for alert in resp.json()["alerts"]:
            assert "id" in alert
            assert "alert_type" in alert
            assert "college_name" in alert

    def test_forbidden_for_non_super_admin(self, client, college_admin_headers):
        resp = client.get("/api/overview/alerts", headers=college_admin_headers)
        assert resp.status_code == 403
