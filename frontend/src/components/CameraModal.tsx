import { apiUrl, authFetch } from '../config/api';
import { useEffect, useState, useCallback, useRef, type MouseEvent } from 'react';
import VideoSpeedControl from './VideoSpeedControl';

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
  status?: string;
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

interface MicPlacement {
  camera_id: string;
  norm_pos: [number, number];
}

export interface CameraModalMic {
  id: string;
  identifier: string;
  name: string;
  status: string;
  placements?: MicPlacement[];
}

export interface CameraModalRfScanner {
  id: string;
  identifier: string;
  position?: { camera_id?: string; norm_pos?: number[]; label?: string } | null;
}

interface RfDetectionOverlay {
  device_name: string | null;
  estimated_zone: string | null;
  is_spike: boolean;
  camera_id: string | null;
  norm_pos: number[] | null;
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
  hallMics?: CameraModalMic[];
  hallId?: string | null;
  hallScanners?: CameraModalRfScanner[];
  onConfirmAlert?: (alert: Alert) => void | Promise<void>;
  onCancelAlert?: (alert: Alert) => void | Promise<void>;
  onClose: () => void;
}

export default function CameraModal({ mode, alert, camera, stats, hallMics = [], hallId = null, hallScanners = [], onConfirmAlert, onCancelAlert, onClose }: CameraModalProps) {
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
          <CameraView camera={camera} stats={stats} hallMics={hallMics} hallId={hallId} hallScanners={hallScanners} />
        ) : (
          <AlertView alert={alert} onConfirmAlert={onConfirmAlert} onCancelAlert={onCancelAlert} />
        )}
      </div>
    </div>
  );
}


// ── Camera View (enlarged live feed + working controls) ───────────────────────

