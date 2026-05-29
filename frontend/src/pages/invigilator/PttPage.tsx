import { Mic, Shield, Radio, Volume2 } from 'lucide-react';
import { useInvigilatorPtt } from '../../hooks/useInvigilatorPtt';
import { isInsecureLanContext } from '../../lib/secureContext';

export default function PttPage() {
  const ptt = useInvigilatorPtt({ autoConnect: true });
  const { isTransmitting, startTransmission, stopTransmission, isConnected, connect, incidentCards } = ptt;
  const insecureLan = isInsecureLanContext();

  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh] px-8 text-center">
      <div className="relative mb-12">
        {/* Pulsing circles behind icon */}
        {isTransmitting && (
          <>
            <div className="absolute inset-0 bg-red-400 rounded-full animate-ping opacity-25"></div>
            <div className="absolute inset-0 bg-red-400 rounded-full animate-ping opacity-20 delay-300"></div>
          </>
        )}
        <div className={`h-32 w-32 rounded-full flex items-center justify-center shadow-2xl transition-all duration-300 ${
          isTransmitting ? 'bg-red-500 scale-110 shadow-red-500/30' : 'bg-white shadow-purple-500/10 border border-gray-100'
        }`}>
          <Radio size={48} className={isTransmitting ? 'text-white' : 'text-thaqib-primary'} />
        </div>
      </div>

      <h2 className="text-2xl font-bold text-gray-900 mb-2">غرفة الاتصال</h2>
      <p className="text-gray-500 mb-12 max-w-xs">
        {isConnected 
          ? 'اضغط مطولاً على الزر أدناه للتحدث مع غرفة العمليات.' 
          : 'جاري الاتصال بخادم الصوت...'}
      </p>
      {insecureLan && (
        <div className="mb-6 w-full max-w-sm rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-right text-xs font-bold text-amber-800">
          Microphone requires HTTPS on mobile. افتح الرابط عبر HTTPS أو استخدم localhost على نفس الجهاز.
        </div>
      )}
      {!isConnected && (
        <button
          onClick={() => void connect()}
          className="mb-6 px-5 py-2 rounded-xl bg-[#44006E] text-white font-bold"
        >
          إعادة الاتصال
        </button>
      )}

      {incidentCards.length > 0 && (
        <div className="w-full max-w-md mb-8 space-y-3">
          {incidentCards.map((incident) => (
            <div key={incident.alert_id} className="bg-red-50 border border-red-100 rounded-2xl p-4 text-right">
              <p className="text-sm font-black text-red-700">{incident.event_type || 'حالة مؤكدة'}</p>
              <p className="text-xs text-gray-500 mt-1">
                {incident.timestamp ? new Date(incident.timestamp).toLocaleString('ar-EG') : 'الآن'}
              </p>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 w-full max-w-xs mb-12">
        <div className="bg-white p-4 rounded-2xl border border-gray-100 shadow-sm flex flex-col items-center">
          <Shield size={20} className="text-green-500 mb-2" />
          <span className="text-[10px] font-bold text-gray-400 uppercase">الحالة</span>
          <span className="text-sm font-bold text-gray-900">{isConnected ? 'متصل' : 'جارِ الربط'}</span>
        </div>
        <div className="bg-white p-4 rounded-2xl border border-gray-100 shadow-sm flex flex-col items-center">
          <Volume2 size={20} className="text-thaqib-primary mb-2" />
          <span className="text-[10px] font-bold text-gray-400 uppercase">الميكروفون</span>
          <span className="text-sm font-bold text-gray-900">
            {ptt.micState === 'blocked' ? 'محجوب' : ptt.micState === 'ready' ? 'جاهز' : ptt.micState === 'requesting' ? 'طلب صلاحية' : 'لم يبدأ'}
          </span>
        </div>
      </div>
      <p className="mb-5 min-h-5 max-w-sm text-xs font-bold text-gray-500">{ptt.statusText}</p>

      <button 
        onMouseDown={() => startTransmission()}
        onMouseUp={() => stopTransmission()}
        onTouchStart={() => startTransmission()}
        onTouchEnd={() => stopTransmission()}
        disabled={!isConnected}
        className={`w-full max-w-xs aspect-square rounded-[40px] flex flex-col items-center justify-center gap-4 transition-all active:scale-95 shadow-2xl disabled:opacity-50 ${
          isTransmitting 
            ? 'bg-red-500 shadow-red-500/40 translate-y-1' 
            : 'bg-thaqib-primary shadow-purple-900/20 hover:bg-thaqib-primary-dark'
        }`}
      >
        <Mic size={40} className="text-white" />
        <span className="text-white font-bold text-lg">
          {isTransmitting ? 'تحدث الآن...' : 'اضغط للتحدث'}
        </span>
      </button>

      {isTransmitting && (
        <p className="mt-8 text-red-500 font-bold animate-pulse text-sm">جاري الإرسال...</p>
      )}
    </div>
  );
}
