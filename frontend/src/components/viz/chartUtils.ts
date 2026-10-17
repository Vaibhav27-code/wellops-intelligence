import type { VisualizationSpec } from '../../types';

export interface ResolvedChartConfig {
  xKey: string;
  yKeys: string[];
  data: Array<Record<string, any>>;
  hasNumeric: boolean;
}

/** Resolves X and Y keys for charts deterministically, ensuring only numeric columns are plotted on Y */
export function resolveChartConfig(
  spec: VisualizationSpec,
  mode: 'line' | 'bar' = 'line'
): ResolvedChartConfig {
  if (!spec.data || !Array.isArray(spec.data) || spec.data.length === 0) {
    return { xKey: '', yKeys: [], data: [], hasNumeric: false };
  }

  const first = spec.data[0];
  const rawKeys = Object.keys(first);

  // Helper to check if a value looks like a valid number
  const isNumericValue = (val: any): boolean => {
    if (typeof val === 'number') return !isNaN(val) && isFinite(val);
    if (typeof val === 'string') {
      const trimmed = val.trim();
      if (!trimmed) return false;
      // Exclude dates like "2026-10-15" or identifiers like "WELL-0001" or "INS-0001"
      if (/^\d{4}[-/]\d{1,2}[-/]\d{1,2}/.test(trimmed)) return false;
      if (/^[A-Za-z]+[-_]\d+/i.test(trimmed)) return false;
      const num = Number(trimmed);
      return !isNaN(num) && isFinite(num);
    }
    return false;
  };

  // Find all columns that contain numeric data in at least one row
  const numericColumns = rawKeys.filter((k) =>
    spec.data.some((row) => isNumericValue(row[k]))
  );

  const hasNumeric = numericColumns.length > 0;

  // 1. Resolve X key
  let xKey = '';
  if (spec.x && rawKeys.includes(spec.x)) {
    xKey = spec.x;
  } else {
    // Look for date/time/temporal key first
    const dateKey =
      rawKeys.find((k) =>
        /^(date|inspection[ _]?date|inspected_at|timestamp|time|week|month|year|period|quarter)$/i.test(
          k
        )
      ) || rawKeys.find((k) => /(date|time|week|month|year|period)/i.test(k));

    // Look for categorical / identifier key
    const catKey =
      rawKeys.find((k) =>
        /^(well[ _]?id|asset[ _]?id|area[ _]?id|area|group|id|name|label|well|asset|group_by)$/i.test(
          k
        )
      ) || rawKeys.find((k) => /(well|area|group|name|label|category)/i.test(k));

    if (mode === 'line') {
      xKey =
        dateKey ||
        catKey ||
        rawKeys.find((k) => !numericColumns.includes(k)) ||
        rawKeys[0];
    } else {
      xKey =
        catKey ||
        dateKey ||
        rawKeys.find((k) => !numericColumns.includes(k)) ||
        rawKeys[0];
    }
  }

  // 2. Resolve Y keys (MUST be numeric!)
  let yKeys: string[] = [];
  if (spec.y) {
    const candidateY = Array.isArray(spec.y) ? spec.y : [spec.y];
    yKeys = candidateY.filter((k) => rawKeys.includes(k) && k !== xKey);
  }

  // If no explicit valid y keys or if candidate was empty, use all numeric columns except xKey
  if (yKeys.length === 0) {
    yKeys = numericColumns.filter((k) => k !== xKey);
  }

  // Absolute fallback: any column other than xKey
  if (yKeys.length === 0) {
    yKeys = rawKeys.filter((k) => k !== xKey);
  }

  // 3. Prepare normalized data
  let preparedData = spec.data.map((row) => {
    const copy: Record<string, any> = { ...row };
    for (const y of yKeys) {
      const v = copy[y];
      if (typeof v === 'number') {
        // ok
      } else if (v !== null && v !== undefined && v !== '') {
        const cleaned = String(v).replace(/[^0-9.-]/g, '');
        const parsed = parseFloat(cleaned);
        copy[y] = isNaN(parsed) ? null : parsed;
      } else {
        copy[y] = null;
      }
    }
    return copy;
  });

  // For line charts, sort by xKey chronologically if it contains dates
  if (mode === 'line' && xKey) {
    const isDateLike = spec.data.every((r) => {
      const val = String(r[xKey] ?? '');
      return /^\d{4}[-/]\d{1,2}/.test(val) || !isNaN(Date.parse(val));
    });
    if (isDateLike) {
      preparedData.sort((a, b) => {
        const da = new Date(String(a[xKey])).getTime();
        const db = new Date(String(b[xKey])).getTime();
        return (isNaN(da) ? 0 : da) - (isNaN(db) ? 0 : db);
      });
    }
  }

  return { xKey, yKeys, data: preparedData, hasNumeric };
}
