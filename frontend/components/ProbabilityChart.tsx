import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface WeeklyPrediction {
  week: number;
  probability: number;
  scored: boolean;
}

interface ProbabilityChartProps {
  data: WeeklyPrediction[];
}

export function ProbabilityChart({ data }: ProbabilityChartProps) {
  return (
    <div className="bg-gray-900/40 backdrop-blur-sm border border-gray-800 rounded-2xl p-6 max-md:p-4">
      <h3 className="text-xl max-md:text-lg text-white mb-6 max-md:mb-4">TD Probability by Week</h3>
      <div className="h-80 max-md:h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="probabilityGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#a855f7" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="week"
              stroke="#9ca3af"
              tick={{ fill: '#9ca3af', fontSize: 12 }}
              label={{ value: 'Week', position: 'insideBottom', offset: -5, fill: '#9ca3af' }}
            />
            <YAxis
              stroke="#9ca3af"
              tick={{ fill: '#9ca3af', fontSize: 12 }}
              label={{ value: 'Probability (%)', angle: -90, position: 'insideLeft', fill: '#9ca3af' }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1f2937',
                border: '1px solid #374151',
                borderRadius: '8px',
                color: '#fff',
              }}
              formatter={(value: number | undefined, _name: string | undefined, props: any) => {
                if (value === undefined) return ['', ''];
                const scored = props.payload.scored;
                return [
                  <div key="tooltip">
                    <div>{value}% probability</div>
                    {scored && <div className="text-green-400 mt-1">✓ Scored TD</div>}
                  </div>,
                  '',
                ];
              }}
              labelFormatter={(week) => `Week ${week}`}
            />
            <Area
              type="monotone"
              dataKey="probability"
              stroke="#a855f7"
              strokeWidth={2}
              fill="url(#probabilityGradient)"
              dot={(props: any) => {
                const { cx, cy, payload } = props;
                if (payload.scored) {
                  return (
                    <circle
                      cx={cx}
                      cy={cy}
                      r={6}
                      fill="#22c55e"
                      stroke="#fff"
                      strokeWidth={2}
                    />
                  );
                }
                return <circle cx={cx} cy={cy} r={3} fill="#a855f7" />;
              }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="flex items-center gap-6 max-md:flex-col max-md:items-start max-md:gap-3 mt-4 text-sm max-md:text-xs">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-purple-500" />
          <span className="text-gray-400">Model Probability</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-green-500" />
          <span className="text-gray-400">TD Scored</span>
        </div>
      </div>
    </div>
  );
}
