import { useState, useEffect } from 'react';
import { authFetch } from '../config/api';

// ── Types ─────────────────────────────────────────────────────────────────────

interface Institution {
  id: string;
  name: string;
  code: string | null;
  contact_email: string | null;
  logo_url: string | null;
  address: string | null;
}

interface SystemSettings {
  // Video & Archive
  video_quality: number;
  alert_max_height: number;
  archive_mode: string;
  // Detection
  detection_interval: number;
  detection_confidence: number;
  detection_imgsz: number;
  tools_confidence: number;
  object_detection_enabled: boolean;
  // Tracking
  tracking_max_distance: number;
  tracking_max_age: number;
  neighbor_k: number;
  // Cheating evaluation
  gaze_sensitivity: number;
  risk_angle_tolerance: number;
  suspicious_duration_threshold: number;
  suspicious_match_ratio: number;
  // Audio
  audio_sensitivity: number;
  alert_cooldown_seconds: number;
  // Re-ID
  reid_match_threshold: number;
  // Performance
  face_mesh_workers: number;
}

const DEFAULT_SETTINGS: SystemSettings = {
  video_quality: 75,
  alert_max_height: 720,
  archive_mode: 'raw',
  detection_interval: 1.0,
  detection_confidence: 0.15,
  detection_imgsz: 640,
  tools_confidence: 0.45,
  object_detection_enabled: true,
  tracking_max_distance: 100,
  tracking_max_age: 30,
  neighbor_k: 6,
  gaze_sensitivity: 70,
  risk_angle_tolerance: 25.0,
  suspicious_duration_threshold: 2.0,
  suspicious_match_ratio: 0.7,
  audio_sensitivity: 65,
  alert_cooldown_seconds: 30,
  reid_match_threshold: 0.80,
  face_mesh_workers: 4,
};

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionHeader({ icon, color, title }: { icon: React.ReactNode; color: string; title: string }) {
  return (
    <h3 className="text-lg font-black text-[#2D005F] mb-5 flex items-center gap-2">
      <span className={`w-7 h-7 ${color} rounded-xl flex items-center justify-center`}>{icon}</span>
      {title}
    </h3>
  );
}

