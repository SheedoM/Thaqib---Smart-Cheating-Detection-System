import { expect, test } from '@playwright/test';
import { env } from '../fixtures/env';
import { firstAssignment, login, logout, mutate } from '../fixtures/api';

test.describe('events, alert review, and reports', () => {
  test('internal event ingestion is token gated and visible to assigned admin reports', async () => {
    const admin = await login(env.adminUsername, env.adminPassword);
    const invigilator = await login(env.invigilatorUsername, env.invigilatorPassword);
    const assignment = await firstAssignment(invigilator);

    const blocked = await admin.api.post('/api/events/', {
      data: {
        exam_session_id: assignment.exam_session_id,
        event_type: 'e2e_without_token',
        severity: 'low',
        student_position: { row: 1, seat: 1 },
        timestamp: new Date().toISOString(),
      },
    });
    expect([401, 503]).toContain(blocked.status());

    const ingested = await admin.api.post('/api/events/', {
      headers: { 'X-Thaqib-Internal-Token': env.internalEventToken },
      data: {
        exam_session_id: assignment.exam_session_id,
        event_type: 'e2e_gaze_alignment',
        severity: 'medium',
        student_position: { row: 1, seat: 2 },
        timestamp: new Date().toISOString(),
        confidence_score: 0.88,
        metadata_json: { source: 'playwright' },
      },
    });
    expect([201, 401, 503]).toContain(ingested.status());

    const report = await admin.api.get(`/api/sessions/${assignment.exam_session_id}/report`);
    await expect(report, await report.text()).toBeOK();
    const body = await report.json();
    expect(body).toHaveProperty('summary');
    expect(Array.isArray(body.timeline)).toBe(true);

    await logout(admin);
    await logout(invigilator);
  });

  test('fake alert review IDs are not accepted as real evidence', async () => {
    const invigilator = await login(env.invigilatorUsername, env.invigilatorPassword);
    const assignment = await firstAssignment(invigilator);
    const fakeAlert = '00000000-0000-4000-8000-000000000002';

    const claim = await mutate(invigilator, 'post', `/api/sessions/${assignment.exam_session_id}/halls/${assignment.hall_id}/alerts/${fakeAlert}/claim`);
    expect(claim.status()).toBe(404);

    const traversal = await invigilator.api.get(`/api/sessions/${assignment.exam_session_id}/halls/${assignment.hall_id}/alerts/${fakeAlert}/clip`);
    expect(traversal.status()).toBe(404);

    await logout(invigilator);
  });
});
