import React from 'react';
import './Modals.css';

const EditAddModal = ({ isOpen, onClose, mode, roomData }) => {
  if (!isOpen) return null;

  const isEdit = mode === 'edit';
  const title = isEdit ? 'تعديل معلومات القاعة' : 'إضافة قاعة';
  
  // Dummy arrays for rendering inputs
  const devices = [1, 2, 3, 4, 5, 6, 7, 8];

  return (
    <div className="modal-overlay" onClick={onClose} dir="rtl">
      <div className="edit-add-modal-content" onClick={(e) => e.stopPropagation()}>
        <h2 className="modal-title">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
            {isEdit ? (
              <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34a.9959.9959 0 00-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
            ) : (
              <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" />
            )}
          </svg>
          {title}
        </h2>

        <div className="modal-body">
          <div className="top-section">
            <div className="basic-info-inputs">
              <input type="text" className="text-input" placeholder="اسم القاعة" defaultValue={isEdit ? roomData?.name?.split(' ')[1] : ''} />
              <input type="text" className="text-input" placeholder="عدد الطلاب" defaultValue={isEdit ? roomData?.students + ' طالب' : ''} />
            </div>

            <div className="image-upload-area">
              <div className="image-preview" style={isEdit ? {backgroundImage: `url(${process.env.PUBLIC_URL + '/classroom.png'})`} : {}}>
                {/* Image Placeholder Background if not edited */}
              </div>
              <button className="change-img-btn">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                  <path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/>
                </svg>
                تغيير الصورة
              </button>
            </div>
          </div>

          <div className="hardware-section">
            <h3 className="section-subtitle">الأجهزة</h3>
            
            <div className="hardware-tables">
              <div className="hardware-column">
                <h4 className="column-title">الكاميرات</h4>
                <div className="inputs-grid">
                  {devices.map(i => (
                    <div className="device-row" key={`cam-${i}`}>
                      <input type="text" className="grid-input" placeholder="اسم الجهاز" />
                      <input type="text" className="grid-input" placeholder="Device Type" />
                      <input type="text" className="grid-input" placeholder="IP Address" />
                      <input type="text" className="grid-input" placeholder="RTSP URL" />
                    </div>
                  ))}
                </div>
              </div>
              
              <div className="hardware-column">
                <h4 className="column-title">المايكات</h4>
                <div className="inputs-grid">
                  {devices.slice(0, 4).map(i => (
                    <div className="device-row" key={`mic-${i}`}>
                      <input type="text" className="grid-input" placeholder="اسم الجهاز" />
                      <input type="text" className="grid-input" placeholder="Device Type" />
                      <input type="text" className="grid-input" placeholder="IP Address" />
                      <input type="text" className="grid-input" placeholder="RTSP URL" />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        <button className="save-btn" onClick={onClose}>حفظ</button>
      </div>
    </div>
  );
};

export default EditAddModal;
