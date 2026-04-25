import { useNavigate } from 'react-router-dom'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { useAuth } from '../hooks/useAuth'
import { useHistorial } from '../hooks/useEvaluacion'
import { Spinner } from '../components/common/Spinner'

const NIVEL_BADGE = {
  bajo:     { label: 'Bajo',     cls: 'badge-riesgo-bajo' },
  moderado: { label: 'Moderado', cls: 'badge-riesgo-moderado' },
  alto:     { label: 'Alto',     cls: 'badge-riesgo-alto' },
  critico:  { label: 'Crítico',  cls: 'badge-riesgo-critico' },
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { user, signOut } = useAuth()
  const { data: historial, isLoading } = useHistorial()

  const chartData = historial?.items?.map((item) => ({
    fecha: new Date(item.fecha).toLocaleDateString('es', { month: 'short', day: 'numeric' }),
    probabilidad: Math.round(item.probabilidad * 100),
    nivel: item.nivel_inflamacion,
  })) || []

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      {/* Navbar */}
      <nav className="bg-white border-b border-slate-100 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-blue-800 rounded-lg flex items-center justify-center">
              <span className="text-white text-xs font-bold">PA</span>
            </div>
            <span className="font-bold text-blue-900">PrevencionApp</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-slate-500">{user?.email}</span>
            <button
              onClick={() => navigate('/formulario')}
              className="btn-primary text-sm py-2"
            >
              + Nueva evaluación
            </button>
            <button
              onClick={signOut}
              className="text-sm text-slate-400 hover:text-slate-600 transition-colors"
            >
              Cerrar sesión
            </button>
          </div>
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-10 space-y-8">
        {/* Título */}
        <div>
          <h1 className="text-3xl font-bold text-slate-800">Mi historial</h1>
          <p className="text-slate-500 mt-1">Evolución de tu riesgo de inflamación sinovial</p>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-20"><Spinner /></div>
        ) : historial?.items?.length === 0 ? (
          <div className="card text-center py-16">
            <div className="text-5xl mb-4">📋</div>
            <h2 className="text-xl font-bold text-slate-700 mb-2">Sin evaluaciones aún</h2>
            <p className="text-slate-400 mb-6">Completa tu primera evaluación para ver tu historial aquí.</p>
            <button onClick={() => navigate('/formulario')} className="btn-primary">
              Iniciar evaluación →
            </button>
          </div>
        ) : (
          <>
            {/* Gráfico de evolución */}
            {chartData.length > 1 && (
              <div className="card">
                <h2 className="font-bold text-slate-800 mb-6">Evolución de riesgo (%)</h2>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis dataKey="fecha" tick={{ fontSize: 12, fill: '#94a3b8' }} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 12, fill: '#94a3b8' }} unit="%" />
                    <Tooltip
                      formatter={(value) => [`${value}%`, 'Probabilidad']}
                      contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0', fontSize: '13px' }}
                    />
                    <Line
                      type="monotone"
                      dataKey="probabilidad"
                      stroke="#0f4c81"
                      strokeWidth={2.5}
                      dot={{ fill: '#0f4c81', r: 4 }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Lista de evaluaciones */}
            <div className="space-y-3">
              {historial.items.map((item) => {
                const badge = NIVEL_BADGE[item.nivel_inflamacion] || NIVEL_BADGE.bajo
                return (
                  <button
                    key={item.evaluacion_id}
                    onClick={() => navigate(`/resultado/${item.evaluacion_id}`)}
                    className="card w-full text-left hover:shadow-md transition-all group"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className={`px-3 py-1 rounded-full text-xs font-semibold ${badge.cls}`}>
                          {badge.label}
                        </div>
                        <div>
                          <p className="font-medium text-slate-800 text-sm">
                            {Math.round(item.probabilidad * 100)}% probabilidad
                          </p>
                          <p className="text-slate-400 text-xs mt-0.5">
                            {new Date(item.fecha).toLocaleDateString('es', {
                              year: 'numeric', month: 'long', day: 'numeric'
                            })}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 text-slate-300 group-hover:text-slate-500 transition-colors">
                        {item.tiene_imagen && <span className="text-xs">📷</span>}
                        <span>→</span>
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>

            {/* Paginación básica */}
            {historial.has_next && (
              <div className="text-center">
                <button className="btn-outline text-sm">Cargar más evaluaciones</button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
