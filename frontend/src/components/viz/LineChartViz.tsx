
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

const COLORS = ['#4F7BE8', '#E8774F', '#4FBE80', '#BE4F9E', '#E8C84F', '#4FBEBE'];

interface LineChartVizProps {
  spec: VisualizationSpec;
}

export function LineChartViz({ spec }: LineChartVizProps) {
  const yKeys = Array.isArray(spec.y)
    ? spec.y
    : spec.y
    ? [spec.y]
    : spec.data.length > 0
    ? Object.keys(spec.data[0]).filter((k) => k !== spec.x)
    : [];

  return (
    <div className="chart-wrapper">
      <h3 className="chart-title">{spec.title}</h3>
      <ResponsiveContainer width="100%" height={280}>
        <ReLineChart data={spec.data} margin={{ top: 8, right: 24, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
          <XAxis
            dataKey={spec.x ?? 'date'}
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
            labelStyle={{ color: '#e2e8f0' }}
          />
          {yKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 12, color: '#9ca3af' }} />}
          {yKeys.map((key, i) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          ))}
        </ReLineChart>
      </ResponsiveContainer>
    </div>
  );
}
