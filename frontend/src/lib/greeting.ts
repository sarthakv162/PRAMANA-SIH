const GREETINGS = new Set([
  'hi',
  'hello',
  'hey',
  'hey there',
  'hi there',
  'hello there',
  'good morning',
  'good afternoon',
  'good evening',
  'namaste',
  'नमस्ते',
  'नमस्कार',
  'வணக்கம்',
  'নমস্কার',
]);

/** Match a standalone greeting without consuming a greeting followed by a real question. */
export function isGreeting(text: string): boolean {
  const normalized = text
    .normalize('NFKC')
    .toLocaleLowerCase()
    .trim()
    .replace(/[!?.…،,।]+$/u, '')
    .replace(/\s+/gu, ' ')
    .trim();
  return GREETINGS.has(normalized);
}
