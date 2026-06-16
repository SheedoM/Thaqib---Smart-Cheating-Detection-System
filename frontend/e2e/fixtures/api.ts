import { expect, request, type APIRequestContext, type APIResponse } from '@playwright/test';
import { env } from './env';

export type ApiSession = {
  api: APIRequestContext;
  csrfToken: string;
  user: Record<string, unknown>;
};

export async function newApiContext(): Promise<APIRequestContext> {
  return request.newContext({
    baseURL: env.apiURL,
    extraHTTPHeaders: {
      Accept: 'application/json',
    },
  });
}

export async function login(username: string, password: string): Promise<ApiSession> {
  const api = await newApiContext();
  const response = await api.post('/api/auth/login', {
    form: { username, password },
  });
  await expect(response, await response.text()).toBeOK();
  const body = await response.json();
  expect(body.token_type).toBe('cookie');
  expect(body.csrf_token).toBeTruthy();
  expect(body.access_token).toBeUndefined();
  expect(body.refresh_token).toBeUndefined();
  return { api, csrfToken: body.csrf_token, user: body.user };
}

export async function mutate(
  session: ApiSession,
  method: 'post' | 'put' | 'patch' | 'delete',
  path: string,
  options: Parameters<APIRequestContext['post']>[1] = {},
): Promise<APIResponse> {
  const headers = {
    ...(options.headers ?? {}),
    'X-CSRF-Token': session.csrfToken,
  };
  return session.api[method](path, { ...options, headers });
}

export async function expectOkJson(response: APIResponse): Promise<Record<string, unknown>> {
  await expect(response, await response.text()).toBeOK();
  return response.json();
}

export async function firstAssignment(session: ApiSession): Promise<Record<string, string>> {
  const response = await session.api.get('/api/sessions/my');
  await expect(response, await response.text()).toBeOK();
  const assignments = await response.json();
  expect(Array.isArray(assignments)).toBe(true);
  expect(assignments.length, 'seed_demo.py must create at least one invigilator assignment').toBeGreaterThan(0);
  return assignments[0];
}

export async function logout(session: ApiSession): Promise<void> {
  const response = await mutate(session, 'post', '/api/auth/logout');
  await expect(response, await response.text()).toBeOK();
  await session.api.dispose();
}
