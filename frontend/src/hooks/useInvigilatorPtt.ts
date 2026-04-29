import { useCallback, useEffect, useRef, useState } from 'react';
import { pttWebSocketUrl } from '../config/api';

export type PttConnectionState = 'idle' | 'connecting' | 'connected' | 'error';

type Options = {
  clientId?: string;
  defaultTargetId?: string;
};

/**
 * Push-to-talk to an invigilator (same protocol as src/tests/ptt_client.html).
 */
export function useInvigilatorPtt(options: Options = {}) {
  const clientId = options.clientId ?? 'control_room_dashboard';
  const defaultTargetId = options.defaultTargetId ?? 'invigilator_demo_1';

  const [state, setState] = useState<PttConnectionState>('idle');
  const [statusText, setStatusText] = useState('غير متصل');

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const scriptNodeRef = useRef<ScriptProcessorNode | null>(null);
  const pttActiveRef = useRef(false);

  const cleanupAudioGraph = useCallback(() => {
    try {
      scriptNodeRef.current?.disconnect();
    } catch {
      /* ignore */
    }
    scriptNodeRef.current = null;
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    mediaStreamRef.current = null;
  }, []);

  const disconnect = useCallback(() => {
    pttActiveRef.current = false;
    cleanupAudioGraph();
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }
    wsRef.current = null;
    setState('idle');
    setStatusText('غير متصل');
  }, [cleanupAudioGraph]);

  useEffect(() => () => disconnect(), [disconnect]);

  const connect = useCallback(async (): Promise<boolean> => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      setState('connected');
      return true;
    }

    setState('connecting');
    setStatusText('جاري الاتصال…');

    const ws = new WebSocket(pttWebSocketUrl(clientId));
    ws.binaryType = 'arraybuffer';

    try {
      await new Promise<void>((resolve, reject) => {
        const to = window.setTimeout(() => reject(new Error('timeout')), 12000);
        ws.addEventListener(
          'open',
          () => {
            window.clearTimeout(to);
            resolve();
          },
          { once: true }
        );
        ws.addEventListener(
          'error',
          () => {
            window.clearTimeout(to);
            reject(new Error('ws'));
          },
          { once: true }
        );
      });
    } catch {
      ws.close();
      wsRef.current = null;
      setState('error');
      setStatusText('تعذر الاتصال بالخادم');
      return false;
    }

    wsRef.current = ws;

    ws.addEventListener('close', () => {
      cleanupAudioGraph();
      void audioContextRef.current?.close().catch(() => undefined);
      audioContextRef.current = null;
      if (wsRef.current === ws) wsRef.current = null;
      setState('idle');
      setStatusText('غير متصل');
    });

    try {
      const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioContext = new Ctx({ sampleRate: 16000 });
      audioContextRef.current = audioContext;

      const mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      mediaStreamRef.current = mediaStream;

      const micSource = audioContext.createMediaStreamSource(mediaStream);
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
            if (data.type === 'start_speak') {
              setStatusText(`المتحدث: ${data.sender_id ?? '—'}`);
            } else if (data.type === 'stop_speak') {
              setStatusText('متصل — اضغط مع الاستمرار للتحدث');
            }
          } catch {
            /* ignore */
          }
        } else if (event.data instanceof ArrayBuffer) {
          const ctx = audioContextRef.current;
          if (ctx) playPcmChunk(ctx, event.data);
        }
      };

      setState('connected');
      setStatusText('متصل — اضغط مع الاستمرار للتحدث');
      return true;
    } catch {
      setState('error');
      setStatusText('تعذر الوصول للميكروفون');
      ws.close();
      wsRef.current = null;
      return false;
    }
  }, [clientId, cleanupAudioGraph]);

  const startSpeak = useCallback(
    (targetId?: string) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      pttActiveRef.current = true;
      const tid = targetId ?? defaultTargetId;
      ws.send(JSON.stringify({ type: 'start_speak', target_id: tid }));
      void audioContextRef.current?.resume();
    },
    [defaultTargetId]
  );

  const stopSpeak = useCallback(
    (targetId?: string) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      pttActiveRef.current = false;
      const tid = targetId ?? defaultTargetId;
      ws.send(JSON.stringify({ type: 'stop_speak', target_id: tid }));
    },
    [defaultTargetId]
  );

  return {
    state,
    statusText,
    defaultTargetId,
    connect,
    disconnect,
    startSpeak,
    stopSpeak,
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
