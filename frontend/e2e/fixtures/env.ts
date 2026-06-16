export const env = {
  webURL: process.env.E2E_WEB_URL ?? 'http://127.0.0.1:5173',
  apiURL: process.env.E2E_API_URL ?? 'http://127.0.0.1:8001',
  simulatorURL: process.env.E2E_SIMULATOR_URL ?? 'http://127.0.0.1:8000',
  adminUsername: process.env.E2E_ADMIN_USERNAME ?? 'admin',
  adminPassword: process.env.E2E_ADMIN_PASSWORD ?? 'Admin12345!',
  invigilatorUsername: process.env.E2E_INVIGILATOR_USERNAME ?? 'invigilator',
  invigilatorPassword: process.env.E2E_INVIGILATOR_PASSWORD ?? 'Demo12345!',
  internalEventToken: process.env.E2E_INTERNAL_EVENT_TOKEN ?? 'test-internal-event-token',
};

export function uniqueName(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}
