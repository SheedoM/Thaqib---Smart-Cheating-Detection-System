import { useState, useEffect, useRef } from 'react';
import CameraModal from '../components/CameraModal';
import { apiUrl, STREAM_BASE } from '../config/api';

// ─── Types ───────────────────────────────────────────────────────────────────

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
}

interface CameraItem {
  id: string;
  identifier: string;
  name: string;
  type: string;
  status: string;
  active: boolean;
  feed_path: string | null;
  source_configured: boolean;
  position?: Record<string, unknown>;
}

interface MicItem {
  id: string;
  identifier: string;
  name: string;
  status: string;
}

interface HallItem {
  id: string;
  name: string;
  status: string;
  cameras: CameraItem[];
  mics: MicItem[];
}

interface DashboardPageProps {
  onLogout: () => void;
}

type TabType = 'cases' | 'cameras';

const NAV_ITEMS = [
  { label: 'الرئيسية', key: 'home', active: true },
  { label: 'القاعات', key: 'halls', active: false },
  { label: 'الإمتحانات', key: 'exams', active: false },
  { label: 'المشرفين', key: 'supervisors', active: false },
  { label: 'التقارير', key: 'reports', active: false },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatTime(isoString: string): string {
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString('en-US', { hour12: false });
  } catch {
    return '—';
  }
}

