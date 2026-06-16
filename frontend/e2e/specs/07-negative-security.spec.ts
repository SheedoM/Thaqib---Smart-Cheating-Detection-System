import { expect, test } from '@playwright/test';
import { env } from '../fixtures/env';
import { firstAssignment, login, logout, mutate } from '../fixtures/api';

test.describe('negative security cases', () => {
  test('stream controls require both auth and CSRF', async () => {
    const admin = await login(env.adminUsername, env.adminPassword);

    const unauthenticated = await fetch(`${env.apiURL}/api/stream/refresh`, { method: 'POST' });
    expect([401, 403]).toContain(unauthenticated.status);

    const noCsrf = await admin.api.post('/api/stream/refresh');
    expect(noCsrf.status()).toBe(403);

    const withCsrf = await mutate(admin, 'post', '/api/stream/reload');
    expect([200, 500]).toContain(withCsrf.status());

    await logout(admin);
  });

  test('alert media path traversal is rejected', async () => {
    const admin = await login(env.adminUsername, env.adminPassword);

    const snapshot = await admin.api.get('/api/stream/alerts/snapshot/../../.env');
    expect([403, 404]).toContain(snapshot.status());

    const video = await admin.api.get('/api/stream/alerts/video/../../.env');
    expect([403, 404]).toContain(video.status());

    await logout(admin);
  });

  test('invigilator cannot start monitoring a fake hall', async () => {
    const invigilator = await login(env.invigilatorUsername, env.invigilatorPassword);
    const assignment = await firstAssignment(invigilator);
    const fakeHall = '00000000-0000-4000-8000-000000000099';

    const denied = await mutate(invigilator, 'post', `/api/sessions/${assignment.exam_session_id}/halls/${fakeHall}/monitoring/start`);
    expect([403, 404]).toContain(denied.status());

    await logout(invigilator);
  });
});
