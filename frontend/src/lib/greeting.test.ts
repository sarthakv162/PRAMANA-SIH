import { describe, expect, it } from 'vitest';
import { isGreeting } from './greeting';

describe('isGreeting', () => {
  it.each(['Hi', ' hello! ', 'Hey there.', 'Good morning', 'नमस्ते।', 'வணக்கம்', 'নমস্কার'])('recognizes standalone greeting %s', (input) => {
    expect(isGreeting(input)).toBe(true);
  });

  it.each(['Hi, can I patent this?', 'Hello, what does section 3(p) say?', 'high', ''])('does not consume a substantive or empty query: %s', (input) => {
    expect(isGreeting(input)).toBe(false);
  });
});
