import { describe, it, expect } from 'vitest';
import { formatTimestamp, truncateText, classNames, formatDuration } from '../utils/helpers';

describe('helpers', () => {
  describe('formatTimestamp', () => {
    it('formats ISO timestamps', () => {
      const result = formatTimestamp('2024-01-15T10:30:00Z');
      expect(result).toBeDefined();
      expect(typeof result).toBe('string');
    });

    it('handles invalid dates', () => {
      const result = formatTimestamp('invalid');
      expect(result).toBe('Invalid Date');
    });
  });

  describe('truncateText', () => {
    it('truncates long strings', () => {
      const result = truncateText('This is a long string', 13);
      expect(result).toBe('This is a ...');
    });

    it('leaves short strings unchanged', () => {
      const result = truncateText('Short', 10);
      expect(result).toBe('Short');
    });
  });

  describe('classNames', () => {
    it('joins class names', () => {
      const result = classNames('a', 'b', 'c');
      expect(result).toBe('a b c');
    });

    it('filters falsy values', () => {
      const result = classNames('a', false, undefined, 'b', null, 'c');
      expect(result).toBe('a b c');
    });
  });

  describe('formatDuration', () => {
    it('formats milliseconds to seconds', () => {
      expect(formatDuration(45000)).toBe('45s');
    });

    it('formats minutes and seconds', () => {
      expect(formatDuration(125000)).toBe('2m 5s');
    });

    it('formats hours', () => {
      expect(formatDuration(3665000)).toBe('1h 1m');
    });
  });
});
