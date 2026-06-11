import { useState, useEffect, useRef } from 'react';
import { authFetch } from '../config/api';
import DashboardPage from './DashboardPage';

// ─── Types ───────────────────────────────────────────────────────────────────

interface OverviewSummary {
  is_multi_college: boolean;
  running_exams: number;
  active_alerts: number;
  active_colleges: number;
  institution_type: string;
}

interface CollegeCard {
  id: string;
  name: string;
  type: string;
  logo_url: string | null;
  running_exams: number;
  active_alerts: number;
  halls_ready: number;
  invigilators_online: number;
}

interface OverviewExam {
  id: string;
  exam_name: string;
  exam_type: string | null;
  status: string;
  scheduled_start: string | null;
  scheduled_end: string | null;
  student_count: number | null;
  hall_count: number;
  active_alerts: number;
  institution_id: string | null;
  college_name: string;
}

interface OverviewAlert {
  id: string;
  alert_type: string;
  status: string;
  exam_session_id: string;
  exam_name: string;
  institution_id: string | null;
  college_name: string;
  created_at: string | null;
  claimed_by: string | null;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatTime(iso: string | null): string {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' }); }
  catch { return '—'; }
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('ar-EG', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch { return '—'; }
}

// ─── KPI Card ─────────────────────────────────────────────────────────────────

function KpiCard({ label, value, accent }: { label: string; value: number; accent?: string }) {
  return (
    <div className="bg-white rounded-2xl px-6 py-4 flex flex-col gap-1 shadow-sm border border-gray-100">
      <span className="text-3xl font-bold" style={{ color: accent ?? '#8e52cb' }}>{value}</span>
      <span className="text-sm text-gray-500">{label}</span>
    </div>
  );
}

// ─── College Card ─────────────────────────────────────────────────────────────

function CollegeCardView({
  college,
  selected,
  onClick,
}: {
  college: CollegeCard;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={[
        'text-right rounded-2xl border-2 p-5 transition-all shadow-sm hover:shadow-md',
        selected ? 'border-[#8e52cb] bg-[#f5eeff]' : 'border-gray-100 bg-white hover:border-[#c496ff]',
      ].join(' ')}
    >
      <div className="flex items-center gap-3 mb-3">
        {college.logo_url ? (
          <img src={college.logo_url} alt="" className="w-9 h-9 rounded-lg object-contain bg-gray-50" />
        ) : (
          <div className="w-9 h-9 rounded-lg bg-[#f5eeff] flex items-center justify-center text-[#8e52cb] font-bold text-lg">
            {college.name.charAt(0)}
          </div>
        )}
        <span className="font-semibold text-[#333] text-[15px] leading-tight">{college.name}</span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Stat label="امتحانات نشطة" value={college.running_exams} accent={college.running_exams > 0 ? '#8e52cb' : undefined} />
        <Stat label="تنبيهات" value={college.active_alerts} accent={college.active_alerts > 0 ? '#ef4444' : undefined} />
        <Stat label="قاعات جاهزة" value={college.halls_ready} />
        <Stat label="مراقبون متصلون" value={college.invigilators_online} accent={college.invigilators_online > 0 ? '#10b981' : undefined} />
      </div>
    </button>
  );
}

function Stat({ label, value, accent }: { label: string; value: number; accent?: string }) {
  return (
    <div className="bg-gray-50 rounded-lg px-3 py-2">
      <div className="font-bold text-lg leading-none" style={{ color: accent ?? '#6b7280' }}>{value}</div>
      <div className="text-xs text-gray-400 mt-0.5">{label}</div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function UniversityDashboardPage({ onLogout }: { onLogout?: () => void }) {
  const [summary, setSummary] = useState<OverviewSummary | null>(null);
  const [colleges, setColleges] = useState<CollegeCard[]>([]);
  const [exams, setExams] = useState<OverviewExam[]>([]);
  const [alerts, setAlerts] = useState<OverviewAlert[]>([]);
  const [selectedCollegeId, setSelectedCollegeId] = useState<string | null>(null);
  const [activeNav, setActiveNav] = useState<'overview' | 'college'>('overview');
  const [loading, setLoading] = useState(true);
  const [alertFilter, setAlertFilter] = useState<string>('all');
  const pollRef = useRef<number | null>(null);

  const loadData = async () => {
    try {
      const [sumRes, colRes, examRes, alertRes] = await Promise.all([
        authFetch('/api/overview/summary'),
        authFetch('/api/overview/colleges'),
        authFetch('/api/overview/exams?status=active'),
        authFetch('/api/overview/alerts'),
      ]);
      if (sumRes.ok) setSummary(await sumRes.json());
      if (colRes.ok) setColleges((await colRes.json()).colleges ?? []);
      if (examRes.ok) setExams((await examRes.json()).exams ?? []);
      if (alertRes.ok) setAlerts((await alertRes.json()).alerts ?? []);
    } catch { /* ignore polling errors */ }
    finally { setLoading(false); }
  };

  useEffect(() => {
    loadData();
    pollRef.current = window.setInterval(loadData, 8000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  // When a college card is clicked → drill-down to DashboardPage scoped to that college
  if (activeNav === 'college' && selectedCollegeId) {
    const college = colleges.find(c => c.id === selectedCollegeId);
    return (
      <div>
        {/* back bar */}
        <div
          className="flex items-center gap-3 px-6 py-3 bg-white border-b border-gray-100 cursor-pointer"
          dir="rtl"
          onClick={() => { setActiveNav('overview'); setSelectedCollegeId(null); }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#8e52cb" strokeWidth="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
          <span className="text-sm font-medium text-[#8e52cb]">العودة إلى لوحة الجامعة</span>
          {college && <span className="text-sm text-gray-500">← {college.name}</span>}
        </div>
        <DashboardPage onLogout={onLogout} />
      </div>
    );
  }

  // ── Overview panel ───────────────────────────────────────────────────────
  const visibleAlerts = alertFilter === 'all'
    ? alerts
    : alerts.filter(a => a.institution_id === alertFilter);

  return (
    <div className="min-h-screen bg-[#fafafb]" dir="rtl">
      {/* ══════ HEADER ══════ */}
      <header className="dashboard-header">
        <div className="dashboard-header-bg">
          <img src="/Frame 1000003437.png" alt="" className="dashboard-header-bg-img" />
          <div className="dashboard-header-bg-overlay" />
        </div>
        <div className="dashboard-header-content">
          <div className="dashboard-navbar">
            {/* left: logout */}
            <div className="dashboard-user-area">
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
            {/* center: title */}
            <div className="dashboard-nav">
              <span className="text-white font-semibold text-lg">لوحة الجامعة</span>
            </div>
            {/* right: logo */}
            <div className="dashboard-logo">
              <img src="/Frame 76.svg" alt="Thaqib" className="dashboard-logo-img" />
            </div>
          </div>

          <h1 className="dashboard-page-title">نظرة عامة</h1>

          {/* KPI strip */}
          {summary && (
            <div className="flex gap-4 px-6 pb-5 flex-wrap" dir="rtl">
              <KpiCard label="امتحانات جارية" value={summary.running_exams} accent="#8e52cb" />
              <KpiCard label="تنبيهات نشطة" value={summary.active_alerts} accent={summary.active_alerts > 0 ? '#ef4444' : '#8e52cb'} />
              <KpiCard label="كليات نشطة" value={summary.active_colleges} accent="#10b981" />
            </div>
          )}
        </div>
      </header>

      {/* ══════ CONTENT ══════ */}
      <main className="dashboard-content">
        {loading ? (
          <div className="dashboard-empty-state">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#9f9fa9" strokeWidth="1.5">
              <path d="M12 2v6m0 8v6m10-12h-6M2 12h6" />
            </svg>
            <h3>جارٍ التحميل...</h3>
          </div>
        ) : (
          <div className="flex flex-col gap-8 p-6">
            {/* Colleges grid */}
            <section>
              <h2 className="text-lg font-bold text-[#333] mb-4">الكليات</h2>
              {colleges.length === 0 ? (
                <div className="bg-white rounded-2xl border border-dashed border-gray-200 p-8 text-center text-gray-400">
                  لا توجد كليات مضافة — أضف كليات من الإعدادات
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {colleges.map(c => (
                    <CollegeCardView
                      key={c.id}
                      college={c}
                      selected={selectedCollegeId === c.id}
                      onClick={() => {
                        setSelectedCollegeId(c.id);
                        setActiveNav('college');
                      }}
                    />
                  ))}
                </div>
              )}
            </section>

            {/* Active exams */}
            <section>
              <h2 className="text-lg font-bold text-[#333] mb-4">الامتحانات الجارية</h2>
              {exams.length === 0 ? (
                <div className="bg-white rounded-2xl border border-gray-100 p-6 text-center text-gray-400">
                  لا توجد امتحانات جارية حالياً
                </div>
              ) : (
                <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden shadow-sm">
                  <table className="w-full text-sm text-right">
                    <thead className="bg-gray-50 text-gray-500">
                      <tr>
                        <th className="px-4 py-3 font-medium">الامتحان</th>
                        <th className="px-4 py-3 font-medium">الكلية</th>
                        <th className="px-4 py-3 font-medium">البداية</th>
                        <th className="px-4 py-3 font-medium">القاعات</th>
                        <th className="px-4 py-3 font-medium">تنبيهات</th>
                        <th className="px-4 py-3 font-medium"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {exams.map(e => (
                        <tr key={e.id} className="hover:bg-gray-50 transition-colors">
                          <td className="px-4 py-3 font-medium text-[#333]">{e.exam_name}</td>
                          <td className="px-4 py-3 text-gray-600">{e.college_name}</td>
                          <td className="px-4 py-3 text-gray-500">{formatDateTime(e.scheduled_start)}</td>
                          <td className="px-4 py-3 text-gray-600">{e.hall_count}</td>
                          <td className="px-4 py-3">
                            {e.active_alerts > 0 ? (
                              <span className="inline-flex items-center gap-1 text-red-600 font-semibold">
                                <span className="w-2 h-2 rounded-full bg-red-500 inline-block" />
                                {e.active_alerts}
                              </span>
                            ) : (
                              <span className="text-green-600">—</span>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            {e.institution_id && (
                              <button
                                onClick={() => {
                                  setSelectedCollegeId(e.institution_id!);
                                  setActiveNav('college');
                                }}
                                className="text-[#8e52cb] text-xs hover:underline font-medium"
                              >
                                عرض
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* Live alerts */}
            <section>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold text-[#333]">التنبيهات النشطة</h2>
                {/* college filter chips */}
                <div className="flex gap-2 flex-wrap">
                  <button
                    onClick={() => setAlertFilter('all')}
                    className={`text-xs rounded-full px-3 py-1 font-medium transition-colors ${alertFilter === 'all' ? 'bg-[#8e52cb] text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
                  >
                    الكل
                  </button>
                  {colleges.map(c => (
                    <button
                      key={c.id}
                      onClick={() => setAlertFilter(alertFilter === c.id ? 'all' : c.id)}
                      className={`text-xs rounded-full px-3 py-1 font-medium transition-colors ${alertFilter === c.id ? 'bg-[#8e52cb] text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
                    >
                      {c.name}
                    </button>
                  ))}
                </div>
              </div>

              {visibleAlerts.length === 0 ? (
                <div className="bg-white rounded-2xl border border-gray-100 p-6 text-center text-gray-400">
                  لا توجد تنبيهات نشطة
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                  {visibleAlerts.map(a => (
                    <AlertRow key={a.id} alert={a} onDrillDown={(id) => { setSelectedCollegeId(id); setActiveNav('college'); }} />
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

// ─── Alert Row Card ───────────────────────────────────────────────────────────

function AlertRow({ alert, onDrillDown }: { alert: OverviewAlert; onDrillDown: (collegeId: string) => void }) {
  return (
    <div className="bg-white rounded-2xl border border-red-100 p-4 flex flex-col gap-2 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold text-red-600 uppercase tracking-wide">{alert.alert_type}</span>
        <span className="text-xs text-gray-400">{formatTime(alert.created_at)}</span>
      </div>
      <div className="text-sm font-medium text-[#333]">{alert.exam_name}</div>
      <div className="text-xs text-gray-500">{alert.college_name}</div>
      {alert.institution_id && (
        <button
          onClick={() => onDrillDown(alert.institution_id!)}
          className="mt-1 text-xs text-[#8e52cb] hover:underline self-start font-medium"
        >
          عرض الكلية ←
        </button>
      )}
    </div>
  );
}
