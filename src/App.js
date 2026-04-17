import React, { useState } from 'react';
import Dashboard from './pages/Dashboard/Dashboard';
import Rooms from './pages/Rooms/Rooms';

function App() {
  const [activeTab, setActiveTab] = useState('الرئيسية');

  return (
    <div className="app-container">
      {activeTab === 'الرئيسية' && <Dashboard activeTab={activeTab} setActiveTab={setActiveTab} />}
      {activeTab === 'القاعات' && <Rooms activeTab={activeTab} setActiveTab={setActiveTab} />}
    </div>
  );
}

export default App;