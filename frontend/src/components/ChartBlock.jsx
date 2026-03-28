import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'

const COLORS = ['#2f81f7', '#a371f7', '#f0883e', '#3fb950', '#f85149', '#58a6ff', '#d2a8ff', '#ffa657']

const tooltipStyle = {
  backgroundColor: '#161b22',
  border: '1px solid #30363d',
  borderRadius: '8px',
  color: '#e6edf3',
  fontSize: '0.8rem',
}

export default function ChartBlock({ spec }) {
  try {
    const data = typeof spec === 'string' ? JSON.parse(spec) : spec
    const { type, title, data: chartData, xKey, yKey, yLabel } = data

    if (!chartData || chartData.length === 0) return null

    return (
      <div className="chart-block">
        {title && <div className="chart-title">{title}</div>}

        <ResponsiveContainer width="100%" height={280}>
          {type === 'pie' ? (
            <PieChart>
              <Pie
                data={chartData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                labelLine={false}
              >
                {chartData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: '0.75rem', color: '#8b949e' }} />
            </PieChart>
          ) : type === 'line' ? (
            <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
              <XAxis dataKey={xKey} tick={{ fill: '#8b949e', fontSize: 11 }} />
              <YAxis label={yLabel ? { value: yLabel, angle: -90, position: 'insideLeft', fill: '#8b949e', fontSize: 10 } : undefined} tick={{ fill: '#8b949e', fontSize: 11 }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: '0.75rem', color: '#8b949e' }} />
              <Line type="monotone" dataKey={yKey} stroke="#2f81f7" strokeWidth={2} dot={{ fill: '#2f81f7', r: 4 }} />
            </LineChart>
          ) : (
            <BarChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
              <XAxis dataKey={xKey} tick={{ fill: '#8b949e', fontSize: 11 }} />
              <YAxis label={yLabel ? { value: yLabel, angle: -90, position: 'insideLeft', fill: '#8b949e', fontSize: 10 } : undefined} tick={{ fill: '#8b949e', fontSize: 11 }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: '0.75rem', color: '#8b949e' }} />
              <Bar dataKey={yKey} radius={[4, 4, 0, 0]}>
                {chartData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    )
  } catch {
    return null
  }
}
