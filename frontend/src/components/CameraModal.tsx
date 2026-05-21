import { apiUrl, authFetch } from '../config/api';
import { useEffect, useState, useCallback } from 'react';

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


// ── Camera View (enlarged live feed + working controls) ───────────────────────

function CameraView({
  camera,
  stats,
}: {
  camera: CameraModalProps['camera'];
  stats: CameraStats | null;
}) {
  const deviceId = camera?.id ?? null;
  const [controls, setControls] = useState<Record<string, unknown>>({});
  const [toggling, setToggling] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);

  const quality = typeof controls.quality === 'number' ? controls.quality : null;
  const resolution = typeof controls.resolution === 'string' ? controls.resolution : null;
  const archiveMode = typeof controls.archive_mode === 'string' ? controls.archive_mode : null;
  const selectedCount = typeof controls.selected_count === 'number' ? controls.selected_count : null;
  const trackedCount = typeof controls.tracked_count === 'number' ? controls.tracked_count : null;

  // Load current controls state on open
  useEffect(() => {
    if (!deviceId) return;
    authFetch(`/api/stream/cameras/${deviceId}/controls`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setControls(d); })
      .catch(() => {});
  }, [deviceId]);

  const post = useCallback(async (path: string) => {
    if (!deviceId || toggling) return;
    setToggling(true);
    try {
      const r = await authFetch(`/api/stream/cameras/${deviceId}${path}`, { method: 'POST' });
      if (r.ok) {
        const d = await r.json();
        setControls(prev => ({ ...prev, ...d }));
      }
    } finally { setToggling(false); }
  }, [deviceId, toggling]);

  // Keyboard shortcuts — all pipeline controls from visualizer bottom bar
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      switch (e.key.toLowerCase()) {
        case 'v': void post('/quality'); break;
        case 'g': void post('/resolution'); break;
        case 'r': void post('/archive'); break;
        case 's': void post('/select-all'); break;
        case 'c': void post('/clear-selection'); break;
        case 't': void post('/toggle/neighbors'); break;
        case 'd': void post('/toggle/papers'); break;
        case 'f': void post('/toggle/phones'); break;
        case 'l': void post('/toggle/gaze-lines'); break;
        case 'w': void post('/toggle/timestamp'); break;
        case 'p': void post('/toggle/panel'); break;
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [post]);

  const qualityLabel = quality === 50 ? 'LOW' : quality === 75 ? 'MED' : quality === 90 ? 'HIGH' : quality != null ? `${quality}%` : '—';

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
        <div className="modal-location-tooltip">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
            <circle cx="12" cy="10" r="3"/>
          </svg>
          <span>{camera ? `${camera.hallName} - ${camera.name}` : 'بث مباشر'}</span>
        </div>

        {camera?.feedPath ? (
          <img src={apiUrl(camera.feedPath)} alt="بث مباشر" className="modal-video-img" />
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

      {/* Live controls */}
      {deviceId && (
        <div style={{ padding: '8px 0 4px', direction: 'ltr' }}>
          {/* Row 1: status + shortcut toggle */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {selectedCount !== null && trackedCount !== null && (
                <span style={{ fontSize: 11, fontWeight: 900, color: '#6b7280', padding: '2px 8px', background: '#f3f4f6', borderRadius: 6 }}>
                  المراقبة: {selectedCount}/{trackedCount}
                </span>
              )}
              {archiveMode && (
                <span style={{ fontSize: 11, fontWeight: 900, color: '#44006E', padding: '2px 8px', background: '#f3e8ff', borderRadius: 6 }}>
                  أرشيف: {archiveMode}
                </span>
              )}
            </div>
            <button onClick={() => setShowShortcuts(s => !s)}
              style={{ background: 'none', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '4px 10px', cursor: 'pointer', fontSize: '12px', color: '#6b7280', fontWeight: 700 }}>
              ⌨ اختصارات {showShortcuts ? '▲' : '▼'}
            </button>
          </div>
          {/* Row 2: action buttons */}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <button onClick={() => void post('/quality')} disabled={toggling}
              style={{ background: '#f3f4f6', border: '1px solid #d1d5db', borderRadius: '8px', padding: '4px 12px', cursor: 'pointer', fontSize: '12px', fontWeight: 900, color: '#374151' }}>
              🎬 Quality: <span style={{ color: '#44006E' }}>{qualityLabel}</span>
              <span style={{ color: '#9ca3af', marginLeft: 4, fontSize: 10 }}>[V]</span>
            </button>
            <button onClick={() => void post('/resolution')} disabled={toggling}
              style={{ background: '#f3f4f6', border: '1px solid #d1d5db', borderRadius: '8px', padding: '4px 12px', cursor: 'pointer', fontSize: '12px', fontWeight: 900, color: '#374151' }}>
              📀 Res: <span style={{ color: '#44006E' }}>{resolution ?? '—'}</span>
              <span style={{ color: '#9ca3af', marginLeft: 4, fontSize: 10 }}>[G]</span>
            </button>
            <button onClick={() => void post('/archive')} disabled={toggling}
              style={{ background: '#f3f4f6', border: '1px solid #d1d5db', borderRadius: '8px', padding: '4px 12px', cursor: 'pointer', fontSize: '12px', fontWeight: 900, color: '#374151' }}>
              💾 Archive: <span style={{ color: '#44006E' }}>{archiveMode ?? '—'}</span>
              <span style={{ color: '#9ca3af', marginLeft: 4, fontSize: 10 }}>[R]</span>
            </button>
            <button onClick={() => void post('/select-all')} disabled={toggling}
              style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: '8px', padding: '4px 12px', cursor: 'pointer', fontSize: '12px', fontWeight: 900, color: '#166534' }}>
              راقب الكل
              <span style={{ color: '#9ca3af', marginLeft: 4, fontSize: 10 }}>[S]</span>
            </button>
            <button onClick={() => void post('/clear-selection')} disabled={toggling}
              style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: '8px', padding: '4px 12px', cursor: 'pointer', fontSize: '12px', fontWeight: 900, color: '#991b1b' }}>
              إلغاء المراقبة
              <span style={{ color: '#9ca3af', marginLeft: 4, fontSize: 10 }}>[C]</span>
            </button>
          </div>
        </div>
      )}

      {/* Keyboard shortcut legend */}
      {showShortcuts && (
        <div style={{ background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '12px 16px', marginBottom: 8, direction: 'rtl' }}>
          <p style={{ fontSize: 11, fontWeight: 900, color: '#6b7280', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>اختصارات لوحة المفاتيح</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '5px 16px', fontSize: 12, alignItems: 'center' }}>
            {([
              ['V', 'تبديل جودة الفيديو — LOW 50% → MED 75% → HIGH 90%'],
              ['G', 'تبديل دقة المعالجة — NATIVE → 1080p → 720p'],
              ['R', 'تبديل وضع الأرشيف (raw / annotated)'],
              ['S', 'مراقبة جميع الطلاب المكتشفين'],
              ['C', 'إيقاف مراقبة الجميع'],
              ['T', 'تبديل رسوم الجيران ON/OFF'],
              ['D', 'تبديل عرض إطارات الورق ON/OFF'],
              ['F', 'تبديل عرض إطارات الهاتف ON/OFF'],
              ['L', 'تبديل خطوط النظرة→ورق ON/OFF'],
              ['W', 'تبديل التوقيت المرئي ON/OFF'],
              ['P', 'إخفاء/إظهار لوحة التحكم'],
              ['Esc', 'إغلاق النافذة'],
            ] as [string, string][]).map(([key, desc]) => (
              <>
                <kbd key={key} style={{ background: '#e5e7eb', borderRadius: 4, padding: '2px 6px', fontFamily: 'monospace', fontWeight: 700, fontSize: 11 }}>{key}</kbd>
                <span style={{ color: '#374151', fontWeight: 700 }}>{desc}</span>
              </>
            ))}
          </div>
        </div>
      )}

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
      const res = await authFetch(`/api/stream/alerts/report/${alert.id}.pdf`);
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
          onPointerDown={(e) => { e.preventDefault(); void onPttStart(); }}
          onPointerUp={(e) => { e.preventDefault(); onPttStop(); }}
          onPointerCancel={() => onPttStop()}
          onMouseDown={(e) => { e.preventDefault(); void onPttStart(); }}
          onMouseUp={(e) => { e.preventDefault(); onPttStop(); }}
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
