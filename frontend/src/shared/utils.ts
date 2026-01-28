import dayjs, { Dayjs } from 'dayjs';

export function formatDateTime(value?: string | null): string {
  if (!value) return '-';
  const parsed = dayjs(value);
  return parsed.isValid() ? parsed.format('YYYY-MM-DD HH:mm:ss') : value;
}

export function toISOString(value: Dayjs | null): string | null {
  if (!value) return null;
  return value.toDate().toISOString();
}

export function toDayjs(value?: string | null): Dayjs | null {
  if (!value) return null;
  const parsed = dayjs(value);
  return parsed.isValid() ? parsed : null;
}

const TAG_COLORS = ['green', 'volcano', 'orange', 'gold', 'lime', 'cyan', 'blue', 'geekblue'] as const;

export function pickTagColor(text: string): string {
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 31 + text.charCodeAt(i)) % TAG_COLORS.length;
  }
  return TAG_COLORS[hash];
}

const PERFORMANCE_KEYWORDS = [
  '强劲',
  '较高',
  '较低',
  '一般',
  '中等',
  '较强',
  '较弱',
  '优秀',
  '良好',
  '普通',
  '高',
  '低',
  '强',
  '弱',
] as const;

const PERFORMANCE_COLOR_MAP: Record<string, string> = {
  强劲: 'green',
  优秀: 'green',
  较强: 'green',
  高: 'green',
  强: 'green',
  较高: 'lime',
  良好: 'cyan',
  中等: 'gold',
  一般: 'gold',
  普通: 'gold',
  较低: 'volcano',
  较弱: 'volcano',
  低: 'volcano',
  弱: 'volcano',
};

export function extractPerformance(notes?: string | null): string {
  if (!notes) return '-';
  const cleaned = notes.replace(/\s+/g, ' ').trim();
  if (!cleaned) return '-';
  const match = cleaned.match(/性能[:：=\s]*([^\n,，;；。]+)/);
  const scope = match ? match[1] : cleaned;
  for (const keyword of PERFORMANCE_KEYWORDS) {
    if (scope.includes(keyword)) {
      return keyword;
    }
  }
  if (match) {
    const value = match[1].trim();
    return value || '-';
  }
  return '-';
}

export function pickPerformanceColor(value: string): string | undefined {
  if (!value || value === '-') return undefined;
  for (const keyword of PERFORMANCE_KEYWORDS) {
    if (value.includes(keyword)) {
      return PERFORMANCE_COLOR_MAP[keyword] || 'geekblue';
    }
  }
  return 'geekblue';
}
