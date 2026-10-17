import React from 'react';
import type { VisualizationSpec } from '../../types';
import { ChevronUp, ChevronDown } from 'lucide-react';

interface DataTableProps {
  spec: VisualizationSpec;
}

/** Sortable, filterable table visualization. */
export function DataTable({ spec }: DataTableProps) {
  const columns = spec.columns ?? (spec.data.length > 0 ? Object.keys(spec.data[0]) : []);
  const [sortCol, setSortCol] = React.useState<string | null>(null);
  const [sortDir, setSortDir] = React.useState<'asc' | 'desc'>('asc');
  const [filter, setFilter] = React.useState('');

  const sorted = React.useMemo(() => {
    let rows = [...spec.data];
    if (filter.trim()) {
      const q = filter.toLowerCase();
      rows = rows.filter((r) =>
        Object.values(r).some((v) => String(v ?? '').toLowerCase().includes(q))
      );
    }
    if (sortCol) {
      rows.sort((a, b) => {
        const av = a[sortCol];
        const bv = b[sortCol];
        const cmp =
          typeof av === 'number' && typeof bv === 'number'
            ? av - bv
            : String(av ?? '').localeCompare(String(bv ?? ''));
        return sortDir === 'asc' ? cmp : -cmp;
      });
    }
    return rows;
  }, [spec.data, sortCol, sortDir, filter]);

  const handleSort = (col: string) => {
    if (sortCol === col) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortCol(col);
      setSortDir('asc');
    }
  };

  return (
    <div className="data-table-wrapper">
      <div className="data-table-toolbar">
        <span className="data-table-title">{spec.title}</span>
        <input
          className="data-table-filter"
          placeholder="Filter…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          aria-label="Filter table"
        />
        <span className="data-table-count">{sorted.length} rows</span>
      </div>

      <div className="data-table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  className="data-table__th"
                  onClick={() => handleSort(col)}
                  role="button"
                  aria-sort={
                    sortCol === col ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'
                  }
                >
                  <span className="data-table__th-inner">
                    {col.replace(/_/g, ' ')}
                    {sortCol === col ? (
                      sortDir === 'asc' ? (
                        <ChevronUp size={12} />
                      ) : (
                        <ChevronDown size={12} />
                      )
                    ) : null}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="data-table__empty">
                  No data
                </td>
              </tr>
            )}
            {sorted.map((row, i) => (
              <tr key={i} className={i % 2 === 0 ? '' : 'data-table__row--alt'}>
                {columns.map((col) => (
                  <td key={col} className="data-table__td">
                    {formatCell(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatCell(val: unknown): React.ReactNode {
  if (val === null || val === undefined) return <span className="cell-null">—</span>;
  if (typeof val === 'boolean') return val ? '✓' : '✗';
  const s = String(val);
  // colour-code status-like strings
  if (/violation|spill|fail|down/i.test(s)) return <span className="cell-err">{s}</span>;
  if (/warn|pending|review/i.test(s)) return <span className="cell-warn">{s}</span>;
  if (/ok|pass|produc|active/i.test(s)) return <span className="cell-ok">{s}</span>;
  return s;
}
