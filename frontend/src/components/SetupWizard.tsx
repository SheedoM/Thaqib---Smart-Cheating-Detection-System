import React, { useState, useRef } from 'react';
import { CloudUpload, CheckCircle2, Loader2, Copy } from 'lucide-react';

interface SetupWizardProps {
  onSuccess: () => void;
}

export default function SetupWizard({ onSuccess }: SetupWizardProps) {
  const [formData, setFormData] = useState({
    institution_name: '',
    admin: '',
    logo_file: null as File | null,
  });

  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [installSuccess, setInstallSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [generatedCreds, setGeneratedCreds] = useState<{username: string, password: string} | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setErrorMsg(null);
  };

  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setFormData({ ...formData, logo_file: file });
      setLogoPreview(URL.createObjectURL(file));
      setErrorMsg(null);
    }
  };

  const handleBoxClick = () => {
    fileInputRef.current?.click();
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      const payload = {
        institution_name: formData.institution_name,
        admin: formData.admin,
        logo_url: formData.logo_file ? formData.logo_file.name : null,
      };

      const response = await fetch('http://localhost:8000/api/setup/install', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        const data = await response.json();
        setInstallSuccess(true);
        if (data.generated_credentials) {
           setGeneratedCreds(data.generated_credentials);
        }
      } else {
        const errData = await response.json();
        setErrorMsg(errData.detail || 'حدث خطأ غير معروف أثناء الإعداد');
      }
    } catch (err) {
      setErrorMsg('تعذر الاتصال بالخادم. تأكد من تشغيل الباك إند.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-[452px] flex flex-col items-center">
      <div className="flex items-center justify-center gap-2 mb-2">
        <h1 className="text-[16px] font-medium text-[#333]">مرحباً بك</h1>
        <span className="text-xl">👋</span>
      </div>
      
      <h2 className="text-[26px] font-semibold text-[#333] mb-10 text-center">
        قم بإضافة المعلومات حول الكلية
      </h2>

      {installSuccess ? (
        <div className="bg-green-50 justify-center border border-green-200 rounded-xl p-8 flex flex-col items-center w-full animate-in fade-in zoom-in-95 duration-500">
          <CheckCircle2 className="w-16 h-16 text-green-500 mb-4" />
          <h3 className="text-2xl font-bold text-green-800 mb-2">تم الإعداد بنجاح</h3>
          <p className="text-green-600 text-center font-medium mb-6">تم إضافة معلومات الكلية وحساب المشرف بنجاح.</p>
          
          {generatedCreds && (
            <div className="bg-white p-4 rounded-lg w-full border border-green-100 text-right space-y-3 shadow-sm mb-6">
              <p className="text-sm text-gray-500 mb-2 font-bold">بيانات الدخول المؤقتة (يرجى حفظها):</p>
              <div className="flex justify-between items-center bg-gray-50 p-2 rounded">
                <button onClick={() => copyToClipboard(generatedCreds.username)} className="text-gray-400 hover:text-green-600">
                  <Copy size={16} />
                </button>
                <div>
                  <span className="font-mono text-left inline-block w-full">{generatedCreds.username}</span>
                  <span className="text-xs text-gray-400 block">:اسم المستخدم</span>
                </div>
              </div>
              <div className="flex justify-between items-center bg-gray-50 p-2 rounded">
                <button onClick={() => copyToClipboard(generatedCreds.password)} className="text-gray-400 hover:text-green-600">
                  <Copy size={16} />
                </button>
                <div>
                  <span className="font-mono text-left inline-block w-full">{generatedCreds.password}</span>
                  <span className="text-xs text-gray-400 block">:كلمة المرور</span>
                </div>
              </div>
            </div>
          )}

          <button 
            onClick={onSuccess}
            className="thaqib-button max-w-[200px]"
          >
            الذهاب لتسجيل الدخول
          </button>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="w-full flex flex-col gap-[17px] animate-in fade-in slide-in-from-bottom-4 duration-500">
          <input
            type="text"
            name="institution_name"
            placeholder="اسم الكلية"
            value={formData.institution_name}
            onChange={handleInputChange}
            className="thaqib-input"
            required
          />

          <input
            type="text"
            name="admin"
            placeholder="الادمن"
            value={formData.admin}
            onChange={handleInputChange}
            className="thaqib-input"
            required
          />

          <div
            onClick={handleBoxClick}
            className="bg-white border-2 border-[#eee] border-dashed rounded-[12px] h-[129px] flex flex-col items-center justify-center cursor-pointer hover:border-[#c496ff] transition-colors relative overflow-hidden"
          >
            {logoPreview ? (
              <img src={logoPreview} alt="Logo Preview" className="h-[80%] w-auto object-contain p-2" />
            ) : (
              <>
                <div className="text-[16px] font-medium text-[#333] opacity-50 mb-3 absolute w-full top-3 px-6 text-right cursor-text" onClick={(e) => e.stopPropagation()}>
                  الشعار
                </div>
                <div className="text-[#8e52cb] mt-4">
                  <CloudUpload size={32} strokeWidth={1.5} />
                </div>
              </>
            )}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleLogoUpload}
              className="hidden"
              accept="image/*"
            />
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
            {isSubmitting ? <Loader2 className="animate-spin" size={24} /> : 'حفظ'}
          </button>
        </form>
      )}
    </div>
  );
}
