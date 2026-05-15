import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, MapPin, Clock, ArrowLeft } from 'lucide-react';
import { authFetch } from '../../config/api';
import type { Assignment } from '../../types/exams';

export default function SchedulePage() {
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchSchedule = async () => {
      try {
        const response = await authFetch('/api/sessions/my');
        if (response.ok) {
          const data = await response.json();
          setAssignments(data);
        } else {
          setError('فشل في تحميل الجدول الزمني.');
        }
      } catch (err) {
        console.error('Error fetching schedule:', err);
        setError('تعذر الاتصال بالخادم.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchSchedule();
  }, []);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-4">
        <Loader2 className="animate-spin text-thaqib-primary" size={40} />
        <p className="text-gray-500 font-medium">جاري تحميل جدولك...</p>
      </div>
    );
  }

  return (
    <div className="px-6 py-8">
      <header className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">مرحباً بك 👋</h2>
        <p className="text-gray-500 font-medium">لديك {assignments.length} جلسات مراقبة مجدولة.</p>
      </header>

      {error && (
        <div className="bg-red-50 border border-red-100 text-red-600 px-4 py-3 rounded-xl mb-6 text-sm">
          {error}
        </div>
      )}

      <div className="space-y-6">
        <section>
          <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4 px-1">اليوم</h3>
          <div className="space-y-4">
            {assignments.length > 0 ? (
              assignments.map((assignment) => (
                <div 
                  key={assignment.id}
                  onClick={() => navigate(`/invigilator/session/${assignment.exam_session_id}/${assignment.hall_id}`)}
                  className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100 active:scale-[0.98] transition-transform cursor-pointer"
                >
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h4 className="font-bold text-lg text-gray-900 mb-1">{assignment.exam_name}</h4>
                      <div className="flex items-center gap-2 text-gray-500 text-sm">
                        <MapPin size={14} className="text-thaqib-light" />
                        <span>قاعة {assignment.hall_name}</span>
                      </div>
                    </div>
                    {assignment.monitoring_started_at && !assignment.monitoring_ended_at ? (
                      <span className="bg-green-100 text-green-600 text-[10px] font-bold px-2 py-1 rounded-full uppercase">نشط الآن</span>
                    ) : (
                      <span className="bg-gray-100 text-gray-500 text-[10px] font-bold px-2 py-1 rounded-full uppercase">مجدول</span>
                    )}
                  </div>

                  <div className="flex items-center justify-between mt-6 pt-4 border-t border-gray-50">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1.5 text-gray-700 font-semibold text-sm">
                        <Clock size={16} className="text-gray-400" />
                        <span>{new Date(assignment.scheduled_start).toLocaleTimeString('ar-EG', { hour: 'numeric', minute: '2-digit' })}</span>
                      </div>
                      <span className="text-gray-300">—</span>
                      <div className="text-gray-700 font-semibold text-sm">
                        <span>{new Date(assignment.scheduled_end).toLocaleTimeString('ar-EG', { hour: 'numeric', minute: '2-digit' })}</span>
                      </div>
                    </div>
                    <div className="text-thaqib-primary font-bold text-sm flex items-center gap-1">
                      <span>عرض</span>
                      <ArrowLeft size={16} />
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-12 bg-white rounded-2xl border border-dashed border-gray-200">
                <p className="text-gray-400">لا توجد جلسات مجدولة حالياً.</p>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
