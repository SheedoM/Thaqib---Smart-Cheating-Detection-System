import React from 'react';
import './Modals.css';

const DeleteModal = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose} dir="rtl">
      <div className="delete-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="delete-icon-wrapper">
          <div className="delete-icon-circle">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
              <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
            </svg>
          </div>
        </div>
        
        <h3 className="delete-title">هل أنت متأكد أنك تريد حذف هذه القاعة؟</h3>
        <p className="delete-description">إذا قمت بحذف القاعة فلن تتمكن من إيجادها أو إضافة أي امتحان بها مرة أخري</p>
        
        <div className="delete-actions">
          <button className="btn-cancel" onClick={onClose}>إلغاء</button>
          <button className="btn-confirm-delete" onClick={onClose}>نعم، حذف</button>
        </div>
      </div>
    </div>
  );
};

export default DeleteModal;
