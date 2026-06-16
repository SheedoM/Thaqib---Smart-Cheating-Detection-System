import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import CameraModal from '../components/CameraModal';
import { authFetch } from '../config/api';

vi.mock('../config/api', () => ({
  apiUrl: (path: string) => path,
  authFetch: vi.fn(),
}));

const mockedAuthFetch = vi.mocked(authFetch);

describe('CameraModal keyboard controls', () => {
  beforeEach(() => {
    mockedAuthFetch.mockReset();
    mockedAuthFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ selected_count: 5, tracked_count: 5 }),
    } as Response);
  });

  it('sends select-all every time S is pressed after the previous request completes', async () => {
    render(
      <CameraModal
        mode="camera"
        alert={null}
        camera={{ id: 'camera-1', name: 'Camera 1', hallName: 'Hall 1', feedPath: '/feed' }}
        stats={null}
        onClose={vi.fn()}
      />,
    );

    await waitFor(() => expect(mockedAuthFetch).toHaveBeenCalledWith('/api/stream/cameras/camera-1/controls'));

    fireEvent.keyDown(window, { key: 's' });
    await waitFor(() => {
      expect(mockedAuthFetch).toHaveBeenCalledWith('/api/stream/cameras/camera-1/select-all', { method: 'POST' });
    });

    fireEvent.keyDown(window, { key: 's' });
    await waitFor(() => {
      const selectAllCalls = mockedAuthFetch.mock.calls.filter(([path]) => path === '/api/stream/cameras/camera-1/select-all');
      expect(selectAllCalls).toHaveLength(2);
    });
  });

  it('posts normalized microphone placement when mic placement mode is active', async () => {
    render(
      <CameraModal
        mode="camera"
        alert={null}
        camera={{ id: 'camera-1', name: 'Camera 1', hallName: 'Hall 1', feedPath: '/feed' }}
        stats={null}
        hallMics={[{ id: 'mic-1', identifier: 'mic-1', name: 'Desk mic', status: 'online', placements: [] }]}
        onClose={vi.fn()}
      />,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'تحديد المايك' }));
    fireEvent.change(screen.getByLabelText('الميكروفون'), { target: { value: 'mic-1' } });

    const image = screen.getByAltText('بث مباشر');
    Object.defineProperty(image, 'getBoundingClientRect', {
      configurable: true,
      value: () => ({ left: 10, top: 20, width: 200, height: 100, right: 210, bottom: 120 }),
    });

    fireEvent.click(image, { clientX: 60, clientY: 70 });

    await waitFor(() => {
      expect(mockedAuthFetch).toHaveBeenCalledWith('/api/devices/mic-1/placements', {
        method: 'PUT',
        body: JSON.stringify({ placements: [{ camera_id: 'camera-1', norm_pos: [0.25, 0.5] }] }),
      });
    });
  });
});
