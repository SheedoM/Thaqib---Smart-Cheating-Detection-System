import React from 'react';
import './Header.css';

const Header = ({ activeTab, setActiveTab, transparent, hideLogo, hideReportsTab }) => {
  return (
    <header className={`dashboard-header ${transparent ? 'transparent' : ''}`}>
      <div className="header-right">
        {!hideLogo && (
          <div className="brand-container">
            <img src={process.env.PUBLIC_URL + '/logo.png'} alt="Thaqib Logo" className="brand-logo" />
          </div>
        )}
      </div>

      <nav className="header-nav">
        <a href="#main" className={`nav-item ${activeTab === 'الرئيسية' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); setActiveTab('الرئيسية'); }}>الرئيسية</a>
        <a href="#rooms" className={`nav-item ${activeTab === 'القاعات' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); setActiveTab('القاعات'); }}>القاعات</a>
        <a href="#exams" className={`nav-item ${activeTab === 'الإمتحانات' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); setActiveTab('الإمتحانات'); }}>الإمتحانات</a>
        <a href="#supervisors" className={`nav-item ${activeTab === 'المشرفين' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); setActiveTab('المشرفين'); }}>المشرفين</a>
        {!hideReportsTab && (
          <a href="#reports" className={`nav-item ${activeTab === 'التقارير' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); setActiveTab('التقارير'); }}>التقارير</a>
        )}
      </nav>

      <div className="header-left">
        <div className="user-actions">
          <button className="icon-btn">
            {/* Gear Icon - Settings */}
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.06-.94l2.03-1.58a.49.49 0 00.12-.61l-1.92-3.32a.488.488 0 00-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.484.484 0 00-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.56-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.06.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .43-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.49-.12-.61l-2.03-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z" /></svg>
          </button>
          <button className="icon-btn">
            {/* Bell Icon - Notifications */}
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2zm-2 1H8v-6c0-2.48 1.51-4.5 4-4.5s4 2.02 4 4.5v6z" /></svg>
          </button>
        </div>

        <div className="user-profile">
          <img src={process.env.PUBLIC_URL + '/profile.png'} alt="User Avatar" className="user-avatar" />
          <div className="user-info">
            <span className="user-name">عمرو طلعت</span>
            <span className="user-role">مشرف النظام</span>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
