import React, { useState } from 'react';
import Dashboard from './pages/Dashboard/Dashboard';
import Rooms from './pages/Rooms/Rooms';
import Exams from './pages/Exams/Exams';
import Monitors from './pages/Monitors/Monitors';
import Reports from './pages/Reports/Reports';

function App() {
  const [activeTab, setActiveTab] = useState('الرئيسية');

  return (
    <div className="app-container">
      {activeTab === 'الرئيسية' && <Dashboard activeTab={activeTab} setActiveTab={setActiveTab} />}
      {activeTab === 'القاعات' && <Rooms activeTab={activeTab} setActiveTab={setActiveTab} />}
      {activeTab === 'الإمتحانات' && <Exams activeTab={activeTab} setActiveTab={setActiveTab} />}
      {activeTab === 'المشرفين' && <Monitors activeTab={activeTab} setActiveTab={setActiveTab} />}
      {activeTab === 'التقارير' && <Reports activeTab={activeTab} setActiveTab={setActiveTab} />}
    </div>
  );
}

export default App;