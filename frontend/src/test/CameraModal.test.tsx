import { fireEvent, render, waitFor } from '@testing-library/react';
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
        pttStatusText="connected"
        onPttStart={vi.fn()}
        onPttStop={vi.fn()}
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
});
