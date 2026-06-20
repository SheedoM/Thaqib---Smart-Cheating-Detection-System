import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import {
  Bell,
  CheckCircle2,
  Loader2,
  Lock,
  LogOut,
  Mic,
  MonitorSmartphone,
  Save,
  ShieldCheck,
  Smartphone,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { authFetch } from '../../config/api';
import { isInsecureLanContext } from '../../lib/secureContext';

type AlertCueMode = 'sound_vibrate' | 'sound_only' | 'vibrate_only' | 'silent';

interface InvigilatorPreferences {
  alert_cue_mode: AlertCueMode;
  alert_volume: number;
  browser_notifications_enabled: boolean;
  compact_display: boolean;
  large_text: boolean;
}

interface UserProfile {
  username: string;
  full_name: string;
  email: string;
  role: string;
  status: string;
}

const DEFAULT_PREFS: InvigilatorPreferences = {
  alert_cue_mode: 'sound_vibrate',
  alert_volume: 80,
  browser_notifications_enabled: false,
  compact_display: false,
  large_text: false,
};

const cueOptions: { value: AlertCueMode; label: string; description: string }[] = [
  { value: 'sound_vibrate', label: 'صوت واهتزاز', description: 'تنبيه واضح داخل القاعة' },
  { value: 'sound_only', label: 'صوت فقط', description: 'بدون اهتزاز الجهاز' },
  { value: 'vibrate_only', label: 'اهتزاز فقط', description: 'مناسب للوضع الهادئ' },
  { value: 'silent', label: 'صامت', description: 'مرئي فقط بدون صوت أو اهتزاز' },
];

function mergePreferences(data: Partial<InvigilatorPreferences> | null): InvigilatorPreferences {
  return { ...DEFAULT_PREFS, ...(data ?? {}) };
}

function notificationStatus(): 'unsupported' | NotificationPermission {
  if (!('Notification' in window) || typeof window.Notification === 'undefined') {
    return 'unsupported';
  }
  return window.Notification.permission;
}

function canVibrate(): boolean {
  return typeof window.navigator.vibrate === 'function';
}

function FieldGroup({
  icon,
  title,
  children,
}: {
  icon: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-purple-50 text-thaqib-primary flex items-center justify-center">
          {icon}
        </div>
        <h2 className="text-base font-black text-gray-900">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function ToggleRow({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-xl bg-gray-50 px-4 py-3">
      <div>
        <p className="text-sm font-black text-gray-800">{label}</p>
        <p className="mt-0.5 text-[11px] font-bold text-gray-400">{hint}</p>
      </div>
      <button
        type="button"
        aria-pressed={checked}
        onClick={() => onChange(!checked)}
        className={`relative h-7 w-[52px] shrink-0 rounded-full transition-colors ${checked ? 'bg-[#00D261]' : 'bg-gray-300'}`}
      >
        <span
          className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow transition-all ${checked ? 'left-1' : 'left-7'}`}
        />
      </button>
    </div>
  );
}

export default function InvigilatorSettingsPage({ onLogout }: { onLogout: () => void }) {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [prefs, setPrefs] = useState<InvigilatorPreferences>(DEFAULT_PREFS);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deviceNotification, setDeviceNotification] = useState(notificationStatus());
  const [micStatus, setMicStatus] = useState<'idle' | 'checking' | 'ready' | 'blocked'>('idle');
  const [password, setPassword] = useState({ current: '', next: '', confirm: '' });
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    Promise.all([
      authFetch('/api/auth/me').then((res) => (res.ok ? res.json() : null)),
      authFetch('/api/users/me/preferences').then((res) => (res.ok ? res.json() : null)),
    ])
      .then(([profileData, preferencesData]) => {
        if (!mounted) return;
        if (profileData) setProfile(profileData);
        setPrefs(mergePreferences(preferencesData));
        setError(null);
      })
      .catch(() => {
        if (mounted) setError('تعذر تحميل الإعدادات.');
      })
      .finally(() => {
        if (mounted) setIsLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  const updatePrefs = <K extends keyof InvigilatorPreferences>(
    key: K,
    value: InvigilatorPreferences[K],
  ) => {
    setSaved(false);
    setPrefs((current) => ({ ...current, [key]: value }));
  };

  const savePreferences = async () => {
    setIsSaving(true);
    setSaved(false);
    setError(null);
    const response = await authFetch('/api/users/me/preferences', {
      method: 'PUT',
      body: JSON.stringify(prefs),
    }).catch(() => null);
    if (response?.ok) {
      const data = await response.json().catch(() => prefs);
      setPrefs(mergePreferences(data));
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2500);
    } else {
      setError('فشل حفظ الإعدادات.');
    }
    setIsSaving(false);
  };

  const requestNotificationPermission = async () => {
    if (!('Notification' in window) || typeof window.Notification === 'undefined') {
      setDeviceNotification('unsupported');
      return;
    }
    const permission = await window.Notification.requestPermission();
    setDeviceNotification(permission);
  };

  const checkMic = async () => {
    if (isInsecureLanContext() || !window.navigator.mediaDevices?.getUserMedia) {
      setMicStatus('blocked');
      return;
    }
    setMicStatus('checking');
    try {
      const stream = await window.navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      setMicStatus('ready');
    } catch {
      setMicStatus('blocked');
    }
  };

  const playTestAlert = () => {
    if ((prefs.alert_cue_mode === 'sound_vibrate' || prefs.alert_cue_mode === 'vibrate_only') && canVibrate()) {
      window.navigator.vibrate([120, 60, 120]);
    }

    if (prefs.browser_notifications_enabled && deviceNotification === 'granted') {
      new window.Notification('تنبيه تجريبي', { body: 'هذه معاينة لإعدادات تنبيهات المراقب.' });
    }

    if (
      prefs.alert_volume > 0 &&
      (prefs.alert_cue_mode === 'sound_vibrate' || prefs.alert_cue_mode === 'sound_only') &&
      'AudioContext' in window
    ) {
      const AudioContextCtor = window.AudioContext;
      const context = new AudioContextCtor();
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.frequency.value = 880;
      gain.gain.value = prefs.alert_volume / 100;
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start();
      oscillator.stop(context.currentTime + 0.14);
    }
  };

  const changePassword = async (event: FormEvent) => {
    event.preventDefault();
    setPasswordError(null);
    setPasswordMessage(null);
    if (password.next !== password.confirm) {
      setPasswordError('كلمتا المرور غير متطابقتين');
      return;
    }
    if (password.next.length < 8) {
      setPasswordError('كلمة المرور الجديدة يجب أن تكون 8 أحرف على الأقل');
      return;
    }
    setPasswordSaving(true);
    const response = await authFetch('/api/users/me/password', {
      method: 'PUT',
      body: JSON.stringify({
        current_password: password.current,
        new_password: password.next,
      }),
    }).catch(() => null);
    if (response?.ok) {
      setPassword({ current: '', next: '', confirm: '' });
      setPasswordMessage('تم تغيير كلمة المرور');
    } else {
      const body = await response?.json().catch(() => null);
      setPasswordError(body?.detail || 'فشل تغيير كلمة المرور');
    }
    setPasswordSaving(false);
  };

  const notificationLabel =
    deviceNotification === 'unsupported'
      ? 'إشعارات المتصفح غير مدعومة'
      : deviceNotification === 'granted'
        ? 'إشعارات المتصفح مسموحة'
        : deviceNotification === 'denied'
          ? 'إشعارات المتصفح محجوبة'
          : 'إشعارات المتصفح بانتظار الإذن';

  const micLabel =
    isInsecureLanContext()
      ? 'الميكروفون يحتاج HTTPS'
      : micStatus === 'checking'
        ? 'جاري فحص الميكروفون'
        : micStatus === 'ready'
          ? 'الميكروفون جاهز'
          : micStatus === 'blocked'
            ? 'تعذر الوصول للميكروفون'
            : 'جاهز لفحص الميكروفون';

  if (isLoading) {
    return (
      <div className="flex h-[60vh] flex-col items-center justify-center gap-4">
        <Loader2 className="animate-spin text-thaqib-primary" size={36} />
        <p className="text-sm font-bold text-gray-500">جاري تحميل الإعدادات...</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-5 py-6" dir="rtl">
      <div className="mb-6 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-black text-[#2D005F]">الإعدادات</h1>
          <p className="mt-1 text-sm font-bold text-gray-400">تفضيلات الحساب والجهاز لهذا المراقب.</p>
        </div>
        {prefs.alert_cue_mode === 'silent' && (
          <span className="rounded-full bg-gray-900 px-3 py-1 text-[11px] font-black text-white">
            التنبيهات صامتة
          </span>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm font-bold text-red-600">
          {error}
        </div>
      )}

      <div className="space-y-4">
        <FieldGroup title="التنبيهات" icon={<Bell size={20} />}>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {cueOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => updatePrefs('alert_cue_mode', option.value)}
                className={`rounded-xl border p-3 text-right transition-all ${
                  prefs.alert_cue_mode === option.value
                    ? 'border-thaqib-primary bg-purple-50 text-thaqib-primary'
                    : 'border-gray-100 bg-gray-50 text-gray-600'
                }`}
              >
                <span className="block text-sm font-black">{option.label}</span>
                <span className="mt-1 block text-[11px] font-bold text-gray-400">{option.description}</span>
              </button>
            ))}
          </div>

          <label className="block rounded-xl bg-gray-50 px-4 py-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-black text-gray-800">مستوى الصوت</span>
              <span className="text-sm font-black text-thaqib-primary">{prefs.alert_volume}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={prefs.alert_volume}
              disabled={prefs.alert_cue_mode === 'silent' || prefs.alert_cue_mode === 'vibrate_only'}
              onChange={(event) => updatePrefs('alert_volume', Number(event.target.value))}
              className="w-full accent-[#44006E] disabled:opacity-40"
            />
          </label>

          <ToggleRow
            label="إشعارات المتصفح"
            hint="تفضيل حسابي، أما إذن المتصفح فيُدار من هذا الجهاز."
            checked={prefs.browser_notifications_enabled}
            onChange={(value) => updatePrefs('browser_notifications_enabled', value)}
          />

          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              onClick={playTestAlert}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-gray-900 px-4 py-3 text-sm font-black text-white active:scale-[0.98]"
            >
              {prefs.alert_cue_mode === 'silent' ? <VolumeX size={18} /> : <Volume2 size={18} />}
              اختبار التنبيه
            </button>
            <button
              type="button"
              onClick={savePreferences}
              disabled={isSaving}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-thaqib-primary px-4 py-3 text-sm font-black text-white disabled:opacity-60 active:scale-[0.98]"
            >
              {isSaving ? <Loader2 size={18} className="animate-spin" /> : saved ? <CheckCircle2 size={18} /> : <Save size={18} />}
              {saved ? 'تم الحفظ' : 'حفظ الإعدادات'}
            </button>
          </div>
        </FieldGroup>

        <FieldGroup title="جاهزية الجهاز" icon={<Smartphone size={20} />}>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="rounded-xl bg-gray-50 p-4">
              <div className="mb-2 flex items-center gap-2 text-sm font-black text-gray-800">
                <Bell size={16} />
                {notificationLabel}
              </div>
              {deviceNotification !== 'unsupported' && (
                <button
                  type="button"
                  onClick={requestNotificationPermission}
                  className="mt-2 rounded-lg bg-white px-3 py-2 text-xs font-black text-thaqib-primary shadow-sm"
                >
                  طلب الإذن
                </button>
              )}
            </div>
            <div className="rounded-xl bg-gray-50 p-4">
              <div className="mb-2 flex items-center gap-2 text-sm font-black text-gray-800">
                <Mic size={16} />
                {micLabel}
              </div>
              <button
                type="button"
                onClick={checkMic}
                disabled={micStatus === 'checking'}
                className="mt-2 rounded-lg bg-white px-3 py-2 text-xs font-black text-thaqib-primary shadow-sm disabled:opacity-60"
              >
                فحص الميكروفون
              </button>
            </div>
          </div>
        </FieldGroup>

        <FieldGroup title="العرض" icon={<MonitorSmartphone size={20} />}>
          <ToggleRow
            label="عرض مضغوط"
            hint="يقلل المسافات في الشاشات الصغيرة."
            checked={prefs.compact_display}
            onChange={(value) => updatePrefs('compact_display', value)}
          />
          <ToggleRow
            label="نص أكبر"
            hint="يرفع وضوح النصوص أثناء الحركة داخل القاعة."
            checked={prefs.large_text}
            onChange={(value) => updatePrefs('large_text', value)}
          />
        </FieldGroup>

        <FieldGroup title="الحساب والأمان" icon={<ShieldCheck size={20} />}>
          <div className="rounded-xl bg-gray-50 p-4">
            <p className="text-sm font-black text-gray-900">{profile?.full_name || 'المراقب'}</p>
            <p className="mt-1 text-xs font-bold text-gray-500">{profile?.email}</p>
            <p className="mt-1 text-[11px] font-bold text-gray-400">اسم المستخدم: {profile?.username}</p>
          </div>

          <form onSubmit={changePassword} className="space-y-3 rounded-xl bg-gray-50 p-4">
            <div className="flex items-center gap-2 text-sm font-black text-gray-800">
              <Lock size={16} />
              تغيير كلمة المرور
            </div>
            <label className="block">
              <span className="mb-1 block text-xs font-black text-gray-500">كلمة المرور الحالية</span>
              <input
                type="password"
                value={password.current}
                onChange={(event) => setPassword((current) => ({ ...current, current: event.target.value }))}
                className="w-full rounded-xl border border-gray-100 bg-white px-4 py-3 text-sm font-bold outline-none focus:border-thaqib-primary"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-black text-gray-500">كلمة المرور الجديدة</span>
              <input
                type="password"
                value={password.next}
                onChange={(event) => setPassword((current) => ({ ...current, next: event.target.value }))}
                className="w-full rounded-xl border border-gray-100 bg-white px-4 py-3 text-sm font-bold outline-none focus:border-thaqib-primary"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-black text-gray-500">تأكيد كلمة المرور</span>
              <input
                type="password"
                value={password.confirm}
                onChange={(event) => setPassword((current) => ({ ...current, confirm: event.target.value }))}
                className="w-full rounded-xl border border-gray-100 bg-white px-4 py-3 text-sm font-bold outline-none focus:border-thaqib-primary"
              />
            </label>
            {passwordError && <p className="text-xs font-bold text-red-600">{passwordError}</p>}
            {passwordMessage && <p className="text-xs font-bold text-green-600">{passwordMessage}</p>}
            <button
              type="submit"
              disabled={passwordSaving}
              className="w-full rounded-xl bg-gray-900 px-4 py-3 text-sm font-black text-white disabled:opacity-60"
            >
              {passwordSaving ? 'جاري التغيير...' : 'تغيير كلمة المرور'}
            </button>
          </form>

          <button
            type="button"
            onClick={onLogout}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm font-black text-red-600"
          >
            <LogOut size={18} />
            تسجيل الخروج
          </button>
        </FieldGroup>
      </div>
    </div>
  );
}
