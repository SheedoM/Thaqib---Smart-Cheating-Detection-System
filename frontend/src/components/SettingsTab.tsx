import { useState, useEffect } from 'react';
import { authFetch } from '../config/api';

// ── Types ─────────────────────────────────────────────────────────────────────

interface Institution {
  id: string; name: string; code: string | null;
  contact_email: string | null; logo_url: string | null; address: string | null;
}

interface SystemSettings {
  // Video & Archive
  video_quality: number; alert_max_height: number; archive_mode: string;
  // Detection
  detection_interval: number; detection_confidence: number;
  detection_imgsz: number; tools_confidence: number;
  // Tracking & Detection engine
  tracking_max_distance: number; tracking_max_age: number; neighbor_k: number;
  risk_angle_tolerance: number; suspicious_duration_threshold: number;
  reid_match_threshold: number; face_mesh_workers: number;
  // Audio
  audio_whisper_model: string; audio_strict_mode: boolean;
  audio_vad_threshold: number; audio_silence_threshold: number;
  audio_speech_buffer_sec: number; audio_noise_reduction: boolean;
  audio_noise_reduction_strength: number; audio_adaptive_gain: boolean;
  audio_adaptive_vad: boolean; audio_session_recording: boolean;
  audio_episode_recording: boolean; audio_episode_min_sec: number;
  audio_episode_grace_sec: number;
}

const DEFAULT: SystemSettings = {
  video_quality: 75, alert_max_height: 720, archive_mode: 'raw',
  detection_interval: 1.0, detection_confidence: 0.15,
  detection_imgsz: 640, tools_confidence: 0.45,
  tracking_max_distance: 100, tracking_max_age: 30, neighbor_k: 6,
  risk_angle_tolerance: 25.0, suspicious_duration_threshold: 2.0,
  reid_match_threshold: 0.80, face_mesh_workers: 4,
  audio_whisper_model: 'tiny', audio_strict_mode: true,
  audio_vad_threshold: 0.5, audio_silence_threshold: 0.01,
  audio_speech_buffer_sec: 2.5, audio_noise_reduction: true,
  audio_noise_reduction_strength: 0.75, audio_adaptive_gain: true,
  audio_adaptive_vad: true, audio_session_recording: true,
  audio_episode_recording: true, audio_episode_min_sec: 3.0,
  audio_episode_grace_sec: 5.0,
};

// ── Shared sub-components ─────────────────────────────────────────────────────

const inputCls = 'w-full bg-gray-50 border border-gray-200 rounded-2xl py-2.5 px-4 outline-none focus:ring-2 focus:ring-purple-200 focus:border-[#44006E] transition-all font-bold text-sm';

function SliderRow({ label, hint, value, min, max, step = 1, unit = '', leftLabel, rightLabel, onChange }: {
  label: string; hint?: string; value: number; min: number; max: number;
  step?: number; unit?: string; leftLabel?: string; rightLabel?: string;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-start">
        <div>
          <p className="text-sm font-black text-gray-700">{label}</p>
          {hint && <p className="text-[10px] text-gray-400 font-bold mt-0.5">{hint}</p>}
        </div>
        <span className="text-sm font-black text-[#44006E] tabular-nums whitespace-nowrap ml-3">{value}{unit}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(Number(e.target.value))} className="w-full accent-[#44006E]" />
      {(leftLabel || rightLabel) && (
        <div className="flex justify-between text-[10px] text-gray-400 font-bold">
          <span>{leftLabel}</span><span>{rightLabel}</span>
        </div>
      )}
    </div>
  );
}

