import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { authFetch } from '../config/api';

vi.mock('../config/api', () => ({
  authFetch: vi.fn(),
  apiUrl: (path: string) => path,
  voiceWebSocketUrl: (hallId: string) => `/api/v1/voice/ws/${hallId}`,
}));

const mockedAuthFetch = vi.mocked(authFetch);

const profile = {
  id: 'invig-1',
  institution_id: 'inst-1',
  username: 'invigilator',
  full_name: 'Invigilator Test',
  email: 'invig@test.com',
  role: 'invigilator',
  status: 'active',
  image: null,
};

const defaultPreferences = {
  alert_cue_mode: 'sound_vibrate',
  alert_volume: 80,
  browser_notifications_enabled: false,
  compact_display: false,
  large_text: false,
};

function response(body: unknown, ok = true, status = ok ? 200 : 400): Response {
  return {
    ok,
    status,
    json: async () => body,
  } as Response;
}

function mockApi(preferences = defaultPreferences) {
  mockedAuthFetch.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === '/api/auth/me') return response(profile);
    if (path === '/api/users/me/preferences' && init?.method === 'PUT') {
      return response(JSON.parse(String(init.body)));
    }
    if (path === '/api/users/me/preferences') return response(preferences);
    if (path === '/api/users/me/password') return response({ message: 'ok' });
    if (path === '/api/auth/logout') return response({ message: 'ok' });
    return response({});
  });
}

describe('InvigilatorSettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.pushState({}, '', '/invigilator/settings');
    Object.defineProperty(window.navigator, 'vibrate', {
      value: vi.fn(),
      configurable: true,
    });
  });

  it('replaces the placeholder route with the settings groups', async () => {
    mockApi();

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'الإعدادات' })).toBeInTheDocument();
    expect(screen.queryByText('قريباً...')).not.toBeInTheDocument();
    expect(screen.getByText('التنبيهات')).toBeInTheDocument();
    expect(screen.getByText('جاهزية الجهاز')).toBeInTheDocument();
    expect(screen.getByText('العرض')).toBeInTheDocument();
    expect(screen.getByText('الحساب والأمان')).toBeInTheDocument();
    expect(mockedAuthFetch).toHaveBeenCalledWith('/api/users/me/preferences');
    expect(screen.getByAltText('Thaqib')).toHaveAttribute('src', '/Frame 75.svg');
  });

  it('saves silent alert preferences and shows the muted badge', async () => {
    mockApi();

    render(<App />);

    fireEvent.click(await screen.findByRole('button', { name: /صامت/ }));
    fireEvent.click(screen.getByRole('button', { name: /حفظ الإعدادات/ }));

    await waitFor(() => {
      expect(mockedAuthFetch).toHaveBeenCalledWith(
        '/api/users/me/preferences',
        expect.objectContaining({
          method: 'PUT',
          body: expect.stringContaining('"alert_cue_mode":"silent"'),
        }),
      );
    });
    expect(screen.getByText('التنبيهات صامتة')).toBeInTheDocument();
  });

  it('validates password confirmation before sending password updates', async () => {
    mockApi();

    render(<App />);

    fireEvent.change(await screen.findByLabelText('كلمة المرور الحالية'), {
      target: { value: 'old-password' },
    });
    fireEvent.change(screen.getByLabelText('كلمة المرور الجديدة'), {
      target: { value: 'new-password' },
    });
    fireEvent.change(screen.getByLabelText('تأكيد كلمة المرور'), {
      target: { value: 'different-password' },
    });
    fireEvent.click(screen.getByRole('button', { name: /تغيير كلمة المرور/ }));

    expect(await screen.findByText('كلمتا المرور غير متطابقتين')).toBeInTheDocument();
    expect(mockedAuthFetch).not.toHaveBeenCalledWith(
      '/api/users/me/password',
      expect.anything(),
    );
  });

  it('shows notification permission fallback when browser notifications are unsupported', async () => {
    Object.defineProperty(window, 'Notification', {
      value: undefined,
      configurable: true,
    });
    mockApi();

    render(<App />);

    expect(await screen.findByText('إشعارات المتصفح غير مدعومة')).toBeInTheDocument();
  });
});
