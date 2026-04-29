import React from 'react';
import './MonitorEditModal.css';

const MonitorEditModal = ({ isOpen, onClose, monitorData }) => {
  const isEdit = !!monitorData;
  if (!isOpen) return null;

  return (
    <div className="monitor-modal-overlay" onClick={onClose}>
      <div className="monitor-edit-card fade-in" onClick={(e) => e.stopPropagation()}>
        <div className="monitor-edit-header">
          <h2 className="monitor-edit-title">
            {isEdit ? 'تعديل معلومات المشرف' : 'إضافة مشرف'}
          </h2>
          {isEdit ? (
            <img src={process.env.PUBLIC_URL + '/icons/fi_1827933.svg'} alt="edit" className="edit-header-icon" />
          ) : (
            <img src={process.env.PUBLIC_URL + '/icons/gg_add.svg'} alt="add" className="edit-header-icon" />
          )}
        </div>

        <div className="monitor-edit-body">
          <div className="monitor-form-fields">
            <div className="monitor-input-group">
              <label>اسم المشرف</label>
              <input 
                type="text" 
                className="monitor-text-input" 
                placeholder="د.احمد السيد"
                defaultValue={monitorData?.name}
              />
            </div>

            <div className="monitor-input-group">
              <label>كود المشرف</label>
              <input 
                type="text" 
                className="monitor-text-input" 
                placeholder="1500256"
                defaultValue={monitorData?.id}
              />
            </div>

            <div className="monitor-input-group">
              <label>رقم الهاتف</label>
              <input 
                type="text" 
                className="monitor-text-input" 
                placeholder="01245678910"
                defaultValue={monitorData?.phone}
              />
            </div>
          </div>

          <div className="monitor-image-upload-area">
            <img 
              src={monitorData?.image ? process.env.PUBLIC_URL + '/' + monitorData.image : process.env.PUBLIC_URL + '/profile.png'} 
              alt="monitor" 
              className="current-monitor-img" 
            />
            <div className="monitor-image-overlay">
              <button className="change-photo-btn">
                <img src={process.env.PUBLIC_URL + '/ic_outline-photo-size-select-actual.svg'} alt="photo" className="photo-btn-icon" />
                <span>{isEdit ? 'تغيير الصورة' : 'إضافة الصورة'}</span>
              </button>
            </div>
          </div>

          <div className="monitor-modal-footer">
            <button className="monitor-cancel-btn" onClick={onClose}>
              إلغاء
            </button>
            <button className="monitor-save-btn" onClick={onClose}>
              {isEdit ? 'حفظ' : 'إضافة مشرف'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MonitorEditModal;
