import { useState, useEffect, useRef } from 'react';

import { authFetch, apiUrl } from '../config/api';

interface Supervisor {
  id: string; full_name: string; username: string;
  email: string; role: string; image?: string; status?: string;
}

export default function SupervisorsTab() {
  const [supervisors, setSupervisors] = useState<Supervisor[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState<Supervisor | null>(null);
  const [deleting, setDeleting] = useState<Supervisor | null>(null);

  const load = async () => {
    try {
      const res = await authFetch('/api/users/');
      if (res.ok) {
        const data = await res.json();
        setSupervisors((data || []).filter((u: any) => u.role !== 'super_admin'));
      }
    } catch { /**/ } finally { setLoading(false); }
  };

  const doDelete = async (id: string) => {
    const res = await authFetch(`/api/users/${id}`, { method: 'DELETE' });
    if (res.ok) { setDeleting(null); load(); }
  };

  useEffect(() => { load(); }, []);

  const filtered = supervisors.filter(s =>
    s.full_name.toLowerCase().includes(search.toLowerCase()) ||
    s.username.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-8" dir="rtl">
      {/* Header */}
      <div className="flex justify-between items-center mb-10">
        <div className="flex items-center gap-4">
          <div className="w-1.5 h-10 bg-[#44006E] rounded-full"></div>
          <h2 className="text-3xl font-black text-[#2D005F]">إدارة المشرفين</h2>
        </div>
        <div className="flex gap-3 items-center">
          <div className="relative">
            <svg className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" placeholder="بحث..." value={search} onChange={e => setSearch(e.target.value)}
              className="bg-white border border-gray-200 rounded-2xl py-2.5 pr-9 pl-4 outline-none focus:ring-2 focus:ring-purple-200 text-sm font-bold w-52 shadow-sm" />
          </div>
          <button onClick={() => { setEditing(null); setModal(true); }}
            className="bg-[#44006e] text-white font-black flex items-center justify-center gap-2 shadow-lg hover:shadow-xl transition-all hover:-translate-y-0.5 active:scale-95 cursor-pointer"
            style={{ width: '200px', height: '50px', borderRadius: '18px' }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            <span className="text-[17px]">إضافة مشرف</span>
          </button>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
          {[1,2,3,4].map(i => <div key={i} className="bg-white rounded-3xl h-56 animate-pulse border border-gray-100"/>)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center py-24 bg-white rounded-3xl border-2 border-dashed border-gray-100">
          <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mb-4">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
          </div>
          <p className="text-gray-400 font-black text-lg mb-3">لا يوجد مشرفين</p>
          <button onClick={() => setModal(true)} className="text-[#44006E] text-sm font-bold hover:underline cursor-pointer">+ أضف أول مشرف</button>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
          {filtered.map(s => (
            <SupervisorCard key={s.id} s={s}
              onEdit={() => { setEditing(s); setModal(true); }}
              onDelete={() => setDeleting(s)} />
          ))}
        </div>
      )}

      {modal && <SupervisorModal supervisor={editing} onClose={() => setModal(false)} onSuccess={() => { setModal(false); load(); }} />}
      {deleting && <DeleteModal name={deleting.full_name} onConfirm={() => doDelete(deleting.id)} onCancel={() => setDeleting(null)} />}
    </div>
  );
}

// ─── Card (Figma 4049:752 style) ─────────────────────────────────────────────
function SupervisorCard({ s, onEdit, onDelete }: { s: Supervisor, onEdit: () => void, onDelete: () => void }) {
  const available = s.status !== 'inactive';
  const initials = s.full_name.split(' ').map((n: string) => n[0]).slice(0, 2).join('');

  return (
    <div className="bg-[#F4F2FA] rounded-3xl overflow-hidden border border-gray-100 hover:shadow-lg transition-all duration-300 group">
      {/* Status badge */}
      <div className="px-4 pt-4 pb-2 flex justify-start">
        <span className={`px-3 py-1 rounded-full text-xs font-black ${available ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-500'}`}>
          {available ? 'متاح' : 'غير متاح'}
        </span>
      </div>

      {/* Avatar */}
      <div className="flex justify-center py-3">
        <div className="w-20 h-20 rounded-full overflow-hidden bg-gradient-to-br from-[#9351bb] to-[#44006E] flex items-center justify-center text-white text-2xl font-black shadow-md group-hover:scale-105 transition-transform duration-300">
          {s.image ? (
            <img 
              src={s.image.startsWith('data:') || s.image.startsWith('http') ? s.image : apiUrl(s.image)} 
              className="w-full h-full object-cover" 
              alt={s.full_name} 
              onError={(e) => {
                e.currentTarget.style.display = 'none';
                (e.currentTarget.parentElement as HTMLElement).innerHTML = initials;
              }}
            />
          ) : initials}
        </div>
      </div>

      {/* Name */}
      <p className="text-center font-black text-[#2D005F] text-base px-3 pb-4">{s.full_name}</p>

      {/* Actions */}
      <div className="flex gap-2 px-4 pb-4">
        <button onClick={onEdit}
          className="flex-1 bg-[#44006E] text-white py-2 rounded-xl font-black text-xs flex items-center justify-center gap-1.5 hover:bg-[#5a0090] transition-all cursor-pointer shadow-sm hover:shadow-md hover:-translate-y-0.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          تعديل
        </button>
        <button onClick={onDelete}
          className="w-9 h-9 bg-white border border-red-200 text-red-400 hover:bg-red-500 hover:text-white rounded-xl flex items-center justify-center transition-all cursor-pointer shrink-0">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
      </div>
    </div>
  );
}

// ─── Add/Edit Modal ───────────────────────────────────────────────────────────
function SupervisorModal({ supervisor, onClose, onSuccess }: { supervisor: Supervisor | null, onClose: () => void, onSuccess: () => void }) {
  const [form, setForm] = useState({ full_name: supervisor?.full_name || '', username: supervisor?.username || '', email: supervisor?.email || '', password: '', role: supervisor?.role || 'invigilator' });
  const [image, setImage] = useState<string | null>(supervisor?.image || null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const imagePreviewSrc = image ? (image.startsWith('data:') || image.startsWith('http') ? image : apiUrl(image)) : null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true); setError(null);
    try {
      let institutionId: string | null = null;
      const meRes = await authFetch('/api/auth/me');
      if (meRes.ok) { const me = await meRes.json(); institutionId = me.institution_id || null; }
      if (!institutionId) {
        const iRes = await authFetch('/api/institutions/');
        if (iRes.ok) { const insts = await iRes.json(); if (insts?.length > 0) institutionId = insts[0].id; }
      }
      if (!institutionId) { setError('لم يتم العثور على المؤسسة.'); setSubmitting(false); return; }

      let imageUrl = supervisor?.image || null;
      if (imageFile) {
        const formData = new FormData();
        formData.append('image', imageFile);
        const uploadRes = await authFetch('/api/users/upload-image', {
          method: 'POST',
          body: formData,
        });
        if (!uploadRes.ok) {
          const err = await uploadRes.json().catch(() => ({ detail: `خطأ ${uploadRes.status}` }));
          setError(typeof err.detail === 'string' ? err.detail : 'فشل رفع الصورة.');
          setSubmitting(false);
          return;
        }
        const uploaded = await uploadRes.json();
        imageUrl = uploaded.url;
      }

      const payload: any = { full_name: form.full_name, username: form.username, email: form.email || `${form.username}@thaqib.example.com`, role: form.role, institution_id: institutionId };
      if (form.password) payload.password = form.password;
      if (imageUrl) payload.image = imageUrl;

      const res = await authFetch(supervisor ? `/api/users/${supervisor.id}` : '/api/users/', { method: supervisor ? 'PUT' : 'POST', body: JSON.stringify(payload) });
      if (res.ok) { setSuccess(true); setTimeout(onSuccess, 1400); }
      else {
        const err = await res.json().catch(() => ({ detail: `خطأ ${res.status}` }));
        let raw = '';
        if (Array.isArray(err.detail)) {
          raw = err.detail.map((d: any) => `${d.loc.join('.')}: ${d.msg}`).join('\n');
        } else {
          raw = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
        }
        setError(raw.includes('already exists') ? `اسم المستخدم مستخدم بالفعل، جرب: ${form.username}2` : raw.includes('password') ? 'كلمة المرور 8 أحرف على الأقل' : raw);
      }
    } catch { setError('تعذر الاتصال بالسيرفر.'); }
    finally { setSubmitting(false); }
  };

  if (success) return (
    <div className="fixed inset-0 z-[120] bg-black/40 backdrop-blur-sm flex items-center justify-center" dir="rtl">
      <div className="bg-white rounded-3xl p-12 shadow-2xl flex flex-col items-center">
        <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mb-4 animate-bounce">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#00D261" strokeWidth="3.5"><polyline points="20 6 9 17 4 12"/></svg>
        </div>
        <h3 className="text-2xl font-black text-[#2D005F] mb-1">تم بنجاح!</h3>
        <p className="text-gray-400 font-medium">تم {supervisor ? 'تعديل' : 'إضافة'} المشرف</p>
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 z-[120] bg-black/40 backdrop-blur-sm flex items-center justify-center p-4" dir="rtl" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-white rounded-[28px] shadow-2xl w-full max-w-md animate-in zoom-in-95 duration-200">
        <div className="px-7 py-5 flex items-center justify-between border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-purple-100 rounded-xl flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#44006E" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            </div>
            <h3 className="text-lg font-black text-[#2D005F]">{supervisor ? 'تعديل المشرف' : 'إضافة مشرف'}</h3>
          </div>
          <button onClick={onClose} className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-7 py-5 space-y-3">
          <input type="text" required placeholder="الاسم الكامل" value={form.full_name} onChange={e => setForm(p => ({ ...p, full_name: e.target.value }))}
            className="w-full bg-gray-50 border border-gray-200 rounded-2xl py-3 px-4 outline-none focus:ring-2 focus:ring-purple-200 focus:border-[#44006E] text-sm font-bold transition-all" />

          <div className="grid grid-cols-2 gap-3">
            <input type="text" required placeholder="اسم المستخدم (a-z)" pattern="[a-zA-Z0-9_.\-]+" value={form.username} onChange={e => setForm(p => ({ ...p, username: e.target.value }))}
              className="bg-gray-50 border border-gray-200 rounded-2xl py-3 px-4 outline-none focus:ring-2 focus:ring-purple-200 focus:border-[#44006E] text-sm font-bold transition-all" />
            <select value={form.role} onChange={e => setForm(p => ({ ...p, role: e.target.value }))}
              className="bg-gray-50 border border-gray-200 rounded-2xl py-3 px-4 outline-none focus:ring-2 focus:ring-purple-200 focus:border-[#44006E] text-sm font-bold transition-all appearance-none">
              <option value="invigilator">مراقب</option>
              <option value="admin">إداري الامتحان</option>
            </select>
          </div>

          <input type="email" placeholder="البريد الإلكتروني (اختياري)" value={form.email} onChange={e => setForm(p => ({ ...p, email: e.target.value }))}
            className="w-full bg-gray-50 border border-gray-200 rounded-2xl py-3 px-4 outline-none focus:ring-2 focus:ring-purple-200 focus:border-[#44006E] text-sm font-bold transition-all" />

          <input type="password" required={!supervisor} minLength={8} placeholder={supervisor ? 'كلمة مرور جديدة (اختياري)' : 'كلمة المرور (8+ أحرف)'} value={form.password} onChange={e => setForm(p => ({ ...p, password: e.target.value }))}
            className="w-full bg-gray-50 border border-gray-200 rounded-2xl py-3 px-4 outline-none focus:ring-2 focus:ring-purple-200 focus:border-[#44006E] text-sm font-bold transition-all" />

          <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={e => {
            const f = e.target.files?.[0];
            if (f) { setImageFile(f); const r = new FileReader(); r.onload = ev => setImage(ev.target?.result as string); r.readAsDataURL(f); }
          }} />
          <div onClick={() => fileRef.current?.click()} className="w-full h-24 bg-gray-50 border-2 border-dashed border-gray-200 rounded-2xl flex flex-col items-center justify-center cursor-pointer hover:border-[#44006E] hover:bg-purple-50 transition-all group relative overflow-hidden">
            {imagePreviewSrc ? (
              <>
                <img 
                  src={imagePreviewSrc} 
                  className="absolute inset-0 w-full h-full object-cover" 
                  alt="preview" 
                />
                <div className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"><span className="text-white font-black text-xs">تغيير الصورة</span></div>
              </>
            ) : (
              <><div className="w-9 h-9 bg-gray-200 group-hover:bg-purple-100 rounded-xl flex items-center justify-center mb-1.5 transition-colors">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9351bb" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
                </div>
                <span className="text-xs font-black text-gray-400 group-hover:text-[#44006E] transition-colors">إضافة الصورة</span></>
            )}
          </div>

          {error && (
            <div className="flex items-start gap-2 bg-red-50 border-2 border-red-200 text-red-700 rounded-2xl px-4 py-3">
              <svg className="shrink-0 mt-0.5" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              <div className="flex-1 min-w-0"><p className="font-black text-sm">فشل الحفظ</p><p className="text-xs mt-0.5 font-medium break-words whitespace-pre-wrap max-h-32 overflow-y-auto" dir="ltr">{error}</p></div>
              <button type="button" onClick={() => setError(null)} className="text-red-400 hover:text-red-600 cursor-pointer shrink-0">✕</button>
            </div>
          )}

          <button type="submit" disabled={submitting}
            className="w-full bg-[#44006E] text-white py-3.5 rounded-2xl font-black text-base shadow-lg shadow-purple-100 hover:-translate-y-0.5 active:scale-95 transition-all cursor-pointer disabled:opacity-60 flex items-center justify-center gap-2">
            {submitting ? <><svg className="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><circle cx="12" cy="12" r="10" strokeOpacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10"/></svg>جاري الحفظ...</> : 'حفظ'}
          </button>
        </form>
      </div>
    </div>
  );
}

