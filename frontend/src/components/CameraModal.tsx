import { apiUrl } from '../config/api';

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return `${h}h ${rm}m`;
}

interface Alert {
  id: string;
  camera_id: string;
  camera_identifier: string;
  camera_name: string;
  hall_id: string;
  hall_name: string;
  track_id: number;
  looking_at: number | null;
  event_type: string;
  severity: string;
  timestamp: string;
  snapshot_file: string;
  video_file?: string | null;
  location: string;
}

interface CameraStats {
  camera_id: string;
  camera_identifier: string;
  camera_name: string;
  hall_id: string;
  hall_name: string;
  is_running: boolean;
  fps: number;
  tracked_count: number;
  selected_count: number;
  frame_index: number;
  alert_count: number;
  latency_ms: number;
  resolution: string;
  frame_drops: number;
  uptime_seconds: number;
}

interface CameraModalProps {
  mode: 'camera' | 'alert';
  alert: Alert | null;
  camera: {
    id: string;
    name: string;
    hallName: string;
    feedPath: string | null;
  } | null;
  stats: CameraStats | null;
  pttStatusText: string;
  onPttStart: () => void | Promise<void>;
  onPttStop: () => void;
  onClose: () => void;
}

export default function CameraModal({ mode, alert, camera, stats, pttStatusText, onPttStart, onPttStop, onClose }: CameraModalProps) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Close button */}
        <button className="modal-close-btn" onClick={onClose}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>

        {mode === 'camera' ? (
          <CameraView camera={camera} stats={stats} />
        ) : (
          <AlertView alert={alert} pttStatusText={pttStatusText} onPttStart={onPttStart} onPttStop={onPttStop} />
        )}
      </div>
    </div>
  );
}


// ── Camera View (enlarged live feed) ─────────────────────────────────────────

function CameraView({
  camera,
  stats,
}: {
  camera: CameraModalProps['camera'];
  stats: CameraStats | null;
}) {
  return (
    <div className="modal-content" dir="rtl">
      {/* Header */}
      <div className="modal-header">
        <h2>{camera?.name || 'الكاميرا'}</h2>
        <div className="modal-header-badge">
          <span className="camera-status-dot active" style={{ marginLeft: '6px' }}></span>
          بث مباشر
        </div>
      </div>

      {/* Video feed */}
      <div className="modal-video-wrapper">
        {/* Location tooltip */}
        <div className="modal-location-tooltip">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
            <circle cx="12" cy="10" r="3"/>
          </svg>
          <span>{camera ? `${camera.hallName} - ${camera.name}` : 'بث مباشر'}</span>
        </div>

        {camera?.feedPath ? (
          <img
            src={apiUrl(camera.feedPath)}
            alt="بث مباشر"
            className="modal-video-img"
          />
        ) : (
          <div className="camera-feed-placeholder" style={{ minHeight: '360px' }}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#9f9fa9" strokeWidth="1.5">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
              <circle cx="12" cy="13" r="4"/>
            </svg>
            <p>الكاميرا غير متصلة</p>
          </div>
        )}
      </div>

      {/* Stats bar */}
      <div className="modal-stats-bar">
        <div className="modal-stat">
          <span className="modal-stat-label">FPS</span>
          <span className="modal-stat-value">{stats?.fps || 0}</span>
        </div>
        <div className="modal-stat">
          <span className="modal-stat-label">LATENCY</span>
          <span className="modal-stat-value">{stats?.latency_ms ? `${Math.round(stats.latency_ms)} ms` : '—'}</span>
        </div>
        <div className="modal-stat">
          <span className="modal-stat-label">RESOLUTION</span>
          <span className="modal-stat-value">{stats?.resolution && stats.resolution !== 'N/A' ? stats.resolution : '—'}</span>
        </div>
        <div className="modal-stat">
          <span className="modal-stat-label">UPTIME</span>
          <span className="modal-stat-value">{stats?.uptime_seconds != null && stats.uptime_seconds > 0 ? formatUptime(stats.uptime_seconds) : '—'}</span>
        </div>
        <div className="modal-stat">
          <span className="modal-stat-label">DROPS</span>
          <span className="modal-stat-value">{stats?.frame_drops ?? 0}</span>
        </div>
        <div className="modal-stat">
          <span className="modal-stat-label">TRACKED</span>
          <span className="modal-stat-value">{stats?.tracked_count || 0}</span>
        </div>
        <div className="modal-stat">
          <span className="modal-stat-label">SELECTED</span>
          <span className="modal-stat-value">{stats?.selected_count || 0}</span>
        </div>
      </div>

      {/* Controls cheat sheet (from demo_video.py) */}
      <div className="modal-controls">
        <div className="modal-controls-header">اختصارات التحكم</div>
        <div className="modal-controls-grid">
          <div className="modal-control-item"><span className="keycap">q</span><span>إنهاء</span></div>
          <div className="modal-control-item"><span className="keycap">s</span><span>تحديد كل الطلاب الظاهرين للمراقبة</span></div>
          <div className="modal-control-item"><span className="keycap">c</span><span>مسح التحديد</span></div>
          <div className="modal-control-item"><span className="keycap">t</span><span>إظهار/إخفاء خطوط الجيران</span></div>
          <div className="modal-control-item"><span className="keycap">p</span><span>إظهار/إخفاء لوحة التحكم</span></div>
        </div>
        <div style={{ marginTop: '10px', color: '#6b7280', fontSize: '12px', fontWeight: 600 }}>
          ملاحظة: هذه الاختصارات تعمل في وضع العرض التجريبي (OpenCV). في لوحة التحكم الحالية سيتم إضافة أزرار تحكم مكافئة لاحقًا.
        </div>
      </div>
    </div>
  );
}


