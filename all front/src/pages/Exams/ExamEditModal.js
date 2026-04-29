import React, { useState } from 'react';
import './ExamEditModal.css';
import DeleteConfirmModal from './DeleteConfirmModal';

const ExamEditModal = ({ isOpen, onClose, examData }) => {
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);

  if (!isOpen) return null;

  const handleDeleteClick = () => {
    setIsDeleteConfirmOpen(true);
  };

  const handleConfirmDelete = () => {
    // Logic to delete would go here
    setIsDeleteConfirmOpen(false);
    onClose();
  };

  return (
    <div className="exam-modal-overlay" onClick={onClose} dir="rtl">
      <div className="exam-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="exam-modal-header">
          <div className="exam-modal-title-group">
            <h2 className="exam-modal-title">
              {examData ? (
                <>
                  {examData.title}
                  <img src={process.env.PUBLIC_URL + '/icons/fi_1827933.svg'} alt="Edit" className="edit-icon-inline" />
                </>
              ) : (
                <>
                  <img src={process.env.PUBLIC_URL + '/icons/gg_add.svg'} alt="Add" className="add-icon-inline" />
                  اسم الامتحان
                </>
              )}
            </h2>
          </div>
          {examData && (
            <button className="delete-exam-btn-modal" onClick={handleDeleteClick}>
              <span>حذف الامتحان</span>
              <img src={process.env.PUBLIC_URL + '/icons/fi_3405244.svg'} alt="Delete" className="delete-icon-modal" />
            </button>
          )}
        </div>

        <div className="exam-modal-body">
          <div className="exam-modal-column-right">
            <div className="exam-input-group">
              <label>الاسم</label>
              <input type="text" className="exam-text-input" defaultValue={examData ? examData.title : ''} placeholder="اسم المادة" />
            </div>
            <div className="exam-input-group">
              <label>نوع الامتحان</label>
              <div className="exam-select-box">
                <span className={!examData ? 'placeholder-text' : ''}>{examData ? examData.type : 'نوع الامتحان'}</span>
                <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} alt="Chevron" className="select-chevron" />
              </div>
            </div>
            <div className="exam-input-group">
              <label>التاريخ</label>
              <input type="text" className="exam-text-input" defaultValue={examData ? examData.date : ''} placeholder="mm/dd/yyyy" />
            </div>
            <div className="exam-input-group">
              <label>الفترة</label>
              <div className="exam-select-box">
                <span className={!examData ? 'placeholder-text' : ''}>{examData ? examData.period : 'الفترة'}</span>
                <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} alt="Chevron" className="select-chevron" />
              </div>
            </div>
          </div>

          <div className="exam-modal-column-left">
            <div className="exam-input-group">
              <label>القاعات</label>
              <div className="exam-multi-select">
                <div className="exam-chips">
                  {examData ? (
                    <>
                      <span className="exam-chip">101B <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} className="chip-close" /></span>
                      <span className="exam-chip">102B <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} className="chip-close" /></span>
                      <span className="exam-chip">103B <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} className="chip-close" /></span>
                    </>
                  ) : (
                    <span className="placeholder-text">حدد القاعات</span>
                  )}
                </div>
                <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} alt="Chevron" className="select-chevron" />
              </div>
            </div>
            
            <div className="exam-input-group">
              <label>{examData ? 'مراقبين 101B' : 'المراقبين'}</label>
              <div className="exam-multi-select">
                <div className="exam-chips">
                  {examData ? (
                    <>
                      <span className="exam-chip">محمد احمد <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} className="chip-close" /></span>
                      <span className="exam-chip">عمر السيد <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} className="chip-close" /></span>
                    </>
                  ) : (
                    <span className="placeholder-text">حدد المراقبين</span>
                  )}
                </div>
                <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} alt="Chevron" className="select-chevron" />
              </div>
            </div>

            {examData && (
              <>
                <div className="exam-input-group">
                  <label>مراقبين 102B</label>
                  <div className="exam-multi-select">
                    <div className="exam-chips">
                      <span className="exam-chip">محمد احمد <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} className="chip-close" /></span>
                      <span className="exam-chip">عمر السيد <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} className="chip-close" /></span>
                    </div>
                    <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} alt="Chevron" className="select-chevron" />
                  </div>
                </div>

                <div className="exam-input-group">
                  <label>مراقبين 103B</label>
                  <div className="exam-multi-select">
                    <div className="exam-chips">
                      <span className="exam-chip">محمد احمد <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} className="chip-close" /></span>
                      <span className="exam-chip">عمر السيد <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} className="chip-close" /></span>
                    </div>
                    <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} alt="Chevron" className="select-chevron" />
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="exam-modal-bottom-section">
          <div className="exam-image-upload-right">
            {!examData ? (
              <div className="exam-add-image-placeholder">
                <img src={process.env.PUBLIC_URL + '/icons/ic_photo.png'} alt="Add Image" className="add-img-icon" />
                <span>إضافة صورة</span>
              </div>
            ) : (
              <div className="exam-image-edit-container">
                <div className="exam-image-preview">
                  <img src={process.env.PUBLIC_URL + '/exam_thumb.jpg'} alt="Preview" className="preview-img" />
                </div>
                <button className="exam-change-img-btn">
                  <img src={process.env.PUBLIC_URL + '/icons/camera.png'} alt="Camera" className="cam-icon" />
                  تغيير الصورة
                </button>
              </div>
            )}
          </div>

          <div className="exam-modal-actions-left">
            <button className="exam-save-btn" onClick={onClose}>
              {examData ? 'حفظ التعديلات' : 'إضافة الامتحان'}
            </button>
            <button className="exam-cancel-btn" onClick={onClose}>إلغاء</button>
          </div>
        </div>
      </div>

      <DeleteConfirmModal 
        isOpen={isDeleteConfirmOpen} 
        onClose={() => setIsDeleteConfirmOpen(false)} 
        onConfirm={handleConfirmDelete}
      />
    </div>
  );
};

export default ExamEditModal;
