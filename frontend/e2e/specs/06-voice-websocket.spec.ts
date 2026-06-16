import { expect, test } from '@playwright/test';
import { env } from '../fixtures/env';
import { firstAssignment, login, logout } from '../fixtures/api';
import { loginAsAdmin, loginAsInvigilator } from '../fixtures/browserAuth';

test.describe('hall voice WebSocket', () => {
  test('authenticated admin and invigilator receive presence and talk events', async ({ browser }) => {
    const invigilatorApi = await login(env.invigilatorUsername, env.invigilatorPassword);
    const assignment = await firstAssignment(invigilatorApi);
    await logout(invigilatorApi);

    const adminContext = await browser.newContext();
    const invigContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    const invigPage = await invigContext.newPage();

    await loginAsAdmin(adminPage);
    await loginAsInvigilator(invigPage);

    const wsResult = await Promise.all([
      invigPage.evaluate((hallId) => new Promise<string>((resolve, reject) => {
        const url = `${location.origin.replace(/^http/, 'ws')}/api/v1/voice/ws/${hallId}`;
        const ws = new WebSocket(url);
        const timer = setTimeout(() => reject(new Error('voice ws timed out')), 15000);
        ws.onmessage = (event) => {
          if (typeof event.data === 'string' && event.data.includes('talk_start')) {
            clearTimeout(timer);
            ws.close();
            resolve(event.data);
          }
        };
        ws.onerror = () => reject(new Error('voice ws error'));
      }), assignment.hall_id),
      adminPage.evaluate((hallId) => new Promise<void>((resolve, reject) => {
        const url = `${location.origin.replace(/^http/, 'ws')}/api/v1/voice/ws/${hallId}`;
        const ws = new WebSocket(url);
        const timer = setTimeout(() => reject(new Error('voice sender timed out')), 15000);
        ws.onopen = () => {
          ws.send(JSON.stringify({ type: 'talk_start' }));
          clearTimeout(timer);
          setTimeout(() => {
            ws.send(JSON.stringify({ type: 'talk_stop' }));
            ws.close();
            resolve();
          }, 250);
        };
        ws.onerror = () => reject(new Error('voice sender error'));
      }), assignment.hall_id),
    ]);

    expect(wsResult[0]).toContain('talk_start');
    await adminContext.close();
    await invigContext.close();
  });
});
