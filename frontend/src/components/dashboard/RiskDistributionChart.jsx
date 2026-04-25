import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'

const NIVEL_COLORS = {
  bajo:     '#22c55e',
  moderado: '#f59e0b',
  alto:     '#ef4444',
  critico:  '#7c3aed',
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const { nivelKey, count } = payload[0].payload
  return (
    <div className="bg-white border border-slate-200 rounded-xl px-3 py-2 shadow-lg text-sm">
      <span style={{ color: NIVEL_COLORS[nivelKey] }} className="font-semibold capitalize">
        {nivelKey}
      </span>
      <span className="text-slate-500 ml-2">{count} evaluación{count !== 1 ? 'es' : ''}</span>
    </div>
  )
}

export function RiskDistributionChart({ data }) {
  const hasData = data?.some((d) => d.count > 0)

  return (
    <div className="card h-full flex flex-col">
      <h2 className="font-bold text-slate-800 mb-4">Distribución por nivel</h2>

      {!hasData ? (
        <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">
          Sin datos suficientes
        </div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -24 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis
                dataKey="nivel"
                tick={{ fontSize: 11, fill: '#94a3b8' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fontSize: 11, fill: '#94a3b8' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: '#f8fafc' }} />
              <Bar dataKey="count" radius={[6, 6, 0, 0]} maxBarSize={48}>
                {data.map((entry) => (
                  <Cell
                    key={entry.nivelKey}
                    fill={NIVEL_COLORS[entry.nivelKey] ?? '#94a3b8'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          <div className="flex flex-wrap gap-3 mt-3">
            {data.filter((d) => d.count > 0).map((d) => (
              <div key={d.nivelKey} className="flex items-center gap-1.5 text-xs text-slate-500">
                <span
                  className="w-2.5 h-2.5 rounded-full inline-block"
                  style={{ background: NIVEL_COLORS[d.nivelKey] }}
                />
                {d.nivel}: {d.count}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
