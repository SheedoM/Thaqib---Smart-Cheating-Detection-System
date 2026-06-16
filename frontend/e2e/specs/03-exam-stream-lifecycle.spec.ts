import { expect, test } from '@playwright/test';
import { env } from '../fixtures/env';
import { firstAssignment, login, logout, mutate } from '../fixtures/api';

test.describe('exam hall monitoring and stream lifecycle', () => {
  test('invigilator can inspect readiness, feeds, status, start, and stop assigned hall', async () => {
    const invigilator = await login(env.invigilatorUsername, env.invigilatorPassword);
    const assignment = await firstAssignment(invigilator);
    const sessionId = assignment.exam_session_id;
    const hallId = assignment.hall_id;

    const readiness = await invigilator.api.get(`/api/sessions/${sessionId}/halls/${hallId}/readiness`);
    await expect(readiness, await readiness.text()).toBeOK();
    expect(await readiness.json()).toHaveProperty('overall_status');

    const feeds = await invigilator.api.get(`/api/sessions/${sessionId}/halls/${hallId}/feeds`);
    await expect(feeds, await feeds.text()).toBeOK();
    const feedBody = await feeds.json();
    expect(Array.isArray(feedBody.feeds)).toBe(true);
    expect(Array.isArray(feedBody.mics)).toBe(true);

    const start = await mutate(invigilator, 'post', `/api/sessions/${sessionId}/halls/${hallId}/monitoring/start`);
    expect([200, 400]).toContain(start.status());

    const status = await invigilator.api.get(`/api/sessions/${sessionId}/halls/${hallId}/status`);
    await expect(status, await status.text()).toBeOK();
    expect(await status.json()).toHaveProperty('monitoring');

    const stop = await mutate(invigilator, 'post', `/api/sessions/${sessionId}/halls/${hallId}/monitoring/stop`);
    expect([200, 404]).toContain(stop.status());

    await logout(invigilator);
  });

  test('unassigned or fake hall access is rejected', async () => {
    const invigilator = await login(env.invigilatorUsername, env.invigilatorPassword);
    const assignment = await firstAssignment(invigilator);
    const fakeHall = '00000000-0000-4000-8000-000000000001';

    const response = await invigilator.api.get(`/api/sessions/${assignment.exam_session_id}/halls/${fakeHall}/status`);
    expect([403, 404]).toContain(response.status());

    await logout(invigilator);
  });
});