// ── Alert View (saved clip/snapshot) ─────────────────────────────────────────

function AlertView({
  alert,
  pttStatusText,
  onPttStart,
  onPttStop,
}: {
  alert: Alert | null;
  pttStatusText: string;
  onPttStart: () => void | Promise<void>;
  onPttStop: () => void;
}) {
  if (!alert) return null;

  const isLikelyUnplayable = Boolean(alert.video_file && alert.video_file.toLowerCase().endsWith('.avi'));

  const downloadReport = async () => {
    try {
      const res = await fetch(apiUrl(`/api/stream/alerts/report/${alert.id}.pdf`));
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `alert_${alert.id}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      // ignore
    }
  };

  return (
    <div className="modal-content" dir="rtl">
      {/* Header */}
      <div className="modal-header">
        <h2>{alert.event_type}</h2>
        <div className="modal-header-badge danger">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          تنبيه مسجّل
        </div>
      </div>

      {/* Alert details */}
      <div className="modal-alert-info">
        <div className="modal-alert-info-row">
          <span className="modal-alert-info-label">نوع التنبيه</span>
          <span className="modal-alert-info-value">{alert.event_type}</span>
        </div>
        <div className="modal-alert-info-row">
          <span className="modal-alert-info-label">الطالب</span>
          <span className="modal-alert-info-value">رقم {alert.track_id}</span>
        </div>
        {alert.looking_at !== null && (
          <div className="modal-alert-info-row">
            <span className="modal-alert-info-label">ينظر إلى</span>
            <span className="modal-alert-info-value">طالب رقم {alert.looking_at}</span>
          </div>
        )}
        <div className="modal-alert-info-row">
          <span className="modal-alert-info-label">الوقت</span>
          <span className="modal-alert-info-value">
            {new Date(alert.timestamp).toLocaleTimeString('en-US', { hour12: false })}
          </span>
        </div>
      </div>

      {/* Clip or snapshot */}
      <div className="modal-video-wrapper">
        <div className="modal-location-tooltip">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
            <circle cx="12" cy="10" r="3"/>
          </svg>
          <span>{alert.location}</span>
        </div>
        {alert.video_file && !isLikelyUnplayable ? (
          <video
            src={apiUrl(`/api/stream/alerts/video/${alert.video_file}`)}
            controls
            autoPlay
            className="modal-video-img"
          />
        ) : (
          <>
            <img
              src={apiUrl(`/api/stream/alerts/snapshot/${alert.snapshot_file}`)}
              alt={`تنبيه - ${alert.event_type}`}
              className="modal-video-img"
            />
            {alert.video_file && (
              <a
                className="modal-download-link"
                href={apiUrl(`/api/stream/alerts/video/${alert.video_file}`)}
                target="_blank"
                rel="noreferrer"
                style={{ display: 'inline-block', marginTop: '10px' }}
              >
                تنزيل مقطع التنبيه
              </a>
            )}
          </>
        )}
      </div>

      {/* Action buttons */}
      <div className="modal-actions">
        <button className="alert-btn-primary" style={{ flex: 1 }} onClick={downloadReport}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
            <polyline points="17 21 17 13 7 13 7 21"/>
            <polyline points="7 3 7 8 15 8"/>
          </svg>
          حفظ التقرير
        </button>
        <button
          className="alert-btn-green"
          style={{ flex: 1 }}
          title={pttStatusText}
          onPointerDown={(e) => {
            e.preventDefault();
            void onPttStart();
          }}
          onPointerUp={(e) => {
            e.preventDefault();
            onPttStop();
          }}
          onPointerCancel={() => onPttStop()}
          onMouseDown={(e) => {
            e.preventDefault();
            void onPttStart();
          }}
          onMouseUp={(e) => {
            e.preventDefault();
            onPttStop();
          }}
          onMouseLeave={() => onPttStop()}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/>
          </svg>
          الاتصال بالمراقب
        </button>
      </div>
    </div>
  );
}
