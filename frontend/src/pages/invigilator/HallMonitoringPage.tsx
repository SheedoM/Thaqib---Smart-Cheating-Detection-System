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
  X,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { authFetch, apiUrl } from '../../config/api';
import type { HallMonitoringStatus, HallReadiness, HallAlert } from '../../types/exams';
import { useHallVoice } from '../../hooks/useHallVoice';
import { isInsecureLanContext } from '../../lib/secureContext';
import CameraFeedGrid, { type CameraFeedGridItem } from '../../components/CameraFeedGrid';

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
  const [activeTab, setActiveTab] = useState<'cameras' | 'cases'>('cameras');
  const [enlargedFeed, setEnlargedFeed] = useState<CameraFeedGridItem | null>(null);
  const [reviewAlert, setReviewAlert] = useState<HallAlert | null>(null);
  const navigate = useNavigate();

  const voice = useHallVoice({ hallId, autoConnect: Boolean(hallId) });
  const controlConnected = voice.participants.some((p) => p.role === 'admin');
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
        setError(null);
        await fetchStatus();
      } else {
        setError('فشل إنهاء جلسة المراقبة. حاول مرة أخرى.');
      }
    } catch (err) {
      console.error('Error stopping monitoring:', err);
      setError('تعذر الاتصال بالخادم أثناء إنهاء المراقبة.');
    }
  };

  const openAlert = async (alert: HallAlert) => {
    setReviewAlert(alert);
    // Claim on open so the control room knows this alert is being handled.
    if (alert.status === 'pending') {
      try {
        await authFetch(`/api/sessions/${sessionId}/halls/${hallId}/alerts/${alert.id}/claim`, {
          method: 'POST',
        });
        await fetchStatus();
      } catch (err) {
        console.error('Error claiming alert:', err);
      }
    }
  };

  const reviewAlertAction = async (alert: HallAlert, action: 'confirm' | 'cancel') => {
    try {
      const response = await authFetch(
        `/api/sessions/${sessionId}/halls/${hallId}/alerts/${alert.id}/${action}`,
        { method: 'POST' }
      );
      if (response.ok) {
        setReviewAlert(null);
        await fetchStatus();
      }
    } catch (err) {
      console.error(`Error on alert ${action}:`, err);
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
  const feedGridItems: CameraFeedGridItem[] = feeds.map((feed) => ({
    id: feed.device_id,
    name: feed.name,
    feedPath: feed.source_configured ? feed.feed_path : null,
    sourceConfigured: feed.source_configured,
    isRunning: Boolean(isMonitoring && feed.source_configured),
  }));
  const visibleAlerts = showAllAlerts ? (status?.alerts ?? []) : (status?.alerts ?? []).slice(0, 3);
  const voiceControlBar = (
    <div className="mb-6 rounded-2xl border border-gray-100 bg-[#F8F9FE] p-4">
      <div className="flex flex-wrap items-center gap-3">
        <div title={voice.statusText} className={`flex items-center gap-2 rounded-xl px-3 py-2 ${
          voice.state === 'error' ? 'bg-red-50 text-red-700' :
          voice.micBlocked ? 'bg-amber-50 text-amber-700' :
          voice.isConnected ? 'bg-green-50 text-green-700' :
          'bg-white text-gray-500'
        }`}>
          {voice.isConnected ? <Wifi size={16} /> : <WifiOff size={16} />}
          <span className="text-xs font-bold">{voiceBadgeLabel}</span>
        </div>
        <button
          type="button"
          disabled={!voice.isConnected || voice.micBlocked}
          onPointerDown={(event) => {
            event.preventDefault();
            void voice.startTalking();
          }}
          onPointerUp={(event) => {
            event.preventDefault();
            voice.stopTalking();
          }}
          onPointerCancel={() => voice.stopTalking()}
          onMouseLeave={() => voice.stopTalking()}
          className={`flex min-h-11 items-center gap-2 rounded-xl px-4 py-2 text-sm font-bold transition-all disabled:cursor-not-allowed disabled:opacity-50 ${
            voice.isTransmitting ? 'bg-red-500 text-white shadow-lg shadow-red-500/20' : 'bg-thaqib-primary text-white shadow-lg shadow-purple-900/10'
          }`}
        >
          <Mic size={18} />
          <span>{voice.isTransmitting ? 'جاري الإرسال...' : 'تحدث مع القاعة'}</span>
        </button>
        {voice.state === 'error' && (
          <button
            type="button"
            onClick={connectVoice}
            className="rounded-xl bg-white px-4 py-2 text-xs font-bold text-red-600 shadow-sm"
          >
            إعادة الاتصال
          </button>
        )}
      </div>
    </div>
  );

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

      <div className="bg-white px-6 py-3 flex gap-2 border-b border-gray-100">
        <button
          type="button"
          onClick={() => setActiveTab('cameras')}
          className={`flex-1 rounded-xl px-4 py-2 text-sm font-bold transition-colors ${
            activeTab === 'cameras' ? 'bg-thaqib-primary text-white' : 'bg-gray-50 text-gray-500'
          }`}
        >
          المراقبة
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('cases')}
          className={`flex-1 rounded-xl px-4 py-2 text-sm font-bold transition-colors ${
            activeTab === 'cases' ? 'bg-thaqib-primary text-white' : 'bg-gray-50 text-gray-500'
          }`}
        >
          الحالات
        </button>
      </div>

      {/* Main Video Section */}
      {activeTab === 'cameras' && (
      <div className="relative bg-black w-full overflow-hidden">
        {isMonitoring && feedGridItems.length > 0 ? (
          <CameraFeedGrid
            cameras={feedGridItems}
            gapClassName="gap-1"
            className="p-1"
            onCameraClick={setEnlargedFeed}
          />
        ) : isMonitoring ? (
          /* Monitoring is active but no feed configured */
          <div className="aspect-video flex flex-col items-center justify-center text-white p-8 text-center">
            <Camera size={48} className="text-gray-600 mb-4 opacity-50" />
            <p className="text-gray-400 font-medium">لا توجد كاميرا مرتبطة بهذه القاعة</p>
          </div>
        ) : (
          <div className="aspect-video flex flex-col items-center justify-center text-white p-8 text-center">
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

      </div>
      )}

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
        {voice.state === 'connecting' && (
          <div className="bg-gray-50 border border-gray-100 text-gray-700 px-4 py-3 rounded-xl mb-6 text-xs font-bold flex items-center gap-2">
            <Loader2 size={16} className="shrink-0 animate-spin" />
            <span>جاري الاتصال بالقناة الصوتية...</span>
          </div>
        )}
        {voice.isConnected && !controlConnected && (
          <div className="bg-blue-50 border border-blue-100 text-blue-700 px-4 py-3 rounded-xl mb-6 text-xs font-bold">
            القناة الصوتية متصلة. بانتظار اتصال الإدارة من غرفة التحكم.
          </div>
        )}
        {voice.incidentCards.length > 0 && (
          <div className="mb-6 space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-xs font-bold text-red-700">حالات مؤكدة من غرفة التحكم</p>
              <button onClick={voice.clearIncidentCards} className="text-[10px] font-bold text-gray-400">مسح</button>
            </div>
            {voice.incidentCards.map((card) => (
              <div key={card.alert_id} className="bg-red-50 border border-red-100 text-red-700 px-4 py-3 rounded-xl text-xs flex items-start gap-2">
                <AlertTriangle size={16} className="shrink-0" />
                <div>
                  <p className="font-bold">
                    {card.event_type || 'حالة مؤكدة'}{card.severity ? ` — ${card.severity}` : ''}
                  </p>
                  {card.timestamp && (
                    <p className="mt-0.5 text-[10px] text-red-500">
                      {new Date(card.timestamp).toLocaleTimeString('en-US', { hour12: false })}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
        {isInsecureLanContext() && (
          <div className="bg-amber-50 border border-amber-100 text-amber-800 px-4 py-3 rounded-xl mb-6 text-xs font-bold">
            Microphone requires HTTPS on mobile. القناة الصوتية ستبقى متصلة للاستقبال، لكن الإرسال يحتاج فتح التطبيق عبر رابط https.
          </div>
        )}

        {activeTab === 'cameras' && isMonitoring && voiceControlBar}

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

        {activeTab === 'cases' && (
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
                visibleAlerts.map((alert) => (
                  <button
                    type="button"
                    key={alert.id}
                    onClick={() => openAlert(alert)}
                    className="w-full text-right flex items-start gap-3 p-3 bg-red-50/50 rounded-xl border border-red-100/50 hover:bg-red-50 active:scale-[0.99] transition-all"
                  >
                    <div className="bg-red-100 p-2 rounded-lg text-red-600">
                      <AlertTriangle size={16} />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-bold text-gray-900 mb-0.5 truncate">{alert.type || alert.event_type}</p>
                      <p className="text-[10px] text-gray-500 leading-tight truncate">{alert.location || alert.message}</p>
                    </div>
                    <div className="mr-auto flex flex-col items-end gap-1 shrink-0">
                      <AlertStatusBadge status={alert.status} />
                      <span className="text-[9px] font-medium text-gray-400">
                        {alert.timestamp ? new Date(alert.timestamp).toLocaleTimeString('en-US', { hour12: false }) : 'منذ قليل'}
                      </span>
                    </div>
                  </button>
                ))
              ) : (
                <div className="text-center py-8 bg-gray-50 rounded-2xl border border-dashed border-gray-100">
                  <Info size={24} className="mx-auto text-gray-300 mb-2" />
                  <p className="text-[11px] text-gray-400 font-medium">لا توجد تنبيهات نشطة حالياً</p>
                </div>
              )}
            </div>
          </section>
        )}

        {activeTab === 'cameras' && isMonitoring && (
          <button
            onClick={handleStopMonitoring}
            className="w-full py-4 text-red-500 font-bold text-sm border-2 border-red-50 rounded-2xl hover:bg-red-50 transition-colors flex items-center justify-center gap-2"
          >
            <Square size={18} fill="currentColor" />
            <span>إنهاء جلسة المراقبة</span>
          </button>
        )}
      </div>

      {/* Enlarged single-camera overlay */}
      {enlargedFeed && (
        <div
          className="fixed inset-0 z-[60] bg-black/90 flex items-center justify-center p-4"
          onClick={() => setEnlargedFeed(null)}
        >
          <button
            onClick={() => setEnlargedFeed(null)}
            className="absolute top-4 left-4 z-10 h-10 w-10 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center"
          >
            <X size={22} />
          </button>
          <div className="w-full max-w-5xl" onClick={(e) => e.stopPropagation()}>
            {enlargedFeed.feedPath ? (
              <img
                src={apiUrl(enlargedFeed.feedPath)}
                alt={enlargedFeed.name}
                className="w-full rounded-xl object-contain bg-black"
              />
            ) : (
              <div className="aspect-video w-full rounded-xl bg-black flex flex-col items-center justify-center text-white/60">
                <Camera size={36} />
                <p className="mt-3 text-sm font-bold">الكاميرا غير متصلة</p>
              </div>
            )}
            <p className="text-center text-white/80 text-sm font-bold mt-3">{enlargedFeed.name}</p>
          </div>
        </div>
      )}

      {/* Alert review modal */}
      {reviewAlert && (
        <AlertReviewModal
          alert={reviewAlert}
          sessionId={sessionId!}
          hallId={hallId!}
          onClose={() => setReviewAlert(null)}
          onConfirm={() => reviewAlertAction(reviewAlert, 'confirm')}
          onCancel={() => reviewAlertAction(reviewAlert, 'cancel')}
        />
      )}
    </div>
  );
}

function AlertStatusBadge({ status }: { status: HallAlert['status'] }) {
  const map: Record<string, { label: string; cls: string }> = {
    pending: { label: 'بانتظار المراجعة', cls: 'bg-amber-100 text-amber-700' },
    claimed: { label: 'قيد المراجعة', cls: 'bg-blue-100 text-blue-700' },
    confirmed: { label: 'مؤكد', cls: 'bg-red-100 text-red-700' },
    cancelled: { label: 'ملغى', cls: 'bg-gray-100 text-gray-500' },
  };
  const item = map[status] ?? map.pending;
  return (
    <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full whitespace-nowrap ${item.cls}`}>
      {item.label}
    </span>
  );
}

function AlertReviewModal({
  alert,
  sessionId,
  hallId,
  onClose,
  onConfirm,
  onCancel,
}: {
  alert: HallAlert;
  sessionId: string;
  hallId: string;
  onClose: () => void;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const base = `/api/sessions/${sessionId}/halls/${hallId}/alerts/${alert.id}`;
  const [showSnapshot, setShowSnapshot] = useState(!alert.has_clip);
  const isReviewed = alert.status === 'confirmed' || alert.status === 'cancelled';

  return (
    <div className="fixed inset-0 z-[60] bg-black/70 flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={onClose}>
      <div
        className="bg-white w-full sm:max-w-lg sm:rounded-3xl rounded-t-3xl p-6 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
        dir="rtl"
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-gray-900">{alert.event_type || alert.type}</h3>
            {alert.location && <p className="text-xs text-gray-400 mt-0.5">{alert.location}</p>}
          </div>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600">
            <X size={22} />
          </button>
        </div>

        {/* Clip / snapshot */}
        <div className="bg-black rounded-2xl overflow-hidden mb-4 aspect-video flex items-center justify-center">
          {alert.has_clip && !showSnapshot ? (
            <video
              src={apiUrl(`${base}/clip`)}
              controls
              autoPlay
              className="w-full h-full object-contain"
              onError={() => setShowSnapshot(true)}
            />
          ) : alert.has_snapshot ? (
            <img src={apiUrl(`${base}/snapshot`)} alt={alert.event_type} className="w-full h-full object-contain" />
          ) : (
            <div className="flex flex-col items-center text-white/50 gap-2 p-8">
              <Camera size={32} />
              <span className="text-xs">لا توجد لقطة محفوظة</span>
            </div>
          )}
        </div>
        {alert.has_clip && alert.has_snapshot && (
          <button
            onClick={() => setShowSnapshot((v) => !v)}
            className="text-[11px] font-bold text-thaqib-primary mb-4"
          >
            {showSnapshot ? 'عرض المقطع' : 'عرض اللقطة'}
          </button>
        )}

        {/* Details */}
        <div className="grid grid-cols-2 gap-2 mb-5 text-xs">
          {alert.track_id != null && (
            <Detail label="الطالب" value={`رقم ${alert.track_id}`} />
          )}
          {alert.looking_at != null && (
            <Detail label="ينظر إلى" value={`رقم ${alert.looking_at}`} />
          )}
          {alert.severity && <Detail label="الخطورة" value={alert.severity} />}
          {alert.timestamp && (
            <Detail label="الوقت" value={new Date(alert.timestamp).toLocaleTimeString('en-US', { hour12: false })} />
          )}
        </div>

        {/* Actions */}
        {isReviewed ? (
          <div className="text-center py-3 bg-gray-50 rounded-xl text-xs font-bold text-gray-500">
            تمت المراجعة — {alert.status === 'confirmed' ? 'مؤكد كحالة غش' : 'ملغى'}
          </div>
        ) : (
          <div className="flex gap-3">
            <button
              onClick={onConfirm}
              className="flex-1 py-3 bg-red-500 hover:bg-red-600 text-white rounded-xl font-bold text-sm flex items-center justify-center gap-2 active:scale-95 transition-all"
            >
              <CheckCircle2 size={18} />
              تأكيد الحالة
            </button>
            <button
              onClick={onCancel}
              className="flex-1 py-3 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-xl font-bold text-sm flex items-center justify-center gap-2 active:scale-95 transition-all"
            >
              <XCircle size={18} />
              إلغاء (إنذار خاطئ)
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[#F8F9FE] rounded-xl px-3 py-2">
      <span className="block text-[10px] font-bold text-gray-400 mb-0.5">{label}</span>
      <span className="text-gray-800 font-bold">{value}</span>
    </div>
  );
}
