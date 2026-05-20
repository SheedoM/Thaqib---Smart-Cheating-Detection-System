import { NavLink, Outlet } from 'react-router-dom';
import { Calendar, Mic, Bell, Settings, LogOut } from 'lucide-react';
import { useInvigilatorPtt } from '../hooks/useInvigilatorPtt';

interface InvigilatorLayoutProps {
  onLogout: () => void;
}

export default function InvigilatorLayout({ onLogout }: InvigilatorLayoutProps) {
  // Auto-connect PTT when invigilator layout mounts so the mic is ready
  // before they navigate into the hall monitoring page.
  const ptt = useInvigilatorPtt({ autoConnect: true });

  return (
    <div className="flex flex-col min-h-screen bg-[#F5F5F7]" dir="rtl">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white border-b border-[#EEE] px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <img src="/Frame 76.svg" alt="Logo" className="h-8 w-auto" />
          <h1 className="text-xl font-bold text-thaqib-primary">Thaqib</h1>
        </div>
        <div className="flex items-center gap-4">
          {/* PTT connection status badge */}
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold ${
            ptt.state === 'connected'
              ? 'bg-green-50 text-green-600'
              : ptt.state === 'connecting'
              ? 'bg-yellow-50 text-yellow-600'
              : ptt.state === 'error'
              ? 'bg-red-50 text-red-500'
              : 'bg-gray-50 text-gray-400'
          }`}>
            <div className={`w-1.5 h-1.5 rounded-full ${
              ptt.state === 'connected'
                ? 'bg-green-500 animate-pulse'
                : ptt.state === 'connecting'
                ? 'bg-yellow-500 animate-pulse'
                : ptt.state === 'error'
                ? 'bg-red-500'
                : 'bg-gray-400'
            }`} />
            {ptt.state === 'connected' ? 'PTT متصل' : ptt.state === 'connecting' ? 'جاري الاتصال' : ptt.state === 'error' ? 'خطأ PTT' : 'PTT غير متصل'}
          </div>
          <button className="p-2 text-gray-500 hover:bg-gray-100 rounded-full relative">
            <Bell size={22} />
            <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
          </button>
          <button
            onClick={onLogout}
            className="p-2 text-gray-500 hover:bg-gray-100 rounded-full"
          >
            <LogOut size={22} />
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 pb-24 overflow-y-auto">
        <Outlet />
      </main>

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-[#EEE] px-6 py-3 flex items-center justify-around">
        <NavLink
          to="/invigilator"
          end
          className={({ isActive }) =>
            `flex flex-col items-center gap-1 transition-colors ${isActive ? 'text-thaqib-primary' : 'text-gray-400'}`
          }
        >
          <Calendar size={24} />
          <span className="text-[11px] font-medium">جدولي</span>
        </NavLink>

        <NavLink
          to="/invigilator/ptt"
          className={({ isActive }) =>
            `flex flex-col items-center gap-1 transition-colors ${isActive ? 'text-thaqib-primary' : 'text-gray-400'}`
          }
        >
          <div className="relative">
            <Mic size={24} />
            {ptt.state === 'connected' && (
              <span className="absolute -top-1 -right-1 w-2 h-2 bg-green-500 rounded-full" />
            )}
          </div>
          <span className="text-[11px] font-medium">اتصال</span>
        </NavLink>

        <NavLink
          to="/invigilator/settings"
          className={({ isActive }) =>
            `flex flex-col items-center gap-1 transition-colors ${isActive ? 'text-thaqib-primary' : 'text-gray-400'}`
          }
        >
          <Settings size={24} />
          <span className="text-[11px] font-medium">الإعدادات</span>
        </NavLink>
      </nav>
    </div>
  );
}
