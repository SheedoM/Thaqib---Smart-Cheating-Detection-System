import { expect, test } from '@playwright/test';
import { env } from '../fixtures/env';
import { login, logout, mutate } from '../fixtures/api';

test.describe('tenant scoping and role matrix', () => {
  test('admin can read management APIs; invigilator is denied admin-only APIs', async () => {
    const admin = await login(env.adminUsername, env.adminPassword);
    const invigilator = await login(env.invigilatorUsername, env.invigilatorPassword);

    await expect(await admin.api.get('/api/halls/')).toBeOK();
    await expect(await admin.api.get('/api/devices/')).toBeOK();
    await expect(await admin.api.get('/api/sessions/')).toBeOK();

    expect((await invigilator.api.get('/api/halls/')).status()).toBe(403);
    expect((await invigilator.api.get('/api/devices/')).status()).toBe(403);
    expect((await invigilator.api.get('/api/sessions/')).status()).toBe(403);
    expect((await invigilator.api.get('/api/sessions/my')).status()).toBe(200);

    await logout(admin);
    await logout(invigilator);
  });

  test('CSRF protects mutating management APIs', async () => {
    const admin = await login(env.adminUsername, env.adminPassword);
    const institutionId = String(admin.user.institution_id);

    const blocked = await admin.api.post('/api/halls/', {
      data: {
        institution_id: institutionId,
        name: 'csrf-blocked-hall',
        capacity: 10,
      },
    });
    expect(blocked.status()).toBe(403);

    const allowed = await mutate(admin, 'post', '/api/halls/', {
      data: {
        institution_id: institutionId,
        name: `csrf-allowed-${Date.now()}`,
        building: 'E2E',
        floor: '1',
        capacity: 10,
        status: 'ready',
      },
    });
    await expect(allowed, await allowed.text()).toBeOK();
    await logout(admin);
  });
});
