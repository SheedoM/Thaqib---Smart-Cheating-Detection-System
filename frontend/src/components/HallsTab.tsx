import { useState, useEffect } from 'react';
import { apiUrl, authFetch } from '../config/api';

interface DeviceItem {
  id?: string;
  name: string;
  type: string;
  status: string;
  ip_address?: string;
  rtsp_url?: string;
  stream_url?: string;
  identifier?: string;
  active?: boolean;
}

interface HallItem {
  id: string;
  name: string;
  capacity?: number;
  image?: string;
  status: string;
  cameras: DeviceItem[];
  mics: DeviceItem[];
}

interface HallsTabProps {
  // We can pass token or rely on localStorage inside requests
}

export default function HallsTab({}: HallsTabProps) {
  const [halls, setHalls] = useState<HallItem[]>([]);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editingHall, setEditingHall] = useState<HallItem | null>(null);
  const [deletingHall, setDeletingHall] = useState<HallItem | null>(null);

  const fetchHalls = async () => {
    try {
      const res = await authFetch('/api/stream/monitoring');
      if (res.ok) {
        const data = await res.json();
        setHalls(data.halls || []);
      }
    } catch (err) {
      console.error('Failed to fetch halls', err);
    }
  };

  const handleDeleteHall = async (id: string) => {
    try {
      const res = await authFetch(`/api/halls/${id}`, { method: 'DELETE' });
      if (res.ok) {
        fetchHalls();
        setDeletingHall(null);
      }
    } catch (err) {
      console.error('Failed to delete hall', err);
    }
  };

  useEffect(() => {
    fetchHalls();
  }, []);

  return (
    <div className="halls-section" dir="rtl" style={{ padding: '24px' }}>
      <div className="flex justify-between items-center mb-10">
        <div className="flex items-center gap-3">
          <div className="w-1.5 h-8 bg-[#44006e] rounded-full"></div>
          <h2 className="text-[32px] font-black text-[#03178c]">إدارة القاعات</h2>
        </div>
        <button 
          className="thaqib-button cursor-pointer flex items-center justify-center gap-2 group shadow-lg hover:shadow-xl transition-all" 
          style={{ width: 'auto', padding: '0 28px', height: '48px', borderRadius: '14px', backgroundColor: '#00D261' }}
          onClick={() => setIsAddModalOpen(true)}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="group-hover:rotate-90 transition-transform duration-300">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          <span className="font-bold text-[17px]">إضافة قاعة</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-8">
        {halls.map(hall => (
          <HallCard 
            key={hall.id} 
            hall={hall} 
            onEdit={() => setEditingHall(hall)} 
            onDelete={() => setDeletingHall(hall)} 
          />
        ))}
        {halls.length === 0 && (
          <div className="col-span-full py-20 text-center bg-white/50 rounded-3xl border-2 border-dashed border-gray-200">
            <div className="w-20 h-20 bg-white rounded-full flex items-center justify-center shadow-md mx-auto mb-4">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path></svg>
            </div>
            <p className="text-gray-500 font-bold text-lg">لا توجد قاعات حالياً</p>
            <p className="text-gray-400 text-sm mt-1">اضغط على "إضافة قاعة" للبدء</p>
          </div>
        )}
      </div>

      {isAddModalOpen && (
        <HallModal 
          onClose={() => setIsAddModalOpen(false)} 
          onSuccess={() => {
            setIsAddModalOpen(false);
            fetchHalls();
          }} 
        />
      )}

      {editingHall && (
        <HallModal 
          hall={editingHall} 
          onClose={() => setEditingHall(null)} 
          onSuccess={() => {
            setEditingHall(null);
            fetchHalls();
          }} 
        />
      )}

      {deletingHall && (
        <DeleteConfirmationModal 
          hallName={deletingHall.name} 
          onClose={() => setDeletingHall(null)} 
          onConfirm={() => handleDeleteHall(deletingHall.id)} 
        />
      )}
    </div>
  );
}

// ─── Hall Card Component ─────────────────────────────────────────────────────

