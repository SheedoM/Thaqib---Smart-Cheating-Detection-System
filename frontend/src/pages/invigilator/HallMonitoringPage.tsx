import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  Loader2, 
  Camera, 
  AlertTriangle, 
  Play, 
  Square, 
  Mic, 
  ChevronRight,
  Info
} from 'lucide-react';
import { authFetch, apiUrl } from '../../config/api';
import type { HallMonitoringStatus } from '../../types/exams';
import { useInvigilatorPtt } from '../../hooks/useInvigilatorPtt';

export default function HallMonitoringPage() {
  const { sessionId, hallId } = useParams<{ sessionId: string; hallId: string }>();
  const [status, setStatus] = useState<HallMonitoringStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const navigate = useNavigate();

  // PTT Hook
  const { isTransmitting, startTransmission, stopTransmission } = useInvigilatorPtt();

  const fetchStatus = async () => {
    try {
      const response = await authFetch(`/api/sessions/${sessionId}/halls/${hallId}/status`);
      if (response.ok) {
        const data = await response.json();
        setStatus(data);
      }
    } catch (err) {
      console.error('Error fetching hall status:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, [sessionId, hallId]);

  const handleStartMonitoring = async () => {
    setIsStarting(true);
    try {
      const response = await authFetch(`/api/sessions/${sessionId}/halls/${hallId}/monitoring/start`, {
        method: 'POST'
      });
      if (response.ok) {
        await fetchStatus();
      } else {
        setError('فشل في بدء المراقبة.');
      }
    } catch (err) {
      setError('خطأ في الاتصال بالخادم.');
    } finally {
      setIsStarting(false);
    }
  };

  const handleStopMonitoring = async () => {
    if (!window.confirm('هل أنت متأكد من إنهاء جلسة المراقبة؟')) return;
    
    try {
      const response = await authFetch(`/api/sessions/${sessionId}/halls/${hallId}/monitoring/stop`, {
        method: 'POST'
      });
      if (response.ok) {
        await fetchStatus();
      }
    } catch (err) {
      console.error('Error stopping monitoring:', err);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-4">
        <Loader2 className="animate-spin text-thaqib-primary" size={40} />
        <p className="text-gray-500 font-medium">جاري الاتصال بالقاعة...</p>
      </div>
    );
  }

  const isMonitoring = status?.is_active;

  return (
    <div className="flex flex-col min-h-full">
      {/* Top Header / Breadcrumb */}
      <div className="bg-white px-6 py-3 flex items-center gap-2 border-b border-gray-100">
        <button onClick={() => navigate('/invigilator')} className="p-1 -mr-2 text-gray-400">
          <ChevronRight size={24} />
        </button>
        <div className="flex flex-col">
          <h2 className="text-sm font-bold text-gray-900 leading-none">
            {status?.exam_name || 'جلسة المراقبة'}
          </h2>
          <span className="text-[10px] text-gray-400 font-medium uppercase mt-1">
            قاعة {status?.hall_name}
          </span>
        </div>
        <div className="mr-auto">
          {isMonitoring ? (
            <div className="flex items-center gap-1.5 px-2 py-1 bg-green-50 rounded-lg">
              <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></div>
              <span className="text-[10px] font-bold text-green-600 uppercase">مباشر</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-2 py-1 bg-gray-50 rounded-lg">
              <div className="w-1.5 h-1.5 bg-gray-400 rounded-full"></div>
              <span className="text-[10px] font-bold text-gray-500 uppercase">متوقف</span>
            </div>
          )}
        </div>
      </div>

      {/* Main Video Section */}
      <div className="relative aspect-video bg-black w-full overflow-hidden">
        {isMonitoring ? (
          <img 
            src={apiUrl(`/api/stream/hall/${hallId}/video`)} 
            alt="Live Stream"
            className="w-full h-full object-contain"
          />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-white p-8 text-center">
            <Camera size={48} className="text-gray-600 mb-4 opacity-50" />
            <p className="text-gray-400 font-medium mb-6">المراقبة لم تبدأ بعد لهذه القاعة</p>
            <button 
              onClick={handleStartMonitoring}
              disabled={isStarting}
              className="bg-thaqib-primary hover:bg-thaqib-primary-dark disabled:opacity-50 text-white px-6 py-3 rounded-xl font-bold flex items-center gap-2 transition-all active:scale-95 shadow-lg shadow-purple-900/20"
            >
              {isStarting ? <Loader2 size={20} className="animate-spin" /> : <Play size={20} />}
              <span>بدء المراقبة الآن</span>
            </button>
          </div>
        )}

        {/* Floating PTT Button for Monitoring Mode */}
        {isMonitoring && (
          <div className="absolute bottom-4 left-4 right-4 flex justify-center pointer-events-none">
            <button 
              onMouseDown={() => startTransmission()}
              onMouseUp={() => stopTransmission()}
              onTouchStart={() => startTransmission()}
              onTouchEnd={() => stopTransmission()}
              className={`pointer-events-auto h-16 w-16 rounded-full flex items-center justify-center transition-all shadow-xl ${
                isTransmitting 
                  ? 'bg-red-500 scale-110 shadow-red-500/40' 
                  : 'bg-thaqib-primary shadow-purple-500/40 active:scale-90'
              }`}
            >
              <Mic size={28} className="text-white" />
            </button>
          </div>
        )}
      </div>

      {/* Status Info & Alerts */}
      <div className="flex-1 bg-white p-6 rounded-t-[32px] -mt-6 relative z-10 shadow-2xl">
        <div className="w-12 h-1 bg-gray-100 rounded-full mx-auto mb-6"></div>

        {error && (
          <div className="bg-red-50 border border-red-100 text-red-600 px-4 py-3 rounded-xl mb-6 text-xs flex items-start gap-2">
            <AlertTriangle size={16} className="shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4 mb-8">
          <div className="bg-[#F8F9FE] p-4 rounded-2xl border border-gray-50">
            <span className="text-[10px] font-bold text-gray-400 uppercase block mb-1">الطلاب</span>
            <span className="text-xl font-bold text-gray-900">{status?.stats?.student_count || 0}</span>
          </div>
          <div className="bg-[#F8F9FE] p-4 rounded-2xl border border-gray-50">
            <span className="text-[10px] font-bold text-gray-400 uppercase block mb-1">تنبيهات نشطة</span>
            <span className={`text-xl font-bold ${status?.stats?.active_alerts ? 'text-red-500' : 'text-gray-900'}`}>
              {status?.stats?.active_alerts || 0}
            </span>
          </div>
        </div>

        <section className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-gray-900 uppercase tracking-tight">آخر التنبيهات</h3>
            {(status?.stats?.active_alerts ?? 0) > 0 && (
              <span className="text-[10px] font-bold text-thaqib-primary px-2 py-0.5 bg-purple-50 rounded-full">عرض الكل</span>
            )}
          </div>
          
          <div className="space-y-3">
            {status?.alerts && status.alerts.length > 0 ? (
              status.alerts.slice(0, 3).map((alert, idx) => (
                <div key={idx} className="flex items-start gap-3 p-3 bg-red-50/50 rounded-xl border border-red-100/50">
                  <div className="bg-red-100 p-2 rounded-lg text-red-600">
                    <AlertTriangle size={16} />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-gray-900 mb-0.5">{alert.type}</p>
                    <p className="text-[10px] text-gray-500 leading-tight">{alert.message}</p>
                  </div>
                  <span className="mr-auto text-[9px] font-medium text-gray-400">منذ قليل</span>
                </div>
              ))
            ) : (
              <div className="text-center py-8 bg-gray-50 rounded-2xl border border-dashed border-gray-100">
                <Info size={24} className="mx-auto text-gray-300 mb-2" />
                <p className="text-[11px] text-gray-400 font-medium">لا توجد تنبيهات نشطة حالياً</p>
              </div>
            )}
          </div>
        </section>

        {isMonitoring && (
          <button 
            onClick={handleStopMonitoring}
            className="w-full py-4 text-red-500 font-bold text-sm border-2 border-red-50 rounded-2xl hover:bg-red-50 transition-colors flex items-center justify-center gap-2"
          >
            <Square size={18} fill="currentColor" />
            <span>إنهاء جلسة المراقبة</span>
          </button>
        )}
      </div>
    </div>
  );
}
