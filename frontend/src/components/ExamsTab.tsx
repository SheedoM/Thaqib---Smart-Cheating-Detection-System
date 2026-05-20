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
interface UserSimple { id: string; full_name: string; }
interface AssignmentSimple {
  id: string;
  invigilator_id: string;
  hall_id: string;
  role: 'primary' | 'secondary';
}

// ─── Main Tab ────────────────────────────────────────────────────────────────

export default function ExamsTab() {
  const [exams, setExams] = useState<ExamItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingExam, setEditingExam] = useState<ExamItem | null>(null);
  const [deletingExam, setDeletingExam] = useState<ExamItem | null>(null);
  const [viewingReport, setViewingReport] = useState<ExamItem | null>(null);

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

  useEffect(() => { fetchExams(); }, []);
  
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
        <button
          onClick={() => { setEditingExam(null); setIsModalOpen(true); }}
          className="bg-[#00D261] hover:bg-[#00B554] text-white px-7 py-3 rounded-[18px] font-black flex items-center gap-2 shadow-lg shadow-green-100 transition-all hover:-translate-y-0.5 active:scale-95 cursor-pointer"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          إضافة إمتحان
        </button>
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
          {exams.map(exam => (
            <ExamCard
              key={exam.id}
              exam={exam}
              onEdit={() => { setEditingExam(exam); setIsModalOpen(true); }}
              onDelete={() => setDeletingExam(exam)}
              onViewReport={() => setViewingReport(exam)}
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
    </div>
  );
}

// ─── Exam Card ───────────────────────────────────────────────────────────────

function ExamCard({ exam, onEdit, onDelete, onViewReport }: { exam: ExamItem, onEdit: () => void, onDelete: () => void, onViewReport: () => void }) {
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
      </div>

      <div className="pt-4 mt-4 border-t border-gray-50 flex justify-between items-center">
        <div className="flex gap-4">
          <button onClick={onEdit} className="text-[#44006E] font-black text-xs hover:underline cursor-pointer flex items-center gap-1">
            تعديل <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="15 18 9 12 15 6"></polyline></svg>
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
            setSupervisors(users.filter(u => u.role === 'invigilator' || u.role === 'referee'))
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
