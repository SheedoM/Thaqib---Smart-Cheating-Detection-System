import { useState, useEffect } from 'react';
import { authFetch } from '../config/api';

interface Institution {
  id: string;
  name: string;
  code: string | null;
  contact_email: string | null;
  logo_url: string | null;
  address: string | null;
}

interface PipelineSettings {
  gaze_sensitivity: number;       // 0–100
  audio_sensitivity: number;      // 0–100
  object_detection_enabled: boolean;
  alert_cooldown_seconds: number; // seconds between repeated alerts per seat
}

const PIPELINE_KEY = 'thaqib_pipeline_settings';

const defaultPipeline: PipelineSettings = {
  gaze_sensitivity: 70,
  audio_sensitivity: 65,
  object_detection_enabled: true,
  alert_cooldown_seconds: 30,
};

function loadPipeline(): PipelineSettings {
  try {
    const raw = localStorage.getItem(PIPELINE_KEY);
    if (raw) return { ...defaultPipeline, ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return { ...defaultPipeline };
}

export default function SettingsTab() {
  // ── Institution ─────────────────────────────────────────────────────────────
  const [institution, setInstitution] = useState<Institution | null>(null);
  const [instLoading, setInstLoading] = useState(true);
  const [instSaving, setInstSaving] = useState(false);
  const [instError, setInstError] = useState<string | null>(null);
  const [instSuccess, setInstSuccess] = useState(false);

  const [instForm, setInstForm] = useState({
    name: '',
    contact_email: '',
    address: '',
    logo_url: '',
    code: '',
  });

  // ── Password ─────────────────────────────────────────────────────────────────
  const [pwForm, setPwForm] = useState({ current: '', next: '', confirm: '' });
  const [pwSaving, setPwSaving] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSuccess, setPwSuccess] = useState(false);

  // ── Pipeline ─────────────────────────────────────────────────────────────────
  const [pipeline, setPipeline] = useState<PipelineSettings>(loadPipeline);
  const [pipelineSaved, setPipelineSaved] = useState(false);

  // ── Load institution on mount ────────────────────────────────────────────────
  useEffect(() => {
    const load = async () => {
      try {
        const res = await authFetch('/api/institutions/');
        if (res.ok) {
          const list: Institution[] = await res.json();
          if (list.length > 0) {
            const inst = list[0];
            setInstitution(inst);
            setInstForm({
              name: inst.name || '',
              contact_email: inst.contact_email || '',
              address: inst.address || '',
              logo_url: inst.logo_url || '',
              code: inst.code || '',
            });
          }
        }
      } catch (err) {
        console.error('Failed to load institution', err);
      } finally {
        setInstLoading(false);
      }
    };
    load();
  }, []);

  // ── Save institution ─────────────────────────────────────────────────────────
  const saveInstitution = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!institution) return;
    setInstSaving(true);
    setInstError(null);
    setInstSuccess(false);
    try {
      const res = await authFetch(`/api/institutions/${institution.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: instForm.name,
          contact_email: instForm.contact_email || null,
          address: instForm.address || null,
          logo_url: instForm.logo_url || null,
          code: instForm.code || null,
        }),
      });
      if (res.ok) {
        const updated: Institution = await res.json();
        setInstitution(updated);
        setInstSuccess(true);
        setTimeout(() => setInstSuccess(false), 3000);
      } else {
        const err = await res.json().catch(() => ({ detail: `خطأ ${res.status}` }));
        setInstError(typeof err.detail === 'string' ? err.detail : 'فشل الحفظ');
      }
    } catch {
      setInstError('تعذر الاتصال بالسيرفر');
    } finally {
      setInstSaving(false);
    }
  };

  // ── Change password ──────────────────────────────────────────────────────────
  const changePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwError(null);
    setPwSuccess(false);
    if (pwForm.next !== pwForm.confirm) { setPwError('كلمتا المرور غير متطابقتين'); return; }
    if (pwForm.next.length < 8) { setPwError('كلمة المرور يجب أن تكون 8 أحرف على الأقل'); return; }
    setPwSaving(true);
    try {
      const res = await authFetch('/api/users/me/password', {
        method: 'PUT',
        body: JSON.stringify({ current_password: pwForm.current, new_password: pwForm.next }),
      });
      if (res.ok) {
        setPwSuccess(true);
        setPwForm({ current: '', next: '', confirm: '' });
        setTimeout(() => setPwSuccess(false), 3000);
      } else {
        const err = await res.json().catch(() => ({ detail: `خطأ ${res.status}` }));
        setPwError(typeof err.detail === 'string' ? err.detail : 'فشل تغيير كلمة المرور');
      }
    } catch {
      setPwError('تعذر الاتصال بالسيرفر');
    } finally {
      setPwSaving(false);
    }
  };

  // ── Save pipeline settings (localStorage) ────────────────────────────────────
  const savePipeline = () => {
    localStorage.setItem(PIPELINE_KEY, JSON.stringify(pipeline));
    setPipelineSaved(true);
    setTimeout(() => setPipelineSaved(false), 2500);
  };

  // ── Shared input style ───────────────────────────────────────────────────────
  const inputCls = 'w-full bg-gray-50 border border-gray-200 rounded-2xl py-2.5 px-4 outline-none focus:ring-2 focus:ring-purple-200 focus:border-[#44006E] transition-all font-bold text-sm';

  return (
    <div className="p-8 max-w-4xl mx-auto" dir="rtl">
      {/* Page header */}
      <div className="flex items-center gap-4 mb-10">
        <div className="w-1.5 h-10 bg-[#44006E] rounded-full" />
        <h2 className="text-3xl font-black text-[#2D005F]">الإعدادات</h2>
      </div>

      <div className="space-y-8">

        {/* ── Institution ──────────────────────────────────────────────── */}
        <section className="bg-white rounded-3xl border border-gray-100 shadow-sm p-7">
          <h3 className="text-lg font-black text-[#2D005F] mb-6 flex items-center gap-2">
            <span className="w-7 h-7 bg-purple-100 rounded-xl flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#44006E" strokeWidth="2.5"><path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 14v3M12 14v3M16 14v3"/></svg>
            </span>
            بيانات المؤسسة
          </h3>

          {instLoading ? (
            <div className="space-y-3">
              {[1,2,3].map(i => <div key={i} className="h-10 bg-gray-100 rounded-2xl animate-pulse" />)}
            </div>
          ) : (
            <form onSubmit={saveInstitution} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-black text-gray-500 mb-1.5">اسم المؤسسة *</label>
                  <input className={inputCls} required value={instForm.name}
                    onChange={e => setInstForm(p => ({ ...p, name: e.target.value }))} />
                </div>
                <div>
                  <label className="block text-xs font-black text-gray-500 mb-1.5">الرمز / الكود</label>
                  <input className={inputCls} placeholder="مثال: UNIV-01" value={instForm.code}
                    onChange={e => setInstForm(p => ({ ...p, code: e.target.value }))} />
                </div>
                <div>
                  <label className="block text-xs font-black text-gray-500 mb-1.5">البريد الإلكتروني</label>
                  <input className={inputCls} type="email" value={instForm.contact_email}
                    onChange={e => setInstForm(p => ({ ...p, contact_email: e.target.value }))} />
                </div>
                <div>
                  <label className="block text-xs font-black text-gray-500 mb-1.5">رابط الشعار</label>
                  <input className={inputCls} placeholder="https://..." value={instForm.logo_url}
                    onChange={e => setInstForm(p => ({ ...p, logo_url: e.target.value }))} />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-xs font-black text-gray-500 mb-1.5">العنوان</label>
                  <input className={inputCls} value={instForm.address}
                    onChange={e => setInstForm(p => ({ ...p, address: e.target.value }))} />
                </div>
              </div>

              {instError && (
                <div className="bg-red-50 border border-red-200 text-red-600 rounded-2xl px-4 py-3 text-sm font-bold">{instError}</div>
              )}
              {instSuccess && (
                <div className="bg-green-50 border border-green-200 text-green-700 rounded-2xl px-4 py-3 text-sm font-bold">✓ تم الحفظ بنجاح</div>
              )}

              <div className="flex justify-end pt-2">
                <button type="submit" disabled={instSaving}
                  className="bg-[#44006E] text-white px-8 py-3 rounded-2xl font-black text-sm shadow-lg shadow-purple-100 hover:-translate-y-0.5 active:scale-95 transition-all disabled:opacity-60 cursor-pointer flex items-center gap-2">
                  {instSaving ? (
                    <><svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><circle cx="12" cy="12" r="10" strokeOpacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10"/></svg>جاري الحفظ...</>
                  ) : 'حفظ التغييرات'}
                </button>
              </div>
            </form>
          )}
        </section>

        {/* ── Pipeline sensitivity ─────────────────────────────────────── */}
        <section className="bg-white rounded-3xl border border-gray-100 shadow-sm p-7">
          <h3 className="text-lg font-black text-[#2D005F] mb-6 flex items-center gap-2">
            <span className="w-7 h-7 bg-blue-100 rounded-xl flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0984E3" strokeWidth="2.5"><circle cx="12" cy="12" r="3"/><path d="M12 1v2m0 18v2m-9-11h2m18 0h2"/></svg>
            </span>
            إعدادات خوارزميات الكشف
          </h3>
          <p className="text-xs text-gray-400 font-bold mb-6">تُحفظ هذه الإعدادات محلياً وتُطبَّق عند بدء المراقبة في هذا المتصفح.</p>

          <div className="space-y-6">
            {/* Gaze sensitivity */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-sm font-black text-gray-700">حساسية كاميرات النظر (Gaze)</label>
                <span className="text-sm font-black text-[#44006E]">{pipeline.gaze_sensitivity}%</span>
              </div>
              <input type="range" min={10} max={100} value={pipeline.gaze_sensitivity}
                onChange={e => setPipeline(p => ({ ...p, gaze_sensitivity: Number(e.target.value) }))}
                className="w-full accent-[#44006E]" />
              <div className="flex justify-between text-[10px] text-gray-400 mt-1 font-bold">
                <span>منخفض (أقل تنبيهات)</span><span>مرتفع (تنبيهات أكثر)</span>
              </div>
            </div>

            {/* Audio sensitivity */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-sm font-black text-gray-700">حساسية كشف الصوت (Audio)</label>
                <span className="text-sm font-black text-[#44006E]">{pipeline.audio_sensitivity}%</span>
              </div>
              <input type="range" min={10} max={100} value={pipeline.audio_sensitivity}
                onChange={e => setPipeline(p => ({ ...p, audio_sensitivity: Number(e.target.value) }))}
                className="w-full accent-[#44006E]" />
              <div className="flex justify-between text-[10px] text-gray-400 mt-1 font-bold">
                <span>منخفض</span><span>مرتفع</span>
              </div>
            </div>

            {/* Alert cooldown */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-sm font-black text-gray-700">فترة تهدئة التنبيهات (ثانية)</label>
                <span className="text-sm font-black text-[#44006E]">{pipeline.alert_cooldown_seconds}s</span>
              </div>
              <input type="range" min={5} max={120} step={5} value={pipeline.alert_cooldown_seconds}
                onChange={e => setPipeline(p => ({ ...p, alert_cooldown_seconds: Number(e.target.value) }))}
                className="w-full accent-[#44006E]" />
              <div className="flex justify-between text-[10px] text-gray-400 mt-1 font-bold">
                <span>5 ث (سريع جداً)</span><span>120 ث (بطيء)</span>
              </div>
            </div>

            {/* Object detection toggle */}
            <div className="flex items-center justify-between bg-gray-50 rounded-2xl px-4 py-3">
              <div>
                <p className="text-sm font-black text-gray-700">كشف الأجسام المحظورة (Object Detection)</p>
                <p className="text-[11px] text-gray-400 font-bold mt-0.5">هواتف، ورقات الغش، إلخ.</p>
              </div>
              <button type="button"
                onClick={() => setPipeline(p => ({ ...p, object_detection_enabled: !p.object_detection_enabled }))}
                className={`relative w-12 h-6 rounded-full transition-colors ${pipeline.object_detection_enabled ? 'bg-[#00D261]' : 'bg-gray-300'}`}>
                <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all ${pipeline.object_detection_enabled ? 'left-6' : 'left-0.5'}`} />
              </button>
            </div>
          </div>

          <div className="flex justify-end pt-4">
            <button onClick={savePipeline}
              className="bg-[#0984E3] text-white px-8 py-3 rounded-2xl font-black text-sm hover:-translate-y-0.5 active:scale-95 transition-all cursor-pointer">
              {pipelineSaved ? '✓ تم الحفظ' : 'حفظ إعدادات الكشف'}
            </button>
          </div>
        </section>

        {/* ── Change Password ──────────────────────────────────────────── */}
        <section className="bg-white rounded-3xl border border-gray-100 shadow-sm p-7">
          <h3 className="text-lg font-black text-[#2D005F] mb-6 flex items-center gap-2">
            <span className="w-7 h-7 bg-red-100 rounded-xl flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#e74c3c" strokeWidth="2.5"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            </span>
            تغيير كلمة المرور
          </h3>

          <form onSubmit={changePassword} className="space-y-4">
            <div>
              <label className="block text-xs font-black text-gray-500 mb-1.5">كلمة المرور الحالية</label>
              <input type="password" required className={inputCls} value={pwForm.current}
                onChange={e => setPwForm(p => ({ ...p, current: e.target.value }))} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-black text-gray-500 mb-1.5">كلمة المرور الجديدة</label>
                <input type="password" required className={inputCls} value={pwForm.next}
                  onChange={e => setPwForm(p => ({ ...p, next: e.target.value }))} />
              </div>
              <div>
                <label className="block text-xs font-black text-gray-500 mb-1.5">تأكيد كلمة المرور</label>
                <input type="password" required className={inputCls} value={pwForm.confirm}
                  onChange={e => setPwForm(p => ({ ...p, confirm: e.target.value }))} />
              </div>
            </div>

            {pwError && (
              <div className="bg-red-50 border border-red-200 text-red-600 rounded-2xl px-4 py-3 text-sm font-bold">{pwError}</div>
            )}
            {pwSuccess && (
              <div className="bg-green-50 border border-green-200 text-green-700 rounded-2xl px-4 py-3 text-sm font-bold">✓ تم تغيير كلمة المرور بنجاح</div>
            )}

            <div className="flex justify-end pt-2">
              <button type="submit" disabled={pwSaving}
                className="bg-red-500 hover:bg-red-600 text-white px-8 py-3 rounded-2xl font-black text-sm shadow-lg shadow-red-100 hover:-translate-y-0.5 active:scale-95 transition-all disabled:opacity-60 cursor-pointer flex items-center gap-2">
                {pwSaving ? 'جاري التغيير...' : 'تغيير كلمة المرور'}
              </button>
            </div>
          </form>
        </section>

      </div>
    </div>
  );
}
