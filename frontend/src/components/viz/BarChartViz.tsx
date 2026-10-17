import {
  BarChart as ReBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import type { VisualizationSpec } from '../../types';
import { resolveChartConfig } from './chartUtils';

const COLORS = ['#4F7BE8', '#E8774F', '#4FBE80', '#BE4F9E', '#E8C84F', '#4FBEBE'];

interface BarChartVizProps {
  spec: VisualizationSpec;
}

export function BarChartViz({ spec }: BarChartVizProps) {
  const { xKey, yKeys, data } = resolveChartConfig(spec, 'bar');

  if (yKeys.length === 0) {
    return (
      <div className="chart-wrapper">
        <h3 className="chart-title">{spec.title}</h3>
        <p style={{ color: 'var(--c-text-muted)', fontSize: '12px', padding: '16px' }}>
          No numeric metrics available to plot as a bar chart. Use Table view to inspect records.
        </p>
      </div>
    );
  }

  const isSingleSeries = yKeys.length === 1;

  return (
    <div className="chart-wrapper">
      <h3 className="chart-title">{spec.title}</h3>
      <ResponsiveContainer width="100%" height={280}>
        <ReBarChart data={data} margin={{ top: 12, right: 24, bottom: 12, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" vertical={false} />
          <XAxis
            dataKey={xKey}
            tick={{ fill: '#9ca3af', fontSize: 11 }}
            axisLine={{ stroke: '#374151' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: '#9ca3af', fontSize: 11 }}
            axisLine={{ stroke: '#374151' }}
            tickLine={false}
            unit={spec.units ? ` ${spec.units}` : ''}
          />
          <Tooltip
            contentStyle={{
              background: '#1e293b',
              border: '1px solid #334155',
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: '#e2e8f0', fontWeight: 600 }}
            cursor={{ fill: 'rgba(255,255,255,0.04)' }}
          />
          {!isSingleSeries && <Legend wrapperStyle={{ fontSize: 12, color: '#9ca3af' }} />}
          {yKeys.map((key, seriesIdx) => {
            const isStacked = (spec as any).stacked !== false && (yKeys.length > 1 || (spec as any).stacked === true || (spec.type as string) === 'stacked_bar');
            return isSingleSeries ? (
              <Bar key={key} dataKey={key} radius={[4, 4, 0, 0]}>
                {data.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            ) : (
              <Bar
                key={key}
                dataKey={key}
                stackId={isStacked ? "a" : undefined}
                fill={COLORS[seriesIdx % COLORS.length]}
                radius={isStacked ? [0, 0, 0, 0] : [4, 4, 0, 0]}
              />
            );
          })}
        </ReBarChart>
      </ResponsiveContainer>
    </div>
  );
}
