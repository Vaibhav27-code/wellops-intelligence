
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

const COLORS = ['#4F7BE8', '#E8774F', '#4FBE80', '#BE4F9E', '#E8C84F', '#4FBEBE'];

interface BarChartVizProps {
  spec: VisualizationSpec;
}

export function BarChartViz({ spec }: BarChartVizProps) {
  const yKeys = Array.isArray(spec.y)
    ? spec.y
    : spec.y
    ? [spec.y]
    : spec.data.length > 0
    ? Object.keys(spec.data[0]).filter((k) => k !== spec.x)
    : [];

  const isSingleSeries = yKeys.length === 1;

  return (
    <div className="chart-wrapper">
      <h3 className="chart-title">{spec.title}</h3>
      <ResponsiveContainer width="100%" height={280}>
        <ReBarChart data={spec.data} margin={{ top: 8, right: 24, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" vertical={false} />
          <XAxis
            dataKey={spec.x ?? 'name'}
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
            cursor={{ fill: 'rgba(255,255,255,0.04)' }}
          />
          {!isSingleSeries && <Legend wrapperStyle={{ fontSize: 12, color: '#9ca3af' }} />}
          {yKeys.map((key, seriesIdx) =>
            isSingleSeries ? (
              <Bar key={key} dataKey={key} radius={[4, 4, 0, 0]}>
                {spec.data.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            ) : (
              <Bar
                key={key}
                dataKey={key}
                fill={COLORS[seriesIdx % COLORS.length]}
                radius={[4, 4, 0, 0]}
              />
            )
          )}
        </ReBarChart>
      </ResponsiveContainer>
    </div>
  );
}
