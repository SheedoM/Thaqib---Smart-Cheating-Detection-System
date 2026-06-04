import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useInvigilatorPtt } from '../hooks/useInvigilatorPtt';

class MockWebSocket extends EventTarget {
  static instances: MockWebSocket[] = [];
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  binaryType = 'blob';
  sent: unknown[] = [];
  onmessage: ((event: MessageEvent) => void) | null = null;

  url: string;

  constructor(url: string) {
    super();
    this.url = url;
    MockWebSocket.instances.push(this);
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      this.dispatchEvent(new Event('open'));
    }, 0);
  }

  send(data: unknown) {
    this.sent.push(data);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.dispatchEvent(new Event('close'));
  }
}

function Harness() {
  const ptt = useInvigilatorPtt({ autoConnect: true });
  return (
    <div>
      <span data-testid="state">{ptt.state}</span>
      <span data-testid="mic">{ptt.micState}</span>
      <span data-testid="status">{ptt.statusText}</span>
      <button onClick={() => ptt.startTransmission()}>talk</button>
    </div>
  );
}

function HallHarness() {
  const ptt = useInvigilatorPtt({
    hallId: 'hall-1',
    clientId: 'invigilator_demo_1',
    defaultTargetId: 'control_room_1',
  });
  return (
    <div>
      <span data-testid="state">{ptt.state}</span>
      <span data-testid="mic">{ptt.micState}</span>
      <button onClick={() => ptt.connect({ prepareMic: true })}>connect voice</button>
      <button onClick={() => ptt.startTransmission({ alertId: 'alert-1' })}>incident talk</button>
    </div>
  );
}

describe('useInvigilatorPtt mobile behavior', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    MockWebSocket.instances = [];
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ username: 'invigilator', role: 'invigilator', ptt_id: 'invigilator_demo_1' }),
    }));
    Object.defineProperty(window.navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: vi.fn() }],
        }),
      },
    });
    class MockAudioContext {
      state = 'running';
      destination = {};
      createMediaStreamSource = vi.fn(() => ({ connect: vi.fn() }));
      createScriptProcessor = vi.fn(() => ({ connect: vi.fn(), disconnect: vi.fn(), onaudioprocess: null }));
      createBuffer = vi.fn(() => ({ copyToChannel: vi.fn() }));
      createBufferSource = vi.fn(() => ({ connect: vi.fn(), start: vi.fn(), buffer: null }));
      resume = vi.fn().mockResolvedValue(undefined);
      close = vi.fn().mockResolvedValue(undefined);
    }
    vi.stubGlobal('AudioContext', MockAudioContext);
  });

  it('auto-connects the websocket without requesting microphone access', async () => {
    render(<Harness />);

    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('connected'));

    expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled();
    expect(screen.getByTestId('mic')).toHaveTextContent('idle');
  });

  it('keeps websocket connected when mobile HTTP blocks microphone capture', async () => {
    vi.mocked(navigator.mediaDevices.getUserMedia).mockRejectedValueOnce(new DOMException('Not allowed', 'NotAllowedError'));
    render(<Harness />);
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('connected'));

    await act(async () => {
      screen.getByRole('button', { name: 'talk' }).click();
    });

    await waitFor(() => expect(screen.getByTestId('mic')).toHaveTextContent('blocked'));
    expect(screen.getByTestId('state')).toHaveTextContent('connected');
    expect(screen.getByTestId('status')).toHaveTextContent('HTTPS');
  });

  it('connects to a hall voice channel and can request microphone readiness during preflight', async () => {
    vi.mocked(navigator.mediaDevices.getUserMedia).mockRejectedValueOnce(new DOMException('Not allowed', 'NotAllowedError'));
    render(<HallHarness />);

    await act(async () => {
      screen.getByRole('button', { name: 'connect voice' }).click();
    });

    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('connected'));
    expect(MockWebSocket.instances[0].url).toContain('/api/v1/ptt/ws/halls/hall-1');
    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('mic')).toHaveTextContent('blocked');
  });

  it('marks alert-context transmissions as incident clips', async () => {
    render(<HallHarness />);

    await act(async () => {
      screen.getByRole('button', { name: 'incident talk' }).click();
    });

    await waitFor(() => expect(MockWebSocket.instances.length).toBe(1));
    const sent = MockWebSocket.instances[0].sent.map((item) => {
      return typeof item === 'string' ? JSON.parse(item) : item;
    });
    expect(sent).toContainEqual({
      type: 'start_speak',
      clip_type: 'incident',
      alert_id: 'alert-1',
    });
  });
});
