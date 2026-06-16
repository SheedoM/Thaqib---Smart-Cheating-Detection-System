import { expect, request, test } from '@playwright/test';
import { env } from '../fixtures/env';

test.describe('camera and microphone simulator', () => {
  test('health, readiness, cameras, and mics endpoints are shaped correctly', async () => {
    const simulator = await request.newContext({ baseURL: env.simulatorURL });
    const health = await simulator.get('/health');
    test.skip(!health.ok(), `simulator is not reachable at ${env.simulatorURL}`);

    expect(await health.json()).toHaveProperty('status');

    const ready = await simulator.get('/ready');
    await expect(ready, await ready.text()).toBeOK();
    expect(await ready.json()).toHaveProperty('ready');

    const cameras = await simulator.get('/cameras');
    await expect(cameras, await cameras.text()).toBeOK();
    expect(Array.isArray(await cameras.json())).toBe(true);

    const mics = await simulator.get('/mics');
    await expect(mics, await mics.text()).toBeOK();
    expect(Array.isArray(await mics.json())).toBe(true);
    await simulator.dispose();
  });
});
