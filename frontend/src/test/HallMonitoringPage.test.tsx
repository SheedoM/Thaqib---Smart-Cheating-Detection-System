import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import HallMonitoringPage from '../pages/invigilator/HallMonitoringPage';
import type { VoiceParticipant } from '../hooks/useHallVoice';

const mockVoice = {
  state: 'connected' as 'idle' | 'connecting' | 'connected' | 'error',
  isConnected: true,
  micState: 'idle' as 'idle' | 'requesting' | 'ready' | 'blocked' | 'error',
  micBlocked: false,
  isTransmitting: false,
  participants: [] as VoiceParticipant[],
  remoteTalking: null as VoiceParticipant | null,
  incidentCards: [] as { alert_id: string; event_type?: string; severity?: string; timestamp?: string | null }[],
  clearIncidentCards: vi.fn(),
  error: null as string | null,
  statusText: 'متصل بالقناة الصوتية',
  connect: vi.fn().mockResolvedValue(true),
  disconnect: vi.fn(),
  startTalking: vi.fn(),
  stopTalking: vi.fn(),
};

let mockHallStatus = {
  exam_name: 'Midterm Exam 2024',
  hall_name: 'قاعة 101',
  is_active: false,
  stats: { student_count: 100, active_alerts: 0 },
  alerts: [],
};

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useParams: () => ({ sessionId: 'session-1', hallId: 'hall-1' }),
  };
});

vi.mock('../hooks/useHallVoice', () => ({
  useHallVoice: () => mockVoice,
}));

vi.mock('../lib/secureContext', () => ({
  isInsecureLanContext: () => false,
}));

vi.mock('../config/api', () => ({
  apiUrl: (path: string) => path,
  authFetch: vi.fn(async (path: string) => {
    if (path.endsWith('/status')) return { ok: true, json: async () => mockHallStatus };
    if (path.endsWith('/feeds')) return { ok: true, json: async () => ({ feeds: [] }) };
    return { ok: true, json: async () => ({ overall_status: 'warning', devices: [] }) };
  }),
}));

describe('HallMonitoringPage voice channel status', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockVoice.state = 'connected';
    mockVoice.isConnected = true;
    mockVoice.micState = 'idle';
    mockVoice.micBlocked = false;
    mockVoice.isTransmitting = false;
    mockVoice.participants = [];
    mockVoice.remoteTalking = null;
    mockVoice.incidentCards = [];
    mockVoice.error = null;
    mockVoice.statusText = 'متصل بالقناة الصوتية';
    mockVoice.connect.mockResolvedValue(true);
    mockHallStatus = {
      exam_name: 'Midterm Exam 2024',
      hall_name: 'قاعة 101',
      is_active: false,
      stats: { student_count: 100, active_alerts: 0 },
      alerts: [],
    };
  });

  it('shows the hall voice channel as connected', async () => {
    render(<HallMonitoringPage />);

    await waitFor(() => expect(screen.queryByText('جاري الاتصال بالقاعة...')).not.toBeInTheDocument());

    expect(screen.getByText('القناة الصوتية متصلة')).toBeInTheDocument();
  });

  it('connects the voice channel when the connect button is clicked', async () => {
    mockVoice.state = 'idle';
    mockVoice.isConnected = false;
    mockVoice.statusText = 'غير متصل';
    render(<HallMonitoringPage />);

    await waitFor(() => expect(screen.queryByText('جاري الاتصال بالقاعة...')).not.toBeInTheDocument());

    screen.getByRole('button', { name: 'الاتصال بالقناة الصوتية' }).click();

    await waitFor(() => expect(mockVoice.connect).toHaveBeenCalledTimes(1));
  });

  it('shows a specific voice connection error', async () => {
    mockVoice.state = 'error';
    mockVoice.isConnected = false;
    mockVoice.statusText = 'فشل الاتصال الصوتي';
    mockVoice.error = 'تعذر الاتصال بالقناة الصوتية';

    render(<HallMonitoringPage />);

    await waitFor(() => expect(screen.queryByText('جاري الاتصال بالقاعة...')).not.toBeInTheDocument());

    expect(screen.getByText('فشل اتصال القناة الصوتية')).toBeInTheDocument();
    expect(screen.getAllByText(/تعذر الاتصال بالقناة الصوتية/).length).toBeGreaterThan(0);
  });
});
