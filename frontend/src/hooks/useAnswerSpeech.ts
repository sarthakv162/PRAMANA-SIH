import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import type { Language } from '../api/types';

/** Bulbul v3 REST accepts at most 2,500 Unicode characters per request. */
export function splitSpeechText(text: string, limit = 2500): string[] {
  if (!Number.isInteger(limit) || limit < 1) throw new RangeError('Speech chunk size must be a positive integer.');
  const chars = Array.from(text.trim());
  const chunks: string[] = [];
  let start = 0;
  while (start < chars.length) {
    let end = Math.min(start + limit, chars.length);
    if (end < chars.length) {
      let wordEnd = -1;
      let sentenceEnd = -1;
      for (let i = start + Math.floor(limit / 2); i < end; i++) {
        if (/\s/.test(chars[i])) wordEnd = i;
        if (/[.!?।]/.test(chars[i]) && /\s/.test(chars[i + 1] ?? '')) sentenceEnd = i + 1;
      }
      if (sentenceEnd > start) end = sentenceEnd;
      else if (wordEnd > start) end = wordEnd;
    }
    const chunk = chars.slice(start, end).join('').trim();
    if (chunk) chunks.push(chunk);
    start = end;
    while (start < chars.length && /\s/.test(chars[start])) start++;
  }
  return chunks;
}

interface SpeechSession {
  controller: AbortController;
  audio: HTMLAudioElement | null;
  url: string | null;
  finish: (() => void) | null;
}

function releaseAudio(session: SpeechSession) {
  if (session.audio) {
    session.audio.onended = null;
    session.audio.onerror = null;
    session.audio.pause();
    session.audio.src = '';
    session.audio = null;
  }
  if (session.url) URL.revokeObjectURL(session.url);
  session.url = null;
  session.finish?.();
  session.finish = null;
}

export function useAnswerSpeech() {
  const [status, setStatus] = useState<'idle' | 'loading' | 'playing'>('idle');
  const [error, setError] = useState('');
  const active = useRef<SpeechSession | null>(null);

  const release = useCallback(() => {
    const session = active.current;
    active.current = null;
    if (!session) return;
    session.controller.abort();
    releaseAudio(session);
  }, []);
  const stop = useCallback(() => { release(); setStatus('idle'); }, [release]);
  useEffect(() => release, [release]);

  const speak = async (text: string, language: Language) => {
    if (active.current) { stop(); return; }
    setError('');
    const chunks = splitSpeechText(text);
    if (!chunks.length) { setError('There is no answer text to read aloud.'); return; }
    const session: SpeechSession = { controller: new AbortController(), audio: null, url: null, finish: null };
    active.current = session;
    try {
      for (const chunk of chunks) {
        setStatus('loading');
        const blob = await api.tts(chunk, language, session.controller.signal);
        if (active.current !== session) return;
        session.url = URL.createObjectURL(blob);
        const audio = new Audio(session.url);
        session.audio = audio;
        await new Promise<void>((resolve, reject) => {
          session.finish = resolve;
          audio.onended = () => resolve();
          audio.onerror = () => reject(new Error('Speech audio playback failed. Please retry.'));
          void audio.play().then(() => {
            if (active.current === session) setStatus('playing');
          }).catch(reject);
        });
        if (active.current !== session) return;
        releaseAudio(session);
      }
    } catch (cause) {
      if (active.current === session && !session.controller.signal.aborted) {
        setError(cause instanceof Error ? cause.message : 'Unable to read the answer aloud.');
      }
    } finally {
      if (active.current === session) { release(); setStatus('idle'); }
    }
  };
  return { status, error, speak, stop };
}
