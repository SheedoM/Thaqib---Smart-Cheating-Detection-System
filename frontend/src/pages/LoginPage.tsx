import React, { useState } from 'react';
import { Loader2 } from 'lucide-react';

export default function LoginPage() {
  const [formData, setFormData] = useState({
    identifier: '',
    password: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setErrorMsg(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      const params = new URLSearchParams();
      params.append('username', formData.identifier);
      params.append('password', formData.password);

      const response = await fetch('http://localhost:8000/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: params.toString(),
      });

      if (response.ok) {
        const data = await response.json();
        // Save tokens to localStorage
        localStorage.setItem('thaqib_access_token', data.access_token);
        localStorage.setItem('thaqib_refresh_token', data.refresh_token);
        
        console.log('Login successful', data);
        alert('تم تسجيل الدخول بنجاح!');
        // In a real app, we would use a router to redirect here
        window.location.reload(); 
      } else {
        const errData = await response.json();
        setErrorMsg(errData.detail || 'خطأ في اسم المستخدم أو كلمة المرور');
      }
    } catch (err) {
      setErrorMsg('تعذر الاتصال بالخادم. تأكد من تشغيل الباك إند.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-[452px] flex flex-col items-center animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center justify-center gap-2 mb-2">
        <h1 className="text-[16px] font-medium text-[#333]">مرحباً بعودتك</h1>
        <span className="text-xl">✨</span>
      </div>
      
      <h2 className="text-[26px] font-semibold text-[#333] mb-10 text-center">
        سجل الدخول إلى حسابك
      </h2>

      <form onSubmit={handleSubmit} className="w-full flex flex-col gap-[17px]">
        {/* Username/Email */}
        <input
          type="text"
          name="identifier"
          placeholder="بريد الكتروني أو اسم المستخدم"
          value={formData.identifier}
          onChange={handleInputChange}
          className="thaqib-input"
          required
        />

        {/* Password */}
        <input
          type="password"
          name="password"
          placeholder="كلمة المرور"
          value={formData.password}
          onChange={handleInputChange}
          className="thaqib-input"
          required
        />

        <div className="flex justify-between items-center mt-1 mb-2">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" className="w-4 h-4 rounded border-gray-300 text-[#8e52cb] focus:ring-[#8e52cb]" />
            <span className="text-sm text-gray-600">تذكرني</span>
          </label>
          <button type="button" className="text-sm text-[#8e52cb] hover:underline">
            نسيت كلمة المرور؟
          </button>
        </div>

        {errorMsg && (
          <div className="text-red-600 bg-red-50 p-3 rounded-lg text-sm font-medium border border-red-200">
            {errorMsg}
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="thaqib-button mt-4 disabled:opacity-70 disabled:cursor-not-allowed"
        >
          {isSubmitting ? <Loader2 className="animate-spin" size={24} /> : 'تسجيل الدخول'}
        </button>

        <p className="text-center text-gray-500 text-sm mt-6">
          ليس لديك حساب؟ <span className="text-[#8e52cb] font-semibold cursor-pointer hover:underline">تواصل مع الإدارة</span>
        </p>
      </form>
    </div>
  );
}
