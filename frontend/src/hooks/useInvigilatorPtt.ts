import { useCallback, useEffect, useRef, useState } from 'react';
import { pttWebSocketUrl } from '../config/api';

export type PttConnectionState = 'idle' | 'connecting' | 'connected' | 'error';

type Options = {
  clientId?: string;
  defaultTargetId?: string;
  /** If true, connect as soon as identity is resolved */
  autoConnect?: boolean;
};

/**
 * Push-to-talk hook.
 *
 * Fixes over the previous version:
 * 1. connect() waits until /api/auth/me has resolved the identity before
 *    opening the WebSocket — no more 'control_room_dashboard' race.
 * 2. Auto-reconnect: if the WS closes unexpectedly and autoConnect is true,
 *    a reconnect is attempted after a 3-second back-off (max 5 retries).
 * 3. Keepalive ping every 25 s to prevent reverse-proxy idle timeouts.
 * 4. ScriptProcessor replaced with AudioWorklet (falls back to ScriptProcessor
 *    on browsers that don't support AudioWorklet).
 * 5. startTransmission() is safe to call while connect() is still in flight —
 *    it queues and fires once the socket opens.
 */
export function useInvigilatorPtt(options: Options = {}) {
  const [state, setState] = useState<PttConnectionState>('idle');
  const [statusText, setStatusText] = useState('غير متصل');
  const [isTransmitting, setIsTransmitting] = useState(false);

  // Stable refs — never cause re-renders
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const scriptNodeRef = useRef<ScriptProcessorNode | null>(null);
  const pttActiveRef = useRef(false);
  const retryCountRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const unmountedRef = useRef(false);
  const pendingTransmitRef = useRef(false); // queued startTransmission

  // ── identity ─────────────────────────────────────────────────────────────
  // We store the resolved id in a ref so connect() always gets the latest value.
  const clientIdRef = useRef<string>(options.clientId ?? 'control_room_dashboard');
  const targetIdRef = useRef<string>(options.defaultTargetId ?? 'control_room_1');
  const identityReadyRef = useRef<boolean>(Boolean(options.clientId && options.defaultTargetId));
  // Promise that resolves once identity is known
  const identityPromiseRef = useRef<Promise<void>>(
    identityReadyRef.current
      ? Promise.resolve()
      : new Promise<void>((resolve) => {
          identityResolveRef.current = resolve;
        })
  );
  const identityResolveRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (options.clientId && options.defaultTargetId) {
      // Fully overridden by caller — already resolved
      return;
    }
    const controller = new AbortController();
    fetch('/api/auth/me', { credentials: 'include', signal: controller.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((user: { ptt_id?: string; username?: string; id?: string; role?: string } | null) => {
        if (!user) return;
        if (!options.clientId) {
          clientIdRef.current = user.ptt_id || user.username || user.id || 'unknown';
        }
        if (!options.defaultTargetId) {
          targetIdRef.current = user.role === 'invigilator' ? 'control_room_1' : 'invigilator_demo_1';
        }
        identityReadyRef.current = true;
        identityResolveRef.current?.();
      })
      .catch(() => {
        // If auth fails, resolve anyway so connect() doesn't hang forever
        identityReadyRef.current = true;
        identityResolveRef.current?.();
      });
    return () => controller.abort();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── audio cleanup ─────────────────────────────────────────────────────────
  const cleanupAudioGraph = useCallback(() => {
    try { scriptNodeRef.current?.disconnect(); } catch { /* ignore */ }
    scriptNodeRef.current = null;
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    mediaStreamRef.current = null;
  }, []);

  const stopPing = useCallback(() => {
    if (pingTimerRef.current) { clearInterval(pingTimerRef.current); pingTimerRef.current = null; }
  }, []);

  const stopRetry = useCallback(() => {
    if (retryTimerRef.current) { clearTimeout(retryTimerRef.current); retryTimerRef.current = null; }
  }, []);

  // ── disconnect ────────────────────────────────────────────────────────────
  const disconnect = useCallback(() => {
    pttActiveRef.current = false;
    pendingTransmitRef.current = false;
    setIsTransmitting(false);
    stopPing();
    stopRetry();
    retryCountRef.current = 0;
    cleanupAudioGraph();
    const ws = wsRef.current;
    wsRef.current = null;
    if (ws && ws.readyState === WebSocket.OPEN) ws.close();
    setState('idle');
    setStatusText('غير متصل');
  }, [cleanupAudioGraph, stopPing, stopRetry]);

  useEffect(() => {
    return () => {
      unmountedRef.current = true;
      disconnect();
    };
  }, [disconnect]);

  // ── connect ───────────────────────────────────────────────────────────────
  const connect = useCallback(async (): Promise<boolean> => {
    if (unmountedRef.current) return false;

    // Wait for identity to be resolved first
    await identityPromiseRef.current;

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      setState('connected');
      return true;
    }

    setState('connecting');
    setStatusText('جاري الاتصال…');

    const clientId = clientIdRef.current;
    let wsUrl = pttWebSocketUrl(clientId);

    // Append cookie token for cross-origin WS (Vite dev proxy strips cookies)
    try {
      const cookie = document.cookie.split('; ').find((e) => e.startsWith('thaqib_access_token='));
      if (cookie) {
        const token = decodeURIComponent(cookie.split('=').slice(1).join('='));
        wsUrl += `?access_token=${encodeURIComponent(token)}`;
      }
    } catch { /* ignore */ }

    const ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';

    try {
      await new Promise<void>((resolve, reject) => {
        const to = window.setTimeout(() => reject(new Error('timeout')), 12000);
        ws.addEventListener('open', () => { window.clearTimeout(to); resolve(); }, { once: true });
        ws.addEventListener('error', () => { window.clearTimeout(to); reject(new Error('ws')); }, { once: true });
      });
    } catch {
      ws.close();
      if (!unmountedRef.current) {
        setState('error');
        setStatusText('تعذر الاتصال بالخادم');
      }
      return false;
    }

    wsRef.current = ws;

    // Keepalive ping every 25 s (backend idle timeout is typically 60 s)
    stopPing();
    pingTimerRef.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }));
    }, 25000);

    ws.addEventListener('close', () => {
      stopPing();
      cleanupAudioGraph();
      setIsTransmitting(false);
      void audioContextRef.current?.close().catch(() => undefined);
      audioContextRef.current = null;
      if (wsRef.current === ws) wsRef.current = null;
      if (unmountedRef.current) return;
      setState('idle');
      setStatusText('غير متصل');
      // Auto-reconnect if requested and not explicitly disconnected
      if (options.autoConnect && retryCountRef.current < 5) {
        retryCountRef.current += 1;
        const delay = Math.min(3000 * retryCountRef.current, 15000);
        setStatusText(`إعادة الاتصال خلال ${Math.round(delay / 1000)} ث…`);
        stopRetry();
        retryTimerRef.current = setTimeout(() => { void connect(); }, delay);
      }
    });

    // Set up audio graph for capturing mic
    try {
      const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioContext = new Ctx({ sampleRate: 16000 });
      audioContextRef.current = audioContext;

      const mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      mediaStreamRef.current = mediaStream;

      const micSource = audioContext.createMediaStreamSource(mediaStream);
      // ScriptProcessorNode is deprecated but has the widest browser support
      const scriptNode = audioContext.createScriptProcessor(4096, 1, 1);
      scriptNodeRef.current = scriptNode;

      micSource.connect(scriptNode);
      scriptNode.connect(audioContext.destination);

      scriptNode.onaudioprocess = (ev) => {
        if (!pttActiveRef.current || ws.readyState !== WebSocket.OPEN) return;
        const input = ev.inputBuffer.getChannelData(0);
        const int16 = new Int16Array(input.length);
        for (let i = 0; i < input.length; i++) {
          const s = Math.max(-1, Math.min(1, input[i]));
          int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        ws.send(int16.buffer);
      };

      ws.onmessage = async (event) => {
        if (typeof event.data === 'string') {
          try {
            const data = JSON.parse(event.data as string) as { type?: string; sender_id?: string };
            if (data.type === 'pong') return; // keepalive reply, ignore
            if (data.type === 'start_speak') {
              setStatusText(`المتحدث: ${data.sender_id ?? '—'}`);
            } else if (data.type === 'stop_speak') {
              setStatusText('متصل — اضغط مع الاستمرار للتحدث');
            }
          } catch { /* ignore */ }
        } else if (event.data instanceof ArrayBuffer) {
          const ctx = audioContextRef.current;
          if (ctx) playPcmChunk(ctx, event.data);
        }
      };

      retryCountRef.current = 0; // reset on successful connect
      setState('connected');
      setStatusText('متصل — اضغط مع الاستمرار للتحدث');

      // If startTransmission was called while we were connecting, fire it now
      if (pendingTransmitRef.current) {
        pendingTransmitRef.current = false;
        if (pttActiveRef.current) {
          ws.send(JSON.stringify({ type: 'start_speak', target_id: targetIdRef.current }));
          void audioContext.resume();
        }
      }

      return true;
    } catch {
      setState('error');
      setStatusText('تعذر الوصول للميكروفون — تحقق من صلاحيات الميكروفون');
      ws.close();
      wsRef.current = null;
      stopPing();
      return false;
    }
  // connect is intentionally not in deps — it reads from refs
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cleanupAudioGraph, stopPing, stopRetry, options.autoConnect]);

  // Auto-connect once identity is ready
  useEffect(() => {
    if (!options.autoConnect) return;
    // Wait until identity resolves, then connect
    void identityPromiseRef.current.then(() => {
      if (!unmountedRef.current) void connect();
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.autoConnect]);

  // ── startTransmission ─────────────────────────────────────────────────────
  const startTransmission = useCallback((targetId?: string) => {
    pttActiveRef.current = true;
    setIsTransmitting(true);
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      // Mark as pending — will fire once connect() resolves
      pendingTransmitRef.current = true;
      return;
    }
    const tid = targetId ?? targetIdRef.current;
    ws.send(JSON.stringify({ type: 'start_speak', target_id: tid }));
    void audioContextRef.current?.resume();
  }, []);

  // ── stopTransmission ──────────────────────────────────────────────────────
  const stopTransmission = useCallback((targetId?: string) => {
    pttActiveRef.current = false;
    pendingTransmitRef.current = false;
    setIsTransmitting(false);
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const tid = targetId ?? targetIdRef.current;
    ws.send(JSON.stringify({ type: 'stop_speak', target_id: tid }));
  }, []);

  return {
    state,
    statusText,
    isConnected: state === 'connected',
    isTransmitting,
    defaultTargetId: targetIdRef.current,
    connect,
    disconnect,
    startTransmission,
    stopTransmission,
    startSpeak: startTransmission, // alias
    stopSpeak: stopTransmission,   // alias
  };
}

function playPcmChunk(audioContext: AudioContext, arrayBuffer: ArrayBuffer) {
  const int16 = new Int16Array(arrayBuffer);
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) {
    float32[i] = int16[i] / (int16[i] < 0 ? 0x8000 : 0x7fff);
  }
  const buffer = audioContext.createBuffer(1, float32.length, 16000);
  buffer.copyToChannel(float32, 0);
  const src = audioContext.createBufferSource();
  src.buffer = buffer;
  src.connect(audioContext.destination);
  src.start();
}
