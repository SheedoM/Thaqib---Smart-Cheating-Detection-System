import React, { useState } from 'react';
import './Reports.css';
import Header from '../../components/Header/Header';

const Reports = ({ activeTab, setActiveTab }) => {
  const [selectedReport, setSelectedReport] = useState(null);

  const reportsList = [
    {
      id: 1,
      subject: 'قواعد البيانات',
      cases: '3 حالات مؤكدة',
      time: 'منذ أسبوعين',
      students: 420,
      warnings: 9,
      date: '12 مارس 2024',
      hall: 'Cs-204',
      professor: 'أ.د وائل عبد القادر',
      absences: 6,
      session: 'الصف 3، المقاعد 7-8',
      content: {
        performance: 'تم مراقبة أداء النظام طوال فترة الامتحان، حيث حافظ على استقرار كامل بنسبة تشغيل بلغت 100%. لم يتم تسجيل أي حالات توقف أو تأخير في استجابة النظام، مما ضمن تجربة سلسة للطلاب والمراقبين على حد سواء.',
        technical: 'لم يتم رصد أي مشكلات تقنية حرجة أثناء سير العملية. تم التعامل مع بعض الاستفسارات البسيطة المتعلقة بتسجيل الدخول بشكل فوري، ولم تؤثر هذه الملاحظات على الجدول الزمني للامتحان أو دقة البيانات المسجلة.',
        security: 'تم تفعيل جميع بروتوكولات الأمان بنجاح، بما في ذلك التشفير الكامل للبيانات والمراقبة اللحظية للأنشطة. لم يتم اكتشاف أي محاولات اختراق أو وصول غير مصرح به، وتم تأكيد سلامة جميع سجلات الدخول والخروج.',
        compliance: 'التزم جميع المشاركين بالسياسات والإجراءات المعتمدة. تم توثيق جميع الأنشطة بدقة، وتوافق سير الامتحان مع المعايير المطلوبة لضمان الشفافية والنزاهة في النتائج النهائية.'
      }
    }
  ];

  for (let i = 2; i <= 8; i++) {
    reportsList.push({
      ...reportsList[0],
      id: i,
      subject: i % 2 === 0 ? 'تصميم منطقي' : 'هندسة برمجيات',
      date: `${12 + i} مارس 2024`
    });
  }

  const handleReportClick = (report) => {
    setSelectedReport(report);
  };

  const handleBack = () => {
    setSelectedReport(null);
  };

  return (
    <div className="reports-page-wrapper" dir="rtl">
      {/* Purple Hero Header */}
      <div className="reports-hero-header">
        <div className="hero-background-overlay"></div>
        
        {/* Standard Header with transparency, fully aligned with 4248:324 */}
        <Header activeTab={activeTab} setActiveTab={setActiveTab} transparent={true} />
        
        <div className="hero-content-area">
          <div className="hero-right-side">
            <h1 className="hero-main-title">التقارير</h1>
            <div className="reports-badge-new">
               <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M9 5H7C5.89543 5 5 5.89543 5 7V19C5 20.1046 5.89543 21 7 21H17C18.1046 21 19 20.1046 19 19V7C19 5.89543 18.1046 5 17 5H15M9 5C9 6.10457 9.89543 7 11 7H13C14.1046 7 15 6.10457 15 5M9 5C9 3.89543 9.89543 3 11 3H13C14.1046 3 15 3.89543 15 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
               <span>التقارير</span>
            </div>
          </div>
          
          <div className="hero-left-side">
             <div className="reports-search-box-hero">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M19 9L12 16L5 9" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                <input type="text" placeholder="بحث" />
             </div>
          </div>
        </div>
      </div>

      <main className="reports-content-main">
        {!selectedReport ? (
          <div className="reports-list-container fade-in">
            <div className="reports-main-title-row">
               <h2 className="reports-section-title">التقارير</h2>
            </div>

            <div className="reports-grid">
              {reportsList.map((report) => (
                <div 
                  key={report.id} 
                  className={`report-card-new ${selectedReport?.id === report.id ? 'active' : ''}`}
                  onClick={() => handleReportClick(report)}
                >
                  <div className="report-card-icon-floating">
                    <img src={report.id % 2 === 0 ? 'http://localhost:3845/assets/874517011ee556f662c3793bf11d92ba0a17b214.png' : 'http://localhost:3845/assets/f8bd39e8efb392e0e2c0a2f693e01f1c398bbb03.png'} alt="subject" />
                  </div>
                  
                  <div className="report-card-content">
                    <h3 className="report-card-title">{report.subject}</h3>
                    
                    <div className="report-card-info-rows">
                      <div className="info-row">
                        <span>{report.cases}</span>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
                          <circle cx="12" cy="12" r="3" fill="currentColor"/>
                        </svg>
                      </div>
                      <div className="info-row">
                        <span>منذ أسبوعين</span>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
                          <path d="M12 6V12L16 14" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                        </svg>
                      </div>
                    </div>

                    <div className="report-card-divider"></div>

                    <div className="report-card-stats-grid">
                      <div className="card-stat-col">
                        <span className="stat-label">التنبيهات</span>
                        <span className="stat-value">{report.warnings}</span>
                      </div>
                      <div className="card-stat-col">
                        <span className="stat-label">عدد الطلاب</span>
                        <span className="stat-value">{report.students}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="report-detail-container fade-in">
            <div className="report-detail-header-new">
              <div className="detail-header-left">
                <div className="meta-info-group">
                   <span className="report-date-text">{selectedReport.date}</span>
                   <span className="report-hall-text">{selectedReport.hall}</span>
                   <button className="download-small-btn">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M21 15V19C21 19.5304 20.7893 20.0391 20.4142 20.4142C20.0391 20.7893 19.5304 21 19 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V15M7 10L12 15M12 15L17 10M12 15V3" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                      <span>تنزيل التقرير</span>
                   </button>
                </div>
              </div>

              <div className="detail-professor-profile">
                <div className="professor-info-text">
                  <h2 className="professor-name-large">{selectedReport.subject}</h2>
                  <span className="professor-fullname">{selectedReport.professor}</span>
                </div>
                <div className="professor-avatar-wrapper">
                  <img src="http://localhost:3845/assets/f8bd39e8efb392e0e2c0a2f693e01f1c398bbb03.png" alt="subject" className="subject-img-large" />
                </div>
              </div>
            </div>

            <div className="report-info-bar-new">
               <div className="info-badge-item student-count">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M17 21V19C17 17.9391 16.5786 16.9217 15.8284 16.1716C15.0783 15.4214 14.0609 15 13 15H5C3.93913 15 2.92172 15.4214 2.17157 16.1716C1.42143 16.9217 1 17.9391 1 19V21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    <path d="M9 11C11.2091 11 13 9.20914 13 7C13 4.79086 11.2091 3 9 3C6.79086 3 5 4.79086 5 7C5 9.20914 6.79086 11 9 11Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  <span>{selectedReport.students} طالب</span>
               </div>
               <div className="info-badge-item room-count">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M3 9L12 2L21 9V20C21 20.5304 20.7893 21.0391 20.4142 21.4142C20.0391 21.7893 19.5304 22 19 22H5C4.46957 22 3.96086 21.7893 3.58579 21.4142C3.21071 21.0391 3 20.5304 3 20V9Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  <span>6 قاعات</span>
               </div>
               <div className="info-badge-item absence-count">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M16 21V19C16 17.9391 15.5786 16.9217 14.8284 16.1716C14.0783 15.4214 13.0609 15 12 15H5C3.93913 15 2.92172 15.4214 2.17157 16.1716C1.42143 16.9217 1 17.9391 1 19V21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  <span>{selectedReport.absences} غياب</span>
               </div>
               <div className="info-badge-item warning-count">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
                    <path d="M12 8V12M12 16H12.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  <span>{selectedReport.warnings} تحذير</span>
               </div>
            </div>

            <div className="report-content-body-new">
               <h3 className="report-body-title">تقرير مقرر {selectedReport.subject} 2026</h3>
               <div className="report-text-sections">
                  <p><strong>أداء النظام والاستقرار (System Performance & Uptime)</strong></p>
                  <p>{selectedReport.content.performance}</p>
                  
                  <p><strong>سجلات الأخطاء والمشاكل التقنية (Error Logs & Technical Issues)</strong></p>
                  <p>{selectedReport.content.technical}</p>
                  
                  <p><strong>المراقبة الأمنية وسلامة الجلسات (Security & Session Integrity)</strong></p>
                  <p>{selectedReport.content.security}</p>
                  
                  <p><strong>التوصيات التقنية المرفوعة (Technical Recommendations)</strong></p>
                  <p>{selectedReport.content.compliance}</p>
               </div>
            </div>
            
            <button className="back-to-list-btn" onClick={handleBack}>
               عودة للتقارير
            </button>
          </div>
        )}
      </main>
    </div>
  );
};

export default Reports;
