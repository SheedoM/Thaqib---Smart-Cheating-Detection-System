import { useState, useEffect } from 'react';
import { apiUrl, authFetch } from '../config/api';
import { Clock, ShieldAlert, AlertTriangle, Users } from 'lucide-react';

interface ExamSession {
  id: string;
  exam_name: string;
  exam_type: string;
  scheduled_start: string;
  status: string;
  student_count: number;
}

export default function ReportsTab({ initialReport = null, onBack }: { initialReport?: ExamSession | null, onBack?: () => void }) {
  const [sessions, setSessions] = useState<ExamSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedReport, setSelectedReport] = useState<ExamSession | null>(initialReport);

  useEffect(() => {
    const fetchReports = async () => {
      try {
        const res = await authFetch('/api/sessions/');
        if (res.ok) {
          const data = await res.json();
          setSessions(data || []);
        }
      } catch (err) {
        console.error('Failed to fetch sessions', err);
      } finally {
        setLoading(false);
      }
    };
    fetchReports();
  }, []);

  const calculateTimeAgo = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      const diffMs = new Date().getTime() - d.getTime();
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
      if (diffDays === 0) return 'اليوم';
      if (diffDays === 1) return 'منذ يوم';
      if (diffDays === 2) return 'منذ يومين';
      if (diffDays <= 7) return `منذ ${diffDays} أيام`;
      if (diffDays <= 14) return 'منذ أسبوع';
      if (diffDays <= 21) return 'منذ أسبوعين';
      return `منذ ${Math.floor(diffDays / 7)} أسابيع`;
    } catch {
      return 'غير معروف';
    }
  };

  const formatDateLong = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('ar-EG', { day: 'numeric', month: 'long', year: 'numeric' });
    } catch {
      return '12 مارس 2026';
    }
  };

  if (selectedReport) {
    return (
      <div className="reports-section p-8 w-full max-w-7xl mx-auto" dir="rtl">
        <button onClick={() => { if (onBack) onBack(); else setSelectedReport(null); }} className="mb-6 text-[#44006E] font-bold flex items-center gap-2 hover:underline cursor-pointer">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
          العودة للقائمة
        </button>

        <div className="bg-white rounded-[24px] border-2 border-gray-100 p-8 shadow-sm">
          {/* Header */}
          <div className="flex justify-between items-start w-full">
            {/* Right side: Icon, Title, Subtitle, Badges */}
            <div className="flex gap-6">
              {/* Icon */}
              <div className="w-[126px] h-[120px] rounded-full bg-gradient-to-br from-indigo-50 to-purple-50 border-4 border-[#f3f3f3] shadow-inner flex items-center justify-center shrink-0">
                <svg width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="#44006E" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                  <line x1="8" y1="21" x2="16" y2="21"></line>
                  <line x1="12" y1="17" x2="12" y2="21"></line>
                </svg>
              </div>
              
              {/* Info */}
              <div className="flex flex-col pt-2">
                <h3 className="text-[32px] font-bold text-gray-800 mb-2">{selectedReport.exam_name}</h3>
                <p className="text-[22px] text-gray-500 mb-6">أ.د وائل عبد القادر</p>
                
                {/* Badges */}
                <div className="flex gap-4 items-center">
                  <div className="bg-[#f9f5ff] text-[#44006E] flex items-center gap-2 px-4 py-2 rounded-2xl h-[40px]">
                    <Users size={20} />
                    <span className="text-[20px] font-medium">{selectedReport.student_count || 520} طالب</span>
                  </div>
                  <div className="border border-[#44006E] text-[#44006E] flex items-center gap-2 px-4 py-2 rounded-2xl h-[40px]">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 14v3M12 14v3M16 14v3"/></svg>
                    <span className="text-[20px] font-medium">6 قاعات</span>
                  </div>
                  <div className="border border-[#ff8919] text-[#ff8919] flex items-center gap-2 px-4 py-2 rounded-2xl h-[40px]">
                    <Users size={20} />
                    <span className="text-[20px] font-medium">6 غياب</span>
                  </div>
                  <div className="border border-[#ff3636] text-[#ff3636] flex items-center gap-2 px-4 py-2 rounded-2xl h-[40px]">
                    <ShieldAlert size={20} />
                    <span className="text-[20px] font-medium">14 تحذير</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Left side: Date, Code, Button */}
            <div className="flex flex-col items-end pt-2">
              <p className="text-[17px] text-gray-400 mb-2">{formatDateLong(selectedReport.scheduled_start)}</p>
              <p className="text-[17px] text-gray-400 mb-8">{selectedReport.exam_type || 'Cs-204'}</p>
              
              <button className="bg-[#44006E] text-white flex items-center gap-2 px-6 py-3 rounded-xl hover:bg-purple-900 transition-colors shadow-md cursor-pointer">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
                <span className="text-[16px] font-medium">تنزيل التقرير</span>
              </button>
            </div>
          </div>

          <div className="w-full h-px bg-gray-200 my-8"></div>

          {/* Body */}
          <div className="px-4">
            <h4 className="text-[28px] font-bold text-gray-800 mb-8">تقرير مقرر {selectedReport.exam_name} 2026</h4>
            
            <div className="text-[20px] text-gray-600 leading-[40px] space-y-6 whitespace-pre-wrap">
              <p className="text-gray-800 font-bold">أداء النظام والاستقرار (System Performance & Uptime)</p>
              <p>سجل خادم المنصة استقراراً عاماً بنسبة إتاحة (Uptime) بلغت 99.9% طوال مدة انعقاد الامتحان. لوحظ ارتفاع حاد ومفاجئ في استهلاك موارد الخادم (CPU و RAM) خلال الدقائق العشر الأولى بسبب عمليات تسجيل الدخول المتزامنة لجميع الطلاب، إلا أن آلية توزيع الأحمال (Load Balancing) استجابت بفعالية ونجحت في استيعاب التكدس دون حدوث أي توقف أو انهيار للنظام (System Crash). استقر معدل استهلاك الموارد عند مستوياته الطبيعية بمجرد بدء الطلاب في الإجابة، وبلغ متوسط زمن الاستجابة (Latency) للطلبات حوالي 120 مللي ثانية، وهو معدل ممتاز ومطابق للمعايير المستهدفة.</p>
              
              <p className="text-gray-800 font-bold mt-8">سجلات الأخطاء والمشاكل التقنية (Error Logs & Technical Issues)</p>
              <p>تم رصد مجموعة من الأخطاء التقنية المحدودة التي لم تؤثر على سير الامتحان بشكل عام. سجل النظام 5 أخطاء من نوع (Timeout Errors) ناتجة عن انقطاع أو ضعف الاتصال بالإنترنت من طرف المستخدم النهائي (Client-side)، وقد تم التدخل تلقائياً عبر ميزة الحفظ المؤقت (Local Storage Sync) لضمان عدم فقدان أي إجابات، وتمت مزامنة البيانات فور عودة الاتصال. كما تم رصد مشكلة برمجية طفيفة (UI Glitch) واجهت طالبين عند محاولة رفع ملفات الإجابة المعقدة، حيث استغرق الخادم وقتاً أطول من المعتاد لمعالجة الطلبات البرمجية (API Requests)، وتم حلها بعمل تحديث للصفحة مع الاحتفاظ بالتقدم.</p>
              
              <p className="text-gray-800 font-bold mt-8">المراقبة الأمنية وسلامة الجلسات (Security & Session Integrity)</p>
              <p>عملت طبقات الحماية بكفاءة عالية؛ حيث قام جدار الحماية (WAF) بحظر 3 محاولات اتصال من عناوين IP خارجية غير مألوفة، وتم تصنيفها كحركة مرور مشبوهة. على مستوى جلسات الامتحان (Exam Sessions)، نجحت خوارزمية منع الغش في رصد وتوثيق 10 محاولات لتبديل النوافذ (Browser Tab Switching) أو فقدان التركيز على شاشة الامتحان (Loss of Focus). كما تم اكتشاف محاولة واحدة للوصول إلى النظام باستخدام شبكة افتراضية (VPN)، مما أدى إلى وضع علامة (Flag) على جلسة المستخدم وتوثيق الـ IP الحقيقي الخاص به في السجلات الأمنية لمراجعته لاحقاً. لم يتم رصد أي محاولات لاختراق قاعدة البيانات أو التلاعب بالبيانات المرسلة.</p>
              
              <p className="text-gray-800 font-bold mt-8">التوصيات التقنية المرفوعة (Technical Recommendations)</p>
              <p>بناءً على المعطيات السابقة، يُوصى بزيادة سعة الخوادم الافتراضية بنسبة 20% (Auto-scaling) قبل بدء الامتحانات المستقبلية التي يتجاوز عدد المسجلين فيها 150 مستخدماً، وذلك لتفادي أي اختناقات محتملة في الشبكة (Bottlenecks) خلال الدقائق الأولى. كما يُنصح بمراجعة وتحسين الأكواد البرمجية الخاصة بنقطة النهاية (Endpoint) المسؤولة عن معالجة ورفع الملفات، لتقليل زمن الاستجابة وتجنب أخطاء الرفع المتأخر. يُقترح أيضاً تحديث سياسات الحماية لإرسال تنبيهات فورية لمسؤولي النظام عبر لوحة التحكم بمجرد رصد استخدام برامج الـ VPN لتسريع اتخاذ الإجراءات اللازمة.</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="reports-section p-8 w-full max-w-7xl mx-auto" dir="rtl">
      {/* Title */}
      <div className="flex justify-between items-center mb-12">
        <h2 className="text-[36px] font-bold text-[#44006E]">التقارير</h2>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-x-6 gap-y-12">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-white/50 animate-pulse h-[250px] rounded-[16px] border border-gray-100"></div>
          ))}
        </div>
      ) : sessions.length === 0 ? (
        <div className="flex flex-col items-center py-24 bg-white rounded-[24px] border border-gray-100 shadow-sm">
          <p className="text-gray-400 font-bold text-lg mb-3">لا توجد تقارير متاحة</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-x-6 gap-y-12 mt-8">
          {sessions.map((session) => {
            const casesCount = Math.floor(Math.random() * 5) + 1; // Mock data since API doesn't provide it yet
            const alertsCount = Math.floor(Math.random() * 20) + 5; // Mock data
            const studentCount = session.student_count || 420;

            return (
              <div
                key={session.id}
                onClick={() => setSelectedReport(session)}
                className="group relative flex flex-col justify-end h-[250px] rounded-[16px] cursor-pointer transition-all duration-300 transform hover:-translate-y-1 bg-white hover:bg-[#44006E] border border-gray-100 hover:border-transparent shadow-sm hover:shadow-[0_12px_24px_rgba(68,0,110,0.25)]"
              >
                {/* Floating Icon overlapping top border */}
                <div className="absolute -top-[30px] left-1/2 -translate-x-1/2 w-[72px] h-[72px] rounded-full bg-gradient-to-br from-indigo-100 to-purple-100 border-[6px] border-[#f3f3f3] shadow-inner flex items-center justify-center overflow-hidden">
                   {/* Fallback SVG if image is not available */}
                   <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#44006E" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                     <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                     <line x1="8" y1="21" x2="16" y2="21"></line>
                     <line x1="12" y1="17" x2="12" y2="21"></line>
                   </svg>
                </div>

                <div className="px-6 pt-12 pb-6 flex flex-col items-center h-full">
                  {/* Title */}
                  <h3 className="text-[28px] font-bold text-center mb-6 leading-tight text-gray-800 group-hover:text-white transition-colors duration-300">
                    {session.exam_name}
                  </h3>

                  {/* Badges / Subtitles */}
                  <div className="flex flex-col gap-2 mb-6 w-full px-4">
                    <div className="flex items-center justify-end gap-2">
                      <span className="text-[16px] font-medium text-gray-400 group-hover:text-purple-200 transition-colors duration-300">
                        {casesCount} حالات مؤكدة
                      </span>
                      <ShieldAlert size={16} className="text-gray-400 group-hover:text-purple-200 transition-colors duration-300" />
                    </div>
                    <div className="flex items-center justify-end gap-2">
                      <span className="text-[16px] font-medium text-gray-400 group-hover:text-purple-200 transition-colors duration-300">
                        {calculateTimeAgo(session.scheduled_start)}
                      </span>
                      <Clock size={16} className="text-gray-400 group-hover:text-purple-200 transition-colors duration-300" />
                    </div>
                  </div>

                  {/* Divider */}
                  <div className="w-full h-px mb-5 bg-gray-100 group-hover:bg-white/10 transition-colors duration-300"></div>

                  {/* Footer Stats */}
                  <div className="flex justify-between items-center w-full px-2">
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-[16px] font-medium text-gray-500 group-hover:text-purple-200 transition-colors duration-300">
                        التنبيهات
                      </span>
                      <span className="text-[24px] font-bold text-gray-800 group-hover:text-white transition-colors duration-300">
                        {alertsCount}
                      </span>
                    </div>
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-[16px] font-medium text-gray-500 group-hover:text-purple-200 transition-colors duration-300">
                        عدد الطلاب
                      </span>
                      <span className="text-[24px] font-bold text-gray-800 group-hover:text-white transition-colors duration-300">
                        {studentCount}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
