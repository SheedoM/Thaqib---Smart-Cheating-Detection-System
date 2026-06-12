import { render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DashboardPage from '../pages/DashboardPage';
import type { VoiceParticipant } from '../hooks/useHallVoice';

const mockVoice = {
  state: 'connected' as 'idle' | 'connecting' | 'connected' | 'error',
  isConnected: true,
  micState: 'ready' as 'idle' | 'requesting' | 'ready' | 'blocked' | 'error',
  micBlocked: false,
  isTransmitting: false,
  participants: [{ id: 'invig_test', role: 'invigilator', name: 'Invigilator Test' }] as VoiceParticipant[],
  remoteTalking: null as VoiceParticipant | null,
  error: null as string | null,
  statusText: 'متصل بالقناة الصوتية',
  connect: vi.fn().mockResolvedValue(true),
  disconnect: vi.fn(),
  startTalking: vi.fn(),
  stopTalking: vi.fn(),
};

vi.mock('../hooks/useHallVoice', () => ({
  useHallVoice: () => mockVoice,
}));

vi.mock('../config/api', () => ({
  apiUrl: (path: string) => path,
  STREAM_BASE: '/api/stream',
  authFetch: vi.fn(async (path: string) => {
    if (path === '/api/auth/me') {
      return { ok: true, json: async () => ({ full_name: 'Admin Test', role: 'admin' }) };
    }
    if (path === '/api/stream/monitoring') {
      return {
        ok: true,
        json: async () => ({
          halls: [
            { id: 'hall-1', name: 'Hall 101', status: 'ready', monitoring_status: 'active', cameras: [], mics: [] },
          ],
        }),
      };
    }
    if (path === '/api/stream/alerts') return { ok: true, json: async () => ({ alerts: [] }) };
    if (path === '/api/stream/status') return { ok: true, json: async () => ({ cameras: {} }) };
    return { ok: true, json: async () => ({}) };
  }),
}));

describe('DashboardPage per-hall voice strip', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockVoice.state = 'connected';
    mockVoice.isConnected = true;
    mockVoice.micState = 'ready';
    mockVoice.micBlocked = false;
    mockVoice.isTransmitting = false;
    mockVoice.participants = [{ id: 'invig_test', role: 'invigilator', name: 'Invigilator Test' }];
    mockVoice.remoteTalking = null;
    mockVoice.error = null;
    mockVoice.statusText = 'متصل بالقناة الصوتية';
    mockVoice.connect.mockResolvedValue(true);
  });

  it('shows the talk control and that the invigilator is connected', async () => {
    render(<DashboardPage />);

    await waitFor(() => expect(screen.getAllByText('Hall 101').length).toBeGreaterThan(0));

    expect(screen.getByRole('button', { name: 'تحدث مع القاعة' })).toBeInTheDocument();
    expect(screen.getByText('المراقب متصل')).toBeInTheDocument();
  });

  it('shows management tabs for admin users', async () => {
    render(<DashboardPage />);

    const nav = screen.getByRole('navigation');

    await waitFor(() => expect(within(nav).getByRole('button', { name: 'القاعات' })).toBeInTheDocument());

    expect(within(nav).getByRole('button', { name: 'المشرفين' })).toBeInTheDocument();
    expect(within(nav).getByRole('button', { name: 'الإعدادات' })).toBeInTheDocument();
  });

  it('shows a reconnect button that retries the voice connection on error', async () => {
    mockVoice.state = 'error';
    mockVoice.isConnected = false;
    mockVoice.error = 'تعذر الاتصال بالقناة الصوتية';
    mockVoice.statusText = 'فشل الاتصال الصوتي';
    mockVoice.participants = [];

    render(<DashboardPage />);

    await waitFor(() => expect(screen.getAllByText('Hall 101').length).toBeGreaterThan(0));

    expect(screen.getByText('فشل الاتصال الصوتي')).toBeInTheDocument();
    expect(screen.getByText('المراقب غير متصل')).toBeInTheDocument();

    screen.getByRole('button', { name: 'إعادة الاتصال' }).click();
    expect(mockVoice.connect).toHaveBeenCalledTimes(1);
  });
});
