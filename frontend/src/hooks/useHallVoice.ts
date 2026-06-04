import { useCallback, useEffect, useRef, useState } from 'react';
import { voiceWebSocketUrl } from '../config/api';
import { isInsecureLanContext } from '../lib/secureContext';

export type VoiceConnectionState = 'idle' | 'connecting' | 'connected' | 'error';
export type VoiceMicState = 'idle' | 'requesting' | 'ready' | 'blocked' | 'error';

export type VoiceParticipant = { id: string; role: string; name: string };

type Options = {
  hallId?: string;
  autoConnect?: boolean;
};

const SAMPLE_RATE = 16000;

/**
 * Minimal hall voice channel.
 *
 * Connects to /api/v1/voice/ws/{hallId} (auth via the HttpOnly access cookie sent
 * on the handshake), plays audio received from the hall, and — while the user holds
 * the talk button — captures the microphone and streams PCM16 frames.
 *
 * Microphone capture requires a secure context (HTTPS or localhost). Over plain
 * http://<LAN-IP> the phone browser blocks the mic; we surface that as micState
 * 'blocked' instead of failing silently.
 */
export function useHallVoice(options: Options = {}) {
  const { hallId, autoConnect } = options;

  const [state, setState] = useState<VoiceConnectionState>('idle');
  const [micState, setMicState] = useState<VoiceMicState>('idle');
  const [isTransmitting, setIsTransmitting] = useState(false);
  const [participants, setParticipants] = useState<VoiceParticipant[]>([]);
  const [remoteTalking, setRemoteTalking] = useState<VoiceParticipant | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const scriptNodeRef = useRef<ScriptProcessorNode | null>(null);
  const talkingRef = useRef(false);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const unmountedRef = useRef(false);

  const getAudioCtx = useCallback((): AudioContext | null => {
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return null;
    if (!audioCtxRef.current) audioCtxRef.current = new Ctx({ sampleRate: SAMPLE_RATE });
    return audioCtxRef.current;
  }, []);

  const playPcm = useCallback((buffer: ArrayBuffer) => {
    const ctx = getAudioCtx();
    if (!ctx) return;
    if (ctx.state === 'suspended') void ctx.resume().catch(() => undefined);
    const int16 = new Int16Array(buffer);
    if (int16.length === 0) return;
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / (int16[i] < 0 ? 0x8000 : 0x7fff);
    }
    const audioBuffer = ctx.createBuffer(1, float32.length, SAMPLE_RATE);
    audioBuffer.copyToChannel(float32, 0);
    const src = ctx.createBufferSource();
    src.buffer = audioBuffer;
    src.connect(ctx.destination);
    src.start();
  }, [getAudioCtx]);

  const cleanupMic = useCallback(() => {
    try { scriptNodeRef.current?.disconnect(); } catch { /* ignore */ }
    scriptNodeRef.current = null;
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    mediaStreamRef.current = null;
  }, []);

  const stopPing = useCallback(() => {
    if (pingTimerRef.current) { clearInterval(pingTimerRef.current); pingTimerRef.current = null; }
  }, []);

  const disconnect = useCallback(() => {
    talkingRef.current = false;
    setIsTransmitting(false);
    stopPing();
    cleanupMic();
    setMicState('idle');
    setParticipants([]);
    setRemoteTalking(null);
    const ws = wsRef.current;
    wsRef.current = null;
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) ws.close();
    setState('idle');
  }, [cleanupMic, stopPing]);

  const connect = useCallback(async (): Promise<boolean> => {
    if (!hallId || unmountedRef.current) return false;
    if (wsRef.current?.readyState === WebSocket.OPEN) return true;

    setState('connecting');
    setError(null);
    const ws = new WebSocket(voiceWebSocketUrl(hallId));
    ws.binaryType = 'arraybuffer';

    const opened = await new Promise<boolean>((resolve) => {
      const to = window.setTimeout(() => resolve(false), 12000);
      ws.addEventListener('open', () => { window.clearTimeout(to); resolve(true); }, { once: true });
      ws.addEventListener('error', () => { window.clearTimeout(to); resolve(false); }, { once: true });
      ws.addEventListener('close', () => { window.clearTimeout(to); resolve(false); }, { once: true });
    });

    if (!opened) {
      if (!unmountedRef.current) {
        setState('error');
        setError('تعذر الاتصال بالقناة الصوتية');
      }
      return false;
    }

    wsRef.current = ws;
    setState('connected');
    setError(null);

    stopPing();
    pingTimerRef.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }));
    }, 25000);

    ws.onmessage = (event) => {
      if (typeof event.data === 'string') {
        let data: { type?: string; participants?: VoiceParticipant[]; id?: string; name?: string; role?: string };
        try { data = JSON.parse(event.data); } catch { return; }
        if (data.type === 'presence') {
          setParticipants(data.participants ?? []);
        } else if (data.type === 'talk_start') {
          setRemoteTalking({ id: data.id ?? '', name: data.name ?? '', role: data.role ?? '' });
        } else if (data.type === 'talk_stop') {
          setRemoteTalking(null);
        }
      } else if (event.data instanceof ArrayBuffer) {
        playPcm(event.data);
      }
    };

    ws.onclose = () => {
      stopPing();
      cleanupMic();
      setMicState('idle');
      setIsTransmitting(false);
      setRemoteTalking(null);
      if (wsRef.current === ws) wsRef.current = null;
      if (!unmountedRef.current) {
        setState('error');
        setError('انقطع الاتصال بالقناة الصوتية');
      }
    };

    return true;
  }, [hallId, cleanupMic, playPcm, stopPing]);

  const ensureMic = useCallback(async (ws: WebSocket): Promise<boolean> => {
    if (mediaStreamRef.current && scriptNodeRef.current) { setMicState('ready'); return true; }
    if (!navigator.mediaDevices?.getUserMedia) {
      setMicState('blocked');
      setError('الميكروفون يتطلب HTTPS — افتح التطبيق عبر رابط https');
      return false;
    }
    setMicState('requesting');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      mediaStreamRef.current = stream;
      const ctx = getAudioCtx();
      if (!ctx) { setMicState('error'); return false; }
      if (ctx.state === 'suspended') await ctx.resume().catch(() => undefined);
      const source = ctx.createMediaStreamSource(stream);
      const node = ctx.createScriptProcessor(4096, 1, 1);
      scriptNodeRef.current = node;
      source.connect(node);
      node.connect(ctx.destination);
      node.onaudioprocess = (ev) => {
        if (!talkingRef.current || ws.readyState !== WebSocket.OPEN) return;
        const input = ev.inputBuffer.getChannelData(0);
        const int16 = new Int16Array(input.length);
        for (let i = 0; i < input.length; i++) {
          const s = Math.max(-1, Math.min(1, input[i]));
          int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        ws.send(int16.buffer);
      };
      setMicState('ready');
      return true;
    } catch {
      cleanupMic();
      setMicState(isInsecureLanContext() ? 'blocked' : 'error');
      setError(isInsecureLanContext()
        ? 'الميكروفون يتطلب HTTPS — افتح التطبيق عبر رابط https'
        : 'تعذر الوصول إلى الميكروفون');
      return false;
    }
  }, [cleanupMic, getAudioCtx]);

  const startTalking = useCallback(async () => {
    let ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      const ok = await connect();
      ws = wsRef.current;
      if (!ok || !ws || ws.readyState !== WebSocket.OPEN) return;
    }
    const micOk = await ensureMic(ws);
    if (!micOk) return;
    talkingRef.current = true;
    setIsTransmitting(true);
    ws.send(JSON.stringify({ type: 'talk_start' }));
  }, [connect, ensureMic]);

  const stopTalking = useCallback(() => {
    talkingRef.current = false;
    setIsTransmitting(false);
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'talk_stop' }));
  }, []);

  // Auto-connect once when requested.
  useEffect(() => {
    if (autoConnect && hallId) void connect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoConnect, hallId]);

  useEffect(() => {
    return () => {
      unmountedRef.current = true;
      disconnect();
      void audioCtxRef.current?.close().catch(() => undefined);
      audioCtxRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const micBlocked = micState === 'blocked';
  const statusText =
    isTransmitting ? 'إرسال' :
    remoteTalking ? `يتحدث: ${remoteTalking.name}` :
    state === 'error' ? (error ?? 'فشل الاتصال الصوتي') :
    state === 'connecting' ? 'جاري الاتصال…' :
    micBlocked ? 'الميكروفون محجوب — يتطلب HTTPS' :
    state === 'connected' ? 'متصل بالقناة الصوتية' :
    'غير متصل';

  return {
    state,
    isConnected: state === 'connected',
    micState,
    micBlocked,
    isTransmitting,
    participants,
    remoteTalking,
    error,
    statusText,
    connect,
    disconnect,
    startTalking,
    stopTalking,
  };
}
