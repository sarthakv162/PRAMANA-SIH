import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import { splitSpeechText, useAnswerSpeech } from './useAnswerSpeech';

vi.mock('../api/client', () => ({ api: { tts: vi.fn() } }));

const audios: FakeAudio[] = [];
class FakeAudio {
  src: string;
  onended: (() => void) | null = null;
  onerror: (() => void) | null = null;
  play = vi.fn(async () => {});
  pause = vi.fn();
  constructor(src: string) { this.src = src; audios.push(this); }
}

describe('Sarvam read-aloud', () => {
  beforeEach(() => {
    audios.length = 0;
    vi.mocked(api.tts).mockReset().mockResolvedValue(new Blob(['test audio fixture'], { type: 'audio/wav' }));
    vi.stubGlobal('Audio', FakeAudio);
    const NativeURL = URL;
    vi.stubGlobal('URL', class extends NativeURL {
      static createObjectURL = vi.fn(() => 'blob:test-audio');
      static revokeObjectURL = vi.fn();
    });
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('plays API audio and releases it when playback ends', async () => {
    const { result } = renderHook(useAnswerSpeech);
    let task: Promise<void>;
    act(() => { task = result.current.speak('A supported claim.', 'hi'); });
    await waitFor(() => expect(result.current.status).toBe('playing'));
    expect(api.tts).toHaveBeenCalledWith('A supported claim.', 'hi', expect.any(AbortSignal));
    expect(audios[0].play).toHaveBeenCalledOnce();
    await act(async () => { audios[0].onended?.(); await task; });
    expect(result.current.status).toBe('idle');
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test-audio');
  });

  it('requests long answer chunks sequentially without truncation', async () => {
    const text = ('A complete claim. ').repeat(300).trim();
    const { result } = renderHook(useAnswerSpeech);
    let task: Promise<void>;
    act(() => { task = result.current.speak(text, 'en'); });
    const chunks = splitSpeechText(text);
    for (let i = 0; i < chunks.length; i++) {
      await waitFor(() => expect(audios).toHaveLength(i + 1));
      expect(api.tts).toHaveBeenCalledTimes(i + 1);
      await act(async () => { audios[i].onended?.(); });
    }
    await act(async () => { await task; });
    expect(vi.mocked(api.tts).mock.calls.map((call) => call[0]).join(' ')).toBe(text);
  });

  it('aborts loading and discards a late response when stopped', async () => {
    let complete!: (blob: Blob) => void;
    vi.mocked(api.tts).mockImplementationOnce(() => new Promise((resolve) => { complete = resolve; }));
    const { result } = renderHook(useAnswerSpeech);
    let task: Promise<void>;
    act(() => { task = result.current.speak('Claim', 'en'); });
    expect(result.current.status).toBe('loading');
    const signal = vi.mocked(api.tts).mock.calls[0][2]!;
    act(() => result.current.stop());
    expect(signal.aborted).toBe(true);
    await act(async () => { complete(new Blob(['fixture'])); await task; });
    expect(audios).toHaveLength(0);
    expect(URL.createObjectURL).not.toHaveBeenCalled();
    expect(result.current.status).toBe('idle');
  });

  it('stops playing audio and cancels future chunks on unmount', async () => {
    const { result, unmount } = renderHook(useAnswerSpeech);
    let task: Promise<void>;
    act(() => { task = result.current.speak('x'.repeat(5000), 'en'); });
    await waitFor(() => expect(result.current.status).toBe('playing'));
    const signal = vi.mocked(api.tts).mock.calls[0][2]!;
    unmount();
    await task!;
    expect(signal.aborted).toBe(true);
    expect(audios[0].pause).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalled();
    expect(api.tts).toHaveBeenCalledOnce();
  });

  it('displays provider errors without silently substituting a browser voice', async () => {
    vi.mocked(api.tts).mockRejectedValueOnce(new Error('Sarvam rejected the speech credentials.'));
    const fallback = vi.fn();
    vi.stubGlobal('speechSynthesis', { speak: fallback });
    const { result } = renderHook(useAnswerSpeech);
    await act(async () => result.current.speak('Claim', 'en'));
    expect(result.current.error).toContain('Sarvam rejected');
    expect(result.current.status).toBe('idle');
    expect(fallback).not.toHaveBeenCalled();
    expect(audios).toHaveLength(0);
  });

  it('cleans up audio when the browser reports playback failure', async () => {
    const { result } = renderHook(useAnswerSpeech);
    let task: Promise<void>;
    act(() => { task = result.current.speak('Claim', 'en'); });
    await waitFor(() => expect(result.current.status).toBe('playing'));
    await act(async () => { audios[0].onerror?.(); await task; });
    expect(result.current.error).toContain('playback failed');
    expect(result.current.status).toBe('idle');
    expect(URL.revokeObjectURL).toHaveBeenCalled();
  });
});

describe('speech chunk boundaries', () => {
  it('preserves sentences, Indic text and supplementary Unicode characters', () => {
    for (const text of ['यह एक वाक्य है। '.repeat(400).trim(), '🙂'.repeat(5001), 'x'.repeat(5001)]) {
      const chunks = splitSpeechText(text);
      expect(chunks.every((chunk) => Array.from(chunk).length <= 2500)).toBe(true);
      expect(chunks.join('').replace(/\s/g, '')).toBe(text.replace(/\s/g, ''));
      expect(chunks.every((chunk) => !chunk.includes('\ufffd'))).toBe(true);
    }
  });
  it('does not send blank text and rejects invalid chunk limits', () => {
    expect(splitSpeechText('  ')).toEqual([]);
    expect(() => splitSpeechText('claim', 0)).toThrow(RangeError);
  });
});
