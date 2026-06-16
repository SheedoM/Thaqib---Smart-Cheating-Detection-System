import { useEffect, useRef, useState } from 'react';
import { authFetch } from '../config/api';

interface UnknownDevice {
  device_name: string | null;
  signal_type: string;
  rssi: number | null;
  estimated_zone: string | null;
  last_seen: string;
  is_spike: boolean;
}

/**
 * Per-hall RF indicator. Polls the RF subsystem for unrecognized / spiking
 * wireless devices heard in the hall and surfaces them to the control room.
 * Renders nothing until the hall is actively monitored.
 */
export default function RfBadge({ hallId, active }: { hallId: string; active: boolean }) {
  const [devices, setDevices] = useState<UnknownDevice[]>([]);
  const [open, setOpen] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await authFetch(`/api/v1/rf/halls/${hallId}/unknown?window_minutes=5`);
        if (!res.ok) return;
        const data: UnknownDevice[] = await res.json();
        if (!cancelled) setDevices(data);
      } catch {
        /* transient — keep last state */
      }
    };
    poll();
    timer.current = window.setInterval(poll, 5000);
    return () => {
      cancelled = true;
      if (timer.current) window.clearInterval(timer.current);
      setDevices([]);
    };
  }, [hallId, active]);

  if (!active) return null;

  const count = devices.length;
  const clean = count === 0;

  return (
    <div style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title="كشف الأجهزة اللاسلكية"
        style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          padding: '4px 10px', borderRadius: '999px', cursor: 'pointer',
          border: '1px solid ' + (clean ? '#cfe8d4' : '#f1b0b0'),
          background: clean ? '#eef8f0' : '#fdecec',
          color: clean ? '#2f7d3b' : '#b42323', fontSize: '13px', fontWeight: 600,
        }}
      >
        <span aria-hidden>📡</span>
        {clean ? 'RF: نظيف' : `${count} جهاز مجهول`}
      </button>

      {open && !clean && (
        <div
          style={{
            position: 'absolute', top: '110%', insetInlineEnd: 0, zIndex: 20,
            minWidth: '260px', background: '#fff', borderRadius: '10px',
            boxShadow: '0 6px 24px rgba(0,0,0,0.15)', border: '1px solid #eee',
            padding: '10px', textAlign: 'right',
          }}
        >
          <div style={{ fontSize: '12px', color: '#888', marginBottom: '6px' }}>
            أجهزة لاسلكية غير معروفة في القاعة
          </div>
          {devices.map((d, i) => (
            <div key={i} style={{ padding: '6px 0', borderTop: i ? '1px solid #f2f2f2' : 'none' }}>
              <div style={{ fontWeight: 600, color: '#b42323' }}>
                {d.is_spike ? '⚠️ ' : ''}{d.device_name || 'جهاز غير معروف'}
                <span style={{ color: '#999', fontWeight: 400, fontSize: '12px' }}>
                  {' '}({d.signal_type.toUpperCase()}{d.rssi != null ? `, ${d.rssi} dBm` : ''})
                </span>
              </div>
              {d.estimated_zone && (
                <div style={{ fontSize: '12px', color: '#555' }}>{d.estimated_zone}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
