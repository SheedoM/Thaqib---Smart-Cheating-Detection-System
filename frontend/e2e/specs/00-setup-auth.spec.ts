import { expect, test } from '@playwright/test';
import { env, uniqueName } from '../fixtures/env';
import { login, logout, mutate, newApiContext } from '../fixtures/api';

test.describe('setup, auth, cookies, CSRF', () => {
  test('health and setup status are explicit', async () => {
    const api = await newApiContext();
    const health = await api.get('/health');
    await expect(health, await health.text()).toBeOK();
    await expect.poll(async () => (await health.json()).status).toBe('ok');

    const status = await api.get('/api/setup/status');
    await expect(status, await status.text()).toBeOK();
    expect(await status.json()).toHaveProperty('is_installed');
    await api.dispose();
  });

  test('installed systems reject setup re-entry and never return plaintext passwords', async () => {
    const api = await newApiContext();
    const status = await api.get('/api/setup/status');
    await expect(status, await status.text()).toBeOK();
    const installed = (await status.json()).is_installed;

    const response = await api.post('/api/setup/install', {
      data: {
        institution_name: uniqueName('E2E University'),
        institution_type: 'standalone',
        admin: uniqueName('admin'),
        admin_password: 'CorrectHorseBattery42!',
      },
    });

    if (installed) {
      expect(response.status()).toBe(400);
    } else {
      expect(response.status()).toBe(201);
      expect(await response.json()).not.toHaveProperty('generated_credentials.password');
    }
    await api.dispose();
  });

  test('login, refresh, CSRF rejection, and logout are cookie based', async () => {
    const session = await login(env.adminUsername, env.adminPassword);

    const me = await session.api.get('/api/auth/me');
    await expect(me, await me.text()).toBeOK();
    expect((await me.json()).username).toBe(env.adminUsername);

    const missingCsrf = await session.api.post('/api/auth/logout');
    expect(missingCsrf.status()).toBe(403);

    const refresh = await mutate(session, 'post', '/api/auth/refresh');
    await expect(refresh, await refresh.text()).toBeOK();
    const refreshed = await refresh.json();
    expect(refreshed.csrf_token).not.toBe(session.csrfToken);
    session.csrfToken = refreshed.csrf_token;

    await logout(session);
  });
});
