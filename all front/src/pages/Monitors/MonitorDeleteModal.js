import React from 'react';
import './MonitorDeleteModal.css';

const MonitorDeleteModal = ({ isOpen, onClose, onConfirm, monitorName }) => {
  if (!isOpen) return null;

  return (
    <div className="monitor-modal-overlay">
      <div className="monitor-delete-card fade-in">
        <div className="delete-icon-wrapper">
          <div className="delete-icon-circle">
            <img src={process.env.PUBLIC_URL + '/icons/red_trash_large.svg'} alt="delete" className="delete-main-icon" />
          </div>
        </div>

        <div className="delete-modal-content">
          <h2 className="delete-modal-title">هل أنت متأكد أنك تريد حذف هذا المشرف ؟</h2>
          <p className="delete-modal-subtitle">
            إذا قمت بحذف المشرف فلن تتمكن من ايجاده او إضافته لأي امتحان مرة اخري
          </p>
        </div>

        <div className="delete-modal-actions">
          <button className="confirm-delete-btn" onClick={onConfirm}>
            نعم. حذف
          </button>
          <button className="cancel-delete-btn" onClick={onClose}>
            إلغاء
          </button>
        </div>
      </div>
    </div>
  );
};

export default MonitorDeleteModal;
