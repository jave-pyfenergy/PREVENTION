/**
 * PrevencionApp — Componente: RiesgoChart
 * Gráfico de evolución temporal del riesgo de inflamación.
 */
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const { probabilidad, nivel } = payload[0].payload

  const nivelColors = {
    bajo: '#22c55e', moderado: '#f59e0b', alto: '#ef4444', critico: '#7c3aed'
  }

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-lg text-sm">
      <p className="font-semibold text-slate-700 mb-1">{label}</p>
      <p style={{ color: nivelColors[nivel] || '#64748b' }}>
        {probabilidad}% · {nivel}
      </p>
    </div>
  )
}

export function RiesgoChart({ evaluaciones }) {
  if (!evaluaciones || evaluaciones.length < 2) return null

  const data = evaluaciones.map((ev) => ({
    fecha: new Date(ev.fecha).toLocaleDateString('es', { month: 'short', day: 'numeric' }),
    probabilidad: Math.round(ev.probabilidad * 100),
    nivel: ev.nivel_inflamacion,
  }))

  // Determinar tendencia
  const primero = data[0]?.probabilidad || 0
  const ultimo = data[data.length - 1]?.probabilidad || 0
  const tendencia = ultimo - primero
  const tendenciaLabel = tendencia > 5 ? '📈 Tendencia al alza' :
                         tendencia < -5 ? '📉 Tendencia a la baja' :
                         '➡️ Estable'

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-bold text-slate-800">Evolución de riesgo</h2>
        <span className="text-xs text-slate-500 bg-slate-100 px-3 py-1 rounded-full">
          {tendenciaLabel}
        </span>
      </div>

      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={data} margin={{ top: 5, right: 5, bottom: 0, left: -20 }}>
          <defs>
            <linearGradient id="riesgoGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#0f4c81" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#0f4c81" stopOpacity={0.01} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis dataKey="fecha" tick={{ fontSize: 11, fill: '#94a3b8' }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#94a3b8' }} unit="%" />
          <ReferenceLine y={30} stroke="#22c55e" strokeDasharray="4 4" strokeOpacity={0.5} />
          <ReferenceLine y={60} stroke="#f59e0b" strokeDasharray="4 4" strokeOpacity={0.5} />
          <ReferenceLine y={85} stroke="#ef4444" strokeDasharray="4 4" strokeOpacity={0.5} />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="probabilidad"
            stroke="#0f4c81"
            strokeWidth={2.5}
            fill="url(#riesgoGradient)"
            dot={{ fill: '#0f4c81', r: 4, strokeWidth: 0 }}
            activeDot={{ r: 6, fill: '#0f4c81' }}
          />
        </AreaChart>
      </ResponsiveContainer>

      <div className="flex gap-4 text-xs text-slate-400">
        <div className="flex items-center gap-1">
          <div className="w-6 border-t border-dashed border-green-400" />
          Bajo
        </div>
        <div className="flex items-center gap-1">
          <div className="w-6 border-t border-dashed border-amber-400" />
          Moderado
        </div>
        <div className="flex items-center gap-1">
          <div className="w-6 border-t border-dashed border-red-400" />
          Alto
        </div>
      </div>
    </div>
  )
}
