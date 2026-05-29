import { useState, useEffect } from 'react';
import { authFetch } from '../config/api';
import { Clock, ShieldAlert, Users } from 'lucide-react';

interface ExamSession {
  id: string;
  exam_name: string;
  exam_type: string;
  scheduled_start: string;
  status: string;
  student_count: number;
}

interface ReportData {
  session_id: string;
  exam_name: string;
  exam_type: string;
  status: string;
  scheduled_start: string;
  actual_start: string | null;
  actual_end: string | null;
  student_count: number;
  kpis: {
    total_events: number;
    high_severity: number;
    medium_severity: number;
    low_severity: number;
    detected_alerts?: number;
    confirmed_incidents?: number;
    cancelled_incidents?: number;
  };
  halls: Array<{
    hall_id: string;
    hall_name: string;
    monitoring_started_at: string | null;
    monitoring_ended_at: string | null;
    duration_minutes: number | null;
    events_count: number;
  }>;
  timeline: Array<{
    id: string;
    alert_id?: string | null;
    event_type: string;
    severity: string;
    timestamp: string;
    confidence_score: number | null;
    student_position?: Record<string, unknown>;
    alert_status?: string;
    resolution_notes?: string | null;
    video_clip_path?: string | null;
    audio_clip_path?: string | null;
    snapshot_file?: string | null;
  }>;
}

