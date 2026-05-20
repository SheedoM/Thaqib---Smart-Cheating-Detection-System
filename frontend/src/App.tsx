import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { authFetch } from './config/api';
import SetupWizard from './components/SetupWizard';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import InvigilatorLayout from './layouts/InvigilatorLayout';
import SchedulePage from './pages/invigilator/SchedulePage';
import HallMonitoringPage from './pages/invigilator/HallMonitoringPage';
import PttPage from './pages/invigilator/PttPage';

export default function App() {
  const [user, setUser] = useState<any>(null);
  const [isInstalled, setIsInstalled] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);

  const checkStatus = async () => {
    try {
      // 1. Check if user is logged in
      const sessionResponse = await authFetch('/api/auth/me');
      if (sessionResponse.ok) {
        const userData = await sessionResponse.json();
        setUser(userData);
        setLoading(false);
        return;
      }

      // 2. Check if system is installed
      const statusResponse = await authFetch('/api/setup/status');
      if (statusResponse.ok) {
        const statusData = await statusResponse.json();
        setIsInstalled(statusData.is_installed);
      } else {
        setIsInstalled(false); // Fallback to setup
      }
    } catch (err) {
      console.error('Error checking status:', err);
      setIsInstalled(false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkStatus();
  }, []);

  const handleLoginSuccess = () => {
    checkStatus();
  };

  const handleLogout = async () => {
    try {
      await authFetch('/api/auth/logout', { method: 'POST' });
    } catch (err) {
      console.error('Logout failed:', err);
    }
    setUser(null);
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#fafafb] gap-4" dir="rtl">
        <Loader2 className="animate-spin text-[#8e52cb]" size={48} />
        <p className="text-gray-500 font-medium font-arabic">جاري التحميل...</p>
      </div>
    );
  }

  // Not installed -> Setup
  if (isInstalled === false && !user) {
    return (
      <div className="flex w-full min-h-screen bg-[#fafafb]" dir="rtl">
        <AuthBanner />
        <div className="flex-1 flex flex-col justify-center items-center px-6 lg:px-20">
          <SetupWizard onSuccess={() => setIsInstalled(true)} />
        </div>
      </div>
    );
  }

  // Not logged in -> Login
  if (!user) {
    return (
      <div className="flex w-full min-h-screen bg-[#fafafb]" dir="rtl">
        <AuthBanner />
        <div className="flex-1 flex flex-col justify-center items-center px-6 lg:px-20">
          <LoginPage onLoginSuccess={handleLoginSuccess} />
        </div>
      </div>
    );
  }

  // Logged in -> Routing based on role
  return (
    <BrowserRouter>
      <Routes>
        {user.role === 'admin' ? (
          <>
            <Route path="/dashboard/*" element={<DashboardPage onLogout={handleLogout} />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </>
        ) : user.role === 'invigilator' ? (
          <Route path="/invigilator" element={<InvigilatorLayout onLogout={handleLogout} />}>
            <Route index element={<SchedulePage />} />
            <Route path="session/:sessionId/:hallId" element={<HallMonitoringPage />} />
            <Route path="ptt" element={<PttPage />} />
            <Route path="settings" element={<div className="p-8 text-center text-gray-500">قريباً...</div>} />
            <Route path="*" element={<Navigate to="/invigilator" replace />} />
          </Route>
        ) : (
          <Route path="*" element={
            <div className="flex flex-col items-center justify-center min-h-screen p-8 text-center">
              <h1 className="text-2xl font-bold text-red-600 mb-4">خطأ في الصلاحيات</h1>
              <p className="text-gray-600 mb-8">عذراً، هذا الحساب لا يملك الصلاحيات الكافية للوصول للنظام.</p>
              <button onClick={handleLogout} className="thaqib-button">تسجيل الخروج</button>
            </div>
          } />
        )}
        
        {/* Default redirect for / or any unknown route */}
        <Route path="/" element={<Navigate to={user.role === 'admin' ? "/dashboard" : "/invigilator"} replace />} />
      </Routes>
    </BrowserRouter>
  );
}

// Reusable Banner Component
function AuthBanner() {
  return (
    <div className="hidden lg:flex w-[55%] relative overflow-hidden m-8 rounded-[24px]">
      <img src="/Frame 1000003437.png" alt="BG" className="absolute inset-0 w-full h-full object-cover z-0" />
      <div className="absolute inset-0 bg-gradient-to-b from-[rgba(147,81,187,0.88)] to-[rgba(68,0,110,0.88)] z-10"></div>
      <div className="absolute inset-0 z-20 flex flex-col items-center">
        <div className="flex flex-col items-center pt-12">
          <div className="h-[90px] w-[130px] flex items-center justify-center mb-6">
            <img src="/Frame 76.svg" alt="Thaqib" className="max-h-full max-w-full object-contain" />
          </div>
          <h1 className="text-[#fffefe] text-[48px] font-semibold leading-tight mb-3 text-center">مرحبا بك فى Thaqib</h1>
          <p className="text-[rgba(255,254,254,0.9)] text-[22px] font-medium text-center">بوابتك إلى المراقبة السهلة.</p>
        </div>
        <div className="flex flex-col items-center mt-auto mb-[72px] gap-[12px] px-8">
          <h2 className="text-[#fffefe] text-[32px] font-semibold text-center mb-2">رؤية ذكية لضمان نزاهة الامتحانات</h2>
          <div className="text-[rgba(255,254,254,0.9)] text-[16px] font-medium leading-[28px] text-center">
            <p>رؤية ذكية تدعم دقة القرار، لضمان تكافؤ الفرص وحماية النزاهة الأكاديمية،</p>
            <p>صُمم ليكون العين الساهرة التي تعزز العدالة دون المساس بالخصوصية.</p>
          </div>
          <div className="flex gap-[6px] mt-4">
            <div className="w-[32px] h-[6px] bg-white rounded-[10px]"></div>
            <div className="w-[6px] h-[6px] bg-[#c496ff] rounded-[100px]"></div>
            <div className="w-[6px] h-[6px] bg-[#c496ff] rounded-[100px]"></div>
          </div>
        </div>
      </div>
    </div>
  );
}
