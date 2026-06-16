import { useEffect, useState } from 'react';
import { authFetch } from '../config/api';

interface Scanner {
  id: string;
  identifier: string;
  status: string;
  position?: { label?: string; camera_id?: string; norm_pos?: number[] } | null;
}

/**
 * RF scanner-node management for a hall. Registering a node returns a one-time
 * pre-shared key that must be copied into the node's config.json; it is shown
 * once and only its hash is stored server-side.
 */
export default function RfScannerSection({ hallId }: { hallId: string }) {
  const [scanners, setScanners] = useState<Scanner[]>([]);
  const [identifier, setIdentifier] = useState('');
  const [label, setLabel] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newKey, setNewKey] = useState<{ id: string; api_key: string } | null>(null);

  const load = async () => {
    try {
      const res = await authFetch(`/api/v1/rf/scanners?hall_id=${hallId}`);
      if (res.ok) setScanners(await res.json());
    } catch { /* ignore */ }
  };

  useEffect(() => { void load(); /* eslint-disable-next-line */ }, [hallId]);

  const addNode = async () => {
    if (!identifier.trim()) { setError('أدخل رقم تعريف للجهاز'); return; }
    setBusy(true); setError(null);
    try {
      const res = await authFetch('/api/v1/rf/scanners', {
        method: 'POST',
        body: JSON.stringify({
          hall_id: hallId,
          identifier: identifier.trim(),
          position: label.trim() ? { label: label.trim() } : null,
        }),
      });
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        throw new Error(e.detail || 'فشل تسجيل الجهاز');
      }
      const created = await res.json();
      setNewKey({ id: created.id, api_key: created.api_key });
      setIdentifier(''); setLabel('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'خطأ');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4 pb-2 border-b border-gray-100">
        <h3 className="text-lg font-semibold text-gray-800">أجهزة استشعار RF (كشف الأجهزة اللاسلكية)</h3>
      </div>

      <div className="space-y-3">
        {scanners.map((sc) => {
          const placed = sc.position?.camera_id && sc.position?.norm_pos;
          return (
            <div key={sc.id} className="bg-gray-50 p-3 rounded-xl border border-gray-100 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span aria-hidden>📡</span>
                <div>
                  <div className="text-sm font-semibold text-gray-800">{sc.identifier}</div>
                  <div className="text-xs text-gray-500">{sc.position?.label || 'بدون موقع محدّد'}</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-xs px-2 py-0.5 rounded-full ${sc.status === 'online' ? 'bg-green-100 text-green-700' : 'bg-gray-200 text-gray-600'}`}>
                  {sc.status === 'online' ? 'متصل' : 'غير متصل'}
                </span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${placed ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-700'}`}>
                  {placed ? 'محدّد على الكاميرا' : 'غير محدّد على الكاميرا'}
                </span>
              </div>
            </div>
          );
        })}
        {scanners.length === 0 && (
          <div className="text-sm text-gray-400 text-center py-2">لم يتم إضافة أجهزة استشعار RF</div>
        )}

        {/* One-time key reveal */}
        {newKey && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm" dir="ltr">
            <div className="text-amber-800 font-semibold mb-2 text-right" dir="rtl">
              ⚠️ انسخ المفتاح الآن — يظهر مرة واحدة فقط (ضعه في config.json للجهاز)
            </div>
            <div className="font-mono text-xs bg-white border border-amber-200 rounded p-2 break-all mb-1">
              scanner_id: {newKey.id}
            </div>
            <div className="font-mono text-xs bg-white border border-amber-200 rounded p-2 break-all flex items-center justify-between gap-2">
              <span>api_key: {newKey.api_key}</span>
              <button type="button" onClick={() => navigator.clipboard?.writeText(newKey.api_key)}
                className="shrink-0 text-[#8e52cb] font-semibold hover:underline">نسخ</button>
            </div>
            <button type="button" onClick={() => setNewKey(null)} className="mt-2 text-xs text-gray-500 hover:underline" dir="rtl">إغلاق</button>
          </div>
        )}

        {/* Add form */}
        <div className="bg-white border border-dashed border-gray-200 rounded-xl p-4 grid grid-cols-2 gap-3 items-end">
          <div className="space-y-1">
            <label className="text-xs text-gray-500">رقم التعريف (Identifier)</label>
            <input type="text" value={identifier} onChange={(e) => setIdentifier(e.target.value)}
              className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg outline-none focus:border-[#8e52cb]" placeholder="rf-front-left" />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-gray-500">الموقع / المنطقة (اختياري)</label>
            <input type="text" value={label} onChange={(e) => setLabel(e.target.value)}
              className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg outline-none focus:border-[#8e52cb]" placeholder="الأمام يسار، صفوف ١-٤" />
          </div>
          <div className="col-span-2 flex items-center justify-between">
            {error && <span className="text-xs text-red-500">{error}</span>}
            <button type="button" onClick={addNode} disabled={busy}
              className="mr-auto text-sm cursor-pointer text-[#8e52cb] font-medium hover:underline flex items-center gap-1 disabled:opacity-60">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              {busy ? 'جاري التسجيل...' : 'تسجيل جهاز RF'}
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-400">حدّد موقع الجهاز على صورة الكاميرا من نافذة الكاميرا المباشرة لعرض مكان الاكتشاف على البث.</p>
      </div>
    </div>
  );
}
