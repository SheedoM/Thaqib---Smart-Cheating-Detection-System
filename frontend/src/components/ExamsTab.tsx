import { useState, useEffect } from 'react';

import { authFetch } from '../config/api';
import ReportsTab from './ReportsTab';

interface ExamItem {
  id: string;
  exam_name: string;
  exam_type: string;
  scheduled_start: string;
  scheduled_end: string;
  status: string;
  student_count: number;
  halls?: { id: string, name: string }[];
  assignments?: AssignmentSimple[];
  period?: string;
  configuration?: { period?: string };
}

interface HallSimple { id: string; name: string; }
interface UserSimple { id: string; full_name: string; image?: string | null; }
interface AssignmentSimple {
  id: string;
  invigilator_id: string;
  hall_id: string;
  role: 'primary' | 'secondary';
}

interface DeviceReadiness {
  id: string;
  type: 'camera' | 'microphone' | string;
  identifier: string;
  name: string;
  status: 'passed' | 'failed';
  message: string;
}

interface HallReadiness {
  hall_id: string;
  hall_name: string;
  overall_status: 'passed' | 'warning';
  failed_count: number;
  devices: DeviceReadiness[];
}

// ─── Main Tab ────────────────────────────────────────────────────────────────

export default function ExamsTab() {
  const [exams, setExams] = useState<ExamItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingExam, setEditingExam] = useState<ExamItem | null>(null);
  const [deletingExam, setDeletingExam] = useState<ExamItem | null>(null);
  const [viewingReport, setViewingReport] = useState<ExamItem | null>(null);
  const [startingExam, setStartingExam] = useState<ExamItem | null>(null);
  const [users, setUsers] = useState<UserSimple[]>([]);
  const [search, setSearch] = useState('');
  
  // Advanced filters state
  const [halls, setHalls] = useState<HallSimple[]>([]);
  const [hallFilter, setHallFilter] = useState('');
  const [dateFilter, setDateFilter] = useState('');
  const [timeFilter, setTimeFilter] = useState('');
  const [activeStatus, setActiveStatus] = useState<'upcoming' | 'past' | 'all'>('all');

  const fetchExams = async () => {
    try {
      const res = await authFetch('/api/sessions/');
      if (res.ok) {
        const data = await res.json();
        setExams((data || []).map((ex: any) => ({
          ...ex,
          period: ex.configuration?.period || 'الفترة الأولي'
        })));
      }
    } catch (err) {
      console.error('Failed to fetch exams', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      const res = await authFetch(`/api/sessions/${id}`, { method: 'DELETE' });
      if (res.ok) { setDeletingExam(null); fetchExams(); }
    } catch (err) { console.error('Delete failed', err); }
  };

  const fetchUsers = async () => {
    try {
      const res = await authFetch('/api/users/');
      if (res.ok) setUsers(await res.json());
    } catch (err) {
      console.error('Failed to fetch users', err);
    }
  };

  const userById = users.reduce<Record<string, UserSimple>>((acc, user) => {
    acc[user.id] = user;
    return acc;
  }, {});

  const fetchHallsList = async () => {
    try {
      const res = await authFetch('/api/halls/');
      if (res.ok) setHalls(await res.json());
    } catch (err) { console.error('Failed to fetch halls list', err); }
  };

  useEffect(() => {
    fetchExams();
    fetchUsers();
    fetchHallsList();
    // Poll every 10 s so running-state cards update automatically.
    const interval = setInterval(fetchExams, 10_000);
    return () => clearInterval(interval);
  }, []);
  
  if (viewingReport) {
    return <ReportsTab initialReport={viewingReport as any} onBack={() => setViewingReport(null)} />;
  }

  return (
    <div className="p-8" dir="rtl">
      <div className="flex justify-between items-center mb-10">
        <div className="flex items-center gap-4">
          <div className="w-1.5 h-10 bg-[#44006E] rounded-full"></div>
          <h2 className="text-3xl font-black text-[#2D005F]">إدارة الإمتحانات</h2>
        </div>
        <div className="flex gap-3 items-center">
          <div className="relative">
            <svg className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" placeholder="بحث باسم المادة..." value={search} onChange={e => setSearch(e.target.value)}
              className="bg-white border border-gray-200 rounded-2xl py-2.5 pr-9 pl-4 outline-none focus:ring-2 focus:ring-purple-200 text-sm font-bold w-64 shadow-sm" />
          </div>
          <button
            onClick={() => { setEditingExam(null); setIsModalOpen(true); }}
            className="bg-[#44006e] text-white font-black flex items-center justify-center gap-2 shadow-lg hover:shadow-xl transition-all hover:-translate-y-0.5 active:scale-95 cursor-pointer"
            style={{ width: '200px', height: '50px', borderRadius: '18px' }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
            <span className="text-[17px]">إضافة إمتحان</span>
          </button>
        </div>
      </div>
      
      {/* ── Tabs & Filters ── */}
      <div className="mb-8 space-y-6">
        {/* Status Tabs */}
        <div className="flex bg-gray-100/50 p-1.5 rounded-2xl w-fit">
          {[
            { id: 'all', label: 'الكل' },
            { id: 'upcoming', label: 'القادمة' },
            { id: 'past', label: 'السابقة' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveStatus(tab.id as any)}
              className={`px-8 py-2.5 rounded-xl font-black text-sm transition-all cursor-pointer ${activeStatus === tab.id ? 'bg-white text-[#44006E] shadow-sm' : 'text-gray-400 hover:text-gray-600'}`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Advanced Filter Bar */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Hall Filter */}
          <div className="relative group">
             <label className="absolute -top-2 right-4 bg-gray-50 px-2 text-[10px] font-black text-gray-400 z-10">فلترة بالقاعة</label>
             <select 
               value={hallFilter} 
               onChange={e => setHallFilter(e.target.value)}
               className="w-full bg-white border border-gray-100 rounded-2xl py-3 px-4 outline-none focus:ring-2 focus:ring-purple-200 font-bold text-sm appearance-none shadow-sm cursor-pointer"
             >
               <option value="">جميع القاعات</option>
               {halls.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
             </select>
          </div>

          {/* Date Filter */}
          <div className="relative group">
             <label className="absolute -top-2 right-4 bg-gray-50 px-2 text-[10px] font-black text-gray-400 z-10">فلترة بالتاريخ</label>
             <input 
               type="date"
               value={dateFilter}
               onChange={e => setDateFilter(e.target.value)}
               className="w-full bg-white border border-gray-100 rounded-2xl py-3 px-4 outline-none focus:ring-2 focus:ring-purple-200 font-bold text-sm shadow-sm cursor-pointer"
             />
             {dateFilter && <button onClick={() => setDateFilter('')} className="absolute left-10 top-1/2 -translate-y-1/2 text-gray-400 hover:text-red-500">✕</button>}
          </div>

          {/* Time Filter */}
          <div className="relative group">
             <label className="absolute -top-2 right-4 bg-gray-50 px-2 text-[10px] font-black text-gray-400 z-10">فلترة بالوقت</label>
             <select 
               value={timeFilter} 
               onChange={e => setTimeFilter(e.target.value)}
               className="w-full bg-white border border-gray-100 rounded-2xl py-3 px-4 outline-none focus:ring-2 focus:ring-purple-200 font-bold text-sm appearance-none shadow-sm cursor-pointer"
             >
               <option value="">جميع الفترات</option>
               <option value="الفترة الأولي">الفترة الأولى</option>
               <option value="الفترة الثانية">الفترة الثانية</option>
               <option value="الفترة الثالثة">الفترة الثالثة</option>
             </select>
          </div>
        </div>
      </div>
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {[1,2,3,4].map(i => <div key={i} className="bg-white rounded-3xl h-[240px] animate-pulse border border-gray-100"></div>)}
        </div>
      ) : exams.length === 0 ? (
        <div className="flex flex-col items-center py-28 bg-white rounded-[40px] border-2 border-dashed border-gray-100">
          <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mb-4">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
          </div>
          <p className="text-gray-400 font-black text-lg mb-4">لا توجد إمتحانات مسجلة</p>
          <button onClick={() => setIsModalOpen(true)} className="text-[#44006E] font-bold text-sm hover:underline cursor-pointer">+ أضف أول إمتحان</button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {exams.filter(ex => {
            const matchesSearch = ex.exam_name.toLowerCase().includes(search.toLowerCase());
            const matchesHall = hallFilter ? ex.halls?.some(h => h.id === hallFilter) : true;
            const matchesDate = dateFilter ? ex.scheduled_start.startsWith(dateFilter) : true;
            const matchesTime = timeFilter ? (ex.period === timeFilter || ex.configuration?.period === timeFilter) : true;
            
            const now = new Date();
            const examDate = new Date(ex.scheduled_start);
            const isPast = examDate < now;
            const matchesStatus = activeStatus === 'all' ? true : (activeStatus === 'past' ? isPast : !isPast);
            
            return matchesSearch && matchesHall && matchesDate && matchesTime && matchesStatus;
          }).map(exam => (
            <ExamCard
              key={exam.id}
              exam={exam}
              userById={userById}
              onEdit={() => { setEditingExam(exam); setIsModalOpen(true); }}
              onDelete={() => setDeletingExam(exam)}
              onViewReport={() => setViewingReport(exam)}
              onStart={() => setStartingExam(exam)}
              onStop={async (hallId) => {
                await authFetch(`/api/sessions/${exam.id}/halls/${hallId}/monitoring/stop`, { method: 'POST' });
                fetchExams();
              }}
            />
          ))}
        </div>
      )}

      {isModalOpen && (
        <ExamModal
          exam={editingExam}
          onClose={() => setIsModalOpen(false)}
          onSuccess={() => { setIsModalOpen(false); fetchExams(); }}
        />
      )}

      {deletingExam && (
        <DeleteConfirmModal
          examName={deletingExam.exam_name}
          onCancel={() => setDeletingExam(null)}
          onConfirm={() => handleDelete(deletingExam.id)}
        />
      )}

      {startingExam && (
        <StartExamModal
          exam={startingExam}
          userById={userById}
          onClose={() => setStartingExam(null)}
          onStarted={() => {
            setStartingExam(null);
            fetchExams();
          }}
        />
      )}
    </div>
  );
}

// ─── Exam Card ───────────────────────────────────────────────────────────────

function ExamCard({
  exam,
  userById,
  onEdit,
  onDelete,
  onViewReport,
  onStart,
  onStop,
}: {
  exam: ExamItem,
  userById: Record<string, UserSimple>,
  onEdit: () => void,
  onDelete: () => void,
  onViewReport: () => void,
  onStart: () => void,
  onStop: (hallId: string) => Promise<void>,
}) {
  const [stoppingHallId, setStoppingHallId] = useState<string | null>(null);

  // Derive running state: is any hall currently being monitored?
  const activeAssignments = (exam.assignments || []).filter(
    (a: any) => a.monitoring_started_at && !a.monitoring_ended_at
  );
  const isRunning = exam.status === 'active' || activeAssignments.length > 0;
  const isCompleted = exam.status === 'completed';

  const handleStop = async (hallId: string) => {
    if (!window.confirm('هل تريد إيقاف مراقبة هذه القاعة؟')) return;
    setStoppingHallId(hallId);
    try { await onStop(hallId); } finally { setStoppingHallId(null); }
  };
  const badgeStyle: Record<string, string> = {
    midterm: 'bg-[#F2EEFF] text-[#6C5CE7]',
    practical: 'bg-[#E1F7FF] text-[#0984E3]',
    final: 'bg-[#FFF0E1] text-[#E67E22]',
  };
  const typeLabel: Record<string, string> = { midterm: 'ميدترم', practical: 'عملي', final: 'فاينال' };

  const formatDate = (iso: string) => {
    try { return new Date(iso).toLocaleDateString('ar-EG', { day: 'numeric', month: 'short', year: 'numeric' }); }
    catch { return iso; }
  };
  const invigilatorNames = Array.from(new Set(
    (exam.assignments || [])
      .map((assignment) => userById[assignment.invigilator_id]?.full_name)
      .filter(Boolean)
  ));

  return (
    <div className="bg-white rounded-3xl p-6 border border-gray-100 shadow-sm hover:shadow-xl transition-all duration-300 group flex flex-col">
      <div className="flex justify-between items-start mb-4">
        <span className={`px-4 py-1 rounded-full text-xs font-black ${badgeStyle[exam.exam_type] || 'bg-gray-100 text-gray-500'}`}>
          {typeLabel[exam.exam_type] || exam.exam_type}
        </span>
        <span className="text-xs text-gray-400 font-bold">{formatDate(exam.scheduled_start)}</span>
      </div>

      <div className="flex-1">
        <h3 className="text-xl font-black text-[#2D005F] mb-1 group-hover:text-[#44006E] transition-colors line-clamp-2">{exam.exam_name}</h3>
        <div className="flex flex-wrap gap-1 mb-3">
          {exam.halls && exam.halls.length > 0
            ? exam.halls.map(h => <span key={h.id} className="text-[11px] font-bold text-gray-400 bg-gray-50 px-2 py-0.5 rounded-lg">{h.name}</span>)
            : <span className="text-[11px] text-gray-300">لا توجد قاعات</span>}
        </div>
        <div className="flex justify-between text-xs font-bold text-gray-400 mt-2">
          <span>{exam.period || 'الفترة الأولي'}</span>
          <span className="text-[#44006E]">{exam.student_count} طالب</span>
        </div>
        <div className="mt-3 text-[11px] font-bold text-gray-400 leading-5">
          <span className="text-gray-500">المراقبين: </span>
          {invigilatorNames.length > 0 ? invigilatorNames.join('، ') : 'لم يتم تعيين مراقبين'}
        </div>

        {/* Status chip */}
        <div className="mt-3">
          {isRunning ? (
            <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-[11px] font-black bg-green-100 text-green-700">
              <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse inline-block"></span>
              جاري الآن
            </span>
          ) : isCompleted ? (
            <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-[11px] font-black bg-gray-100 text-gray-400">منتهي</span>
          ) : (
            <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-[11px] font-black bg-blue-50 text-blue-500">مجدول</span>
          )}
        </div>

        {/* Per-hall stop controls when running */}
        {isRunning && exam.halls && exam.halls.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {exam.halls.map((hall) => {
              const hallActive = (exam.assignments || []).some(
                (a: any) => a.hall_id === hall.id && a.monitoring_started_at && !a.monitoring_ended_at
              );
              return hallActive ? (
                <div key={hall.id} className="flex items-center justify-between bg-red-50 border border-red-100 rounded-xl px-3 py-2">
                  <span className="text-[11px] font-black text-red-700">{hall.name}</span>
                  <button
                    onClick={() => handleStop(hall.id)}
                    disabled={stoppingHallId === hall.id}
                    className="text-[10px] font-black text-red-500 hover:text-red-700 underline disabled:opacity-50"
                  >
                    {stoppingHallId === hall.id ? 'جاري الإيقاف...' : 'إيقاف'}
                  </button>
                </div>
              ) : null;
            })}
          </div>
        )}
      </div>

      <div className="pt-4 mt-4 border-t border-gray-50 flex justify-between items-center">
        <div className="flex flex-wrap gap-4">
          <button onClick={onEdit} className="text-[#44006E] font-black text-xs hover:underline cursor-pointer flex items-center gap-1">
            تعديل <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="15 18 9 12 15 6"></polyline></svg>
          </button>
          <button onClick={onStart} className="text-[#0984E3] font-black text-xs hover:underline cursor-pointer flex items-center gap-1">
            بدء الامتحان <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
          </button>
          <button onClick={onViewReport} className="text-[#00D261] font-black text-xs hover:underline cursor-pointer flex items-center gap-1">
            التقرير <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
          </button>
        </div>
        <button onClick={onDelete} className="w-8 h-8 flex items-center justify-center text-red-200 hover:text-red-500 hover:bg-red-50 rounded-xl transition-all cursor-pointer">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
        </button>
      </div>
    </div>
  );
}

function StartExamModal({
  exam,
  userById,
  onClose,
  onStarted,
}: {
  exam: ExamItem;
  userById: Record<string, UserSimple>;
  onClose: () => void;
  onStarted: () => void;
}) {
  const [readinessByHall, setReadinessByHall] = useState<Record<string, HallReadiness>>({});
  const [loadingHallId, setLoadingHallId] = useState<string | null>(null);
  const [startingHallId, setStartingHallId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const halls = exam.halls || [];

  const loadReadiness = async (hallId: string) => {
    setLoadingHallId(hallId);
    setError(null);
    try {
      const res = await authFetch(`/api/sessions/${exam.id}/halls/${hallId}/readiness`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `خطأ ${res.status}` }));
        throw new Error(typeof err.detail === 'string' ? err.detail : 'فشل فحص الأجهزة');
      }
      const data = await res.json();
      setReadinessByHall((prev) => ({ ...prev, [hallId]: data }));
    } catch (err: any) {
      setError(err.message || 'تعذر فحص أجهزة القاعة');
    } finally {
      setLoadingHallId(null);
    }
  };

  useEffect(() => {
    halls.forEach((hall) => { void loadReadiness(hall.id); });
  }, [exam.id]);

  const startHall = async (hallId: string) => {
    const readiness = readinessByHall[hallId];
    if (readiness?.overall_status === 'warning') {
      const ok = window.confirm('توجد تحذيرات في فحص الأجهزة. هل تريد بدء المراقبة رغم ذلك؟');
      if (!ok) return;
    }

    setStartingHallId(hallId);
    setError(null);
    try {
      const res = await authFetch(`/api/sessions/${exam.id}/halls/${hallId}/monitoring/start`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `خطأ ${res.status}` }));
        throw new Error(typeof err.detail === 'string' ? err.detail : 'فشل بدء المراقبة');
      }
      onStarted();
    } catch (err: any) {
      setError(err.message || 'تعذر بدء المراقبة');
    } finally {
      setStartingHallId(null);
    }
  };

  return (
    <div className="fixed inset-0 z-[120] bg-black/40 backdrop-blur-sm flex items-center justify-center p-4" dir="rtl" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-white rounded-[28px] shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto">
        <div className="px-7 py-5 border-b border-gray-100 flex justify-between items-center sticky top-0 bg-white z-10 rounded-t-[28px]">
          <div>
            <h3 className="text-xl font-black text-[#2D005F]">بدء الامتحان من لوحة الإدارة</h3>
            <p className="text-xs text-gray-400 font-bold mt-1">{exam.exam_name}</p>
          </div>
          <button onClick={onClose} className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        <div className="p-7 space-y-4">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-600 rounded-2xl px-4 py-3 text-sm font-bold">
              {error}
            </div>
          )}

          {halls.length === 0 ? (
            <div className="text-center py-14 text-gray-400 font-bold border-2 border-dashed border-gray-100 rounded-3xl">
              لا توجد قاعات مرتبطة بهذا الامتحان.
            </div>
          ) : halls.map((hall) => {
            const readiness = readinessByHall[hall.id];
            const assignedNames = Array.from(new Set(
              (exam.assignments || [])
                .filter((assignment) => assignment.hall_id === hall.id)
                .map((assignment) => userById[assignment.invigilator_id]?.full_name)
                .filter(Boolean)
            ));

            return (
              <section key={hall.id} className="border border-gray-100 rounded-3xl p-5 bg-[#FCFBFF]">
                <div className="flex justify-between gap-4 items-start mb-4">
                  <div>
                    <h4 className="text-lg font-black text-[#2D005F]">{hall.name}</h4>
                    <p className="text-xs text-gray-400 font-bold mt-1">
                      المراقبين: {assignedNames.length ? assignedNames.join('، ') : 'لم يتم تعيين مراقبين'}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => loadReadiness(hall.id)}
                      disabled={loadingHallId === hall.id}
                      className="px-4 py-2 rounded-xl bg-white border border-gray-200 text-gray-500 text-xs font-black hover:bg-gray-50 disabled:opacity-60"
                    >
                      {loadingHallId === hall.id ? 'جاري الفحص...' : 'إعادة الفحص'}
                    </button>
                    <button
                      type="button"
                      onClick={() => startHall(hall.id)}
                      disabled={startingHallId === hall.id}
                      className="px-5 py-2 rounded-xl bg-[#44006E] text-white text-xs font-black shadow-md hover:bg-[#340055] disabled:opacity-60"
                    >
                      {startingHallId === hall.id ? 'جاري البدء...' : 'بدء القاعة'}
                    </button>
                  </div>
                </div>

                <div className={`mb-4 px-3 py-2 rounded-xl text-xs font-black ${readiness?.overall_status === 'passed' ? 'bg-green-50 text-green-600' : 'bg-yellow-50 text-yellow-700'}`}>
                  {readiness
                    ? readiness.overall_status === 'passed'
                      ? 'كل الأجهزة اجتازت الفحص'
                      : `${readiness.failed_count} أجهزة تحتاج للمراجعة، ويمكن البدء عند الضرورة`
                    : 'لم يتم الفحص بعد'}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {(readiness?.devices || []).map((device) => (
                    <div key={device.id} className="bg-white border border-gray-100 rounded-2xl px-3 py-3 flex items-start gap-3">
                      <span className={`mt-1 w-2.5 h-2.5 rounded-full shrink-0 ${device.status === 'passed' ? 'bg-green-500' : 'bg-yellow-500'}`}></span>
                      <div className="min-w-0">
                        <p className="text-xs font-black text-gray-700">{device.name}</p>
                        <p className="text-[11px] text-gray-400 font-bold">{device.type === 'camera' ? 'كاميرا' : 'مايكروفون'} - {device.message}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ─── Exam Modal ──────────────────────────────────────────────────────────────

function ExamModal({ exam, onClose, onSuccess }: { exam: ExamItem | null, onClose: () => void, onSuccess: () => void }) {
  const [formData, setFormData] = useState({
    exam_name: exam?.exam_name || '',
    exam_type: exam?.exam_type || 'midterm',
    date: exam?.scheduled_start ? new Date(exam.scheduled_start).toISOString().slice(0, 10) : '',
    student_count: exam?.student_count || 30,
    hall_ids: exam?.halls?.map(h => h.id) || [] as string[],
    period: exam?.period || exam?.configuration?.period || 'الفترة الأولي',
    invigilator_ids: Array.from(new Set(exam?.assignments?.map(a => a.invigilator_id) || [])) as string[],
  });
  const [halls, setHalls] = useState<HallSimple[]>([]);
  const [supervisors, setSupervisors] = useState<UserSimple[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    authFetch('/api/halls/')
      .then((r) => {
        if (r.ok) return r.json().then(setHalls);
      })
      .catch(() => {});
    authFetch('/api/users/')
      .then((r) => {
        if (r.ok) {
          return r.json().then((users: any[]) =>
            setSupervisors(users.filter(u => u.role === 'invigilator'))
          );
        }
      })
      .catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.date) { setError('يرجى تحديد التاريخ'); return; }
    setIsSubmitting(true);
    setError(null);
    try {
      const payload = {
        exam_name: formData.exam_name,
        exam_type: formData.exam_type,
        scheduled_start: `${formData.date}T09:00:00`,
        scheduled_end: `${formData.date}T12:00:00`,
        student_count: Number(formData.student_count),
        status: 'scheduled',
        hall_ids: formData.hall_ids,
        configuration: { period: formData.period },
      };

      const url = exam ? `/api/sessions/${exam.id}` : '/api/sessions/';
      const method = exam ? 'PUT' : 'POST';

      const res = await authFetch(url, { method, body: JSON.stringify(payload) });

      if (res.ok) {
        const saved = await res.json();
        if (exam?.assignments?.length) {
          for (const assignment of exam.assignments) {
            try {
              await authFetch(`/api/sessions/${saved.id}/assignments/${assignment.id}`, {
                method: 'DELETE'
              });
            } catch { /* keep saving even if a stale assignment was already gone */ }
          }
        }
        for (const hallId of formData.hall_ids) {
          for (const [index, uid] of formData.invigilator_ids.entries()) {
            try {
              await authFetch(`/api/sessions/${saved.id}/assignments`, {
                method: 'POST',
                body: JSON.stringify({
                  invigilator_id: uid,
                  hall_id: hallId,
                  role: index === 0 ? 'primary' : 'secondary'
                })
              });
            } catch { /* ignore duplicate or partial assignment failures */ }
          }
        }
        setIsSuccess(true);
        setTimeout(onSuccess, 1800);
      } else {
        const err = await res.json().catch(() => ({ detail: `خطأ ${res.status}` }));
        setError(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
      }
    } catch {
      setError('تعذر الاتصال بالسيرفر. تأكد من تشغيل الباك اند.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSuccess) return (
    <div className="fixed inset-0 z-[120] bg-black/40 backdrop-blur-sm flex items-center justify-center" dir="rtl">
      <div className="bg-white rounded-3xl p-12 shadow-2xl flex flex-col items-center text-center">
        <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mb-4 animate-bounce">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#00D261" strokeWidth="3.5"><polyline points="20 6 9 17 4 12" /></svg>
        </div>
        <h3 className="text-2xl font-black text-[#2D005F] mb-1">تمت العملية بنجاح!</h3>
        <p className="text-gray-400 font-medium">تم حفظ بيانات الإمتحان</p>
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 z-[120] bg-black/40 backdrop-blur-sm flex items-center justify-center p-4" dir="rtl">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg max-h-[92vh] overflow-y-auto">
        {/* Header */}
        <div className="px-6 py-4 flex justify-between items-center border-b border-gray-100 sticky top-0 bg-white z-10 rounded-t-3xl">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-purple-100 rounded-xl flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#44006E" strokeWidth="2.5"><path d="M12 5V19M5 12H19" /></svg>
            </div>
            <h3 className="text-lg font-black text-[#2D005F]">{exam ? 'تعديل الإمتحان' : 'إضافة إمتحان جديد'}</h3>
          </div>
          <button onClick={onClose} className="w-8 h-8 bg-gray-100 text-gray-400 hover:text-gray-600 rounded-full flex items-center justify-center cursor-pointer transition-colors">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {/* Exam name */}
          <div>
            <label className="block text-xs font-black text-gray-500 mb-1.5">اسم المادة *</label>
            <input
              type="text" required
              placeholder="مثال: قواعد البيانات"
              className="w-full bg-gray-50 border border-gray-200 rounded-2xl py-2.5 px-4 outline-none focus:ring-2 focus:ring-purple-200 focus:border-[#44006E] transition-all font-bold text-sm"
              value={formData.exam_name}
              onChange={e => setFormData(p => ({ ...p, exam_name: e.target.value }))}
            />
          </div>

          {/* Type + Count */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-black text-gray-500 mb-1.5">نوع الامتحان</label>
              <select
                className="w-full bg-gray-50 border border-gray-200 rounded-2xl py-2.5 px-4 outline-none focus:ring-2 focus:ring-purple-200 focus:border-[#44006E] transition-all font-bold text-sm appearance-none"
                value={formData.exam_type}
                onChange={e => setFormData(p => ({ ...p, exam_type: e.target.value }))}
              >
                <option value="midterm">ميدترم</option>
                <option value="practical">عملي</option>
                <option value="final">فاينال</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-black text-gray-500 mb-1.5">عدد الطلاب</label>
              <input
                type="number" required min="1"
                className="w-full bg-gray-50 border border-gray-200 rounded-2xl py-2.5 px-4 outline-none focus:ring-2 focus:ring-purple-200 focus:border-[#44006E] transition-all font-bold text-sm"
                value={formData.student_count}
                onChange={e => setFormData(p => ({ ...p, student_count: parseInt(e.target.value) || 1 }))}
              />
            </div>
          </div>

          {/* Date + Period */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-black text-gray-500 mb-1.5">التاريخ *</label>
              <input
                type="date" required
                className="w-full bg-gray-50 border border-gray-200 rounded-2xl py-2.5 px-4 outline-none focus:ring-2 focus:ring-purple-200 focus:border-[#44006E] transition-all font-bold text-sm"
                value={formData.date}
                onChange={e => setFormData(p => ({ ...p, date: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-xs font-black text-gray-500 mb-1.5">الفترة</label>
              <select
                className="w-full bg-gray-50 border border-gray-200 rounded-2xl py-2.5 px-4 outline-none focus:ring-2 focus:ring-purple-200 focus:border-[#44006E] transition-all font-bold text-sm appearance-none"
                value={formData.period}
                onChange={e => setFormData(p => ({ ...p, period: e.target.value }))}
              >
                <option value="الفترة الأولي">الفترة الأولي</option>
                <option value="الفترة الثانية">الفترة الثانية</option>
                <option value="الفترة الثالثة">الفترة الثالثة</option>
              </select>
            </div>
          </div>

          {/* Halls */}
          <div>
            <label className="block text-xs font-black text-gray-500 mb-1.5">
              القاعات {formData.hall_ids.length > 0 && <span className="text-[#44006E] mr-1">({formData.hall_ids.length} محددة)</span>}
            </label>
            <div className="bg-gray-50 border border-gray-200 rounded-2xl p-3 flex flex-wrap gap-2 min-h-[52px]">
              {halls.length === 0 ? (
                <span className="text-gray-300 text-xs self-center">جاري التحميل...</span>
              ) : halls.map(hall => (
                <button key={hall.id} type="button"
                  onClick={() => setFormData(p => ({ ...p, hall_ids: p.hall_ids.includes(hall.id) ? p.hall_ids.filter(id => id !== hall.id) : [...p.hall_ids, hall.id] }))}
                  className={`px-3 py-1.5 rounded-xl text-xs font-black transition-all active:scale-90 ${formData.hall_ids.includes(hall.id) ? 'bg-[#44006E] text-white' : 'bg-white text-gray-500 border border-gray-200 hover:border-[#44006E]'}`}
                >{hall.name}</button>
              ))}
            </div>
          </div>

          {/* Supervisors */}
          <div>
            <label className="block text-xs font-black text-gray-500 mb-1.5">
              المراقبين {formData.invigilator_ids.length > 0 && <span className="text-[#00D261] mr-1">({formData.invigilator_ids.length} محدد)</span>}
            </label>
            <div className="bg-gray-50 border border-gray-200 rounded-2xl p-3 flex flex-wrap gap-2 min-h-[52px]">
              {supervisors.length === 0 ? (
                <span className="text-gray-300 text-xs self-center">لا يوجد مراقبين مسجلين</span>
              ) : supervisors.map(sup => (
                <button key={sup.id} type="button"
                  onClick={() => setFormData(p => ({ ...p, invigilator_ids: p.invigilator_ids.includes(sup.id) ? p.invigilator_ids.filter(id => id !== sup.id) : [...p.invigilator_ids, sup.id] }))}
                  className={`px-3 py-1.5 rounded-xl text-xs font-black transition-all active:scale-90 ${formData.invigilator_ids.includes(sup.id) ? 'bg-[#00D261] text-white' : 'bg-white text-gray-500 border border-gray-200 hover:border-green-400'}`}
                >{sup.full_name}</button>
              ))}
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-3 bg-red-50 border border-red-200 text-red-600 rounded-2xl px-4 py-3">
              <svg className="shrink-0" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              <span className="text-xs font-bold flex-1" dir="ltr">{error}</span>
              <button type="button" onClick={() => setError(null)} className="text-red-400 hover:text-red-600 cursor-pointer">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
          )}

          {/* Buttons */}
          <div className="flex gap-3 pt-2">
            <button
              type="submit" disabled={isSubmitting}
              className="flex-[2] bg-[#44006E] text-white py-3.5 rounded-2xl font-black text-base shadow-lg shadow-purple-100 hover:-translate-y-0.5 active:scale-95 transition-all cursor-pointer disabled:opacity-60 flex items-center justify-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <svg className="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><circle cx="12" cy="12" r="10" strokeOpacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10" /></svg>
                  جاري الحفظ...
                </>
              ) : (exam ? 'حفظ التعديلات' : 'إضافة الامتحان')}
            </button>
            <button
              type="button" onClick={onClose}
              className="flex-1 border-2 border-red-400 text-red-500 py-3.5 rounded-2xl font-black text-base hover:bg-red-50 transition-all cursor-pointer"
            >
              إلغاء
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Delete Confirm Modal ─────────────────────────────────────────────────────

function DeleteConfirmModal({
  examName,
  onConfirm,
  onCancel,
}: {
  examName: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [isDeleting, setIsDeleting] = useState(false);

  const handleConfirm = async () => {
    setIsDeleting(true);
    await onConfirm();
  };

  return (
    <div
      className="fixed inset-0 z-[130] flex items-center justify-center p-4"
      dir="rtl"
      onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
    >
      {/* Blurred backdrop */}
      <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" />

      {/* Modal */}
      <div className="relative bg-white rounded-[28px] shadow-2xl w-full max-w-sm p-8 flex flex-col items-center text-center animate-in zoom-in-95 duration-200">

        {/* Icon */}
        <div className="w-16 h-16 bg-red-50 rounded-2xl flex items-center justify-center mb-5">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#EF4444" strokeWidth="2.5">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            <line x1="10" y1="11" x2="10" y2="17"></line>
            <line x1="14" y1="11" x2="14" y2="17"></line>
          </svg>
        </div>

        {/* Title */}
        <h3 className="text-xl font-black text-gray-900 mb-2">
          هل أنت متأكد أنك تريد حذف هذا الإمتحان ؟
        </h3>

        {/* Subtitle */}
        <p className="text-sm text-gray-400 font-medium mb-7 leading-relaxed">
          سيتم حذف {examName} ولن تتمكن من إيجاده أو إضافته<br />
          أو العثور على المعلومات الخاصة به
        </p>

        {/* Buttons */}
        <div className="flex gap-3 w-full">
          <button
            onClick={handleConfirm}
            disabled={isDeleting}
            className="flex-1 bg-red-500 hover:bg-red-600 text-white py-3 rounded-2xl font-black text-sm shadow-lg shadow-red-100 hover:-translate-y-0.5 active:scale-95 transition-all cursor-pointer disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {isDeleting ? (
              <>
                <svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <circle cx="12" cy="12" r="10" strokeOpacity="0.25"/>
                  <path d="M12 2a10 10 0 0 1 10 10" />
                </svg>
                جاري الحذف...
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></svg>
                نعم، حذف
              </>
            )}
          </button>
          <button
            onClick={onCancel}
            disabled={isDeleting}
            className="flex-1 bg-white text-gray-500 border-2 border-gray-200 py-3 rounded-2xl font-black text-sm hover:bg-gray-50 hover:border-gray-300 transition-all cursor-pointer disabled:opacity-50"
          >
            إلغاء
          </button>
        </div>
      </div>
    </div>
  );
}
