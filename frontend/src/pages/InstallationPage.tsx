import React, { useState } from 'react';
import { User, Lock, Mail, UserCircle, CheckCircle, CloudUpload } from 'lucide-react';

export default function InstallationPage() {
  const [step, setStep] = useState(1);
  const [isAnimating, setIsAnimating] = useState(true);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const [formData, setFormData] = useState({
    institution_name: '',
    logo_file: null as File | null,
    admin_full_name: '',
    admin_username: '',
    admin_email: '',
    admin_password: '',
  });

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setIsAnimating(false);
    }, 2000);
    return () => clearTimeout(timer);
  }, []);

  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setFormData({ ...formData, logo_file: file as any });
      setLogoPreview(URL.createObjectURL(file));
    }
  };

  const handleBoxClick = () => {
    fileInputRef.current?.click();
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleNext = () => {
    if (formData.institution_name.trim()) setStep(2);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const response = await fetch('http://localhost:8000/api/setup/install', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          institution_name: formData.institution_name,
          logo_url: "placeholder_logo.png",
          admin_full_name: formData.admin_full_name,
          admin_username: formData.admin_username,
          admin_email: formData.admin_email,
          admin_password: formData.admin_password
        })
      });

      if (response.ok) {
        alert("✅ تم إعداد النظام وحفظ حساب المشرف بنجاح!");
      } else {
        const errData = await response.json();
        alert("❌ حدث خطأ أثناء الإعداد: " + errData.detail);
      }
    } catch (err) {
      alert("❌ تعذر الاتصال بالخادم. تأكد من تشغيل الباك إند.");
    }
  };

  return (
    <div className={`flex min-h-screen w-full font-ibm-plex ${isAnimating ? 'overflow-hidden' : ''}`} dir="rtl">
      {/* Left Form Panel */}
      <div className={`bg-white flex flex-col justify-center items-center relative transition-all duration-1000 ease-in-out ${isAnimating ? 'w-0 opacity-0 overflow-hidden px-0' : 'w-1/2 opacity-100 p-12'}`}>
        <div className="absolute top-8 left-8 text-sm text-gray-400 font-semibold min-w-max">
          خطوة {step} من 2
        </div>

        <form onSubmit={handleSubmit} className="w-full max-w-md space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 min-w-[28rem]">
          {step === 1 && (
            <div className="space-y-6">
              <div className="text-center space-y-2 mb-8">
                <h1 className="text-2xl font-bold text-gray-800">مرحباً بك 👋</h1>
                <p className="text-gray-500 font-semibold">قم بإضافة المعلومات حول الكلية</p>
              </div>

              <div className="space-y-4">
                <input
                  type="text" name="institution_name" placeholder="اسم الكلية"
                  value={formData.institution_name} onChange={handleInputChange}
                  className="input-field" required
                />

                <div
                  onClick={handleBoxClick}
                  className="border-2 border-dashed border-gray-200 rounded-xl p-8 flex flex-col items-center justify-center cursor-pointer hover:bg-gray-50 hover:border-thaqib-primary transition-colors group relative overflow-hidden h-40"
                >
                  {logoPreview ? (
                    <img src={logoPreview} alt="Preview" className="w-full h-full object-contain" />
                  ) : (
                    <>
                      <div className="bg-gray-400 group-hover:bg-thaqib-primary text-white rounded-lg p-2 mb-3 transition-colors">
                        <CloudUpload size={24} />
                      </div>
                      <span className="text-gray-500 font-semibold text-sm">إضافة اللوجو</span>
                    </>
                  )}
                  <input type="file" ref={fileInputRef} onChange={handleLogoUpload} className="hidden" accept="image/*" />
                </div>
              </div>

              <button type="button" onClick={handleNext} className="btn-primary mt-8">التالي</button>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-6 animate-in fade-in slide-in-from-right-8 duration-500">
              <div className="text-center space-y-2 mb-8">
                <h1 className="text-2xl font-bold text-gray-800">حساب المشرف 👤</h1>
                <p className="text-gray-500 font-semibold">الرجاء إنشاء حساب المشرف الأساسي للمسؤول</p>
              </div>

              <div className="space-y-4">
                <div className="relative">
                  <UserCircle className="absolute right-3 top-3.5 text-gray-400" size={20} />
                  <input
                    type="text" name="admin_full_name" placeholder="الاسم الكامل"
                    value={formData.admin_full_name} onChange={handleInputChange}
                    className="input-field pr-10" required
                  />
                </div>
                <div className="relative">
                  <User className="absolute right-3 top-3.5 text-gray-400" size={20} />
                  <input
                    type="text" name="admin_username" placeholder="اسم المستخدم"
                    value={formData.admin_username} onChange={handleInputChange}
                    className="input-field pr-10" required
                  />
                </div>
                <div className="relative">
                  <Mail className="absolute right-3 top-3.5 text-gray-400" size={20} />
                  <input
                    type="email" name="admin_email" placeholder="البريد الإلكتروني"
                    value={formData.admin_email} onChange={handleInputChange}
                    className="input-field pr-10" required
                  />
                </div>
                <div className="relative">
                  <Lock className="absolute right-3 top-3.5 text-gray-400" size={20} />
                  <input
                    type="password" name="admin_password" placeholder="كلمة المرور"
                    value={formData.admin_password} onChange={handleInputChange}
                    className="input-field pr-10" required
                  />
                </div>
              </div>

              <div className="flex gap-4 mt-8">
                <button type="button" onClick={() => setStep(1)} className="w-1/3 bg-gray-100 text-gray-600 py-3 rounded-lg font-bold">رجوع</button>
                <button type="submit" className="w-2/3 btn-primary flex items-center justify-center gap-2">
                  <span>حفظ وإكمال الإعداد</span>
                  <CheckCircle size={18} />
                </button>
              </div>
            </div>
          )}
        </form>
      </div>

      {/* Right Panel */}
      <div className={`bg-thaqib-primary text-white flex flex-col justify-center items-center relative transition-all duration-1000 ease-in-out ${isAnimating ? 'w-full' : 'w-1/2'}`}>
        <div className="z-10 flex flex-col items-center max-w-lg text-center space-y-8 animate-in fade-in zoom-in-95 duration-1000">
           <img src="/thaqib-logo.png" alt="Thaqib Logo" className="w-auto h-48 object-contain" />
           <h1 className="text-4xl font-bold">مرحبا بك في ثاقب</h1>
           <p className="text-blue-100 text-lg">رؤية ذكية تدعم دقة القرار، لضمان تكافؤ الفرص وحماية النزاهة الأكاديمية.</p>
        </div>
      </div>
    </div>
  );
}
