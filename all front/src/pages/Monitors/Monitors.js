import React, { useState } from 'react';
import './Monitors.css';
import Header from '../../components/Header/Header';
import MonitorEditModal from './MonitorEditModal';
import MonitorDeleteModal from './MonitorDeleteModal';

const mockMonitors = [
  { id: 1, name: 'د.احمد السيد', status: 'غير متاح', image: 'profile.png' },
  { id: 2, name: 'د.احمد السيد', status: 'متاح', image: 'profile.png' },
  { id: 3, name: 'د.احمد السيد', status: 'متاح', image: 'profile.png' },
  { id: 4, name: 'د.احمد السيد', status: 'غير متاح', image: 'profile.png' },
  { id: 5, name: 'د.احمد السيد', status: 'متاح', image: 'profile.png' },
  { id: 6, name: 'د.احمد السيد', status: 'غير متاح', image: 'profile.png' },
  { id: 7, name: 'د.احمد السيد', status: 'متاح', image: 'profile.png' },
  { id: 8, name: 'د.احمد السيد', status: 'غير متاح', image: 'profile.png' },
];

const Monitors = ({ activeTab, setActiveTab }) => {
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [selectedMonitor, setSelectedMonitor] = useState(null);

  const handleEditClick = (monitor) => {
    setSelectedMonitor(monitor);
    setIsEditModalOpen(true);
  };

  const handleDeleteClick = (monitor) => {
    setSelectedMonitor(monitor);
    setIsDeleteModalOpen(true);
  };

  return (
    <div className="dashboard-layout" dir="rtl">
      <div className="dashboard-header-bg">
        <div className="decorative-overlay"></div>
      </div>

      <Header activeTab={activeTab} setActiveTab={setActiveTab} />

      <main className="dashboard-main monitors-main">
        <div className="exams-header-section">
          <div className="exams-header-right">
            <h1 className="hero-title">المشرفين</h1>
            <div className="exam-status-badge-button">
              <span>المشرفين</span>
              <img src={process.env.PUBLIC_URL + '/icons/la_users.svg'} alt="Users Icon" className="status-badge-icon" />
            </div>
          </div>
          
          <div className="exams-header-left">
            <div className="search-dropdown-box">
              <span>بحث</span>
              <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} alt="Chevron" className="search-icon-chevron" />
            </div>
          </div>
        </div>

        <div className="monitors-content-container fade-in">
          <div className="exams-list-controls">
            <h2 className="content-section-title">المشرفين</h2>
            <button className="create-monitor-btn" onClick={() => handleEditClick(null)}>
              <span>إضافة مشرف</span>
              <img src={process.env.PUBLIC_URL + '/icons/gg_add.svg'} alt="Add" className="btn-add-icon" />
            </button>
          </div>

          <div className="monitors-cards-grid">
            {mockMonitors.map(monitor => (
              <div key={monitor.id} className="monitor-card">
                <div className="monitor-card-header">
                  <span className={`monitor-status-badge ${monitor.status === 'متاح' ? 'available' : 'unavailable'}`}>
                    {monitor.status}
                  </span>
                </div>
                
                <div className="monitor-card-body">
                  <div className="monitor-image-wrap">
                    <img src={process.env.PUBLIC_URL + '/' + monitor.image} alt={monitor.name} className="monitor-img" />
                  </div>
                  <h3 className="monitor-name">{monitor.name}</h3>
                </div>

                <div className="monitor-card-footer">
                  <button className="monitor-edit-btn" onClick={() => handleEditClick(monitor)}>
                    <span>تعديل</span>
                    <img src={process.env.PUBLIC_URL + '/icons/fi_1827933.svg'} alt="Edit" className="edit-icon-small" />
                  </button>
                  <button className="monitor-delete-btn" onClick={() => handleDeleteClick(monitor)}>
                    <img src={process.env.PUBLIC_URL + '/icons/fi_3405244.svg'} alt="Delete" className="delete-icon-small" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* Modals */}
      <MonitorEditModal 
        isOpen={isEditModalOpen} 
        onClose={() => setIsEditModalOpen(false)} 
        monitorData={selectedMonitor}
      />
      <MonitorDeleteModal 
        isOpen={isDeleteModalOpen} 
        onClose={() => setIsDeleteModalOpen(false)} 
        onConfirm={() => setIsDeleteModalOpen(false)}
        monitorName={selectedMonitor?.name}
      />
    </div>
  );
};

export default Monitors;