// ─── Delete Confirm ───────────────────────────────────────────────────────────
function DeleteModal({ name, onConfirm, onCancel }: { name: string, onConfirm: () => void, onCancel: () => void }) {
  const [deleting, setDeleting] = useState(false);
  return (
    <div className="fixed inset-0 z-[130] flex items-center justify-center p-4" dir="rtl" onClick={e => { if (e.target === e.currentTarget) onCancel(); }}>
      <div className="absolute inset-0 bg-black/20 backdrop-blur-sm"/>
      <div className="relative bg-white rounded-[28px] shadow-2xl w-full max-w-sm p-8 flex flex-col items-center text-center animate-in zoom-in-95 duration-200">
        <div className="w-16 h-16 bg-red-50 rounded-2xl flex items-center justify-center mb-5">
          <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#EF4444" strokeWidth="2.5"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
        </div>
        <h3 className="text-lg font-black text-gray-900 mb-2">حذف المشرف؟</h3>
        <p className="text-sm text-gray-400 mb-7 leading-relaxed">سيتم حذف <span className="font-black text-gray-600">{name}</span> بشكل نهائي</p>
        <div className="flex gap-3 w-full">
          <button onClick={async () => { setDeleting(true); await onConfirm(); }} disabled={deleting}
            className="flex-1 bg-red-500 hover:bg-red-600 text-white py-3 rounded-2xl font-black text-sm shadow-lg hover:-translate-y-0.5 transition-all cursor-pointer disabled:opacity-60 flex items-center justify-center gap-2">
            {deleting ? <><svg className="animate-spin" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><circle cx="12" cy="12" r="10" strokeOpacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10"/></svg>حذف...</> : 'نعم، حذف'}
          </button>
          <button onClick={onCancel} disabled={deleting} className="flex-1 border-2 border-gray-200 text-gray-500 py-3 rounded-2xl font-black text-sm hover:bg-gray-50 transition-all cursor-pointer disabled:opacity-50">إلغاء</button>
        </div>
      </div>
    </div>
  );
}
