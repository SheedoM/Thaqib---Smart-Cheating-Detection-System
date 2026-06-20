import { NavLink, Outlet } from 'react-router-dom';
import { Calendar, Bell, Settings, LogOut } from 'lucide-react';
import { isInsecureLanContext } from '../lib/secureContext';

interface InvigilatorLayoutProps {
  onLogout: () => void;
}

export default function InvigilatorLayout({ onLogout }: InvigilatorLayoutProps) {
  return (
    <div className="flex flex-col min-h-screen bg-[#F5F5F7]" dir="rtl">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white border-b border-[#EEE] px-6 py-4 flex items-center justify-between">
        <div className="flex items-center">
          <img src="/Frame 75.svg" alt="Thaqib" className="h-10 w-auto object-contain" />
        </div>
        <div className="flex items-center gap-4">
          {isInsecureLanContext() && (
            <div className="hidden sm:block px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 text-[10px] font-bold">
              HTTPS مطلوب للميكروفون
            </div>
          )}
          <button className="p-2 text-gray-500 hover:bg-gray-100 rounded-full relative">
            <Bell size={22} />
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
