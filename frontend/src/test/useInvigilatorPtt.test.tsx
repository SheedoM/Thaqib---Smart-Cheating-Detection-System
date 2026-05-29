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
});