export default function ReportsTab({ initialReport = null, onBack }: { initialReport?: ExamSession | null, onBack?: () => void }) {
  const [sessions, setSessions] = useState<ExamSession[]>([]);
  const [statsBySession, setStatsBySession] = useState<Record<string, { events: number; highSeverity: number }>>({});
  const [loading, setLoading] = useState(true);
  const [selectedReport, setSelectedReport] = useState<ExamSession | null>(initialReport);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [reportLoading, setReportLoading] = useState(false);

  useEffect(() => {
    const fetchReports = async () => {
      try {
        const res = await authFetch('/api/sessions/');
        if (res.ok) {
          const data = await res.json();
          setSessions(data || []);
        }
      } catch (err) {
        console.error('Failed to fetch sessions', err);
      } finally {
        setLoading(false);
      }
    };
    fetchReports();
  }, []);

  // Fetch detail report data when a session is selected
  useEffect(() => {
    if (!selectedReport) { setReportData(null); return; }
    setReportLoading(true);
    authFetch(`/api/sessions/${selectedReport.id}/report`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setReportData(data))
      .catch(() => setReportData(null))
      .finally(() => setReportLoading(false));
  }, [selectedReport]);

  // Lightweight summary stats for the list view (from /api/events/)
  useEffect(() => {
    if (sessions.length === 0) return;

    const fetchStats = async () => {
      const entries = await Promise.all(sessions.map(async (session) => {
        try {
          const res = await authFetch(`/api/events/?exam_session_id=${session.id}&limit=1000`);
          if (!res.ok) return [session.id, { events: 0, highSeverity: 0 }] as const;
          const events = await res.json() as { severity: string }[];
          return [session.id, {
            events: events.length,
            highSeverity: events.filter((event) => event.severity === 'high').length,
          }] as const;
        } catch {
          return [session.id, { events: 0, highSeverity: 0 }] as const;
        }
      }));

      setStatsBySession(Object.fromEntries(entries));
    };

    fetchStats();
  }, [sessions]);

  const calculateTimeAgo = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      const diffMs = new Date().getTime() - d.getTime();
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
      if (diffDays === 0) return 'اليوم';
      if (diffDays === 1) return 'منذ يوم';
      if (diffDays === 2) return 'منذ يومين';
      if (diffDays <= 7) return `منذ ${diffDays} أيام`;
      if (diffDays <= 14) return 'منذ أسبوع';
      if (diffDays <= 21) return 'منذ أسبوعين';
      return `منذ ${Math.floor(diffDays / 7)} أسابيع`;
    } catch {
      return 'غير معروف';
    }
  };

  const formatDateLong = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('ar-EG', { day: 'numeric', month: 'long', year: 'numeric' });
    } catch {
      return '12 مارس 2026';
    }
  };

  if (selectedReport) {
    const kpis = reportData?.kpis;
    const halls = reportData?.halls || [];
    const timeline = reportData?.timeline || [];

    return (
      <div className="reports-section p-8 w-full max-w-7xl mx-auto" dir="rtl">
        <button onClick={() => { if (onBack) onBack(); else setSelectedReport(null); }} className="mb-6 text-[#44006E] font-bold flex items-center gap-2 hover:underline cursor-pointer">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
          العودة للقائمة
        </button>

        <div className="bg-white rounded-[24px] border-2 border-gray-100 p-8 shadow-sm">
          {/* Header */}
          <div className="flex justify-between items-start w-full">
            <div className="flex gap-6">
              <div className="w-[126px] h-[120px] rounded-full bg-gradient-to-br from-indigo-50 to-purple-50 border-4 border-[#f3f3f3] shadow-inner flex items-center justify-center shrink-0">
                <svg width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="#44006E" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                  <line x1="8" y1="21" x2="16" y2="21"></line>
                  <line x1="12" y1="17" x2="12" y2="21"></line>
                </svg>
              </div>
              <div className="flex flex-col pt-2">
                <h3 className="text-[32px] font-bold text-gray-800 mb-2">{selectedReport.exam_name}</h3>
                <p className="text-[16px] text-gray-500 mb-4">{selectedReport.exam_type} — {selectedReport.status}</p>
                {/* KPI Badges */}
                <div className="flex gap-3 flex-wrap">
                  <div className="bg-[#f9f5ff] text-[#44006E] flex items-center gap-2 px-4 py-2 rounded-2xl">
                    <Users size={18} />
                    <span className="text-[16px] font-medium">{selectedReport.student_count} طالب</span>
                  </div>
                  {reportLoading ? (
                    <div className="animate-pulse bg-gray-100 rounded-2xl w-28 h-10" />
                  ) : (
                    <>
                      <div className="border border-[#44006E] text-[#44006E] flex items-center gap-2 px-4 py-2 rounded-2xl">
                        <Clock size={18} />
                        <span className="text-[16px] font-medium">{kpis?.total_events ?? 0} حالة</span>
                      </div>
                      <div className="border border-[#ff3636] text-[#ff3636] flex items-center gap-2 px-4 py-2 rounded-2xl">
                        <ShieldAlert size={18} />
                        <span className="text-[16px] font-medium">{kpis?.confirmed_incidents ?? 0} حالات مؤكدة</span>
                      </div>
                      <div className="border border-gray-300 text-gray-600 flex items-center gap-2 px-4 py-2 rounded-2xl">
                        <ShieldAlert size={18} />
                        <span className="text-[16px] font-medium">{kpis?.cancelled_incidents ?? 0} ملغاة</span>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
            <div className="flex flex-col items-end pt-2">
              <p className="text-[15px] text-gray-400 mb-2">{formatDateLong(selectedReport.scheduled_start)}</p>
              <a
                href={`/api/sessions/${selectedReport.id}/report`}
                target="_blank"
                rel="noreferrer"
                className="bg-[#44006E] text-white flex items-center gap-2 px-6 py-3 rounded-xl hover:bg-purple-900 transition-colors shadow-md"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
                <span className="text-[15px] font-medium">تنزيل التقرير</span>
              </a>
            </div>
          </div>

          <div className="w-full h-px bg-gray-200 my-8"></div>

          {/* Hall Summary Table */}
          {halls.length > 0 && (
            <div className="mb-8">
              <h4 className="text-lg font-bold text-gray-800 mb-4">ملخص القاعات</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="bg-gray-50 text-gray-500 font-bold">
                      <th className="text-right px-4 py-3 rounded-r-xl">القاعة</th>
                      <th className="text-right px-4 py-3">بدء المراقبة</th>
                      <th className="text-right px-4 py-3">نهاية المراقبة</th>
                      <th className="text-right px-4 py-3">المدة (دقيقة)</th>
                      <th className="text-right px-4 py-3 rounded-l-xl">الحالات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {halls.map((hall) => (
                      <tr key={hall.hall_id} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="px-4 py-3 font-bold text-gray-800">{hall.hall_name}</td>
                        <td className="px-4 py-3 text-gray-500">{hall.monitoring_started_at ? new Date(hall.monitoring_started_at).toLocaleTimeString('ar-EG') : '—'}</td>
                        <td className="px-4 py-3 text-gray-500">{hall.monitoring_ended_at ? new Date(hall.monitoring_ended_at).toLocaleTimeString('ar-EG') : 'جاري'}</td>
                        <td className="px-4 py-3 text-gray-700">{hall.duration_minutes ?? '—'}</td>
                        <td className="px-4 py-3"><span className="px-2 py-0.5 bg-purple-50 text-purple-700 rounded-lg font-bold">{hall.events_count}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Event Timeline */}
          {timeline.length > 0 && (
            <div>
              <h4 className="text-lg font-bold text-gray-800 mb-4">سجل التنبيهات والمراجعة</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="bg-gray-50 text-gray-500 font-bold">
                      <th className="text-right px-4 py-3 rounded-r-xl">الوقت</th>
                      <th className="text-right px-4 py-3">النوع</th>
                      <th className="text-right px-4 py-3">الطالب</th>
                      <th className="text-right px-4 py-3">الحالة</th>
                      <th className="text-right px-4 py-3">الدليل</th>
                      <th className="text-right px-4 py-3 rounded-l-xl">ملاحظات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {timeline.map((ev) => {
                      const trackId = ev.student_position?.track_id ?? '—';
                      return (
                        <tr key={ev.id} className="border-b border-gray-50 hover:bg-gray-50">
                          <td className="px-4 py-3 text-gray-500">{new Date(ev.timestamp).toLocaleTimeString('ar-EG')}</td>
                          <td className="px-4 py-3 font-bold text-gray-800">{ev.event_type}</td>
                          <td className="px-4 py-3 text-gray-700">{String(trackId)}</td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-0.5 rounded-lg font-bold ${
                              ev.alert_status === 'confirmed' ? 'bg-red-50 text-red-700' :
                              ev.alert_status === 'cancelled' ? 'bg-gray-100 text-gray-600' :
                              'bg-yellow-50 text-yellow-700'
                            }`}>
                              {ev.alert_status === 'confirmed' ? 'مؤكدة' : ev.alert_status === 'cancelled' ? 'ملغاة' : 'مكتشفة'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-gray-500">
                            {ev.video_clip_path ? 'مقطع فيديو' : ev.snapshot_file ? 'لقطة' : ev.audio_clip_path ? 'صوت' : '—'}
                          </td>
                          <td className="px-4 py-3 text-gray-500">{ev.resolution_notes || '—'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {!reportLoading && !kpis && (
            <div className="text-center py-12 text-gray-400">
              <p>لا توجد أحداث مسجلة لهذا الامتحان بعد.</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="reports-section p-8 w-full max-w-7xl mx-auto" dir="rtl">
      {/* Title */}
      <div className="flex justify-between items-center mb-12">
        <h2 className="text-[36px] font-bold text-[#44006E]">التقارير</h2>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-x-6 gap-y-12">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-white/50 animate-pulse h-[250px] rounded-[16px] border border-gray-100"></div>
          ))}
        </div>
      ) : sessions.length === 0 ? (
        <div className="flex flex-col items-center py-24 bg-white rounded-[24px] border border-gray-100 shadow-sm">
          <p className="text-gray-400 font-bold text-lg mb-3">لا توجد تقارير متاحة</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-x-6 gap-y-12 mt-8">
          {sessions.map((session) => {
            const stats = statsBySession[session.id] || { events: 0, highSeverity: 0 };
            const studentCount = session.student_count || 420;

            return (
              <div
                key={session.id}
                onClick={() => setSelectedReport(session)}
                className="group relative flex flex-col justify-end h-[250px] rounded-[16px] cursor-pointer transition-all duration-300 transform hover:-translate-y-1 bg-white hover:bg-[#44006E] border border-gray-100 hover:border-transparent shadow-sm hover:shadow-[0_12px_24px_rgba(68,0,110,0.25)]"
              >
                {/* Floating Icon overlapping top border */}
                <div className="absolute -top-[30px] left-1/2 -translate-x-1/2 w-[72px] h-[72px] rounded-full bg-gradient-to-br from-indigo-100 to-purple-100 border-[6px] border-[#f3f3f3] shadow-inner flex items-center justify-center overflow-hidden">
                   {/* Fallback SVG if image is not available */}
                   <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#44006E" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                     <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                     <line x1="8" y1="21" x2="16" y2="21"></line>
                     <line x1="12" y1="17" x2="12" y2="21"></line>
                   </svg>
                </div>

                <div className="px-6 pt-12 pb-6 flex flex-col items-center h-full">
                  {/* Title */}
                  <h3 className="text-[28px] font-bold text-center mb-6 leading-tight text-gray-800 group-hover:text-white transition-colors duration-300">
                    {session.exam_name}
                  </h3>

                  {/* Badges / Subtitles */}
                  <div className="flex flex-col gap-2 mb-6 w-full px-4">
                    <div className="flex items-center justify-end gap-2">
                      <span className="text-[16px] font-medium text-gray-400 group-hover:text-purple-200 transition-colors duration-300">
                        {stats.events} تنبيه
                      </span>
                      <ShieldAlert size={16} className="text-gray-400 group-hover:text-purple-200 transition-colors duration-300" />
                    </div>
                    <div className="flex items-center justify-end gap-2">
                      <span className="text-[16px] font-medium text-gray-400 group-hover:text-purple-200 transition-colors duration-300">
                        {calculateTimeAgo(session.scheduled_start)}
                      </span>
                      <Clock size={16} className="text-gray-400 group-hover:text-purple-200 transition-colors duration-300" />
                    </div>
                  </div>

                  {/* Divider */}
                  <div className="w-full h-px mb-5 bg-gray-100 group-hover:bg-white/10 transition-colors duration-300"></div>

                  {/* Footer Stats */}
                  <div className="flex justify-between items-center w-full px-2">
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-[16px] font-medium text-gray-500 group-hover:text-purple-200 transition-colors duration-300">
                        التنبيهات
                      </span>
                      <span className="text-[24px] font-bold text-gray-800 group-hover:text-white transition-colors duration-300">
                        {stats.highSeverity}
                      </span>
                    </div>
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-[16px] font-medium text-gray-500 group-hover:text-purple-200 transition-colors duration-300">
                        عدد الطلاب
                      </span>
                      <span className="text-[24px] font-bold text-gray-800 group-hover:text-white transition-colors duration-300">
                        {studentCount}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
