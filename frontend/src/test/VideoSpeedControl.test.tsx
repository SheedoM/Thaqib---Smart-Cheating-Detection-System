import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { createRef } from 'react';
import VideoSpeedControl from '../components/VideoSpeedControl';

describe('VideoSpeedControl', () => {
  it('sets the attached video playback rate when a speed is selected', () => {
    const videoRef = createRef<HTMLVideoElement>();

    render(
      <>
        <video ref={videoRef} />
        <VideoSpeedControl videoRef={videoRef} />
      </>,
    );

    fireEvent.click(screen.getByRole('button', { name: '2x' }));

    expect(videoRef.current?.playbackRate).toBe(2);
    expect(screen.getByRole('button', { name: '2x' })).toHaveAttribute('aria-pressed', 'true');
  });
});