function Toggle({ label, hint, value, onChange }: {
  label: string; hint?: string; value: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm font-black text-gray-700">{label}</p>
        {hint && <p className="text-[11px] text-gray-400 font-bold mt-0.5">{hint}</p>}
      </div>
      <button type="button" onClick={() => onChange(!value)}
        className={`relative w-12 h-6 rounded-full transition-colors flex-shrink-0 ${value ? 'bg-[#00D261]' : 'bg-gray-300'}`}>
        <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all ${value ? 'left-6' : 'left-0.5'}`} />
      </button>
    </div>
  );
}

function SelectRow({ label, hint, value, options, onChange }: {
  label: string; hint?: string; value: string | number;
  options: { label: string; value: string | number }[]; onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <p className="text-sm font-black text-gray-700">{label}</p>
      {hint && <p className="text-[10px] text-gray-400 font-bold">{hint}</p>}
      <div className="flex gap-2 flex-wrap">
        {options.map(opt => (
          <button key={String(opt.value)} type="button" onClick={() => onChange(String(opt.value))}
            className={`px-4 py-2 rounded-xl text-sm font-black border transition-all ${
              String(value) === String(opt.value)
                ? 'bg-[#44006E] text-white border-[#44006E]'
                : 'bg-gray-50 text-gray-600 border-gray-200 hover:border-[#44006E]'
            }`}>
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function FieldGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-50 rounded-2xl p-4 space-y-4">
      <p className="text-xs font-black text-gray-400 uppercase tracking-widest">{title}</p>
      {children}
    </div>
  );
}

function SaveButton({ saving, saved, label = 'حفظ', onClick }: {
  saving: boolean; saved: boolean; label?: string; onClick?: () => void;
}) {
  return (
    <div className="flex justify-end pt-4 border-t border-gray-100 mt-2">
      <button type={onClick ? 'button' : 'submit'} onClick={onClick} disabled={saving}
        className="bg-[#44006E] text-white px-8 py-3 rounded-2xl font-black text-sm shadow-lg shadow-purple-100 hover:-translate-y-0.5 active:scale-95 transition-all disabled:opacity-60 cursor-pointer flex items-center gap-2 min-w-36 justify-center">
        {saving
          ? <><svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><circle cx="12" cy="12" r="10" strokeOpacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10"/></svg>جاري الحفظ...</>
          : saved ? '✓ تم الحفظ' : label}
      </button>
    </div>
  );
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'institution', label: 'المؤسسة' },
  { id: 'video',       label: 'إعدادات الفيديو' },
  { id: 'tracking',   label: 'التتبع والكشف' },
  { id: 'audio',      label: 'الصوت' },
] as const;
type TabId = typeof TABS[number]['id'];

// ── Main ──────────────────────────────────────────────────────────────────────

export default function SettingsTab() {
  const [activeTab, setActiveTab] = useState<TabId>('institution');

  // Institution
  const [institution, setInstitution] = useState<Institution | null>(null);
  const [instLoading, setInstLoading] = useState(true);
  const [instSaving, setInstSaving] = useState(false);
  const [instSaved, setInstSaved] = useState(false);
  const [instError, setInstError] = useState<string | null>(null);
  const [instForm, setInstForm] = useState({ name: '', contact_email: '', address: '', logo_url: '', code: '' });

  // System settings
  const [sys, setSys] = useState<SystemSettings>(DEFAULT);
  const [sysLoading, setSysLoading] = useState(true);
  const [sysSaving, setSysSaving] = useState(false);
  const [sysSaved, setSysSaved] = useState(false);

  // Password
  const [pw, setPw] = useState({ current: '', next: '', confirm: '' });
  const [pwSaving, setPwSaving] = useState(false);
  const [pwSaved, setPwSaved] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);

  useEffect(() => {
    authFetch('/api/institutions/').then(r => r.ok ? r.json() : [])
      .then((list: Institution[]) => {
        if (list.length > 0) {
          const i = list[0];
          setInstitution(i);
          setInstForm({ name: i.name || '', contact_email: i.contact_email || '', address: i.address || '', logo_url: i.logo_url || '', code: i.code || '' });
        }
      }).finally(() => setInstLoading(false));

    authFetch('/api/settings/').then(r => r.ok ? r.json() : null)
      .then((d: SystemSettings | null) => { if (d) setSys(d); })
      .finally(() => setSysLoading(false));
  }, []);

  const set = <K extends keyof SystemSettings>(key: K, value: SystemSettings[K]) =>
    setSys(p => ({ ...p, [key]: value }));

  const saveInstitution = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!institution) return;
    setInstSaving(true); setInstError(null); setInstSaved(false);
    const res = await authFetch(`/api/institutions/${institution.id}`, {
      method: 'PUT',
      body: JSON.stringify({ name: instForm.name, contact_email: instForm.contact_email || null, address: instForm.address || null, logo_url: instForm.logo_url || null, code: instForm.code || null }),
    }).catch(() => null);
    if (res?.ok) { setInstSaved(true); setTimeout(() => setInstSaved(false), 3000); }
    else setInstError('فشل الحفظ');
    setInstSaving(false);
  };

  const saveSys = async () => {
    setSysSaving(true); setSysSaved(false);
    const res = await authFetch('/api/settings/', { method: 'PUT', body: JSON.stringify(sys) }).catch(() => null);
    if (res?.ok) { setSysSaved(true); setTimeout(() => setSysSaved(false), 3000); }
    setSysSaving(false);
  };

  const changePassword = async (e: React.FormEvent) => {
    e.preventDefault(); setPwError(null); setPwSaved(false);
    if (pw.next !== pw.confirm) { setPwError('كلمتا المرور غير متطابقتين'); return; }
    if (pw.next.length < 8) { setPwError('8 أحرف على الأقل'); return; }
    setPwSaving(true);
    const res = await authFetch('/api/users/me/password', {
      method: 'PUT', body: JSON.stringify({ current_password: pw.current, new_password: pw.next }),
    }).catch(() => null);
    if (res?.ok) { setPwSaved(true); setPw({ current: '', next: '', confirm: '' }); setTimeout(() => setPwSaved(false), 3000); }
    else { const e = await res?.json().catch(() => null); setPwError(e?.detail || 'فشل تغيير كلمة المرور'); }
    setPwSaving(false);
  };

  // ── Tab renderers ─────────────────────────────────────────────────────────

  const renderInstitution = () => (
    <form onSubmit={saveInstitution} className="space-y-5">
      {instLoading
        ? [1,2,3].map(i => <div key={i} className="h-10 bg-gray-100 rounded-2xl animate-pulse" />)
        : <>
          <FieldGroup title="الهوية">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-black text-gray-500 mb-1.5">اسم المؤسسة *</label>
                <input required className={inputCls} value={instForm.name} onChange={e => setInstForm(p => ({ ...p, name: e.target.value }))} />
              </div>
              <div>
                <label className="block text-xs font-black text-gray-500 mb-1.5">الرمز</label>
                <input className={inputCls} placeholder="UNIV-01" value={instForm.code} onChange={e => setInstForm(p => ({ ...p, code: e.target.value }))} />
              </div>
            </div>
          </FieldGroup>
          <FieldGroup title="التواصل">
            <div>
              <label className="block text-xs font-black text-gray-500 mb-1.5">البريد الإلكتروني</label>
              <input className={inputCls} type="email" value={instForm.contact_email} onChange={e => setInstForm(p => ({ ...p, contact_email: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-black text-gray-500 mb-1.5">العنوان</label>
              <input className={inputCls} value={instForm.address} onChange={e => setInstForm(p => ({ ...p, address: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-black text-gray-500 mb-1.5">رابط الشعار</label>
              <input className={inputCls} placeholder="https://..." value={instForm.logo_url} onChange={e => setInstForm(p => ({ ...p, logo_url: e.target.value }))} />
            </div>
          </FieldGroup>
          <FieldGroup title="الأمان">
            <div>
              <label className="block text-xs font-black text-gray-500 mb-1.5">كلمة المرور الحالية</label>
              <input type="password" className={inputCls} value={pw.current} onChange={e => setPw(p => ({ ...p, current: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-black text-gray-500 mb-1.5">كلمة المرور الجديدة</label>
              <input type="password" className={inputCls} value={pw.next} onChange={e => setPw(p => ({ ...p, next: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-black text-gray-500 mb-1.5">تأكيد كلمة المرور</label>
              <input type="password" className={inputCls} value={pw.confirm} onChange={e => setPw(p => ({ ...p, confirm: e.target.value }))} />
            </div>
            {pwError && <p className="text-red-500 text-xs font-bold">{pwError}</p>}
            {pwSaved && <p className="text-green-600 text-xs font-bold">✓ تم تغيير كلمة المرور</p>}
            <div className="flex justify-end">
              <button type="button" onClick={changePassword} disabled={pwSaving}
                className="bg-gray-800 text-white px-5 py-2 rounded-xl font-black text-sm hover:-translate-y-0.5 transition-all disabled:opacity-60">
                {pwSaving ? 'جاري...' : 'تغيير كلمة المرور'}
              </button>
            </div>
          </FieldGroup>
          {instError && <p className="text-red-500 text-sm font-bold">{instError}</p>}
          {instSaved && <p className="text-green-600 text-sm font-bold">✓ تم حفظ بيانات المؤسسة</p>}
          <SaveButton saving={instSaving} saved={instSaved} label="حفظ بيانات المؤسسة" />
        </>
      }
    </form>
  );

  const renderVideo = () => (
    <div className="space-y-5">
      {sysLoading ? <div className="h-40 bg-gray-100 rounded-2xl animate-pulse" /> : <>

        <FieldGroup title="كشف الأشخاص (YOLO)">
          <SliderRow label="فترة الكشف" unit="s" value={sys.detection_interval} min={0.1} max={5} step={0.1}
            hint="الفاصل الزمني بين تشغيلات YOLO — أعلى = FPS أسرع وكشف أقل"
            leftLabel="0.1s (مستمر)" rightLabel="5s (اقتصادي)"
            onChange={v => set('detection_interval', v)} />
          <SliderRow label="حد ثقة كشف الأشخاص" unit="%" value={Math.round(sys.detection_confidence * 100)} min={5} max={95} step={5}
            leftLabel="5% (حساس)" rightLabel="95% (صارم)"
            onChange={v => set('detection_confidence', v / 100)} />
          <SelectRow label="دقة الاستدلال (imgsz)"
            hint="640 = أسرع · 1280 = أدق لكاميرات بعيدة"
            value={sys.detection_imgsz}
            options={[{ label: '320 — سريع جداً', value: 320 }, { label: '640 — متوازن', value: 640 }, { label: '1280 — دقيق', value: 1280 }]}
            onChange={v => set('detection_imgsz', Number(v))} />
          <SliderRow label="حد ثقة كشف الأدوات" unit="%" value={Math.round(sys.tools_confidence * 100)} min={10} max={95} step={5}
            leftLabel="حساس" rightLabel="صارم"
            onChange={v => set('tools_confidence', v / 100)} />
        </FieldGroup>
        <SaveButton saving={sysSaving} saved={sysSaved} onClick={saveSys} />
      </>}
    </div>
  );

  const renderTracking = () => (
    <div className="space-y-5">
      {sysLoading ? <div className="h-40 bg-gray-100 rounded-2xl animate-pulse" /> : <>
        <FieldGroup title="التتبع">
          <SliderRow label="أقصى مسافة تتبع" unit="px" value={sys.tracking_max_distance} min={20} max={300} step={10}
            hint="أقصى مسافة (بكسل) لربط كشف جديد بمسار موجود"
            leftLabel="20 (دقيق)" rightLabel="300 (مرن)"
            onChange={v => set('tracking_max_distance', v)} />
          <SliderRow label="عمر المسار الأقصى" unit=" إطار" value={sys.tracking_max_age} min={5} max={150} step={5}
            hint="إطارات قبل حذف مسار مفقود — 30 إطار ≈ ثانية واحدة"
            leftLabel="5 (سريع)" rightLabel="150 (صبور)"
            onChange={v => set('tracking_max_age', v)} />
          <SliderRow label="عدد الجيران المقارَنين (K)" value={sys.neighbor_k} min={2} max={15}
            hint="عدد الطلاب المجاورين الذين تُقارَن نظرة الطالب بأوراقهم"
            leftLabel="2" rightLabel="15"
            onChange={v => set('neighbor_k', v)} />
        </FieldGroup>
        <FieldGroup title="تقييم الغش (Gaze)">
          <SliderRow label="زاوية التسامح" unit="°" value={sys.risk_angle_tolerance} min={5} max={60} step={0.5}
            hint="الزاوية الأقصى بين اتجاه النظر وورقة الطالب المجاور لتسجيلها كمشبوهة"
            leftLabel="5° (صارم)" rightLabel="60° (متساهل)"
            onChange={v => set('risk_angle_tolerance', v)} />
          <SliderRow label="مدة الشك المطلوبة" unit="s" value={sys.suspicious_duration_threshold} min={0.5} max={10} step={0.5}
            hint="ثواني يجب أن يستمر فيها النظر المشبوه قبل إطلاق التنبيه"
            leftLabel="0.5s (حساس)" rightLabel="10s (متساهل)"
            onChange={v => set('suspicious_duration_threshold', v)} />
        </FieldGroup>
        <FieldGroup title="Re-ID والأداء">
          <SliderRow label="حد تطابق Re-ID" unit="%" value={Math.round(sys.reid_match_threshold * 100)} min={50} max={99} step={1}
            hint="حد التشابه لمطابقة طالب معاد ظهوره"
            leftLabel="50% (مرن)" rightLabel="99% (صارم)"
            onChange={v => set('reid_match_threshold', v / 100)} />
          <SliderRow label="عمليات MediaPipe المتوازية" unit="" value={sys.face_mesh_workers} min={1} max={8}
            hint="أكثر عمليات = معالجة أسرع لكن RAM أعلى"
            leftLabel="1 (أبطأ)" rightLabel="8 (أسرع)"
            onChange={v => set('face_mesh_workers', v)} />
        </FieldGroup>
        <SaveButton saving={sysSaving} saved={sysSaved} onClick={saveSys} />
      </>}
    </div>
  );

  const renderAudio = () => (
    <div className="space-y-5">
      {sysLoading ? <div className="h-40 bg-gray-100 rounded-2xl animate-pulse" /> : <>
        <FieldGroup title="محرك التعرف (Whisper)">
          <SelectRow label="حجم نموذج Whisper"
            hint="أصغر = أسرع لكن أقل دقة · أكبر = أدق لكن أبطأ"
            value={sys.audio_whisper_model}
            options={[
              { label: 'tiny — أسرع', value: 'tiny' },
              { label: 'base', value: 'base' },
              { label: 'small — موصى به للعربية', value: 'small' },
              { label: 'medium — أدق', value: 'medium' },
            ]}
            onChange={v => set('audio_whisper_model', v)} />
          <Toggle label="الوضع الصارم" hint="أي كلام = تنبيه (امتحان صامت). إيقافه = الكشف بالكلمات المفتاحية فقط"
            value={sys.audio_strict_mode} onChange={v => set('audio_strict_mode', v)} />
        </FieldGroup>
        <FieldGroup title="كشف الصوت (VAD)">
          <SliderRow label="حد ثقة VAD" unit="%" value={Math.round(sys.audio_vad_threshold * 100)} min={10} max={90} step={5}
            hint="Silero VAD: ثقة أعلى = أقل إيجابيات زائفة"
            leftLabel="10% (حساس)" rightLabel="90% (صارم)"
            onChange={v => set('audio_vad_threshold', v / 100)} />
          <SliderRow label="حد الصمت (RMS)" unit="" value={sys.audio_silence_threshold} min={0} max={0.1} step={0.005}
            hint="مستوى الطاقة تحته يُعتبر صمتاً"
            leftLabel="0 (كل شيء)" rightLabel="0.1 (صارم)"
            onChange={v => set('audio_silence_threshold', v)} />
          <SliderRow label="مخزن الكلام قبل الإرسال إلى Whisper" unit="s" value={sys.audio_speech_buffer_sec} min={0.5} max={10} step={0.5}
            hint="ثواني كلام تتراكم قبل استدعاء Whisper — أكثر = دقة أعلى وكمون أعلى"
            leftLabel="0.5s" rightLabel="10s"
            onChange={v => set('audio_speech_buffer_sec', v)} />
          <Toggle label="تكييف عتبة VAD تلقائياً"
            hint="يتعلم مستوى الضجيج تلقائياً ويضبط العتبة"
            value={sys.audio_adaptive_vad} onChange={v => set('audio_adaptive_vad', v)} />
        </FieldGroup>
        <FieldGroup title="تحسين الصوت">
          <Toggle label="تقليل الضجيج (Noise Reduction)"
            hint="يُقلل ضجيج الغرفة والتكييف قبل التعرف"
            value={sys.audio_noise_reduction} onChange={v => set('audio_noise_reduction', v)} />
          {sys.audio_noise_reduction && (
            <SliderRow label="قوة تقليل الضجيج" unit="%" value={Math.round(sys.audio_noise_reduction_strength * 100)} min={10} max={100} step={5}
              leftLabel="10% (خفيف)" rightLabel="100% (قوي)"
              onChange={v => set('audio_noise_reduction_strength', v / 100)} />
          )}
          <Toggle label="Adaptive Gain" hint="يُعوّض الميكروفونات ذات الحساسيات المختلفة"
            value={sys.audio_adaptive_gain} onChange={v => set('audio_adaptive_gain', v)} />
        </FieldGroup>
        <FieldGroup title="التسجيل والأرشيف">
          <Toggle label="تسجيل كامل لجلسة الصوت"
            hint="يسجّل كل الميكروفونات طوال الامتحان للمراجعة اللاحقة"
            value={sys.audio_session_recording} onChange={v => set('audio_session_recording', v)} />
          <Toggle label="تسجيل حلقات الغش المستمر"
            hint="يحفظ مقطع واحد طويل لكل حادثة غش متواصلة"
            value={sys.audio_episode_recording} onChange={v => set('audio_episode_recording', v)} />
          {sys.audio_episode_recording && <>
            <SliderRow label="الحد الأدنى لمدة الحادثة" unit="s" value={sys.audio_episode_min_sec} min={1} max={30} step={0.5}
              hint="ما دون هذا يُعتبر خطأ / ضجيج"
              leftLabel="1s" rightLabel="30s"
              onChange={v => set('audio_episode_min_sec', v)} />
            <SliderRow label="فترة الانتظار بعد آخر تنبيه" unit="s" value={sys.audio_episode_grace_sec} min={1} max={30} step={0.5}
              hint="إذا لم يأتِ تنبيه جديد خلال هذه المدة، تُغلق الحادثة وتُحفظ"
              leftLabel="1s" rightLabel="30s"
              onChange={v => set('audio_episode_grace_sec', v)} />
          </>}
        </FieldGroup>
        <SaveButton saving={sysSaving} saved={sysSaved} onClick={saveSys} />
      </>}
    </div>
  );

  const tabContent: Record<TabId, () => React.ReactNode> = {
    institution: renderInstitution,
    video: renderVideo,
    tracking: renderTracking,
    audio: renderAudio,
  };

  return (
    <div className="p-6 max-w-3xl mx-auto" dir="rtl">
      <div className="flex items-center gap-4 mb-6">
        <div className="w-1.5 h-10 bg-[#44006E] rounded-full" />
        <h2 className="text-2xl font-black text-[#2D005F]">الإعدادات</h2>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-2xl mb-6">
        {TABS.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={`flex-1 py-2.5 px-3 rounded-xl text-sm font-black transition-all whitespace-nowrap
              ${activeTab === tab.id ? 'bg-white text-[#44006E] shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="bg-white rounded-3xl border border-gray-100 shadow-sm p-6">
        {tabContent[activeTab]()}
      </div>
    </div>
  );
}
