import React, { useState, useRef, useEffect } from 'react';
import { ImagePlus, User, Lock, Mail, ChevronRight, UserCircle, CheckCircle } from 'lucide-react';

export default function App() {
  const [step, setStep] = useState(1);
  const [isAnimating, setIsAnimating] = useState(true);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [formData, setFormData] = useState({
    institution_name: '',
    logo_file: null as File | null,
    admin_full_name: '',
    admin_username: '',
    admin_email: '',
    admin_password: '',
  });

  useEffect(() => {
    // Show full screen banner for 2 seconds, then slide
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
          logo_url: "placeholder_logo.png", // File upload handled separately in production
          admin_full_name: formData.admin_full_name,
          admin_username: formData.admin_username,
          admin_email: formData.admin_email,
          admin_password: formData.admin_password
        })
      });

      if (response.ok) {
        alert("✅ تم إعداد النظام وحفظ حساب المشرف بنجاح!");
        // Redirect to login or admin dashboard here
      } else {
        const errData = await response.json();
        alert("❌ حدث خطأ أثناء الإعداد: " + errData.detail);
      }
    } catch (err) {
      alert("❌ تعذر الاتصال بالخادم. تأكد من تشغيل الباك إند.");
    }
  };

  return (
    <div className={`flex min-h-screen w-full font-cairo ${isAnimating ? 'overflow-hidden' : ''}`} dir="rtl">
      {/* Left Form Panel */}
      <div className={`bg-white flex flex-col justify-center items-center relative transition-all duration-1000 ease-in-out ${isAnimating ? 'w-0 opacity-0 overflow-hidden px-0' : 'w-1/2 opacity-100 p-12'}`}>
        <div className="absolute top-8 left-8 text-sm text-gray-400 font-semibold min-w-max">
          خطوة {step} من 2
        </div>

        <form onSubmit={handleSubmit} className="w-full max-w-md space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 min-w-[28rem]">

          {/* Step 1: Institution Details */}
          {step === 1 && (
            <div className="space-y-6">
              <div className="text-center space-y-2 mb-8">
                <h1 className="text-2xl font-bold text-gray-800">مرحباً بك 👋</h1>
                <p className="text-gray-500 font-semibold">قم بإضافة المعلومات حول الكلية</p>
              </div>

              <div className="space-y-4">
                <input
                  type="text"
                  name="institution_name"
                  placeholder="اسم الكلية"
                  value={formData.institution_name}
                  onChange={handleInputChange}
                  className="input-field"
                  required
                />

                {/* Logo Upload Box */}
                <div
                  onClick={handleBoxClick}
                  className="border-2 border-dashed border-gray-200 rounded-xl p-8 flex flex-col items-center justify-center cursor-pointer hover:bg-gray-50 hover:border-thaqib-primary transition-colors group relative overflow-hidden h-40"
                >
                  {logoPreview ? (
                    <img src={logoPreview} alt="Preview" className="w-full h-full object-contain" />
                  ) : (
                    <>
                      <div className="bg-gray-400 group-hover:bg-thaqib-primary text-white rounded-lg p-2 mb-3 transition-colors">
                        <ImagePlus size={24} />
                      </div>
                      <span className="text-gray-500 font-semibold text-sm">إضافة اللوجو</span>
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
              </div>

              <button
                type="button"
                onClick={handleNext}
                className="btn-primary mt-8 flex items-center justify-center gap-2"
              >
                <span>التالي</span>
                <ChevronRight size={18} className="translate-y-[1px]" />
              </button>
            </div>
          )}

          {/* Step 2: Admin Account Details */}
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
                    type="text" name="admin_full_name"
                    placeholder="الاسم الكامل"
                    value={formData.admin_full_name} onChange={handleInputChange}
                    className="input-field pr-10" required
                  />
                </div>

                <div className="relative">
                  <User className="absolute right-3 top-3.5 text-gray-400" size={20} />
                  <input
                    type="text" name="admin_username"
                    placeholder="اسم المستخدم"
                    value={formData.admin_username} onChange={handleInputChange}
                    className="input-field pr-10" required
                  />
                </div>

                <div className="relative">
                  <Mail className="absolute right-3 top-3.5 text-gray-400" size={20} />
                  <input
                    type="email" name="admin_email"
                    placeholder="البريد الإلكتروني"
                    value={formData.admin_email} onChange={handleInputChange}
                    className="input-field pr-10" required
                  />
                </div>

                <div className="relative">
                  <Lock className="absolute right-3 top-3.5 text-gray-400" size={20} />
                  <input
                    type="password" name="admin_password"
                    placeholder="كلمة المرور"
                    value={formData.admin_password} onChange={handleInputChange}
                    className="input-field pr-10" required
                  />
                </div>
              </div>

              <div className="flex gap-4 mt-8">
                <button
                  type="button" onClick={() => setStep(1)}
                  className="w-1/3 bg-gray-100 text-gray-600 py-3 rounded-lg font-bold hover:bg-gray-200 transition-colors"
                >
                  رجوع
                </button>
                <button type="submit" className="w-2/3 btn-primary flex items-center justify-center gap-2">
                  <span>حفظ وإكمال الإعداد</span>
                  <CheckCircle size={18} className="translate-y-[1px]" />
                </button>
              </div>
            </div>
          )}
        </form>
      </div>

      {/* Right Branding Panel */}
      <div className={`bg-thaqib-primary text-white flex flex-col justify-center items-center relative overflow-hidden transition-all duration-1000 ease-in-out ${isAnimating ? 'w-full' : 'w-1/2'}`}>
        {/* Abstract Background Waves Placeholder */}
        <div className="absolute inset-0 opacity-10 pointer-events-none">
          <svg className="absolute w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
            <path d="M0,50 Q25,20 50,50 T100,50 L100,100 L0,100 Z" fill="currentColor" />
            <path d="M0,60 Q35,80 70,40 T100,60 L100,100 L0,100 Z" fill="currentColor" opacity="0.5" />
          </svg>
        </div>

        <div className="z-10 flex flex-col items-center max-w-lg text-center space-y-8 animate-in fade-in zoom-in-95 duration-1000">

          {/* Real Thaqib Logo */}
          <div className={`flex flex-col items-center justify-center transition-transform duration-1000 ${isAnimating ? 'scale-125' : 'scale-100'}`}>
            <img
              src="/thaqib-logo.png"
              alt="Thaqib Logo"
              className="w-auto h-32 md:h-48 object-contain drop-shadow-xl mb-4"
              onError={(e) => {
                // If the user hasn't added the logo yet, fallback nicely
                (e.target as HTMLImageElement).src = "https://via.placeholder.com/300x150/44006E/FFFFFF?text=Thaqib+Owl+Logo";
              }}
            />
            {!isAnimating && <h2 className="text-3xl font-bold tracking-[0.2em] mt-2 animate-in fade-in duration-700">THAQIB</h2>}
          </div>

          <div className={`space-y-4 mt-8 transition-opacity duration-1000 max-w-md w-full ${isAnimating ? 'opacity-0 h-0 overflow-hidden' : 'opacity-100 h-auto'}`}>
            <h1 className="text-4xl font-bold">مرحبا بك في ثاقب</h1>
            <p className="text-blue-100 text-lg leading-relaxed">
              رؤية ذكية تدعم دقة القرار، لضمان تكافؤ الفرص وحماية النزاهة الأكاديمية،
              صُمم ليكون العين الساهرة التي تعزز العدالة دون المساس بالخصوصية.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
