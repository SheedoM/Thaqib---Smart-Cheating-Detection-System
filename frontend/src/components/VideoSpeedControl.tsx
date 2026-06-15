import type { RefObject } from 'react';
import { useEffect, useState } from 'react';

const SPEEDS = [0.25, 0.5, 1, 2] as const;

interface VideoSpeedControlProps {
  videoRef: RefObject<HTMLVideoElement | null>;
}

export default function VideoSpeedControl({ videoRef }: VideoSpeedControlProps) {
  const [speed, setSpeed] = useState<number>(1);

  useEffect(() => {
    setSpeed(1);
    if (videoRef.current) {
      videoRef.current.playbackRate = 1;
    }
  }, [videoRef]);

  const applySpeed = (nextSpeed: number) => {
    setSpeed(nextSpeed);
    if (videoRef.current) {
      videoRef.current.playbackRate = nextSpeed;
    }
  };

  return (
    <div className="flex items-center gap-1 rounded-xl bg-white/90 p-1 shadow-sm" dir="ltr" aria-label="Video playback speed">
      {SPEEDS.map((item) => (
        <button
          key={item}
          type="button"
          aria-pressed={speed === item}
          onClick={() => applySpeed(item)}
          className={`rounded-lg px-2.5 py-1 text-[11px] font-bold transition-colors ${
            speed === item ? 'bg-thaqib-primary text-white' : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          {item}x
        </button>
      ))}
    </div>
  );
}
