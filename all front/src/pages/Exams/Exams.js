import React, { useState } from 'react';
import './Exams.css';
import Header from '../../components/Header/Header';
import ExamEditModal from './ExamEditModal';

const mockExams = [
  { id: 1, title: 'قواعد البيانات', date: '12 مارس 2026', type: 'ميدترم', halls: '101B, 120B, 103B', period: 'الفترة الثانية', students: 680, icon: 'exam_card_default.png' },
  { id: 2, title: 'قواعد البيانات', date: '12 مارس 2026', type: 'ميدترم', halls: '101B, 120B, 103B', period: 'الفترة الثانية', students: 680, icon: 'brain_blue.png' },
  { id: 3, title: 'قواعد البيانات', date: '12 مارس 2026', type: 'ميدترم', halls: '101B, 120B, 103B', period: 'الفترة الثانية', students: 680, icon: 'brain_blue.png' },
  { id: 4, title: 'قواعد البيانات', date: '12 مارس 2026', type: 'ميدترم', halls: '101B, 120B, 103B', period: 'الفترة الثانية', students: 680, icon: 'exam_card_default.png' },
  { id: 5, title: 'قواعد البيانات', date: '12 مارس 2026', type: 'ميدترم', halls: '101B, 120B, 103B', period: 'الفترة الثانية', students: 680, icon: 'brain_blue.png' },
  { id: 6, title: 'قواعد البيانات', date: '12 مارس 2026', type: 'ميدترم', halls: '101B, 120B, 103B', period: 'الفترة الثانية', students: 680, icon: 'brain_blue.png' },
  { id: 7, title: 'قواعد البيانات', date: '12 مارس 2026', type: 'عملي', halls: '101B, 120B, 103B', period: 'الفترة الثانية', students: 680, icon: 'brain_blue.png' },
  { id: 8, title: 'قواعد البيانات', date: '12 مارس 2026', type: 'ميدترم', halls: '101B, 120B, 103B', period: 'الفترة الثانية', students: 680, icon: 'brain_blue.png' },
  { id: 9, title: 'قواعد البيانات', date: '12 مارس 2026', type: 'ميدترم', halls: '101B, 120B, 103B', period: 'الفترة الثانية', students: 680, icon: 'brain_blue.png' },
  { id: 10, title: 'قواعد البيانات', date: '12 مارس 2026', type: 'ميدترم', halls: '101B, 120B, 103B', period: 'الفترة الثانية', students: 680, icon: 'brain_blue.png' },
  { id: 11, title: 'قواعد البيانات', date: '12 مارس 2026', type: 'ميدترم', halls: '101B, 120B, 103B', period: 'الفترة الثانية', students: 680, icon: 'brain_blue.png' },
  { id: 12, title: 'قواعد البيانات', date: '12 مارس 2026', type: 'ميدترم', halls: '101B, 120B, 103B', period: 'الفترة الثانية', students: 680, icon: 'brain_blue.png' },
];

const Exams = ({ activeTab, setActiveTab }) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedExam, setSelectedExam] = useState(null);

  const openAddModal = () => {
    setSelectedExam(null);
    setIsModalOpen(true);
  };

  const openEditModal = (exam) => {
    setSelectedExam(exam);
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setSelectedExam(null);
  };

  return (
    <div className="dashboard-layout" dir="rtl">
      <div className="dashboard-header-bg">
        <div className="decorative-overlay"></div>
      </div>

      <Header activeTab={activeTab} setActiveTab={setActiveTab} />

      <main className="dashboard-main exams-main">
        <div className="exams-header-section">
          <div className="exams-header-right">
            <h1 className="hero-title">الإمتحانات</h1>
            <div className="exam-status-badge-button">
              <span>الإمتحانات</span>
              <img src={process.env.PUBLIC_URL + '/icons/arcticons_example.svg'} alt="Exam Icon" className="status-badge-icon" />
            </div>
          </div>
          
          <div className="exams-header-left">
            <div className="search-dropdown-box">
              <span>بحث</span>
              <img src={process.env.PUBLIC_URL + '/icons/chevron-down.png'} alt="Chevron" className="search-icon-chevron" />
            </div>
          </div>
        </div>

        <div className="exams-content-container fade-in">
          <div className="exams-list-controls">
            <h2 className="content-section-title">الإمتحانات</h2>
            <button className="create-exam-btn" onClick={openAddModal}>
              <span>إضافة إمتحان</span>
              <img src={process.env.PUBLIC_URL + '/icons/gg_add.svg'} alt="Add" className="btn-add-icon" />
            </button>
          </div>

          <div className="exams-cards-grid">
            {mockExams.map(exam => (
              <div key={exam.id} className="exam-card-item">
                <div className="exam-card-top">
                  <span className="exam-card-date">{exam.date}</span>
                  <span className={`exam-badge ${exam.type === 'عملي' ? 'practical' : exam.type === 'فاينال' ? 'final' : 'midterm'}`}>
                    {exam.type}
                  </span>
                </div>
                
                <div className="exam-card-divider"></div>

                <div className="exam-card-content">
                  <div className="exam-card-icon-wrap">
                    <img src={process.env.PUBLIC_URL + '/icons/' + exam.icon} alt="Icon" className="exam-card-img" />
                  </div>
                  <div className="exam-card-info-col">
                    <div className="exam-card-info">
                      <h3 className="exam-card-title">{exam.title}</h3>
                      <p className="exam-card-halls">{exam.halls}</p>
                      <p className="exam-card-period">{exam.period}</p>
                    </div>
                    
                    <div className="exam-card-bottom">
                      <span className="exam-student-stat">{exam.students} طالب</span>
                      <div className="exam-card-edit" onClick={() => openEditModal(exam)} style={{ cursor: 'pointer' }}>
                        <span>تعديل</span>
                        <img src={process.env.PUBLIC_URL + '/21.svg'} alt="Edit" className="edit-link-icon" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>

      <ExamEditModal 
        isOpen={isModalOpen} 
        onClose={closeModal} 
        examData={selectedExam} 
      />
    </div>
  );
};

export default Exams;