function SliderRow({
  label, hint, value, min, max, step = 1, unit = '',
  leftLabel, rightLabel, onChange,
}: {
  label: string; hint?: string; value: number; min: number; max: number;
  step?: number; unit?: string; leftLabel?: string; rightLabel?: string;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="flex justify-between items-center mb-1.5">
        <div>
          <span className="text-sm font-black text-gray-700">{label}</span>
          {hint && <p className="text-[10px] text-gray-400 font-bold mt-0.5">{hint}</p>}
        </div>
        <span className="text-sm font-black text-[#44006E] tabular-nums">{value}{unit}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full accent-[#44006E]" />
      {(leftLabel || rightLabel) && (
        <div className="flex justify-between text-[10px] text-gray-400 mt-0.5 font-bold">
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
    <div className="flex items-center justify-between bg-gray-50 rounded-2xl px-4 py-3">
      <div>
        <p className="text-sm font-black text-gray-700">{label}</p>
        {hint && <p className="text-[11px] text-gray-400 font-bold mt-0.5">{hint}</p>}
      </div>
      <button type="button" onClick={() => onChange(!value)}
        className={`relative w-12 h-6 rounded-full transition-colors ${value ? 'bg-[#00D261]' : 'bg-gray-300'}`}>
        <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all ${value ? 'left-6' : 'left-0.5'}`} />
      </button>
    </div>
  );
}

function SelectRow({ label, hint, value, options, onChange }: {
  label: string; hint?: string; value: string | number;
  options: { label: string; value: string | number }[];
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="block text-xs font-black text-gray-500 mb-1.5">{label}</label>
      {hint && <p className="text-[10px] text-gray-400 font-bold mb-1">{hint}</p>}
      <div className="flex gap-2 flex-wrap">
        {options.map(opt => (
          <button key={String(opt.value)} type="button"
            onClick={() => onChange(String(opt.value))}
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

function SaveBar({ saving, saved, onClick }: { saving: boolean; saved: boolean; onClick: () => void }) {
  return (
    <div className="flex justify-end pt-4 border-t border-gray-100 mt-4">
      <button onClick={onClick} disabled={saving}
        className="bg-[#44006E] text-white px-8 py-3 rounded-2xl font-black text-sm shadow-lg shadow-purple-100 hover:-translate-y-0.5 active:scale-95 transition-all disabled:opacity-60 cursor-pointer flex items-center gap-2">
        {saving ? (
          <><svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
            <circle cx="12" cy="12" r="10" strokeOpacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10"/>
          </svg>جاري الحفظ...</>
        ) : saved ? '✓ تم الحفظ' : 'حفظ الإعدادات'}
      </button>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function SettingsTab() {
  const inputCls = 'w-full bg-gray-50 border border-gray-200 rounded-2xl py-2.5 px-4 outline-none focus:ring-2 focus:ring-purple-200 focus:border-[#44006E] transition-all font-bold text-sm';

  // ── Institution ──────────────────────────────────────────────────────────────
  const [institution, setInstitution] = useState<Institution | null>(null);
  const [instLoading, setInstLoading] = useState(true);
  const [instSaving, setInstSaving] = useState(false);
  const [instError, setInstError] = useState<string | null>(null);
  const [instSuccess, setInstSuccess] = useState(false);
  const [instForm, setInstForm] = useState({ name: '', contact_email: '', address: '', logo_url: '', code: '' });

  // ── System settings ──────────────────────────────────────────────────────────
  const [sys, setSys] = useState<SystemSettings>(DEFAULT_SETTINGS);
  const [sysLoading, setSysLoading] = useState(true);
  const [sysSaving, setSysSaving] = useState(false);
  const [sysSaved, setSysSaved] = useState(false);

  // ── Password ─────────────────────────────────────────────────────────────────
  const [pwForm, setPwForm] = useState({ current: '', next: '', confirm: '' });
  const [pwSaving, setPwSaving] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSuccess, setPwSuccess] = useState(false);

  // ── Load data ────────────────────────────────────────────────────────────────
  useEffect(() => {
    // Institution
    authFetch('/api/institutions/').then(r => r.ok ? r.json() : [])
      .then((list: Institution[]) => {
        if (list.length > 0) {
          const i = list[0];
          setInstitution(i);
          setInstForm({ name: i.name || '', contact_email: i.contact_email || '', address: i.address || '', logo_url: i.logo_url || '', code: i.code || '' });
        }
      }).finally(() => setInstLoading(false));

    // System settings
    authFetch('/api/settings/').then(r => r.ok ? r.json() : null)
      .then((data: SystemSettings | null) => { if (data) setSys(data); })
      .finally(() => setSysLoading(false));
  }, []);

  // ── Save institution ─────────────────────────────────────────────────────────
  const saveInstitution = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!institution) return;
    setInstSaving(true); setInstError(null); setInstSuccess(false);
    try {
      const res = await authFetch(`/api/institutions/${institution.id}`, {
        method: 'PUT',
        body: JSON.stringify({ name: instForm.name, contact_email: instForm.contact_email || null, address: instForm.address || null, logo_url: instForm.logo_url || null, code: instForm.code || null }),
      });
      if (res.ok) { setInstSuccess(true); setTimeout(() => setInstSuccess(false), 3000); }
      else { const e = await res.json().catch(() => ({ detail: `خطأ ${res.status}` })); setInstError(typeof e.detail === 'string' ? e.detail : 'فشل الحفظ'); }
    } catch { setInstError('تعذر الاتصال بالسيرفر'); }
    finally { setInstSaving(false); }
  };

  // ── Save system settings ─────────────────────────────────────────────────────
  const saveSystemSettings = async () => {
    setSysSaving(true); setSysSaved(false);
    try {
      const res = await authFetch('/api/settings/', { method: 'PUT', body: JSON.stringify(sys) });
      if (res.ok) { setSysSaved(true); setTimeout(() => setSysSaved(false), 3000); }
    } catch { /* silent */ }
    finally { setSysSaving(false); }
  };

  // ── Change password ──────────────────────────────────────────────────────────
  const changePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwError(null); setPwSuccess(false);
    if (pwForm.next !== pwForm.confirm) { setPwError('كلمتا المرور غير متطابقتين'); return; }
    if (pwForm.next.length < 8) { setPwError('كلمة المرور يجب أن تكون 8 أحرف على الأقل'); return; }
    setPwSaving(true);
    try {
      const res = await authFetch('/api/users/me/password', { method: 'PUT', body: JSON.stringify({ current_password: pwForm.current, new_password: pwForm.next }) });
      if (res.ok) { setPwSuccess(true); setPwForm({ current: '', next: '', confirm: '' }); setTimeout(() => setPwSuccess(false), 3000); }
      else { const e = await res.json().catch(() => ({ detail: `خطأ ${res.status}` })); setPwError(typeof e.detail === 'string' ? e.detail : 'فشل تغيير كلمة المرور'); }
    } catch { setPwError('تعذر الاتصال بالسيرفر'); }
    finally { setPwSaving(false); }
  };

  const set = (key: keyof SystemSettings, value: number | boolean | string) =>
    setSys(p => ({ ...p, [key]: value }));

  return (
    <div className="p-8 max-w-4xl mx-auto" dir="rtl">
      {/* Header */}
      <div className="flex items-center gap-4 mb-10">
        <div className="w-1.5 h-10 bg-[#44006E] rounded-full" />
        <h2 className="text-3xl font-black text-[#2D005F]">الإعدادات</h2>
      </div>

      <div className="space-y-8">

        {/* ── 1. Institution ──────────────────────────────────────────── */}
        <section className="bg-white rounded-3xl border border-gray-100 shadow-sm p-7">
          <SectionHeader
            color="bg-purple-100"
            icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#44006E" strokeWidth="2.5"><path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 14v3M12 14v3M16 14v3"/></svg>}
            title="بيانات المؤسسة"
          />
          {instLoading ? (
            <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-10 bg-gray-100 rounded-2xl animate-pulse" />)}</div>
          ) : (
            <form onSubmit={saveInstitution} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-black text-gray-500 mb-1.5">اسم المؤسسة *</label>
                  <input required className={inputCls} value={instForm.name} onChange={e => setInstForm(p => ({ ...p, name: e.target.value }))} />
                </div>
                <div>
                  <label className="block text-xs font-black text-gray-500 mb-1.5">الرمز / الكود</label>
                  <input className={inputCls} placeholder="مثال: UNIV-01" value={instForm.code} onChange={e => setInstForm(p => ({ ...p, code: e.target.value }))} />
                </div>
                <div>
                  <label className="block text-xs font-black text-gray-500 mb-1.5">البريد الإلكتروني</label>
                  <input className={inputCls} type="email" value={instForm.contact_email} onChange={e => setInstForm(p => ({ ...p, contact_email: e.target.value }))} />
                </div>
                <div>
                  <label className="block text-xs font-black text-gray-500 mb-1.5">رابط الشعار</label>
                  <input className={inputCls} placeholder="https://..." value={instForm.logo_url} onChange={e => setInstForm(p => ({ ...p, logo_url: e.target.value }))} />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-xs font-black text-gray-500 mb-1.5">العنوان</label>
                  <input className={inputCls} value={instForm.address} onChange={e => setInstForm(p => ({ ...p, address: e.target.value }))} />
                </div>
              </div>
              {instError && <div className="bg-red-50 border border-red-200 text-red-600 rounded-2xl px-4 py-3 text-sm font-bold">{instError}</div>}
              {instSuccess && <div className="bg-green-50 border border-green-200 text-green-700 rounded-2xl px-4 py-3 text-sm font-bold">✓ تم الحفظ بنجاح</div>}
              <div className="flex justify-end pt-2">
                <button type="submit" disabled={instSaving}
                  className="bg-[#44006E] text-white px-8 py-3 rounded-2xl font-black text-sm shadow-lg shadow-purple-100 hover:-translate-y-0.5 active:scale-95 transition-all disabled:opacity-60 cursor-pointer flex items-center gap-2">
                  {instSaving ? 'جاري الحفظ...' : 'حفظ التغييرات'}
                </button>
              </div>
            </form>
          )}
        </section>

        {/* ── 2. Video & Archive ──────────────────────────────────────── */}
        <section className="bg-white rounded-3xl border border-gray-100 shadow-sm p-7">
          <SectionHeader
            color="bg-indigo-100"
            icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" strokeWidth="2.5"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>}
            title="إعدادات الفيديو والأرشفة"
          />
          {sysLoading ? <div className="h-32 bg-gray-100 rounded-2xl animate-pulse" /> : (
            <div className="space-y-5">
              <SliderRow
                label="جودة ملفات الفيديو المحفوظة" unit="%" value={sys.video_quality} min={30} max={100} step={5}
                hint="50 = جودة منخفضة (ملفات صغيرة) · 75 = متوازن · 90 = جودة عالية"
                leftLabel="ملفات أصغر" rightLabel="جودة أعلى"
                onChange={v => set('video_quality', v)}
              />
              <SliderRow
                label="الحد الأقصى لارتفاع مقاطع التنبيه" unit="px" value={sys.alert_max_height} min={0} max={2160} step={360}
                hint="0 = بدون تصغير (الدقة الأصلية) · 720 = HD"
                leftLabel="0 (أصلي)" rightLabel="2160 (4K)"
                onChange={v => set('alert_max_height', v)}
              />
              <SelectRow
                label="وضع الأرشفة (Archive Mode)"
                hint="raw = لقطات نظيفة بدون تعليقات · annotated = مع صناديق التتبع والتعليقات"
                value={sys.archive_mode}
                options={[{ label: 'raw — تسجيل نظيف', value: 'raw' }, { label: 'annotated — مع التعليقات', value: 'annotated' }]}
                onChange={v => set('archive_mode', v)}
              />
            </div>
          )}
          <SaveBar saving={sysSaving} saved={sysSaved} onClick={saveSystemSettings} />
        </section>

        {/* ── 3. Detection ────────────────────────────────────────────── */}
        <section className="bg-white rounded-3xl border border-gray-100 shadow-sm p-7">
          <SectionHeader
            color="bg-blue-100"
            icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0984E3" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>}
            title="إعدادات الكشف (Detection)"
          />
          {sysLoading ? <div className="h-48 bg-gray-100 rounded-2xl animate-pulse" /> : (
            <div className="space-y-5">
              <SliderRow
                label="فترة الكشف (ثانية)" unit="s" value={sys.detection_interval} min={0.1} max={5} step={0.1}
                hint="الفاصل الزمني بين تشغيلات YOLO الكاملة — أعلى = أسرع FPS"
                leftLabel="0.1s (سريع جداً)" rightLabel="5s (أبطأ)"
                onChange={v => set('detection_interval', v)}
              />
              <SliderRow
                label="حد الثقة في كشف الأشخاص" unit="%" value={Math.round(sys.detection_confidence * 100)} min={5} max={95} step={5}
                hint="أقل = يكشف أكثر (تحذيرات زائفة أكثر)"
                leftLabel="5% (حساس جداً)" rightLabel="95% (صارم)"
                onChange={v => set('detection_confidence', v / 100)}
              />
              <SelectRow
                label="دقة الاستدلال (YOLO imgsz)"
                hint="640 = أسرع · 1280 = أدق لكاميرات بعيدة"
                value={sys.detection_imgsz}
                options={[{ label: '320 — سريع جداً', value: 320 }, { label: '640 — متوازن', value: 640 }, { label: '1280 — دقيق', value: 1280 }]}
                onChange={v => set('detection_imgsz', Number(v))}
              />
              <SliderRow
                label="حد ثقة كشف الأدوات المحظورة (هاتف/ورقة)" unit="%" value={Math.round(sys.tools_confidence * 100)} min={10} max={95} step={5}
                hint="أقل = يكشف أكثر أجساماً"
                leftLabel="حساس" rightLabel="صارم"
                onChange={v => set('tools_confidence', v / 100)}
              />
              <Toggle
                label="كشف الأجسام المحظورة (Object Detection)"
                hint="هواتف، ورقات الغش، إلخ."
                value={sys.object_detection_enabled}
                onChange={v => set('object_detection_enabled', v)}
              />
            </div>
          )}
          <SaveBar saving={sysSaving} saved={sysSaved} onClick={saveSystemSettings} />
        </section>

        {/* ── 4. Gaze & Audio ─────────────────────────────────────────── */}
        <section className="bg-white rounded-3xl border border-gray-100 shadow-sm p-7">
          <SectionHeader
            color="bg-yellow-100"
            icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f39c12" strokeWidth="2.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>}
            title="إعدادات النظر وتقييم الغش (Gaze)"
          />
          {sysLoading ? <div className="h-48 bg-gray-100 rounded-2xl animate-pulse" /> : (
            <div className="space-y-5">
              <SliderRow
                label="حساسية اتجاه النظر (Gaze Sensitivity)" unit="%" value={sys.gaze_sensitivity} min={10} max={100}
                hint="مرتبط بـ risk_angle_tolerance — أعلى = تنبيهات أكثر"
                leftLabel="منخفض (تنبيهات أقل)" rightLabel="مرتفع (تنبيهات أكثر)"
                onChange={v => set('gaze_sensitivity', v)}
              />
              <SliderRow
                label="زاوية التسامح في النظر (°)" unit="°" value={sys.risk_angle_tolerance} min={5} max={60} step={0.5}
                hint="أكبر = يتساهل أكثر في تحديد اتجاه النظر"
                leftLabel="5° (صارم)" rightLabel="60° (متساهل)"
                onChange={v => set('risk_angle_tolerance', v)}
              />
              <SliderRow
                label="مدة الشك المطلوبة (ثانية)" unit="s" value={sys.suspicious_duration_threshold} min={0.5} max={10} step={0.5}
                hint="عدد الثواني التي يجب أن ينظر فيها الطالب قبل الإبلاغ"
                leftLabel="0.5s (حساس)" rightLabel="10s (متساهل)"
                onChange={v => set('suspicious_duration_threshold', v)}
              />
              <SliderRow
                label="نسبة الإطارات المشبوهة" unit="%" value={Math.round(sys.suspicious_match_ratio * 100)} min={10} max={100} step={5}
                hint="% من الإطارات المتتالية التي يجب أن تُظهر نظرة مشبوهة"
                leftLabel="10% (حساس)" rightLabel="100% (صارم)"
                onChange={v => set('suspicious_match_ratio', v / 100)}
              />
              <SliderRow
                label="حساسية كشف الصوت (Audio)" unit="%" value={sys.audio_sensitivity} min={10} max={100}
                leftLabel="منخفض" rightLabel="مرتفع"
                onChange={v => set('audio_sensitivity', v)}
              />
              <SliderRow
                label="فترة تهدئة التنبيهات (ثانية)" unit="s" value={sys.alert_cooldown_seconds} min={5} max={120} step={5}
                hint="الحد الأدنى بين تنبيهات متكررة لنفس المقعد"
                leftLabel="5s (سريع)" rightLabel="120s (بطيء)"
                onChange={v => set('alert_cooldown_seconds', v)}
              />
            </div>
          )}
          <SaveBar saving={sysSaving} saved={sysSaved} onClick={saveSystemSettings} />
        </section>

        {/* ── 5. Tracking ─────────────────────────────────────────────── */}
        <section className="bg-white rounded-3xl border border-gray-100 shadow-sm p-7">
          <SectionHeader
            color="bg-green-100"
            icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#00b894" strokeWidth="2.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>}
            title="إعدادات التتبع (Tracking)"
          />
          {sysLoading ? <div className="h-32 bg-gray-100 rounded-2xl animate-pulse" /> : (
            <div className="space-y-5">
              <SliderRow
                label="أقصى مسافة للتتبع (px)" unit="px" value={sys.tracking_max_distance} min={20} max={300} step={10}
                hint="أقصى مسافة (بكسل) لربط كشف بمسار موجود"
                leftLabel="20 (دقيق)" rightLabel="300 (مرن)"
                onChange={v => set('tracking_max_distance', v)}
              />
              <SliderRow
                label="عمر المسار الأقصى (إطارات)" unit=" إطار" value={sys.tracking_max_age} min={5} max={150} step={5}
                hint="عدد الإطارات قبل حذف مسار مفقود (30 إطار ≈ ثانية واحدة)"
                leftLabel="5 (سريع الحذف)" rightLabel="150 (صبور)"
                onChange={v => set('tracking_max_age', v)}
              />
              <SliderRow
                label="عدد الجيران المقارَنين (K)" unit=" جيران" value={sys.neighbor_k} min={2} max={15}
                hint="عدد الطلاب المجاورين الذين تُقارَن نظرة الطالب بأوراقهم"
                leftLabel="2" rightLabel="15"
                onChange={v => set('neighbor_k', v)}
              />
            </div>
          )}
          <SaveBar saving={sysSaving} saved={sysSaved} onClick={saveSystemSettings} />
        </section>

        {/* ── 6. Re-ID & Performance ──────────────────────────────────── */}
        <section className="bg-white rounded-3xl border border-gray-100 shadow-sm p-7">
          <SectionHeader
            color="bg-orange-100"
            icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#e67e22" strokeWidth="2.5"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>}
            title="إعادة التعرف والأداء (Re-ID & Performance)"
          />
          {sysLoading ? <div className="h-24 bg-gray-100 rounded-2xl animate-pulse" /> : (
            <div className="space-y-5">
              <SliderRow
                label="حد تطابق إعادة التعرف (REID)" unit="%" value={Math.round(sys.reid_match_threshold * 100)} min={50} max={99} step={1}
                hint="حد التشابه لمطابقة طالب معاد ظهوره — أعلى = أكثر دقة وأقل مطابقات خاطئة"
                leftLabel="50% (مرن)" rightLabel="99% (صارم)"
                onChange={v => set('reid_match_threshold', v / 100)}
              />
              <SliderRow
                label="عدد عمليات MediaPipe المتوازية" unit=" عملية" value={sys.face_mesh_workers} min={1} max={8}
                hint="أكثر عمليات = معالجة وجوه أسرع لكن استهلاك RAM أعلى"
                leftLabel="1 (أبطأ / RAM أقل)" rightLabel="8 (أسرع / RAM أكثر)"
                onChange={v => set('face_mesh_workers', v)}
              />
            </div>
          )}
          <SaveBar saving={sysSaving} saved={sysSaved} onClick={saveSystemSettings} />
        </section>

        {/* ── 7. Change Password ──────────────────────────────────────── */}
        <section className="bg-white rounded-3xl border border-gray-100 shadow-sm p-7">
          <SectionHeader
            color="bg-red-100"
            icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#e74c3c" strokeWidth="2.5"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>}
            title="تغيير كلمة المرور"
          />
          <form onSubmit={changePassword} className="space-y-4">
            <div>
              <label className="block text-xs font-black text-gray-500 mb-1.5">كلمة المرور الحالية</label>
              <input type="password" required className={inputCls} value={pwForm.current} onChange={e => setPwForm(p => ({ ...p, current: e.target.value }))} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-black text-gray-500 mb-1.5">كلمة المرور الجديدة</label>
                <input type="password" required className={inputCls} value={pwForm.next} onChange={e => setPwForm(p => ({ ...p, next: e.target.value }))} />
              </div>
              <div>
                <label className="block text-xs font-black text-gray-500 mb-1.5">تأكيد كلمة المرور</label>
                <input type="password" required className={inputCls} value={pwForm.confirm} onChange={e => setPwForm(p => ({ ...p, confirm: e.target.value }))} />
              </div>
            </div>
            {pwError && <div className="bg-red-50 border border-red-200 text-red-600 rounded-2xl px-4 py-3 text-sm font-bold">{pwError}</div>}
            {pwSuccess && <div className="bg-green-50 border border-green-200 text-green-700 rounded-2xl px-4 py-3 text-sm font-bold">✓ تم تغيير كلمة المرور بنجاح</div>}
            <div className="flex justify-end pt-2">
              <button type="submit" disabled={pwSaving}
                className="bg-red-500 hover:bg-red-600 text-white px-8 py-3 rounded-2xl font-black text-sm shadow-lg shadow-red-100 hover:-translate-y-0.5 active:scale-95 transition-all disabled:opacity-60 cursor-pointer">
                {pwSaving ? 'جاري التغيير...' : 'تغيير كلمة المرور'}
              </button>
            </div>
          </form>
        </section>

      </div>
    </div>
  );
}
