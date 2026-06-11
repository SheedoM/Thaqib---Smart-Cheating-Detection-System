import { useState } from 'react';
import { Camera, Loader2, Maximize2 } from 'lucide-react';
import { apiUrl } from '../config/api';

export interface CameraFeedGridStats {
  is_running?: boolean;
  fps?: number;
  latency_ms?: number;
  resolution?: string;
  uptime_seconds?: number;
}

export interface CameraFeedGridAlert {
  event_type?: string;
  type?: string;
}

export interface CameraFeedGridItem<TAlert extends CameraFeedGridAlert = CameraFeedGridAlert> {
  id: string;
  name: string;
  feedPath: string | null;
  sourceConfigured: boolean;
  isRunning?: boolean;
  stats?: CameraFeedGridStats | null;
  alert?: TAlert | null;
}

interface CameraFeedGridProps<TAlert extends CameraFeedGridAlert = CameraFeedGridAlert> {
  cameras: CameraFeedGridItem<TAlert>[];
  className?: string;
  gapClassName?: string;
  onCameraClick?: (camera: CameraFeedGridItem<TAlert>) => void;
  onAlertClick?: (alert: TAlert) => void;
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) return `${minutes}m ${remainingSeconds}s`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}

function gridColumnsClass(count: number): string {
  if (count <= 1) return 'grid-cols-1';
  if (count === 2) return 'grid-cols-1 md:grid-cols-2';
  if (count === 3) return 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3';
  return 'grid-cols-1 md:grid-cols-2';
}

export default function CameraFeedGrid<TAlert extends CameraFeedGridAlert = CameraFeedGridAlert>({
  cameras,
  className = '',
  gapClassName = 'gap-4',
  onCameraClick,
  onAlertClick,
}: CameraFeedGridProps<TAlert>) {
  return (
    <div className={`grid ${gridColumnsClass(cameras.length)} ${gapClassName} ${className}`}>
      {cameras.map((camera) => (
        <CameraFeedTile
          key={camera.id}
          camera={camera}
          onCameraClick={onCameraClick}
          onAlertClick={onAlertClick}
        />
      ))}
    </div>
  );
}

function CameraFeedTile<TAlert extends CameraFeedGridAlert>({
  camera,
  onCameraClick,
  onAlertClick,
}: {
  camera: CameraFeedGridItem<TAlert>;
  onCameraClick?: (camera: CameraFeedGridItem<TAlert>) => void;
  onAlertClick?: (alert: TAlert) => void;
}) {
  const [imageErrored, setImageErrored] = useState(false);
  const alert = camera.alert ?? null;
  const canStream = Boolean(camera.feedPath && camera.sourceConfigured);
  const streamRunning = Boolean(camera.isRunning);
  const showLoading = canStream && !streamRunning;

  return (
    <button
      type="button"
      className={`camera-feed group ${alert ? 'camera-feed-alert' : ''}`}
      onClick={() => onCameraClick?.(camera)}
    >
      <div className="camera-feed-label">
        <span className={`camera-status-dot ${streamRunning ? 'active' : 'inactive'}`}></span>
        <span>{camera.name}</span>
      </div>

      {streamRunning && camera.feedPath ? (
        <>
          <img
            src={apiUrl(camera.feedPath)}
            alt={camera.name}
            className="camera-feed-img"
            onLoad={() => setImageErrored(false)}
            onError={() => setImageErrored(true)}
          />
          {imageErrored && (
            <div className="camera-feed-placeholder absolute inset-0 bg-black/70">
              <Loader2 size={22} className="animate-spin" />
              <p>جاري إعادة الاتصال...</p>
            </div>
          )}
        </>
      ) : showLoading ? (
        <div className="camera-feed-placeholder">
          <Camera size={48} strokeWidth={1.5} />
          <p>جاري تحميل البث...</p>
        </div>
      ) : (
        <div className="camera-feed-placeholder">
          <Camera size={48} strokeWidth={1.5} />
          <p>الكاميرا غير متصلة</p>
        </div>
      )}

      <span className="absolute top-3 left-3 z-[6] flex h-8 w-8 items-center justify-center rounded-full bg-black/40 text-white opacity-0 transition-opacity group-hover:opacity-100">
        <Maximize2 size={15} />
      </span>

      <div className="camera-feed-stats">
        {alert ? (
          <div className="camera-alert-bar">
            <span className="camera-alert-type">{alert.event_type || alert.type || 'حالة نشطة'}</span>
            {onAlertClick && (
              <button
                type="button"
                className="camera-alert-view-btn"
                onClick={(event) => {
                  event.stopPropagation();
                  onAlertClick(alert);
                }}
              >
                عرض الحالة
              </button>
            )}
          </div>
        ) : streamRunning ? (
          <>
            <span>FPS: {camera.stats?.fps || 0}</span>
            <span>•</span>
            <span>{camera.stats?.latency_ms ? `${Math.round(camera.stats.latency_ms)}ms` : '—'}</span>
            <span>•</span>
            <span>{camera.stats?.resolution && camera.stats.resolution !== 'N/A' ? camera.stats.resolution : '—'}</span>
            <span>•</span>
            <span>{camera.stats?.uptime_seconds != null && camera.stats.uptime_seconds > 0 ? formatUptime(camera.stats.uptime_seconds) : '—'}</span>
          </>
        ) : (
          <span>{canStream ? '—' : 'لا يوجد مصدر بث'}</span>
        )}
      </div>
    </button>
  );
}
