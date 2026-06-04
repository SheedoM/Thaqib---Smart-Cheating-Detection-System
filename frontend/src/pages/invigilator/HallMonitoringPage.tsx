import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Loader2,
  Camera,
  AlertTriangle,
  Play,
  Square,
  Mic,
  ChevronRight,
  Info,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { authFetch, apiUrl } from '../../config/api';
import type { HallMonitoringStatus, HallReadiness } from '../../types/exams';
import { useHallVoice } from '../../hooks/useHallVoice';
import { isInsecureLanContext } from '../../lib/secureContext';

interface FeedItem {
  device_id: string;
  name: string;
  feed_path: string;
  source_configured: boolean;
}

export default function HallMonitoringPage() {
  const { sessionId, hallId } = useParams<{ sessionId: string; hallId: string }>();
  const [status, setStatus] = useState<HallMonitoringStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [readiness, setReadiness] = useState<HallReadiness | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [feeds, setFeeds] = useState<FeedItem[]>([]);
  const [showAllAlerts, setShowAllAlerts] = useState(false);
  const navigate = useNavigate();

  const voice = useHallVoice({ hallId, autoConnect: Boolean(hallId) });
  const controlConnected = voice.participants.some((p) => p.role === 'admin' || p.role === 'referee');
  const voiceDiagnostic = voice.error || voice.statusText;
  const voiceBadgeLabel =
    voice.isTransmitting ? 'يتحدث' :
    voice.state === 'error' ? 'فشل الصوت' :
    voice.state === 'connecting' ? 'يتصل' :
    voice.remoteTalking ? `يتحدث: ${voice.remoteTalking.name}` :
    voice.micBlocked ? 'ميك محجوب' :
    voice.micState === 'ready' ? 'ميك جاهز' :
    voice.isConnected && !controlConnected ? 'بانتظار الإدارة' :
    voice.state === 'connected' ? 'الصوت متصل' : 'غير متصل';
  const voiceButtonLabel =
    voice.state === 'connecting' ? 'جاري الاتصال...' :
    voice.state === 'error' ? 'إعادة اتصال القناة الصوتية' :
    voice.micState === 'ready' ? 'الصوت جاهز' :
    voice.isConnected ? 'القناة الصوتية متصلة' :
    'الاتصال بالقناة الصوتية';

  const fetchStatus = useCallback(async () => {
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
  }, [sessionId, hallId]);

  const fetchFeeds = useCallback(async () => {
    try {
      const response = await authFetch(`/api/sessions/${sessionId}/halls/${hallId}/feeds`);
      if (response.ok) {
        const data = await response.json();
        setFeeds(data.feeds || []);
      }
    } catch (err) {
      console.error('Error fetching hall feeds:', err);
    }
  }, [sessionId, hallId]);

  useEffect(() => {
    fetchStatus();
    fetchFeeds();
    const interval = setInterval(fetchStatus, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, [fetchStatus, fetchFeeds]);

  const runReadinessCheck = async () => {
    setIsChecking(true);
    setError(null);
    try {
      const response = await authFetch(`/api/sessions/${sessionId}/halls/${hallId}/readiness`);
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: `خطأ ${response.status}` }));
        throw new Error(typeof err.detail === 'string' ? err.detail : 'فشل فحص الأجهزة.');
      }
      const data = await response.json();
      setReadiness(data);
      return data as HallReadiness;
    } catch (err: any) {
      setError(err.message || 'تعذر فحص أجهزة القاعة.');
      return null;
    } finally {
      setIsChecking(false);
    }
  };

  const connectVoice = async () => {
    const ok = await voice.connect();
    if (!ok) {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    await runReadinessCheck();
  };

  const handleStartMonitoring = async (force = false) => {
    if (!force) {
      const nextReadiness = await runReadinessCheck();
      if (!nextReadiness) return;
      if (nextReadiness.overall_status === 'warning') return;
    }

    setIsStarting(true);
    try {
      const response = await authFetch(`/api/sessions/${sessionId}/halls/${hallId}/monitoring/start`, {
        method: 'POST'
      });
      if (response.ok) {
        setReadiness(null);
        // Immediately refetch status and feeds after starting (1B fix)
        await fetchStatus();
        await fetchFeeds();
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
  // Use the first configured feed for the main view
  const primaryFeed = feeds.find((f) => f.source_configured) ?? feeds[0] ?? null;
  const visibleAlerts = showAllAlerts ? (status?.alerts ?? []) : (status?.alerts ?? []).slice(0, 3);

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
        <div className="mr-auto flex items-center gap-2">
          {/* PTT connection badge */}
          <div title={voice.statusText} className={`flex items-center gap-1 px-2 py-1 rounded-lg ${
            voice.state === 'error' ? 'bg-red-50' : voice.micBlocked ? 'bg-amber-50' : voice.state === 'connected' ? 'bg-green-50' : 'bg-gray-50'
          }`}>
            {voice.state === 'connected' ? (
              <Wifi size={12} className={voice.micBlocked ? 'text-amber-500' : 'text-green-500'} />
            ) : (
              <WifiOff size={12} className={voice.state === 'error' ? 'text-red-500' : 'text-gray-400'} />
            )}
            <span className={`text-[9px] font-bold uppercase ${
              voice.state === 'error' ? 'text-red-600' : voice.micBlocked ? 'text-amber-700' : voice.state === 'connected' ? 'text-green-600' : 'text-gray-400'
            }`}>
              {voiceBadgeLabel}
            </span>
          </div>
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
        {isMonitoring && primaryFeed ? (
          <img
            src={apiUrl(primaryFeed.feed_path)}
            alt="Live Stream"
            className="w-full h-full object-contain"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.opacity = '0.3';
            }}
          />
        ) : isMonitoring ? (
          /* Monitoring is active but no feed configured */
          <div className="absolute inset-0 flex flex-col items-center justify-center text-white p-8 text-center">
            <Camera size={48} className="text-gray-600 mb-4 opacity-50" />
            <p className="text-gray-400 font-medium">لا توجد كاميرا مرتبطة بهذه القاعة</p>
          </div>
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-white p-8 text-center">
            <Camera size={48} className="text-gray-600 mb-4 opacity-50" />
            <p className="text-gray-400 font-medium mb-6">المراقبة لم تبدأ بعد لهذه القاعة</p>
            <button
              onClick={() => handleStartMonitoring(false)}
              disabled={isStarting || isChecking}
              className="bg-thaqib-primary hover:bg-thaqib-primary-dark disabled:opacity-50 text-white px-6 py-3 rounded-xl font-bold flex items-center gap-2 transition-all active:scale-95 shadow-lg shadow-purple-900/20"
            >
              {isStarting || isChecking ? <Loader2 size={20} className="animate-spin" /> : <Play size={20} />}
              <span>{isChecking ? 'جاري فحص الأجهزة...' : 'بدء المراقبة الآن'}</span>
            </button>
            <button
              onClick={connectVoice}
              disabled={voice.state === 'connecting'}
              className="mt-3 bg-white/10 hover:bg-white/20 disabled:opacity-50 text-white px-5 py-2 rounded-xl font-bold flex items-center gap-2 transition-all active:scale-95 border border-white/20"
            >
              {voice.state === 'connecting' ? <Loader2 size={18} className="animate-spin" /> : <Mic size={18} />}
              <span>{voiceButtonLabel}</span>
            </button>
          </div>
        )}

        {/* PTT status overlays — always visible over the video */}
        {voice.state === 'error' && (
          <div className="absolute top-3 left-3 right-3 z-10 bg-red-500/90 backdrop-blur-sm text-white px-3 py-2 rounded-xl text-xs font-bold flex items-center gap-2">
            <WifiOff size={14} className="shrink-0" />
            <span className="truncate">{voice.error || 'فشل اتصال القناة الصوتية'}</span>
            <button onClick={connectVoice} className="mr-auto shrink-0 bg-white/20 hover:bg-white/30 px-2 py-1 rounded-lg text-[11px]">إعادة</button>
          </div>
        )}
        {voice.state === 'connecting' && (
          <div className="absolute top-3 left-3 right-3 z-10 bg-gray-900/70 backdrop-blur-sm text-white px-3 py-2 rounded-xl text-xs font-bold flex items-center gap-2">
            <Loader2 size={14} className="shrink-0 animate-spin" />
            <span>جاري الاتصال بالقناة الصوتية…</span>
          </div>
        )}

        {/* Floating PTT Button for Monitoring Mode */}
        {isMonitoring && (
          <div className="absolute bottom-4 left-4 right-4 flex justify-center pointer-events-none">
            <button
              onMouseDown={() => voice.startTalking()}
              onMouseUp={() => voice.stopTalking()}
              onTouchStart={(e) => { e.preventDefault(); voice.startTalking(); }}
              onTouchEnd={(e) => { e.preventDefault(); voice.stopTalking(); }}
              className={`pointer-events-auto h-16 w-16 rounded-full flex items-center justify-center transition-all shadow-xl ${
                voice.isTransmitting
                  ? 'bg-red-500 scale-110 shadow-red-500/40'
                  : voice.state === 'connected'
                  ? 'bg-thaqib-primary shadow-purple-500/40 active:scale-90'
                  : 'bg-gray-500 shadow-gray-500/20 active:scale-90'
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
        {voice.state === 'error' && (
          <div className="bg-red-50 border border-red-100 text-red-700 px-4 py-3 rounded-xl mb-6 text-xs flex items-start gap-2">
            <WifiOff size={16} className="shrink-0" />
            <div>
              <p className="font-bold">فشل اتصال القناة الصوتية</p>
              <p className="mt-1 text-red-600 break-words">{voiceDiagnostic}</p>
            </div>
          </div>
        )}
        {voice.isConnected && !controlConnected && (
          <div className="bg-blue-50 border border-blue-100 text-blue-700 px-4 py-3 rounded-xl mb-6 text-xs font-bold">
            القناة الصوتية متصلة. بانتظار اتصال الإدارة من غرفة التحكم.
          </div>
        )}
        {isInsecureLanContext() && (
          <div className="bg-amber-50 border border-amber-100 text-amber-800 px-4 py-3 rounded-xl mb-6 text-xs font-bold">
            Microphone requires HTTPS on mobile. القناة الصوتية ستبقى متصلة للاستقبال، لكن الإرسال يحتاج فتح التطبيق عبر رابط https.
          </div>
        )}

        {!isMonitoring && readiness && (
          <div className="mb-6 bg-yellow-50 border border-yellow-200 rounded-2xl p-4">
            <div className="flex items-start gap-3 mb-4">
              <AlertTriangle size={18} className="text-yellow-600 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-bold text-yellow-800">
                  {readiness.overall_status === 'passed' ? 'كل الأجهزة جاهزة' : 'توجد تحذيرات قبل بدء المراقبة'}
                </p>
                <p className="text-xs text-yellow-700 mt-1">
                  يمكنك إعادة الفحص أو بدء المراقبة رغم التحذيرات عند الضرورة.
                </p>
              </div>
            </div>
            <div className="space-y-2 mb-4">
              {readiness.devices.map((device) => (
                <div key={device.id} className="bg-white rounded-xl px-3 py-2 flex items-start gap-3 border border-yellow-100">
                  <span className={`mt-1.5 w-2.5 h-2.5 rounded-full shrink-0 ${device.status === 'passed' ? 'bg-green-500' : 'bg-yellow-500'}`}></span>
                  <div>
                    <p className="text-xs font-bold text-gray-800">{device.name}</p>
                    <p className="text-[11px] text-gray-500">{device.type === 'camera' ? 'كاميرا' : 'مايكروفون'} - {device.message}</p>
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={runReadinessCheck}
                disabled={isChecking}
                className="flex-1 py-3 bg-white border border-yellow-200 text-yellow-700 rounded-xl text-xs font-bold disabled:opacity-60"
              >
                {isChecking ? 'جاري الفحص...' : 'إعادة الفحص'}
              </button>
              <button
                type="button"
                onClick={() => handleStartMonitoring(true)}
                disabled={isStarting}
                className="flex-1 py-3 bg-thaqib-primary text-white rounded-xl text-xs font-bold disabled:opacity-60"
              >
                {isStarting ? 'جاري البدء...' : 'بدء رغم التحذيرات'}
              </button>
            </div>
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
              <button
                type="button"
                onClick={() => setShowAllAlerts((value) => !value)}
                className="text-[10px] font-bold text-thaqib-primary px-2 py-0.5 bg-purple-50 rounded-full"
              >
                {showAllAlerts ? 'عرض أقل' : 'عرض الكل'}
              </button>
            )}
          </div>

          <div className="space-y-3">
            {visibleAlerts.length > 0 ? (
              visibleAlerts.map((alert, idx) => (
                <div key={idx} className="flex items-start gap-3 p-3 bg-red-50/50 rounded-xl border border-red-100/50">
                  <div className="bg-red-100 p-2 rounded-lg text-red-600">
                    <AlertTriangle size={16} />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-gray-900 mb-0.5">{alert.type || alert.event_type}</p>
                    <p className="text-[10px] text-gray-500 leading-tight">{alert.message || alert.severity}</p>
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