function CameraView({
  camera,
  stats,
  hallMics,
  hallId,
  hallScanners,
}: {
  camera: CameraModalProps['camera'];
  stats: CameraStats | null;
  hallMics: CameraModalMic[];
  hallId: string | null;
  hallScanners: CameraModalRfScanner[];
}) {
  const deviceId = camera?.id ?? null;
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [micPlacementMode, setMicPlacementMode] = useState(false);
  const [selectedMicId, setSelectedMicId] = useState(hallMics[0]?.id ?? '');
  const [localMics, setLocalMics] = useState<CameraModalMic[]>(hallMics);
  const inFlightPathsRef = useRef<Set<string>>(new Set());

  // ── RF: placement + live detection overlay ──
  const [rfPlacementMode, setRfPlacementMode] = useState(false);
  const [selectedScannerId, setSelectedScannerId] = useState(hallScanners[0]?.id ?? '');
  const [localScanners, setLocalScanners] = useState<CameraModalRfScanner[]>(hallScanners);
  const [rfDetections, setRfDetections] = useState<RfDetectionOverlay[]>([]);

  useEffect(() => {
    setLocalMics(hallMics);
    setSelectedMicId((current) => current || hallMics[0]?.id || '');
  }, [hallMics]);

  useEffect(() => {
    setLocalScanners(hallScanners);
    setSelectedScannerId((current) => current || hallScanners[0]?.id || '');
  }, [hallScanners]);

  // Poll the RF subsystem for currently-unknown devices in this hall.
  useEffect(() => {
    if (!hallId) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await authFetch(`/api/v1/rf/halls/${hallId}/unknown?window_minutes=5`);
        if (!res.ok) return;
        const data: RfDetectionOverlay[] = await res.json();
        if (!cancelled) setRfDetections(data);
      } catch { /* keep last */ }
    };
    poll();
    const t = window.setInterval(poll, 5000);
    return () => { cancelled = true; window.clearInterval(t); };
  }, [hallId]);

  const placeSelectedScanner = useCallback(async (event: MouseEvent<HTMLImageElement>) => {
    if (!deviceId || !selectedScannerId) return;
    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const x = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    const y = Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height));
    const norm_pos: [number, number] = [Number(x.toFixed(4)), Number(y.toFixed(4))];
    await authFetch(`/api/v1/rf/scanners/${selectedScannerId}/placement`, {
      method: 'PUT',
      body: JSON.stringify({ camera_id: deviceId, norm_pos }),
    });
    setLocalScanners((items) => items.map((sc) => (
      sc.id === selectedScannerId
        ? { ...sc, position: { ...(sc.position || {}), camera_id: deviceId, norm_pos } }
        : sc
    )));
  }, [deviceId, selectedScannerId]);

  const scannerPins = localScanners.filter((sc) => sc.position?.camera_id === deviceId && sc.position?.norm_pos);
  const rfMarkers = rfDetections.filter((d) => d.camera_id === deviceId && d.norm_pos);

  // Load current controls state on open
  useEffect(() => {
    if (!deviceId) return;
    authFetch(`/api/stream/cameras/${deviceId}/controls`)
      .catch(() => {});
  }, [deviceId]);

  const post = useCallback(async (path: string) => {
    if (!deviceId || inFlightPathsRef.current.has(path)) return;
    inFlightPathsRef.current.add(path);
    try {
      await authFetch(`/api/stream/cameras/${deviceId}${path}`, { method: 'POST' });
    } finally {
      inFlightPathsRef.current.delete(path);
    }
  }, [deviceId]);

  const placeSelectedMic = useCallback(async (event: MouseEvent<HTMLImageElement>) => {
    if (!deviceId || !selectedMicId) return;
    const mic = localMics.find((item) => item.id === selectedMicId);
    if (!mic) return;

    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const x = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    const y = Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height));
    const norm_pos: [number, number] = [Number(x.toFixed(4)), Number(y.toFixed(4))];
    const placements = [
      ...(mic.placements || []).filter((placement) => placement.camera_id !== deviceId),
      { camera_id: deviceId, norm_pos },
    ];

    await authFetch(`/api/devices/${selectedMicId}/placements`, {
      method: 'PUT',
      body: JSON.stringify({ placements }),
    });

    setLocalMics((items) => items.map((item) => (
      item.id === selectedMicId ? { ...item, placements } : item
    )));
  }, [deviceId, localMics, selectedMicId]);

  const visiblePins = localMics.flatMap((mic) => (
    (mic.placements || [])
      .filter((placement) => placement.camera_id === deviceId)
      .map((placement) => ({ ...placement, mic }))
  ));

  // Keyboard shortcuts — all pipeline controls from visualizer bottom bar
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if (e.repeat) return;
      let path: string | null = null;
      switch (e.key.toLowerCase()) {
        case 'v': path = '/quality'; break;
        case 'g': path = '/resolution'; break;
        case 'r': path = '/archive'; break;
        case 's': path = '/select-all'; break;
        case 'c': path = '/clear-selection'; break;
        case 't': path = '/toggle/neighbors'; break;
        case 'd': path = '/toggle/papers'; break;
        case 'f': path = '/toggle/phones'; break;
        case 'l': path = '/toggle/gaze-lines'; break;
        case 'k': path = '/toggle/facemesh'; break;
        case 'w': path = '/toggle/timestamp'; break;
        case 'p': path = '/toggle/panel'; break;
      }
      if (!path) return;
      e.preventDefault();
      void post(path);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [post]);

  return (
    <div className="modal-content" dir="rtl">
      {/* Header */}
      <div className="modal-header">
        <h2>{camera?.name || 'الكاميرا'}</h2>
        <div className={`modal-header-badge ${stats?.is_running ? 'active' : 'inactive'}`}>
          <span className={`camera-status-dot ${stats?.is_running ? 'active' : 'inactive'}`} style={{ marginLeft: '6px' }}></span>
          {stats?.is_running ? 'بث مباشر' : 'غير متصل'}
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
          <>
            <style>{`@keyframes rfPulse {0%{box-shadow:0 0 0 0 rgba(220,38,38,0.55)}70%{box-shadow:0 0 0 16px rgba(220,38,38,0)}100%{box-shadow:0 0 0 0 rgba(220,38,38,0)}}`}</style>
            <img
              src={apiUrl(camera.feedPath)}
              alt="بث مباشر"
              className="modal-video-img"
              onClick={micPlacementMode ? placeSelectedMic : rfPlacementMode ? placeSelectedScanner : undefined}
              style={(micPlacementMode || rfPlacementMode) ? { cursor: 'crosshair' } : undefined}
            />
            {visiblePins.map(({ mic, norm_pos }) => (
              <span
                key={`${mic.id}-${norm_pos[0]}-${norm_pos[1]}`}
                title={mic.name}
                style={{
                  position: 'absolute',
                  left: `${norm_pos[0] * 100}%`,
                  top: `${norm_pos[1] * 100}%`,
                  transform: 'translate(-50%, -50%)',
                  borderRadius: 999,
                  background: mic.id === selectedMicId ? '#8e52cb' : '#111827',
                  color: '#fff',
                  padding: '4px 8px',
                  fontSize: 11,
                  fontWeight: 800,
                  boxShadow: '0 6px 18px rgba(0,0,0,0.25)',
                  pointerEvents: 'none',
                }}
              >
                {mic.name}
              </span>
            ))}
            {/* RF scanner node pins (static location markers) */}
            {scannerPins.map((sc) => (
              <span
                key={`scan-${sc.id}`}
                title={sc.identifier}
                style={{
                  position: 'absolute',
                  left: `${sc.position!.norm_pos![0] * 100}%`,
                  top: `${sc.position!.norm_pos![1] * 100}%`,
                  transform: 'translate(-50%, -50%)',
                  borderRadius: 999,
                  background: sc.id === selectedScannerId && rfPlacementMode ? '#2563eb' : 'rgba(17,24,39,0.85)',
                  color: '#fff', padding: '3px 7px', fontSize: 11, fontWeight: 800,
                  boxShadow: '0 4px 12px rgba(0,0,0,0.3)', pointerEvents: 'none',
                }}
              >
                📡 {sc.identifier}
              </span>
            ))}
            {/* RF live detection markers (pulsing) */}
            {rfMarkers.map((d, i) => (
              <div
                key={`rf-${i}`}
                style={{
                  position: 'absolute',
                  left: `${d.norm_pos![0] * 100}%`,
                  top: `${d.norm_pos![1] * 100}%`,
                  transform: 'translate(-50%, -50%)',
                  pointerEvents: 'none', textAlign: 'center',
                }}
              >
                <div style={{
                  width: 18, height: 18, borderRadius: 999, margin: '0 auto',
                  background: '#dc2626', border: '2px solid #fff', animation: 'rfPulse 1.6s infinite',
                }} />
                <div style={{
                  marginTop: 4, display: 'inline-block', background: '#dc2626', color: '#fff',
                  padding: '2px 8px', borderRadius: 8, fontSize: 11, fontWeight: 800, whiteSpace: 'nowrap',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                }}>
                  📡 {d.is_spike ? '⚠️ ' : ''}{d.device_name || 'جهاز مجهول'}
                </div>
              </div>
            ))}
          </>
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
          {/* Row 1: shortcut toggle */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 6 }}>
            <button onClick={() => setShowShortcuts(s => !s)}
              style={{ background: 'none', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '4px 10px', cursor: 'pointer', fontSize: '12px', color: '#6b7280', fontWeight: 700 }}>
              ⌨ اختصارات {showShortcuts ? '▲' : '▼'}
            </button>
            {hallMics.length > 0 && (
              <button
                type="button"
                onClick={() => { setMicPlacementMode((value) => !value); setRfPlacementMode(false); }}
                aria-pressed={micPlacementMode}
                style={{ marginRight: 8, background: micPlacementMode ? '#8e52cb' : 'none', color: micPlacementMode ? '#fff' : '#6b7280', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '4px 10px', cursor: 'pointer', fontSize: '12px', fontWeight: 700 }}
              >
                تحديد المايك
              </button>
            )}
            {localScanners.length > 0 && (
              <button
                type="button"
                onClick={() => { setRfPlacementMode((value) => !value); setMicPlacementMode(false); }}
                aria-pressed={rfPlacementMode}
                style={{ marginRight: 8, background: rfPlacementMode ? '#2563eb' : 'none', color: rfPlacementMode ? '#fff' : '#6b7280', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '4px 10px', cursor: 'pointer', fontSize: '12px', fontWeight: 700 }}
              >
                تحديد جهاز RF
              </button>
            )}
          </div>
          {rfPlacementMode && localScanners.length > 0 && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, direction: 'rtl', marginBottom: 6 }}>
              <label style={{ fontSize: 12, color: '#4b5563', fontWeight: 800 }}>
                جهاز RF
                <select
                  aria-label="جهاز RF"
                  value={selectedScannerId}
                  onChange={(event) => setSelectedScannerId(event.target.value)}
                  style={{ marginRight: 8, border: '1px solid #e5e7eb', borderRadius: 8, padding: '4px 8px' }}
                >
                  {localScanners.map((sc) => (
                    <option key={sc.id} value={sc.id}>{sc.identifier}</option>
                  ))}
                </select>
              </label>
              <span style={{ fontSize: 11, color: '#6b7280', alignSelf: 'center' }}>انقر على البث لتحديد موقع الجهاز</span>
            </div>
          )}
          {micPlacementMode && hallMics.length > 0 && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, direction: 'rtl' }}>
              <label style={{ fontSize: 12, color: '#4b5563', fontWeight: 800 }}>
                الميكروفون
                <select
                  aria-label="الميكروفون"
                  value={selectedMicId}
                  onChange={(event) => setSelectedMicId(event.target.value)}
                  style={{ marginRight: 8, border: '1px solid #e5e7eb', borderRadius: 8, padding: '4px 8px' }}
                >
                  {hallMics.map((mic) => (
                    <option key={mic.id} value={mic.id}>{mic.name}</option>
                  ))}
                </select>
              </label>
            </div>
          )}
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
              ['K', 'تبديل عرض نقاط خريطة الوجه ON/OFF'],
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
  onConfirmAlert,
  onCancelAlert,
}: {
  alert: Alert | null;
  onConfirmAlert?: (alert: Alert) => void | Promise<void>;
  onCancelAlert?: (alert: Alert) => void | Promise<void>;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);

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
          <>
            <video
              ref={videoRef}
              src={apiUrl(`/api/stream/alerts/video/${alert.video_file}`)}
              controls
              autoPlay
              className="modal-video-img"
            />
            <div className="absolute bottom-3 left-3">
              <VideoSpeedControl videoRef={videoRef} />
            </div>
          </>
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
        {alert.status !== 'confirmed' && (
          <button className="alert-btn-primary" style={{ flex: 1, background: '#16a34a' }} onClick={() => void onConfirmAlert?.(alert)}>
            تأكيد الحالة
          </button>
        )}
        {alert.status !== 'cancelled' && (
          <button className="alert-btn-primary" style={{ flex: 1, background: '#6b7280' }} onClick={() => void onCancelAlert?.(alert)}>
            إلغاء بعد المراجعة
          </button>
        )}
        <button className="alert-btn-primary" style={{ flex: 1 }} onClick={downloadReport}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
            <polyline points="17 21 17 13 7 13 7 21"/>
            <polyline points="7 3 7 8 15 8"/>
          </svg>
          حفظ التقرير
        </button>
      </div>
    </div>
  );
}
