import { useState, useEffect, useRef } from 'react';
import CameraModal from '../components/CameraModal';
import HallsTab from '../components/HallsTab';
import ExamsTab from '../components/ExamsTab';
import SupervisorsTab from '../components/SupervisorsTab';
import SettingsTab from '../components/SettingsTab';
import { apiUrl, authFetch, STREAM_BASE } from '../config/api';
import { useHallVoice } from '../hooks/useHallVoice';

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
  monitoring_status: 'active' | 'inactive';
  cameras: CameraItem[];
  mics: MicItem[];
}



interface CurrentUser {
  full_name: string;
  role: string;
}

type TabType = 'cases' | 'cameras';

const NAV_ITEMS = [
  { label: 'الرئيسية', key: 'home', active: true },
  { label: 'القاعات', key: 'halls', active: false },
  { label: 'الإمتحانات', key: 'exams', active: false },
  { label: 'المشرفين', key: 'supervisors', active: false },
  { label: 'الإعدادات', key: 'settings', active: false },
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

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return `${h}h ${rm}m`;
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

function HallVoiceControl({
  hallId,
  hallName,
}: {
  hallId: string;
  hallName: string;
}) {
  const voice = useHallVoice({ hallId, autoConnect: true });
  const others = voice.participants.filter((p) => p.role === 'invigilator');
  const invigilatorConnected = others.length > 0;
  const isError = voice.state === 'error';

  const statusLabel =
    voice.isTransmitting ? 'إرسال' :
    voice.remoteTalking ? `يتحدث: ${voice.remoteTalking.name}` :
    isError ? 'فشل الاتصال الصوتي' :
    voice.micBlocked ? 'الميكروفون محجوب' :
    voice.isConnected ? 'متصل' :
    voice.state === 'connecting' ? 'يتصل' : 'غير متصل';

  return (
    <div
      style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}
      title={voice.statusText}
      aria-label={`صوت ${hallName}`}
    >
      <span
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 6, minHeight: 34, padding: '7px 10px',
          borderRadius: 8,
          background: isError ? '#fef2f2' : voice.isConnected ? '#ecfdf5' : '#f4f4f5',
          color: isError ? '#b91c1c' : voice.isConnected ? '#047857' : '#71717a',
          fontSize: 12, fontWeight: 800, whiteSpace: 'nowrap',
        }}
      >
        <span style={{
          width: 8, height: 8, borderRadius: 999, display: 'inline-block',
          background: voice.isTransmitting ? '#ef4444' : isError ? '#ef4444' : voice.isConnected ? '#10b981' : '#a1a1aa',
        }} />
        {statusLabel}
      </span>
      <span
        style={{
          minHeight: 34, display: 'inline-flex', alignItems: 'center', padding: '7px 10px', borderRadius: 8,
          background: invigilatorConnected ? '#eef2ff' : '#f4f4f5',
          color: invigilatorConnected ? '#3730a3' : '#71717a',
          fontSize: 12, fontWeight: 800, whiteSpace: 'nowrap',
        }}
      >
        {invigilatorConnected ? 'المراقب متصل' : 'المراقب غير متصل'}
      </span>
      {isError && (
        <button
          type="button"
          className="alert-btn-primary"
          style={{ background: '#6b7280', paddingInline: 10 }}
          onClick={(e) => { e.stopPropagation(); void voice.connect(); }}
        >
          إعادة الاتصال
        </button>
      )}
      <button
        type="button"
        className="alert-btn-green"
        disabled={voice.micBlocked}
        title={voice.statusText}
        onPointerDown={(e) => { e.preventDefault(); e.stopPropagation(); void voice.startTalking(); }}
        onPointerUp={(e) => { e.preventDefault(); e.stopPropagation(); voice.stopTalking(); }}
        onPointerCancel={() => voice.stopTalking()}
        onMouseLeave={() => voice.stopTalking()}
        style={{ background: voice.isTransmitting ? '#ef4444' : undefined, paddingInline: 12 }}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
          <line x1="12" y1="19" x2="12" y2="23"/>
          <line x1="8" y1="23" x2="16" y2="23"/>
        </svg>
        تحدث مع القاعة
      </button>
    </div>
  );
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function DashboardPage({ onLogout }: { onLogout?: () => void }) {
  const [activeNav, setActiveNav] = useState('home');
  const [activeTab, setActiveTab] = useState<TabType>('cameras');
  const [selectedHallId, setSelectedHallId] = useState<string>('all');
  const [halls, setHalls] = useState<HallItem[]>([]);
  const [hallsLoaded, setHallsLoaded] = useState(false);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [recentAlertByCameraId, setRecentAlertByCameraId] = useState<Record<string, Alert | null>>({});
  const [statsByCamera, setStatsByCamera] = useState<Record<string, CameraStats>>({});
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
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
  const lastSeenAlertIdByCameraRef = useRef<Record<string, string>>({});
  const clearTimersRef = useRef<Record<string, number>>({});
  const notifWrapRef = useRef<HTMLDivElement | null>(null);

  const confirmAlert = async (alert: Alert) => {
    const res = await authFetch(`/api/alerts/${alert.id}/confirm`, { method: 'POST' });
    if (!res.ok) return;
    await res.json().catch(() => null);
    setAlerts(prev => prev.map(item => item.id === alert.id ? { ...item, status: 'confirmed' } : item));
    setSelectedAlert(prev => prev && prev.id === alert.id ? { ...prev, status: 'confirmed' } : prev);
  };

  const cancelAlert = async (alert: Alert) => {
    const res = await authFetch(`/api/alerts/${alert.id}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ notes: 'Cancelled after review.' }),
    });
    if (!res.ok) return;
    setAlerts(prev => prev.map(item => item.id === alert.id ? { ...item, status: 'cancelled' } : item));
    setSelectedAlert(prev => prev && prev.id === alert.id ? { ...prev, status: 'cancelled' } : prev);
  };

  useEffect(() => {
    return () => {
      if (hallsPollRef.current) clearInterval(hallsPollRef.current);
      if (alertPollRef.current) clearInterval(alertPollRef.current);
      if (statsPollRef.current) clearInterval(statsPollRef.current);
      Object.values(clearTimersRef.current).forEach((t) => clearTimeout(t));
    };
  }, []);

  useEffect(() => {
    const onDocDown = (ev: MouseEvent) => {
      const el = notifWrapRef.current;
      if (!el) return;
      if (ev.target instanceof Node && !el.contains(ev.target)) setNotificationsOpen(false);
    };
    document.addEventListener('mousedown', onDocDown);
    return () => document.removeEventListener('mousedown', onDocDown);
  }, []);

  useEffect(() => {
    const loadCurrentUser = async () => {
      try {
        const res = await authFetch('/api/auth/me');
        if (res.ok) setCurrentUser(await res.json());
      } catch {
        // ignore; the app shell will handle unauthenticated sessions
      }
    };

    const pollMonitoring = async () => {
      try {
        const res = await authFetch(`${STREAM_BASE}/monitoring`);
        const data = await res.json();
        setHalls(data.halls || []);
      } catch {
        // ignore polling errors
      } finally {
        // mark that we've attempted the first load so UI doesn't stay blank
        setHallsLoaded(true);
      }
    };

    const pollAlerts = async () => {
      try {
        const res = await authFetch(`${STREAM_BASE}/alerts`);
        const data = await res.json();
        const nextAlerts: Alert[] = data.alerts || [];
        setAlerts(nextAlerts);

        // Detect newest alert per camera and show a temporary notification (5s).
        const newestByCamera: Record<string, Alert> = {};
        for (const a of nextAlerts) {
          if (!a?.camera_id) continue;
          if (!newestByCamera[a.camera_id]) newestByCamera[a.camera_id] = a;
        }

        const nextRecent: Record<string, Alert | null> = {};
        for (const [cameraId, newest] of Object.entries(newestByCamera)) {
          const lastSeen = lastSeenAlertIdByCameraRef.current[cameraId];
          if (lastSeen !== newest.id) {
            lastSeenAlertIdByCameraRef.current[cameraId] = newest.id;
            nextRecent[cameraId] = newest;

            const oldTimer = clearTimersRef.current[cameraId];
            if (oldTimer) clearTimeout(oldTimer);
            clearTimersRef.current[cameraId] = window.setTimeout(() => {
              setRecentAlertByCameraId((prev) => ({ ...prev, [cameraId]: null }));
            }, 5000);
          }
        }

        if (Object.keys(nextRecent).length > 0) {
          setRecentAlertByCameraId((prev) => ({ ...prev, ...nextRecent }));
        }
      } catch { /* ignore */ }
    };

    const pollStats = async () => {
      try {
        const res = await authFetch(`${STREAM_BASE}/status`);
        const data = await res.json();
        setStatsByCamera(data.cameras || {});
      } catch { /* ignore */ }
    };

    loadCurrentUser();
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

  const refreshStreams = async () => {
    try {
      await authFetch(`${STREAM_BASE}/refresh`, { method: 'POST' });
    } catch {
      // ignore
    }
  };

  // ─── Render ────────────────────────────────────────────────────────────────
  const visibleHalls = selectedHallId === 'all' ? halls : halls.filter((hall) => hall.id === selectedHallId);
  const selectedHallName = halls.find((hall) => hall.id === selectedHallId)?.name;
  const visibleAlerts = selectedHallName ? alerts.filter((alert) => alert.hall_name === selectedHallName) : alerts;

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
            <div className="dashboard-user-area" ref={notifWrapRef}>
              <div className="dashboard-user-info">
                <span className="dashboard-user-name">{currentUser?.full_name || 'المستخدم'}</span>
                <span className="dashboard-user-role">{currentUser?.role || '—'}</span>
              </div>
              <div className="dashboard-avatar">
                <img
                  src="/profile.jpg"
                  alt="صورة الحساب"
                  className="dashboard-avatar-img"
                  onError={(e) => {
                    (e.currentTarget as HTMLImageElement).style.display = 'none';
                  }}
                />
              </div>
              <div className="dashboard-user-divider"></div>
              {/* Refresh streams */}
              <button className="dashboard-icon-btn" title="تحديث البث" onClick={refreshStreams}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 12a9 9 0 1 1-2.64-6.36"/>
                  <polyline points="21 3 21 9 15 9"/>
                </svg>
              </button>
              {/* Notification bell */}
              <button
                className="dashboard-icon-btn"
                title="الإشعارات"
                onClick={() => setNotificationsOpen((v) => !v)}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                  <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                </svg>
                {alerts.length > 0 && (
                  <span className="dashboard-notification-badge">{alerts.length}</span>
                )}
              </button>
              {notificationsOpen && (
                <div className="dashboard-notifications-dropdown" dir="rtl">
                  <div className="dashboard-notifications-header">
                    <span>أحدث الإشعارات</span>
                    <button
                      className="dashboard-notifications-viewall"
                      onClick={() => {
                        setActiveTab('cases');
                        setNotificationsOpen(false);
                      }}
                    >
                      عرض الكل
                    </button>
                  </div>
                  <div className="dashboard-notifications-list">
                    {(alerts.slice(0, 5) || []).map((a) => (
                      <button
                        key={a.id}
                        className="dashboard-notification-item"
                        onClick={() => {
                          openAlertModal(a);
                          setNotificationsOpen(false);
                        }}
                      >
                        <div className="dashboard-notification-title">{a.event_type}</div>
                        <div className="dashboard-notification-meta">
                          <span>{a.hall_name} — {a.camera_name}</span>
                          <span>•</span>
                          <span>{formatTime(a.timestamp)}</span>
                        </div>
                      </button>
                    ))}
                    {alerts.length === 0 && (
                      <div className="dashboard-notifications-empty">لا يوجد إشعارات</div>
                    )}
                  </div>
                </div>
              )}
              {/* Settings */}
              <button className="dashboard-icon-btn" title="الإعدادات" onClick={() => setActiveNav('settings')}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="3"/>
                  <path d="M12 1v2m0 18v2m-9-11h2m18 0h2m-2.636-7.364l-1.414 1.414M6.05 17.95l-1.414 1.414m0-14.728l1.414 1.414M17.95 17.95l1.414 1.414"/>
                </svg>
              </button>
              {onLogout && (
                <button className="dashboard-icon-btn" title="تسجيل الخروج" onClick={onLogout}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                    <polyline points="16 17 21 12 16 7"/>
                    <line x1="21" y1="12" x2="9" y2="12"/>
                  </svg>
                </button>
              )}
            </div>

            {/* Center: nav items */}
            <nav className="dashboard-nav">
              {NAV_ITEMS.map((item) => (
                <button
                  key={item.key}
                  className={`dashboard-nav-item ${activeNav === item.key ? 'active' : ''}`}
                  onClick={() => setActiveNav(item.key)}
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
          <h1 className="dashboard-page-title">
            {NAV_ITEMS.find(n => n.key === activeNav)?.label || 'الرئيسية'}
          </h1>

          {/* Sub-header: tabs + hall selector */}
          {activeNav === 'home' && (
            <div className="dashboard-subheader">
              {/* Right (in RTL): tab buttons */}
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

              {/* Left (in RTL): hall selector */}
              <label className="dashboard-hall-select">
                <select
                  value={selectedHallId}
                  onChange={(event) => setSelectedHallId(event.target.value)}
                  style={{ border: 0, background: 'transparent', color: 'inherit', font: 'inherit', outline: 'none' }}
                >
                  <option value="all">كل القاعات</option>
                  {halls.map((hall) => (
                    <option key={hall.id} value={hall.id}>{hall.name}</option>
                  ))}
                </select>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="6 9 12 15 18 9"/>
                </svg>
              </label>
            </div>
          )}
        </div>
      </header>

      {/* ══════════ MAIN CONTENT ══════════ */}
      <main className="dashboard-content">
        {activeNav === 'home' ? (
          activeTab === 'cases' ? (
            <CasesTab
              alerts={visibleAlerts}
              onViewAlert={openAlertModal}
            />
          ) : (
              <CamerasTab
                halls={visibleHalls}
                hallsLoaded={hallsLoaded}
                statsByCamera={statsByCamera}
                onClickCamera={openCameraModal}
                recentAlertByCameraId={recentAlertByCameraId}
                onViewAlert={openAlertModal}
              />
          )
        ) : activeNav === 'halls' ? (
          <HallsTab />
        ) : activeNav === 'exams' ? (
          <ExamsTab />
        ) : activeNav === 'supervisors' ? (
          <SupervisorsTab />
        ) : activeNav === 'settings' ? (
          <SettingsTab />
        ) : (
          <div className="dashboard-empty-state">
            <h3>قريباً</h3>
            <p>هذا القسم قيد التطوير وسيتم إضافته قريباً.</p>
          </div>
        )}
      </main>

      {/* ══════════ MODAL ══════════ */}
      {modalMode && (
        <CameraModal
          mode={modalMode}
          alert={selectedAlert}
          camera={selectedCamera}
          stats={selectedCamera ? statsByCamera[selectedCamera.id] ?? null : null}
          onConfirmAlert={confirmAlert}
          onCancelAlert={cancelAlert}
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
          <AlertCard
            key={alert.id}
            alert={alert}
            onViewAlert={onViewAlert}
          />
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
      </div>
    </div>
  );
}


// ── Cameras Tab ──────────────────────────────────────────────────────────────

function CamerasTab({
  halls,
  hallsLoaded,
  statsByCamera,
  onClickCamera,
  recentAlertByCameraId,
  onViewAlert,
}: {
  halls: HallItem[];
  hallsLoaded: boolean;
  statsByCamera: Record<string, CameraStats>;
  onClickCamera: (camera: CameraItem, hallName: string) => void;
  recentAlertByCameraId: Record<string, Alert | null>;
  onViewAlert: (alert: Alert) => void;
}) {
  if (!hallsLoaded) {
    return (
      <div className="dashboard-empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#9f9fa9" strokeWidth="1.5">
          <path d="M12 2v6m0 8v6m10-12h-6M2 12h6" />
        </svg>
        <h3>جارٍ تحميل القاعات...</h3>
        <p>الرجاء الانتظار</p>
      </div>
    );
  }

  if (halls.length === 0) {
    return (
      <div className="dashboard-empty-state">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#9f9fa9" strokeWidth="1.5">
          <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
          <circle cx="12" cy="13" r="4"/>
        </svg>
        <h3>لا توجد قاعات مضافة</h3>
        <p>الرجاء إضافة قاعات وكاميرات من قسم إدارة القاعات</p>
      </div>
    );
  }

  return (
    <div className="cameras-section">
      {halls.map((hall) => (
        <div key={hall.id} className="camera-hall-group">
          <div className="camera-hall-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <h2 className="hall-title">{hall.name}</h2>
              {hall.monitoring_status === 'active' ? (
                <span className="hall-monitoring-badge active">جاري المراقبة</span>
              ) : (
                <span className="hall-monitoring-badge inactive">في انتظار البدء</span>
              )}
            </div>
            <div style={{ marginRight: 'auto', marginLeft: 0 }}>
              <HallVoiceControl hallId={hall.id} hallName={hall.name} />
            </div>
          </div>
          {hall.cameras.length === 0 ? (
            <div className="dashboard-empty-state" style={{ minHeight: '200px', backgroundColor: 'rgba(255,255,255,0.5)', borderRadius: '14px' }}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#9f9fa9" strokeWidth="1.5">
                <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
                <circle cx="12" cy="13" r="4"/>
              </svg>
              <p>لا توجد كاميرات في هذه القاعة</p>
            </div>
          ) : (
            <div className="cameras-grid">
              {hall.cameras.map((camera) => {
              const stats = statsByCamera[camera.id];
              const recentAlert = recentAlertByCameraId[camera.id] ?? null;
              const hasActiveAlert = Boolean(recentAlert);
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
                  {/* REC badge removed */}
                  {/* Alert overlay removed (we show the alert bar instead) */}
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
                    {recentAlert ? (
                      <div className="camera-alert-bar">
                        <span className="camera-alert-type">{recentAlert.event_type}</span>
                        <button
                          className="camera-alert-view-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            onViewAlert(recentAlert);
                          }}
                        >
                          عرض الحالة
                        </button>
                      </div>
                    ) : streamRunning ? (
                      <>
                        <span>FPS: {stats?.fps || 0}</span>
                        <span>•</span>
                        <span>{stats?.latency_ms ? `${Math.round(stats.latency_ms)}ms` : '—'}</span>
                        <span>•</span>
                        <span>{stats?.resolution && stats.resolution !== 'N/A' ? stats.resolution : '—'}</span>
                        <span>•</span>
                        <span>{stats?.uptime_seconds != null && stats.uptime_seconds > 0 ? formatUptime(stats.uptime_seconds) : '—'}</span>
                      </>
                    ) : (
                      <span>—</span>
                    )}
                  </div>
                </div>
              );
              })}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
