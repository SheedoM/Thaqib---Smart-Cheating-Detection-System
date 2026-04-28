import { useState, useEffect } from 'react';
import { apiUrl } from '../config/api';

interface DeviceItem {
  name: string;
  type: string;
  status: string;
  ip_address?: string;
  rtsp_url?: string;
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

  const fetchHalls = async () => {
    try {
      const token = localStorage.getItem('thaqib_access_token');
      // We will use the monitoring endpoint to get halls with cameras and mics
      const res = await fetch(apiUrl('/api/stream/monitoring'), {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (res.ok) {
        const data = await res.json();
        setHalls(data.halls || []);
      }
    } catch (err) {
      console.error('Failed to fetch halls', err);
    }
  };

  const handleDeleteHall = async (id: string) => {
    if (confirm("هل أنت متأكد من حذف هذه القاعة؟")) {
      try {
        const token = localStorage.getItem('thaqib_access_token');
        await fetch(apiUrl(`/api/halls/${id}`), {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${token}` }
        });
        fetchHalls();
      } catch (err) {
        console.error('Failed to delete hall', err);
      }
    }
  };

  useEffect(() => {
    fetchHalls();
  }, []);

  return (
    <div className="halls-section" dir="rtl" style={{ padding: '24px' }}>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-semibold text-[#333]">إدارة القاعات</h2>
        <button 
          className="thaqib-button cursor-pointer flex items-center justify-center gap-2" 
          style={{ width: 'auto', padding: '0 24px', height: '44px' }}
          onClick={() => setIsAddModalOpen(true)}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          <span>إضافة قاعة</span>
        </button>
      </div>

      <div className="flex flex-wrap gap-5">
        {halls.map(hall => (
          <div key={hall.id} className="relative overflow-hidden shrink-0 shadow-sm" style={{ width: '286px', height: '286px', backgroundColor: '#fff', borderRadius: '16px', border: '1px solid #eaeaea', display: 'flex', flexDirection: 'column' }}>
            {/* Top background */}
            <div className="absolute top-0 left-0 right-0 h-[85px] bg-[#efeff3] z-0"></div>

            {/* Badges container (RTL) */}
            <div className="relative z-10 flex justify-between items-start p-4">
              {/* Right side in RTL (Capacity) */}
              <span className="px-3 py-1 rounded-md text-sm font-bold bg-[#cdbbdb] text-[#44006e]">
                {hall.capacity || 0} طالب
              </span>

              {/* Left side in RTL (Status) */}
              <span className={`px-3 py-1 font-bold rounded-md text-sm ${
                hall.cameras?.some(c => c.active) 
                  ? 'bg-[#d8f3dc] text-[#1b4332]' 
                  : 'bg-[#ffddd2] text-[#9d0208]'
              }`}>
                {hall.cameras?.some(c => c.active) ? 'متاحة' : 'غير متاحة'}
              </span>
            </div>

            {/* Center Image */}
            <div className="relative z-10 flex justify-center mt-[-15px]">
              <div className="w-[85px] h-[85px] rounded-full border-[4px] border-white overflow-hidden bg-gray-200">
                <img src={hall.image || "/c4b54a3086bba70544daebd23a684e9ed5ddbe56.jpg"} alt={hall.name} className="w-full h-full object-cover" 
                  onError={(e) => { e.currentTarget.src = 'https://images.unsplash.com/photo-1540544660406-6aee9fda6553?auto=format&fit=crop&q=80&w=300' }} 
                />
              </div>
            </div>

            {/* Hall Name */}
            <div className="relative z-10 text-center mt-3 flex-1">
              <h3 className="font-extrabold text-[20px] text-[#4a4a4a]">{hall.name}</h3>
            </div>

            <div className="p-4 flex gap-3 relative z-10 border-t border-gray-50 bg-gray-50/50">
              {/* Edit Button */}
              <button 
                className="flex-1 h-[44px] flex items-center justify-center gap-2 bg-[#44006e] text-white text-[16px] font-bold rounded-xl hover:bg-[#340055] transition-colors cursor-pointer"
                onClick={() => setEditingHall(hall)}
              >
                <span>تعديل</span>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
              </button>

              {/* Delete Button */}
              <button 
                className="w-[44px] h-[44px] flex items-center justify-center border-2 border-[#e63946] rounded-xl text-[#e63946] hover:bg-red-50 transition-colors shrink-0 cursor-pointer"
                title="حذف القاعة"
                onClick={() => handleDeleteHall(hall.id)}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
              </button>
            </div>
          </div>
        ))}
        {halls.length === 0 && (
          <div className="col-span-full py-12 text-center text-gray-500">
            لا توجد قاعات حالياً. اضغط على أضف قاعة لإضافة الأولى.
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
    </div>
  );
}

// ─── Modal Component ─────────────────────────────────────────────────────────

function HallModal({ onClose, onSuccess, hall }: { onClose: () => void, onSuccess: () => void, hall?: HallItem }) {
  const [name, setName] = useState(hall?.name || '');
  const [capacity, setCapacity] = useState(hall?.capacity?.toString() || '30');
  const [image, setImage] = useState<string>(hall ? (hall.image || '/c4b54a3086bba70544daebd23a684e9ed5ddbe56.jpg') : '');
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
      const token = localStorage.getItem('thaqib_access_token');
      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      };

      // 1. Get User/Institution
      const userRes = await fetch(apiUrl('/api/auth/me'), { headers });
      if (!userRes.ok) throw new Error('Failed to get user context');
      const user = await userRes.json();
      const institution_id = user.institution_id;

      if (!institution_id) {
        throw new Error('User has no associated institution');
      }

      let targetHallId = hall?.id;

      // 2. Create or Update Hall
      if (!targetHallId) {
        const hallRes = await fetch(apiUrl('/api/halls/'), {
          method: 'POST',
          headers,
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
        // Update hall (assuming PUT /api/halls/{id})
        const hallRes = await fetch(apiUrl(`/api/halls/${targetHallId}`), {
          method: 'PUT',
          headers,
          body: JSON.stringify({
            name,
            capacity: parseInt(capacity),
            image
          })
        });
        if (!hallRes.ok) throw new Error('Failed to update hall');
      }

      // 3. For editing, we might need to delete existing devices or just add new ones.
      // For simplicity in this iteration, if we are creating, we POST new devices.
      // If editing, we create devices that don't have an ID yet.
      // In a real app we'd sync devices, but here we'll just add the new ones.
      
      const allDevices = [...cameras, ...mics];
      const newDevices = allDevices.filter(d => !d.id);

      for (const dev of newDevices) {
        if (!dev.name) continue;
        await fetch(apiUrl('/api/devices/'), {
          method: 'POST',
          headers,
          body: JSON.stringify({
            hall_id: targetHallId,
            name: dev.name,
            identifier: dev.identifier || dev.name.replace(/\s+/g, '-').toLowerCase(),
            type: dev.type,
            ip_address: dev.ip_address || null,
            stream_url: dev.stream_url || null,
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
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col" dir="rtl">
        
        {/* Header Title Above Image */}
        <div className="p-5 border-b border-gray-100 flex justify-between items-center bg-white z-10 relative">
          <div></div> {/* Spacer for flex-between */}
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center gap-3">
            {hall ? (
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#44006e" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
            ) : (
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#44006e" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
            )}
            <h2 className="text-xl font-bold text-[#44006e]">{hall ? 'تعديل القاعة' : 'إضافة قاعة جديدة'}</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 cursor-pointer hover:text-gray-600 transition-colors bg-gray-50 rounded-full p-2">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        {/* Banner with image and upload option */}
        <div className={`relative h-40 group ${!image ? 'bg-gray-50 border-b border-dashed border-gray-300' : 'bg-gray-200'}`}>
          {image ? (
            <img src={image} alt="Banner" className="w-full h-full object-cover" onError={(e) => { e.currentTarget.src = 'https://images.unsplash.com/photo-1540544660406-6aee9fda6553?auto=format&fit=crop&q=80&w=1200' }} />
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center text-gray-400 gap-2">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
              <span className="text-sm font-medium">اضغط لرفع صورة القاعة</span>
            </div>
          )}
          
          <label className={`absolute inset-0 cursor-pointer flex items-center justify-center transition-all ${image ? 'bg-black/40 opacity-0 group-hover:opacity-100' : 'opacity-100 w-full h-full'}`}>
            {image && (
              <span className="bg-white/20 hover:bg-white/30 px-4 py-2 rounded-lg backdrop-blur-sm text-white font-medium flex items-center gap-2">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                تغيير الصورة
              </span>
            )}
            <input type="file" accept="image/*" className="hidden" onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                const reader = new FileReader();
                reader.onload = (ev) => {
                  if (ev.target?.result) {
                    setImage(ev.target.result as string);
                  }
                };
                reader.readAsDataURL(e.target.files[0]);
              }
            }} />
          </label>
        </div>

        <div className="p-6 overflow-y-auto flex-1">
          {errorMsg && (
            <div className="mb-6 bg-red-50 text-red-600 p-4 rounded-lg font-medium text-sm">
              {errorMsg}
            </div>
          )}

          <form id="hall-form" onSubmit={handleSubmit} className="space-y-8">
            {/* General Info */}
            <div>
              <h3 className="text-lg font-semibold text-[#8e52cb] mb-4 pb-2 border-b border-purple-100">المعلومات الأساسية</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700">اسم القاعة</label>
                  <input 
                    type="text" 
                    required 
                    value={name} 
                    onChange={e => setName(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#8e52cb] focus:border-transparent outline-none transition-all"
                    placeholder="مثال: قاعة 101"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700">السعة الاستيعابية</label>
                  <input 
                    type="number" 
                    required 
                    value={capacity} 
                    onChange={e => setCapacity(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#8e52cb] focus:border-transparent outline-none transition-all"
                    placeholder="عدد الطلاب"
                  />
                </div>
              </div>
            </div>

            {/* Cameras */}
            <div>
              <div className="flex justify-between items-center mb-4 pb-2 border-b border-gray-100">
                <h3 className="text-lg font-semibold text-gray-800">الكاميرات المراقبة</h3>
                <button type="button" onClick={handleAddCamera} className="text-sm cursor-pointer text-[#8e52cb] font-medium hover:underline flex items-center gap-1">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                  إضافة كاميرا
                </button>
              </div>
              
              <div className="space-y-4">
                {cameras.map((cam, idx) => (
                  <div key={idx} className="bg-gray-50 p-4 rounded-xl border border-gray-100 relative group">
                    <button type="button" onClick={() => removeArray(cameras, setCameras, idx)} className="absolute top-4 left-4 cursor-pointer text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    </button>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-1">
                        <label className="text-xs text-gray-500">اسم الكاميرا</label>
                        <input type="text" value={cam.name} disabled={!!cam.id} onChange={e => updateArray(cameras, setCameras, idx, 'name', e.target.value)} className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg outline-none focus:border-[#8e52cb] disabled:bg-gray-100" placeholder="مثال: كاميرا المدخل" required />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs text-gray-500">رقم التعريف (Identifier)</label>
                        <input type="text" value={cam.identifier} disabled={!!cam.id} onChange={e => updateArray(cameras, setCameras, idx, 'identifier', e.target.value)} className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg outline-none focus:border-[#8e52cb] disabled:bg-gray-100" placeholder="cam-main-1" />
                      </div>
                      <div className="col-span-2 space-y-1">
                        <label className="text-xs text-gray-500">رابط البث (Stream URL)</label>
                        <input type="text" value={cam.stream_url || ''} disabled={!!cam.id} onChange={e => updateArray(cameras, setCameras, idx, 'stream_url', e.target.value)} className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg outline-none focus:border-[#8e52cb] disabled:bg-gray-100" placeholder="rtsp://admin:admin@192.168.1.100/stream" />
                      </div>
                    </div>
                  </div>
                ))}
                {cameras.length === 0 && <div className="text-sm text-gray-400 text-center py-2">لم يتم إضافة كاميرات</div>}
              </div>
            </div>

            {/* Mics */}
            <div>
              <div className="flex justify-between items-center mb-4 pb-2 border-b border-gray-100">
                <h3 className="text-lg font-semibold text-gray-800">أجهزة الصوت</h3>
                <button type="button" onClick={handleAddMic} className="text-sm cursor-pointer text-[#8e52cb] font-medium hover:underline flex items-center gap-1">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                  إضافة مايكروفون
                </button>
              </div>
              
              <div className="space-y-4">
                {mics.map((mic, idx) => (
                  <div key={idx} className="bg-gray-50 p-4 rounded-xl border border-gray-100 relative group">
                    <button type="button" onClick={() => removeArray(mics, setMics, idx)} className="absolute top-4 cursor-pointer left-4 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    </button>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-1">
                        <label className="text-xs text-gray-500">اسم المايكروفون</label>
                        <input type="text" value={mic.name} disabled={!!mic.id} onChange={e => updateArray(mics, setMics, idx, 'name', e.target.value)} className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg outline-none focus:border-[#8e52cb] disabled:bg-gray-100" placeholder="مايك المنصة" required />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs text-gray-500">رقم التعريف (Identifier)</label>
                        <input type="text" value={mic.identifier} disabled={!!mic.id} onChange={e => updateArray(mics, setMics, idx, 'identifier', e.target.value)} className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg outline-none focus:border-[#8e52cb] disabled:bg-gray-100" placeholder="mic-main-1" />
                      </div>
                    </div>
                  </div>
                ))}
                {mics.length === 0 && <div className="text-sm text-gray-400 text-center py-2">لم يتم إضافة أجهزة صوت</div>}
              </div>
            </div>

          </form>
        </div>

        <div className="p-6 border-t border-gray-100 bg-gray-50 flex gap-3 justify-end">
          <button type="button" onClick={onClose} className="px-6 py-2 cursor-pointer rounded-lg text-gray-600 font-medium hover:bg-gray-200 transition-colors">
            إلغاء
          </button>
          <button type="submit" form="hall-form" disabled={isSubmitting} className="px-6 py-2 cursor-pointer rounded-lg bg-[#8e52cb] text-white font-medium hover:bg-[#7a45af] transition-colors shadow-md disabled:opacity-70 disabled:cursor-not-allowed">
            {isSubmitting ? 'جاري الحفظ...' : 'حفظ القاعة'}
          </button>
        </div>
      </div>
    </div>
  );
}
