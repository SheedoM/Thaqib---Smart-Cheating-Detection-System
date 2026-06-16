import React, { useState, useRef } from 'react';
import { CloudUpload, CheckCircle2, Loader2, Copy, Plus, Trash2 } from 'lucide-react';
import { apiUrl } from '../config/api';

interface SetupWizardProps {
  onSuccess: () => void;
}

const INSTITUTION_TYPES = [
  { value: 'university', label: 'جامعة', description: 'تدير كليات متعددة' },
  { value: 'college', label: 'كلية', description: 'كلية مستقلة' },
  { value: 'school', label: 'مدرسة', description: 'مدرسة أو معهد' },
  { value: 'standalone', label: 'مستقل', description: 'منشأة منفردة' },
] as const;

interface CollegeEntry { name: string; code: string }

export default function SetupWizard({ onSuccess }: SetupWizardProps) {
  const [step, setStep] = useState<'info' | 'colleges' | 'done'>('info');
  const [formData, setFormData] = useState({
    institution_name: '',
    institution_type: 'standalone' as string,
    admin: '',
    admin_password: '',
    logo_file: null as File | null,
  });
  const [colleges, setColleges] = useState<CollegeEntry[]>([{ name: '', code: '' }]);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [generatedCreds, setGeneratedCreds] = useState<{ username: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setErrorMsg(null);
  };

  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      const file = e.target.files[0];
      setFormData({ ...formData, logo_file: file });
      setLogoPreview(URL.createObjectURL(file));
      setErrorMsg(null);
    }
  };

  const copyToClipboard = (text: string) => navigator.clipboard.writeText(text);

  // ── college list helpers ─────────────────────────────────────────────────
  const addCollege = () => setColleges(prev => [...prev, { name: '', code: '' }]);
  const removeCollege = (i: number) => setColleges(prev => prev.filter((_, idx) => idx !== i));
  const updateCollege = (i: number, field: keyof CollegeEntry, value: string) =>
    setColleges(prev => prev.map((c, idx) => idx === i ? { ...c, [field]: value } : c));

  // ── submit ───────────────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (formData.institution_type === 'university' && step === 'info') {
      setStep('colleges');
      return;
    }
    await doInstall();
  };

  const doInstall = async () => {
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const payload: Record<string, unknown> = {
        institution_name: formData.institution_name,
        institution_type: formData.institution_type,
        admin: formData.admin,
        admin_password: formData.admin_password,
        logo_url: formData.logo_file ? formData.logo_file.name : null,
      };
      if (formData.institution_type === 'university') {
        const validColleges = colleges.filter(c => c.name.trim().length >= 2);
        if (validColleges.length > 0) {
          payload.colleges = validColleges.map(c => ({
            name: c.name.trim(),
            code: c.code.trim() || undefined,
          }));
        }
      }

      const response = await fetch(apiUrl('/api/setup/install'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        const data = await response.json();
        setGeneratedCreds(data.generated_credentials);
        setStep('done');
      } else {
        const errData = await response.json();
        setErrorMsg(errData.detail || 'حدث خطأ غير معروف أثناء الإعداد');
        if (step === 'colleges') setStep('info');
      }
    } catch {
      setErrorMsg('تعذر الاتصال بالخادم. تأكد من تشغيل الباك إند.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // ─── Render: Done ────────────────────────────────────────────────────────
  if (step === 'done') {
    return (
      <div className="w-full max-w-[452px] flex flex-col items-center">
        <div className="bg-green-50 justify-center border border-green-200 rounded-xl p-8 flex flex-col items-center w-full animate-in fade-in zoom-in-95 duration-500">
          <CheckCircle2 className="w-16 h-16 text-green-500 mb-4" />
          <h3 className="text-2xl font-bold text-green-800 mb-2">تم الإعداد بنجاح</h3>
          <p className="text-green-600 text-center font-medium mb-6">تم إضافة المعلومات وحساب مسؤول النظام بنجاح.</p>
          {generatedCreds && (
            <div className="bg-white p-4 rounded-lg w-full border border-green-100 text-right space-y-3 shadow-sm mb-6">
              <p className="text-sm text-gray-500 mb-2 font-bold">بيانات الدخول</p>
              <div className="flex justify-between items-center bg-gray-50 p-2 rounded">
                <button onClick={() => copyToClipboard(generatedCreds.username)} className="text-gray-400 hover:text-green-600">
                  <Copy size={16} />
                </button>
                <div>
                  <span className="font-mono text-left inline-block w-full">{generatedCreds.username}</span>
                  <span className="text-xs text-gray-400 block">:اسم المستخدم</span>
                </div>
              </div>
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg p-2">
                كلمة المرور هي التي أدخلتها في نموذج الإعداد ولا يتم إرجاعها من الخادم.
              </p>
            </div>
          )}
          <button onClick={onSuccess} className="thaqib-button max-w-[200px]">
            الذهاب لتسجيل الدخول
          </button>
        </div>
      </div>
    );
  }

  // ─── Render: Colleges step (university only) ─────────────────────────────
  if (step === 'colleges') {
    return (
      <div className="w-full max-w-[452px] flex flex-col items-center">
        <h2 className="text-[24px] font-semibold text-[#333] mb-2 text-center">إضافة الكليات</h2>
        <p className="text-gray-500 text-sm mb-6 text-center">اختياري — يمكنك إضافتهم لاحقاً من لوحة التحكم</p>
        <div className="w-full flex flex-col gap-3">
          {colleges.map((c, i) => (
            <div key={i} className="flex gap-2 items-center">
              <input
                type="text"
                placeholder={`اسم الكلية ${i + 1}`}
                value={c.name}
                onChange={e => updateCollege(i, 'name', e.target.value)}
                className="thaqib-input flex-1"
              />
              <input
                type="text"
                placeholder="الرمز"
                value={c.code}
                onChange={e => updateCollege(i, 'code', e.target.value)}
                className="thaqib-input w-24"
              />
              {colleges.length > 1 && (
                <button type="button" onClick={() => removeCollege(i)} className="text-red-400 hover:text-red-600 p-1">
                  <Trash2 size={16} />
                </button>
              )}
            </div>
          ))}
          <button
            type="button"
            onClick={addCollege}
            className="flex items-center gap-1 text-sm text-[#8e52cb] hover:underline self-start mt-1"
          >
            <Plus size={16} /> إضافة كلية أخرى
          </button>
        </div>
        {errorMsg && (
          <div className="text-red-600 bg-red-50 p-3 rounded-lg text-sm font-medium border border-red-200 mt-4 w-full">
            {errorMsg}
          </div>
        )}
        <div className="flex gap-3 mt-6 w-full">
          <button
            type="button"
            onClick={() => setStep('info')}
            className="thaqib-button bg-gray-200 text-gray-700 hover:bg-gray-300 flex-1"
          >
            رجوع
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            onClick={doInstall}
            className="thaqib-button flex-1 disabled:opacity-70 disabled:cursor-not-allowed"
          >
            {isSubmitting ? <Loader2 className="animate-spin" size={20} /> : 'إنهاء الإعداد'}
          </button>
        </div>
        <button
          type="button"
          disabled={isSubmitting}
          onClick={doInstall}
          className="text-sm text-gray-400 hover:text-gray-600 mt-3"
        >
          تخطي وإنهاء الإعداد بدون كليات
        </button>
      </div>
    );
  }

  // ─── Render: Info step ───────────────────────────────────────────────────
  return (
    <div className="w-full max-w-[452px] flex flex-col items-center">
      <div className="flex items-center justify-center gap-2 mb-2">
        <h1 className="text-[16px] font-medium text-[#333]">مرحباً بك</h1>
        <span className="text-xl">👋</span>
      </div>
      <h2 className="text-[26px] font-semibold text-[#333] mb-8 text-center">
        قم بإعداد النظام
      </h2>

      <form onSubmit={handleSubmit} className="w-full flex flex-col gap-[17px] animate-in fade-in slide-in-from-bottom-4 duration-500">
        {/* Institution type selector */}
        <div className="w-full">
          <label className="block text-sm font-medium text-gray-600 mb-2 text-right">نوع المنشأة</label>
          <div className="grid grid-cols-2 gap-2">
            {INSTITUTION_TYPES.map(t => (
              <button
                key={t.value}
                type="button"
                onClick={() => setFormData(prev => ({ ...prev, institution_type: t.value }))}
                className={[
                  'rounded-xl border-2 p-3 text-right transition-colors',
                  formData.institution_type === t.value
                    ? 'border-[#8e52cb] bg-[#f5eeff]'
                    : 'border-[#eee] bg-white hover:border-[#c496ff]',
                ].join(' ')}
              >
                <div className="font-semibold text-[14px] text-[#333]">{t.label}</div>
                <div className="text-xs text-gray-400 mt-0.5">{t.description}</div>
              </button>
            ))}
          </div>
        </div>

        <input
          type="text"
          name="institution_name"
          placeholder={
            formData.institution_type === 'university' ? 'اسم الجامعة'
            : formData.institution_type === 'college' ? 'اسم الكلية'
            : formData.institution_type === 'school' ? 'اسم المدرسة'
            : 'اسم المنشأة'
          }
          value={formData.institution_name}
          onChange={handleInputChange}
          className="thaqib-input"
          required
        />

        <input
          type="text"
          name="admin"
          placeholder="مسؤول النظام"
          value={formData.admin}
          onChange={handleInputChange}
          className="thaqib-input"
          required
        />

        <input
          type="password"
          name="admin_password"
          placeholder="كلمة مرور مسؤول النظام"
          value={formData.admin_password}
          onChange={handleInputChange}
          className="thaqib-input"
          minLength={12}
          required
        />

        <div
          onClick={() => fileInputRef.current?.click()}
          className="bg-white border-2 border-[#eee] border-dashed rounded-[12px] h-[129px] flex flex-col items-center justify-center cursor-pointer hover:border-[#c496ff] transition-colors relative overflow-hidden"
        >
          {logoPreview ? (
            <img src={logoPreview} alt="Logo Preview" className="h-[80%] w-auto object-contain p-2" />
          ) : (
            <>
              <div className="text-[16px] font-medium text-[#333] opacity-50 mb-3 absolute w-full top-3 px-6 text-right">
                الشعار
              </div>
              <div className="text-[#8e52cb] mt-4">
                <CloudUpload size={32} strokeWidth={1.5} />
              </div>
            </>
          )}
          <input type="file" ref={fileInputRef} onChange={handleLogoUpload} className="hidden" accept="image/*" />
        </div>

        {errorMsg && (
          <div className="text-red-600 bg-red-50 p-3 rounded-lg text-sm font-medium border border-red-200">
            {errorMsg}
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="thaqib-button mt-[23px] disabled:opacity-70 disabled:cursor-not-allowed"
        >
          {isSubmitting ? (
            <Loader2 className="animate-spin" size={24} />
          ) : formData.institution_type === 'university' ? (
            'التالي: إضافة الكليات'
          ) : (
            'حفظ'
          )}
        </button>
      </form>
    </div>
  );
}
