import React from 'react';
import './DeleteConfirmModal.css';

const DeleteConfirmModal = ({ isOpen, onClose, onConfirm }) => {
  if (!isOpen) return null;

  return (
    <div className="delete-modal-overlay" onClick={onClose} dir="rtl">
      <div className="delete-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="delete-modal-icon-container">
          <img src={process.env.PUBLIC_URL + '/icons/red_trash_large.svg'} alt="Delete Icon" className="large-delete-icon" />
        </div>
        
        <h3 className="delete-modal-title">هل أنت متأكد أنك تريد حذف هذا الإمتحان ؟</h3>
        <p className="delete-modal-subtitle">
          إذا قمت بحذف الإمتحان فلن تتمكن من ايجاده او إضافته او العثور على المعلومات الخاصة به
        </p>

        <div className="delete-modal-actions">
          <button className="confirm-delete-btn" onClick={onConfirm}>نعم. حذف</button>
          <button className="cancel-delete-btn" onClick={onClose}>إلغاء</button>
        </div>
      </div>
    </div>
  );
};

export default DeleteConfirmModal;
