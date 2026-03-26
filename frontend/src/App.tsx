import { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import SetupWizard from './components/SetupWizard';
import LoginPage from './pages/LoginPage';

type ViewState = 'loading' | 'setup' | 'login' | 'dashboard';

export default function App() {
  const [view, setView] = useState<ViewState>('loading');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/setup/status');
        if (response.ok) {
          const data = await response.json();
          setView(data.is_installed ? 'login' : 'setup');
        } else {
          setErrorMsg('فشل في التحقق من حالة النظام.');
          setView('setup'); // Fallback to setup
        }
      } catch (err) {
        console.error('Error checking setup status:', err);
        setErrorMsg('تعذر الاتصال بالخادم. تأكد من تشغيل الباك إند.');
        setView('setup'); // Fallback
      }
    };

    checkStatus();
  }, []);

  return (
    <div className="flex w-full min-h-screen bg-[#fafafb]" dir="rtl">
      {/* Right Banner - Reusable across Auth/Setup views */}
      <div className="hidden lg:flex w-[55%] relative overflow-hidden m-8 rounded-[24px]">
        {/* Banner Base Background Image */}
        <img 
          src="/Frame 1000003437.png" 
          alt="Background Texture" 
          className="absolute inset-0 w-full h-full object-cover z-0"
        />
        
        {/* Gradient Overlay at 88% opacity (rgba) */}
        <div className="absolute inset-0 bg-gradient-to-b from-[rgba(147,81,187,0.88)] to-[rgba(68,0,110,0.88)] z-10"></div>

        {/* Content Container */}
        <div className="absolute inset-0 z-20 flex flex-col items-center">
          
          {/* Top Group: Logo & Welcome Text */}
          <div className="flex flex-col items-center pt-12">
            <div className="h-[90px] w-[130px] flex items-center justify-center mb-6">
              <img 
                src="/Frame 76.svg" 
                alt="Thaqib Logo" 
                className="max-h-full max-w-full object-contain"
              />
            </div>
            
            <h1 className="text-[#fffefe] text-[48px] font-semibold leading-tight mb-3 text-center">
              مرحبا بك فى ثاقب
            </h1>
            <p className="text-[rgba(255,254,254,0.9)] text-[22px] font-medium leading-[28px] text-center">
              بوابتك إلى المراقبة السهلة.
            </p>
          </div>

          {/* Bottom Group: Description Text */}
          <div className="flex flex-col items-center mt-auto mb-[72px] gap-[12px] px-8">
            <h2 className="text-[#fffefe] text-[32px] font-semibold leading-tight text-center mb-2">
              رؤية ذكية لضمان نزاهة الامتحانات
            </h2>
            <div className="text-[rgba(255,254,254,0.9)] text-[16px] font-medium leading-[28px] text-center">
              <p>رؤية ذكية تدعم دقة القرار، لضمان تكافؤ الفرص وحماية النزاهة الأكاديمية،</p>
              <p>صُمم ليكون العين الساهرة التي تعزز العدالة دون المساس بالخصوصية.</p>
            </div>
            {/* Dots */}
            <div className="flex gap-[6px] mt-4">
              <div className="w-[32px] h-[6px] bg-white rounded-[10px]"></div>
              <div className="w-[6px] h-[6px] bg-[#c496ff] rounded-[100px]"></div>
              <div className="w-[6px] h-[6px] bg-[#c496ff] rounded-[100px]"></div>
            </div>
          </div>
        </div>
      </div>

      {/* Left Area - Dynamic based on view */}
      <div className="flex-1 flex flex-col justify-center items-center px-6 lg:px-20 relative">
        {view === 'loading' && (
          <div className="flex flex-col items-center gap-4">
            <Loader2 className="animate-spin text-[#8e52cb]" size={48} />
            <p className="text-gray-500 font-medium font-arabic">جاري التحميل...</p>
          </div>
        )}

        {view === 'setup' && (
          <>
            {errorMsg && (
              <div className="absolute top-10 left-10 right-10 z-50">
                <div className="bg-amber-50 border border-amber-200 text-amber-800 px-4 py-2 rounded-lg text-sm text-center">
                  {errorMsg} (إظهار شاشة الإعداد بشكل افتراضي)
                </div>
              </div>
            )}
            <SetupWizard onSuccess={() => setView('login')} />
          </>
        )}

        {view === 'login' && <LoginPage />}

        {view === 'dashboard' && (
          <div className="text-center">
            <h1 className="text-3xl font-bold mb-4">لوحة التحكم</h1>
            <p>مرحباً بك في النظام الرئيسي!</p>
          </div>
        )}
      </div>
    </div>
  );
}