function HallCard({ hall, onEdit, onDelete }: { hall: HallItem, onEdit: () => void, onDelete: () => void }) {
  const isAvailable = hall.cameras?.some(c => c.active);

  return (
    <div className="group bg-white rounded-[24px] border border-gray-100 shadow-sm hover:shadow-2xl hover:-translate-y-2 transition-all duration-300 overflow-hidden flex flex-col h-[340px] relative">
      {/* Top Banner with Badges */}
      <div className="h-[100px] bg-[#EFEFF3] relative overflow-hidden">
        <div className="absolute inset-0 opacity-10">
           <svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none">
             <path d="M0 0 L100 0 L100 100 Z" fill="#44006E" />
           </svg>
        </div>
        
        <div className="p-4 flex justify-between items-start relative z-10">
          <span className={`px-3 py-1 rounded-full text-[11px] font-black ${isAvailable ? 'bg-[#D8F3DC] text-[#1B4332]' : 'bg-[#FFD6D6] text-[#9D0208]'}`}>
            {isAvailable ? 'متاحة' : 'غير متاحة'}
          </span>
          <span className="px-3 py-1 rounded-full text-[11px] font-black bg-[#E7E1FF] text-[#44006E]">
            {hall.capacity || 0} طالب
          </span>
        </div>
      </div>

      {/* Hall Image (Floating) */}
      <div className="flex justify-center -mt-[50px] relative z-20">
        <div className="w-[100px] h-[100px] rounded-full border-[6px] border-white shadow-lg overflow-hidden bg-white">
          <img 
            src={hall.image || "https://images.unsplash.com/photo-1540544660406-6aee9fda6553?auto=format&fit=crop&q=80&w=300"} 
            alt={hall.name} 
            className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
            onError={(e) => { e.currentTarget.src = 'https://images.unsplash.com/photo-1540544660406-6aee9fda6553?auto=format&fit=crop&q=80&w=300' }}
          />
        </div>
      </div>

      {/* Hall Details */}
      <div className="flex-1 px-6 pt-4 text-center">
        <h3 className="text-[22px] font-black text-[#2D005F] mb-1">{hall.name}</h3>
        <p className="text-gray-400 text-sm font-medium">إدارة القاعة والأجهزة المتصلة</p>
      </div>

      {/* Actions */}
      <div className="p-5 flex gap-3 border-t border-gray-50 bg-[#FCFBFF]">
        <button 
          onClick={onEdit}
          className="flex-1 h-[46px] flex items-center justify-center gap-2 bg-[#44006E] text-white text-[15px] font-bold rounded-xl hover:bg-[#340055] shadow-md transition-all cursor-pointer"
        >
          <span>تعديل</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
        </button>
        <button 
          onClick={onDelete}
          className="w-[46px] h-[46px] flex items-center justify-center bg-white border-2 border-[#FFD6D6] rounded-xl text-[#E63946] hover:bg-[#FFE5E5] transition-all cursor-pointer shadow-sm"
          title="حذف القاعة"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
        </button>
      </div>
    </div>
  );
}

// ─── Delete Confirmation Modal ───────────────────────────────────────────────

