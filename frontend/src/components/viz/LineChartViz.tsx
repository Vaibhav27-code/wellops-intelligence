import {
  LineChart as ReLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { VisualizationSpec } from '../../types';
import { resolveChartConfig } from './chartUtils';

const COLORS = ['#4F7BE8', '#E8774F', '#4FBE80', '#BE4F9E', '#E8C84F', '#4FBEBE'];

interface LineChartVizProps {
  spec: VisualizationSpec;
}

export function LineChartViz({ spec }: LineChartVizProps) {
  const { xKey, yKeys, data } = resolveChartConfig(spec, 'line');

  if (yKeys.length === 0) {
    return (
      <div className="chart-wrapper">
        <h3 className="chart-title">{spec.title}</h3>
        <p style={{ color: 'var(--c-text-muted)', fontSize: '12px', padding: '16px' }}>
          No numeric metrics available to plot as a line chart. Use Table view to inspect records.
        </p>
      </div>
    );
  }

  return (
    <div className="chart-wrapper">
      <h3 className="chart-title">{spec.title}</h3>
      <ResponsiveContainer width="100%" height={280}>
        <ReLineChart data={data} margin={{ top: 12, right: 24, bottom: 12, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
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
            domain={['auto', 'auto']}
          />
          <Tooltip
            contentStyle={{
              background: '#1e293b',
              border: '1px solid #334155',
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: '#e2e8f0', fontWeight: 600 }}
          />
          {yKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 12, color: '#9ca3af' }} />}
          {yKeys.map((key, i) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2}
              dot={{ r: 4, strokeWidth: 1, fill: COLORS[i % COLORS.length] }}
              activeDot={{ r: 6 }}
              connectNulls={true}
            />
          ))}
        </ReLineChart>
      </ResponsiveContainer>
    </div>
  );
}