function timeSince(isoString: string): string {
  try {
    const d = new Date(isoString);
    const seconds = Math.floor((Date.now() - d.getTime()) / 1000);
    if (seconds < 60) return `${seconds}ث`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}د`;
  } catch {
    return '—';
  }
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function DashboardPage({ onLogout }: DashboardPageProps) {
  const [activeTab, setActiveTab] = useState<TabType>('cameras');
  const [halls, setHalls] = useState<HallItem[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [statsByCamera, setStatsByCamera] = useState<Record<string, CameraStats>>({});
  const [modalMode, setModalMode] = useState<'camera' | 'alert' | null>(null);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [selectedCamera, setSelectedCamera] = useState<{
    id: string;
    name: string;
    hallName: string;
    feedPath: string | null;
  } | null>(null);
  const hallsPollRef = useRef<number | null>(null);
  const alertPollRef = useRef<number | null>(null);
  const statsPollRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (hallsPollRef.current) clearInterval(hallsPollRef.current);
      if (alertPollRef.current) clearInterval(alertPollRef.current);
      if (statsPollRef.current) clearInterval(statsPollRef.current);
    };
  }, []);

  useEffect(() => {
    const pollMonitoring = async () => {
      try {
        const res = await fetch(apiUrl(`${STREAM_BASE}/monitoring`));
        const data = await res.json();
        setHalls(data.halls || []);
      } catch {
        // ignore polling errors
      }
    };

    const pollAlerts = async () => {
      try {
        const res = await fetch(apiUrl(`${STREAM_BASE}/alerts`));
        const data = await res.json();
        setAlerts(data.alerts || []);
      } catch { /* ignore */ }
    };

    const pollStats = async () => {
      try {
        const res = await fetch(apiUrl(`${STREAM_BASE}/status`));
        const data = await res.json();
        setStatsByCamera(data.cameras || {});
      } catch { /* ignore */ }
    };

    pollMonitoring();
    pollAlerts();
    pollStats();

    hallsPollRef.current = window.setInterval(pollMonitoring, 5000);
    alertPollRef.current = window.setInterval(pollAlerts, 3000);
    statsPollRef.current = window.setInterval(pollStats, 2000);

    return () => {
      if (hallsPollRef.current) clearInterval(hallsPollRef.current);
      if (alertPollRef.current) clearInterval(alertPollRef.current);
      if (statsPollRef.current) clearInterval(statsPollRef.current);
    };
  }, []);

  const openCameraModal = (camera: CameraItem, hallName: string) => {
    setModalMode('camera');
    setSelectedAlert(null);
    setSelectedCamera({
      id: camera.id,
      name: camera.name,
      hallName,
      feedPath: camera.feed_path,
    });
  };

  const openAlertModal = (alert: Alert) => {
    setModalMode('alert');
    setSelectedAlert(alert);
    setSelectedCamera(null);
  };

  const closeModal = () => {
    setModalMode(null);
    setSelectedAlert(null);
    setSelectedCamera(null);
  };

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="dashboard-root" dir="rtl">
      {/* ══════════ HEADER ══════════ */}
      <header className="dashboard-header">
        {/* Background texture */}
        <div className="dashboard-header-bg">
          <img
            src="/Frame 1000003437.png"
            alt=""
            className="dashboard-header-bg-img"
          />
          <div className="dashboard-header-bg-overlay"></div>
        </div>

        {/* Header content */}
        <div className="dashboard-header-content">
          {/* Top nav bar */}
          <div className="dashboard-navbar">
            {/* Left side: user info */}
            <div className="dashboard-user-area">
              <div className="dashboard-user-info">
                <span className="dashboard-user-name">عمرو طلعت</span>
                <span className="dashboard-user-role">مشرف النظام</span>
              </div>
              <div className="dashboard-avatar">
                <div className="dashboard-avatar-placeholder">م</div>
              </div>
              <div className="dashboard-user-divider"></div>
              {/* Notification bell */}
              <button className="dashboard-icon-btn" title="الإشعارات">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                  <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                </svg>
                {alerts.length > 0 && (
                  <span className="dashboard-notification-badge">{alerts.length}</span>
                )}
              </button>
              {/* Settings */}
              <button className="dashboard-icon-btn" title="الإعدادات" onClick={onLogout}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="3"/>
                  <path d="M12 1v2m0 18v2m-9-11h2m18 0h2m-2.636-7.364l-1.414 1.414M6.05 17.95l-1.414 1.414m0-14.728l1.414 1.414M17.95 17.95l1.414 1.414"/>
                </svg>
              </button>
            </div>

            {/* Center: nav items */}
            <nav className="dashboard-nav">
              {NAV_ITEMS.map((item) => (
                <button
                  key={item.key}
                  className={`dashboard-nav-item ${item.active ? 'active' : ''}`}
                >
                  {item.label}
                </button>
              ))}
            </nav>

            {/* Right: logo */}
            <div className="dashboard-logo">
              <img src="/Frame 76.svg" alt="Thaqib" className="dashboard-logo-img" />
            </div>
          </div>

          {/* Page title */}
          <h1 className="dashboard-page-title">الرئيسية</h1>

          {/* Sub-header: tabs + hall selector */}
          <div className="dashboard-subheader">
            {/* Left: hall selector */}
            <div className="dashboard-hall-select">
              <span>القاعة</span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="6 9 12 15 18 9"/>
              </svg>
            </div>

            {/* Right: tab buttons */}
            <div className="dashboard-tabs">
              <button
                className={`dashboard-tab ${activeTab === 'cameras' ? '' : 'active'}`}
                onClick={() => setActiveTab('cases')}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10"/>
                  <polyline points="12 6 12 12 16 14"/>
                </svg>
                أخر الحالات
              </button>
              <button
                className={`dashboard-tab ${activeTab === 'cameras' ? 'active' : ''}`}
                onClick={() => setActiveTab('cameras')}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
                  <circle cx="12" cy="13" r="4"/>
                </svg>
                عرض الكاميرات
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* ══════════ MAIN CONTENT ══════════ */}
      <main className="dashboard-content">
        {activeTab === 'cases' ? (
          <CasesTab
            alerts={alerts}
            onViewAlert={openAlertModal}
          />
        ) : (
          <CamerasTab
            halls={halls}
            statsByCamera={statsByCamera}
            onClickCamera={openCameraModal}
            alerts={alerts}
          />
        )}
      </main>

      {/* ══════════ MODAL ══════════ */}
      {modalMode && (
        <CameraModal
          mode={modalMode}
          alert={selectedAlert}
          camera={selectedCamera}
          stats={selectedCamera ? statsByCamera[selectedCamera.id] ?? null : null}
          onClose={closeModal}
        />
      )}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// SUB-COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════════

// ── Cases Tab ────────────────────────────────────────────────────────────────

function CasesTab({
  alerts,
  onViewAlert,
}: {
  alerts: Alert[];
  onViewAlert: (alert: Alert) => void;
}) {
  if (alerts.length === 0) {
    return (
      <div className="dashboard-empty-state">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#9f9fa9" strokeWidth="1.5">
          <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/>
          <path d="M9 12l2 2 4-4"/>
        </svg>
        <h3>لا توجد حالات حالياً</h3>
        <p>سيتم عرض التنبيهات هنا عند اكتشاف سلوك مشبوه</p>
        <p style={{ fontSize: '14px', color: '#9f9fa9', marginTop: '8px' }}>
          تأكد من تشغيل الكاميرات من تبويب "عرض الكاميرات"
        </p>
      </div>
    );
  }

  return (
    <div className="cases-section">
      <div className="cases-grid">
        {alerts.map((alert) => (
          <AlertCard key={alert.id} alert={alert} onViewAlert={onViewAlert} />
        ))}
      </div>
    </div>
  );
}

function AlertCard({
  alert,
  onViewAlert,
}: {
  alert: Alert;
  onViewAlert: (alert: Alert) => void;
}) {
  const isHighPriority = alert.severity === 'high';

  return (
    <div className={`alert-card ${isHighPriority ? 'alert-card-danger' : 'alert-card-success'}`}>
      {/* Header row: time + status */}
      <div className="alert-card-header">
        <span className="alert-card-time">{formatTime(alert.timestamp)}</span>
        <div className="alert-card-status">
          <span className={`alert-card-status-text ${isHighPriority ? 'danger' : 'success'}`}>
            {isHighPriority ? 'أولوية قصوى' : 'تم حلها'}
          </span>
          {isHighPriority ? (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fb2c36" strokeWidth="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/>
              <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
          ) : (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00bc7d" strokeWidth="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
              <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
          )}
        </div>
      </div>

      {/* Title */}
      <h3 className="alert-card-title">{alert.event_type}</h3>

      {/* Details */}
      <div className="alert-card-details">
        <div className="alert-card-detail-row">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9f9fa9" strokeWidth="2">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
            <circle cx="12" cy="10" r="3"/>
          </svg>
          <span>{alert.location}</span>
        </div>
        <div className="alert-card-detail-row">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9f9fa9" strokeWidth="2">
            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
            <circle cx="12" cy="13" r="4"/>
          </svg>
          <span>{alert.hall_name} - {alert.camera_name}</span>
        </div>
        <div className="alert-card-detail-row">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#71717b" strokeWidth="2">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
          <span> مستمر: {timeSince(alert.timestamp)}</span>
        </div>
      </div>

      {/* Actions */}
      <div className="alert-card-actions">
        <button className="alert-btn-primary" onClick={() => onViewAlert(alert)}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="23 7 16 12 23 17 23 7"/>
            <rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
          </svg>
          عرض الحالة
        </button>
        <button className="alert-btn-green">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/>
          </svg>
          الاتصال بالمراقب
        </button>
      </div>
    </div>
  );
}


// ── Cameras Tab ──────────────────────────────────────────────────────────────

function CamerasTab({
  halls,
  statsByCamera,
  onClickCamera,
  alerts,
}: {
  halls: HallItem[];
  statsByCamera: Record<string, CameraStats>;
  onClickCamera: (camera: CameraItem, hallName: string) => void;
  alerts: Alert[];
}) {
  return (
    <div className="cameras-section">
      {halls.map((hall) => (
        <div key={hall.id} className="camera-hall-group">
          <div className="camera-hall-header">
            <h2 className="hall-title">{hall.name}</h2>
            <button className="alert-btn-green" style={{ marginRight: 'auto', marginLeft: 0 }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/>
              </svg>
              الاتصال بالمراقب
            </button>
          </div>
          <div className="cameras-grid">
            {hall.cameras.map((camera) => {
              const stats = statsByCamera[camera.id];
              const hasActiveAlert = alerts.some((alert) => alert.camera_id === camera.id && alert.severity === 'high');
              const canStream = Boolean(camera.feed_path);
              const streamRunning = Boolean(stats?.is_running);
              const showLoading = canStream && !streamRunning;

              return (
                <div
                  key={camera.id}
                  className={`camera-feed ${hasActiveAlert ? 'camera-feed-alert' : ''}`}
                  onClick={() => onClickCamera(camera, hall.name)}
                >
                  <div className="camera-feed-label">
                    <span className={`camera-status-dot ${streamRunning ? 'active' : 'inactive'}`}></span>
                    <span>{camera.name}</span>
                  </div>
                  {(streamRunning || canStream) && (
                    <div className="camera-rec-indicator">
                      <span className="rec-dot"></span>
                      REC
                    </div>
                  )}
                  {hasActiveAlert && (
                    <div className="camera-alert-overlay">
                      <span className="camera-alert-badge">حركة مشبوهة</span>
                    </div>
                  )}
                  {streamRunning && camera.feed_path ? (
                    <img
                      src={apiUrl(camera.feed_path)}
                      alt={camera.name}
                      className="camera-feed-img"
                    />
                  ) : showLoading ? (
                    <div className="camera-feed-placeholder">
                      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#9f9fa9" strokeWidth="1.5">
                        <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
                        <circle cx="12" cy="13" r="4"/>
                      </svg>
                      <p>جاري تحميل البث...</p>
                    </div>
                  ) : (
                    <div className="camera-feed-placeholder">
                      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#9f9fa9" strokeWidth="1.5">
                        <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
                        <circle cx="12" cy="13" r="4"/>
                      </svg>
                      <p>الكاميرا غير متصلة</p>
                    </div>
                  )}
                  <div className="camera-feed-stats">
                    {streamRunning ? (
                      <>
                        <span>FPS: {stats?.fps || 0}</span>
                        <span>•</span>
                        <span>Tracked: {stats?.tracked_count || 0}</span>
                        <span>•</span>
                        <span>RES: 1080p</span>
                      </>
                    ) : (
                      <span>—</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