function DeleteConfirmationModal({ hallName, onClose, onConfirm }: { hallName: string, onClose: () => void, onConfirm: () => void }) {
  return (
    <div className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="bg-white rounded-[32px] shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200" dir="rtl">
        <div className="p-8 flex flex-col items-center text-center">
          {/* Danger Icon */}
          <div className="w-20 h-20 bg-[#FFF0F0] rounded-full flex items-center justify-center mb-6 shadow-inner">
            <div className="w-14 h-14 bg-[#FFE1E1] rounded-full flex items-center justify-center">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#E63946" strokeWidth="3">
                <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M10 11v6M14 11v6" />
              </svg>
            </div>
          </div>

          <h2 className="text-[24px] font-black text-[#2D005F] mb-3">هل أنت متأكد أنك تريد حذف هذه القاعة؟</h2>
          <p className="text-gray-500 font-medium text-[16px] leading-relaxed px-4">
            إذا قمت بحذف القاعة فلن نتمكن من إيجادها أو إضافة أي امتحان بها مرة أخرى
          </p>
        </div>

        <div className="p-6 flex gap-4 bg-gray-50 border-t border-gray-100">
          <button 
            onClick={onConfirm}
            className="flex-1 h-[52px] bg-[#E63946] text-white font-black rounded-2xl hover:bg-[#D62839] shadow-lg hover:shadow-red-200 transition-all cursor-pointer"
          >
            نعم، حذف
          </button>
          <button 
            onClick={onClose}
            className="flex-1 h-[52px] bg-white border-2 border-gray-200 text-gray-500 font-black rounded-2xl hover:bg-gray-100 transition-all cursor-pointer"
          >
            إلغاء
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Hall Modal (Add/Edit) ──────────────────────────────────────────────────

function HallModal({ onClose, onSuccess, hall }: { onClose: () => void, onSuccess: () => void, hall?: HallItem }) {
  const [name, setName] = useState(hall?.name || '');
  const [capacity, setCapacity] = useState(hall?.capacity?.toString() || '30');
  const [image, setImage] = useState<string>(hall ? (hall.image || '') : '');
  const [cameras, setCameras] = useState<any[]>(hall?.cameras || []);
  const [mics, setMics] = useState<any[]>(hall?.mics || []);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleAddCamera = () => {
    setCameras([...cameras, { name: '', identifier: '', ip_address: '', stream_url: '', type: 'camera' }]);
  };

  const handleAddMic = () => {
    setMics([...mics, { name: '', identifier: '', ip_address: '', type: 'microphone' }]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      const userRes = await authFetch('/api/auth/me');
      if (!userRes.ok) throw new Error('Failed to get user context');
      const user = await userRes.json();
      const institution_id = user.institution_id;

      if (!institution_id) throw new Error('User has no associated institution');

      let targetHallId = hall?.id;

      if (!targetHallId) {
        const hallRes = await authFetch('/api/halls/', {
          method: 'POST',
          body: JSON.stringify({
            institution_id,
            name,
            capacity: parseInt(capacity),
            image,
            status: 'active'
          })
        });

        if (!hallRes.ok) {
          const errData = await hallRes.json();
          throw new Error(errData.detail || 'Failed to create hall');
        }
        const createdHall = await hallRes.json();
        targetHallId = createdHall.id;
      } else {
        const hallRes = await authFetch(`/api/halls/${targetHallId}`, {
          method: 'PUT',
          body: JSON.stringify({
            name,
            capacity: parseInt(capacity),
            image
          })
        });
        if (!hallRes.ok) throw new Error('Failed to update hall');
      }
      
      const allDevices = [...cameras, ...mics];
      const newDevices = allDevices.filter(d => !d.id);

      for (const dev of newDevices) {
        if (!dev.name) continue;
        await authFetch('/api/devices/', {
          method: 'POST',
          body: JSON.stringify({
            hall_id: targetHallId,
            name: dev.name,
            identifier: dev.identifier || dev.name.replace(/\s+/g, '-').toLowerCase(),
            type: dev.type,
            ip_address: dev.ip_address || null,
            stream_url: dev.stream_url || dev.rtsp_url || null,
            status: 'active'
          })
        });
      }

      onSuccess();
    } catch (err: any) {
      setErrorMsg(err.message || 'حدث خطأ أثناء الحفظ');
    } finally {
      setIsSubmitting(false);
    }
  };

  const updateArray = (arr: any[], setArr: any, index: number, field: string, value: string) => {
    const newArr = [...arr];
    newArr[index][field] = value;
    setArr(newArr);
  };

  const removeArray = (arr: any[], setArr: any, index: number) => {
    const newArr = [...arr];
    newArr.splice(index, 1);
    setArr(newArr);
  };

  return (
    <div className="fixed inset-0 z-[100] bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="bg-white rounded-[32px] shadow-2xl w-full max-w-4xl max-h-[92vh] overflow-hidden flex flex-col animate-in zoom-in-95 duration-200" dir="rtl">
        
        {/* Header */}
        <div className="p-6 border-b border-gray-100 flex justify-between items-center bg-[#FCFBFF]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-100 rounded-xl flex items-center justify-center">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#44006e" strokeWidth="2.5"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path></svg>
            </div>
            <h2 className="text-2xl font-black text-[#2D005F]">{hall ? 'تعديل القاعة' : 'إضافة قاعة جديدة'}</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 cursor-pointer hover:text-gray-600 transition-colors bg-gray-100 rounded-full p-2">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>

        <div className="p-8 overflow-y-auto flex-1">
          {errorMsg && (
            <div className="mb-6 bg-red-50 text-red-600 p-4 rounded-2xl font-bold text-sm border border-red-100">
              {errorMsg}
            </div>
          )}

          <form id="hall-form" onSubmit={handleSubmit} className="space-y-10">
            {/* Banner Section */}
            <div className="relative h-56 rounded-[24px] overflow-hidden group bg-gray-100 border-2 border-dashed border-gray-300">
              {image ? (
                <img src={image} alt="Banner" className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex flex-col items-center justify-center text-gray-400 gap-3">
                  <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center shadow-sm">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
                  </div>
                  <span className="text-sm font-bold">ارفع صورة تعبيرية للقاعة</span>
                </div>
              )}
              
              <label className="absolute inset-0 cursor-pointer flex items-center justify-center bg-black/40 opacity-0 group-hover:opacity-100 transition-all">
                <span className="bg-white px-6 py-2.5 rounded-xl text-[#44006E] font-black shadow-xl flex items-center gap-2">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                  تغيير الصورة
                </span>
                <input type="file" accept="image/*" className="hidden" onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    const reader = new FileReader();
                    reader.onload = (ev) => { if (ev.target?.result) setImage(ev.target.result as string); };
                    reader.readAsDataURL(e.target.files[0]);
                  }
                }} />
              </label>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="space-y-2">
                <label className="text-sm font-black text-gray-700">اسم القاعة</label>
                <input 
                  type="text" 
                  required 
                  value={name} 
                  onChange={e => setName(e.target.value)}
                  className="w-full px-5 py-3 bg-gray-50 border border-gray-200 rounded-[16px] focus:ring-4 focus:ring-purple-100 focus:border-[#44006e] outline-none transition-all font-bold"
                  placeholder="مثال: قاعة 101B"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-black text-gray-700">السعة الاستيعابية</label>
                <input 
                  type="number" 
                  required 
                  value={capacity} 
                  onChange={e => setCapacity(e.target.value)}
                  className="w-full px-5 py-3 bg-gray-50 border border-gray-200 rounded-[16px] focus:ring-4 focus:ring-purple-100 focus:border-[#44006e] outline-none transition-all font-bold"
                  placeholder="30 طالب"
                />
              </div>
            </div>

            {/* Devices Section */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
              {/* Cameras */}
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="text-lg font-black text-[#2D005F]">الكاميرات</h3>
                  <button type="button" onClick={handleAddCamera} className="text-sm font-black text-[#44006e] bg-purple-50 px-4 py-1.5 rounded-full hover:bg-purple-100 transition-colors flex items-center gap-1 cursor-pointer">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                    إضافة
                  </button>
                </div>
                
                <div className="space-y-4">
                  {cameras.map((cam, idx) => (
                    <div key={idx} className="bg-gray-50 p-5 rounded-[20px] border border-gray-100 relative group/dev shadow-sm">
                      <button type="button" onClick={() => removeArray(cameras, setCameras, idx)} className="absolute -top-2 -left-2 w-8 h-8 bg-white border border-red-100 text-red-500 rounded-full flex items-center justify-center opacity-0 group-hover/dev:opacity-100 transition-all shadow-md hover:bg-red-50">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                      </button>
                      <div className="space-y-3">
                        <input type="text" value={cam.name} disabled={!!cam.id} onChange={e => updateArray(cameras, setCameras, idx, 'name', e.target.value)} className="w-full text-sm font-bold bg-white px-4 py-2 rounded-xl border border-gray-200 outline-none focus:border-[#44006e]" placeholder="اسم الكاميرا" required />
                        <input type="text" value={cam.stream_url || cam.rtsp_url || ''} disabled={!!cam.id} onChange={e => updateArray(cameras, setCameras, idx, 'stream_url', e.target.value)} className="w-full text-[11px] font-mono bg-white px-4 py-2 rounded-xl border border-gray-200 outline-none focus:border-[#44006e]" placeholder="rtsp://..." />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Microphones */}
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="text-lg font-black text-[#2D005F]">أجهزة الصوت</h3>
                  <button type="button" onClick={handleAddMic} className="text-sm font-black text-[#44006e] bg-purple-50 px-4 py-1.5 rounded-full hover:bg-purple-100 transition-colors flex items-center gap-1 cursor-pointer">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                    إضافة
                  </button>
                </div>
                
                <div className="space-y-4">
                  {mics.map((mic, idx) => (
                    <div key={idx} className="bg-gray-50 p-5 rounded-[20px] border border-gray-100 relative group/dev shadow-sm">
                      <button type="button" onClick={() => removeArray(mics, setMics, idx)} className="absolute -top-2 -left-2 w-8 h-8 bg-white border border-red-100 text-red-500 rounded-full flex items-center justify-center opacity-0 group-hover/dev:opacity-100 transition-all shadow-md hover:bg-red-50">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                      </button>
                      <input type="text" value={mic.name} disabled={!!mic.id} onChange={e => updateArray(mics, setMics, idx, 'name', e.target.value)} className="w-full text-sm font-bold bg-white px-4 py-2 rounded-xl border border-gray-200 outline-none focus:border-[#44006e]" placeholder="اسم المايكروفون" required />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </form>
        </div>

        {/* Footer Actions */}
        <div className="p-8 border-t border-gray-100 bg-[#FCFBFF] flex gap-4 justify-end">
          <button type="button" onClick={onClose} className="px-8 py-3 rounded-2xl text-gray-500 font-black hover:bg-gray-100 transition-colors cursor-pointer">
            إلغاء
          </button>
          <button type="submit" form="hall-form" disabled={isSubmitting} className="px-10 py-3 rounded-2xl bg-[#44006E] text-white font-black shadow-xl hover:shadow-purple-200 transition-all cursor-pointer disabled:opacity-70">
            {isSubmitting ? 'جاري الحفظ...' : 'حفظ القاعة'}
          </button>
        </div>
      </div>
    </div>
  );
}
