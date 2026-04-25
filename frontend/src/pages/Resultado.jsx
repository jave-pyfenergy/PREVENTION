import { useParams, useNavigate } from 'react-router-dom'
import { useResultado } from '../hooks/useEvaluacion'
import { useAuth } from '../hooks/useAuth'
import { Spinner } from '../components/common/Spinner'

const NIVEL_CONFIG = {
  bajo:     { color: 'green',  label: 'Riesgo Bajo',     icon: '✅', pct: 25 },
  moderado: { color: 'amber',  label: 'Riesgo Moderado', icon: '⚠️', pct: 55 },
  alto:     { color: 'red',    label: 'Riesgo Alto',     icon: '🔴', pct: 80 },
  critico:  { color: 'purple', label: 'Riesgo Crítico',  icon: '🚨', pct: 97 },
}

const COLOR_CLASSES = {
  green:  { bar: 'bg-green-500',  badge: 'badge-riesgo-bajo',     text: 'text-green-700'  },
  amber:  { bar: 'bg-amber-500',  badge: 'badge-riesgo-moderado', text: 'text-amber-700'  },
  red:    { bar: 'bg-red-500',    badge: 'badge-riesgo-alto',     text: 'text-red-700'    },
  purple: { bar: 'bg-purple-600', badge: 'badge-riesgo-critico',  text: 'text-purple-700' },
}

export default function Resultado() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()
  const { data: resultado, isLoading, isError } = useResultado(sessionId)

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Spinner className="mx-auto mb-4" />
          <p className="text-slate-500 animate-pulse-soft">Analizando tu evaluación con IA...</p>
        </div>
      </div>
    )
  }

  if (isError || !resultado) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="card text-center max-w-md">
          <div className="text-4xl mb-4">❌</div>
          <h2 className="text-xl font-bold text-slate-800 mb-2">Resultado no encontrado</h2>
          <p className="text-slate-500 mb-6">La evaluación puede haber expirado (TTL: 24h).</p>
          <button onClick={() => navigate('/formulario')} className="btn-primary">
            Nueva evaluación
          </button>
        </div>
      </div>
    )
  }

  const nivel = resultado.nivel_inflamacion || 'bajo'
  const config = NIVEL_CONFIG[nivel] || NIVEL_CONFIG.bajo
  const colors = COLOR_CLASSES[config.color]
  const pct = Math.round(resultado.probabilidad * 100)

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 py-12 px-4">
      <div className="max-w-2xl mx-auto space-y-6 animate-fade-in">

        {/* Header resultado */}
        <div className="card text-center">
          <div className="text-5xl mb-4">{config.icon}</div>
          <span className={`inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-semibold ${colors.badge}`}>
            {config.label}
          </span>

          <div className="mt-6 mb-2">
            <div className="flex justify-between text-sm text-slate-500 mb-1">
              <span>Probabilidad de inflamación</span>
              <span className={`font-bold ${colors.text}`}>{pct}%</span>
            </div>
            <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={`h-full ${colors.bar} rounded-full transition-all duration-1000`}
                style={{ width: `${config.pct}%` }}
              />
            </div>
          </div>

          {!resultado.es_confiable && (
            <p className="text-xs text-amber-600 bg-amber-50 rounded-lg px-3 py-2 mt-4">
              ⚠️ Confianza del modelo por debajo del umbral óptimo. Considere nueva evaluación con imagen.
            </p>
          )}
        </div>

        {/* Recomendación */}
        <div className="card">
          <h3 className="font-bold text-slate-800 mb-3 flex items-center gap-2">
            <span>💡</span> Recomendación
          </h3>
          <p className="text-slate-600 leading-relaxed">{resultado.recomendacion}</p>
        </div>

        {/* Mapa Grad-CAM */}
        {resultado.gradcam_url && (
          <div className="card">
            <h3 className="font-bold text-slate-800 mb-3 flex items-center gap-2">
              <span>🔬</span> Análisis visual (Grad-CAM)
            </h3>
            <p className="text-slate-500 text-sm mb-4">
              Las zonas marcadas en rojo son las que el modelo identificó como indicadoras de posible inflamación.
            </p>
            <img
              src={resultado.gradcam_url}
              alt="Mapa de calor Grad-CAM"
              className="w-full rounded-xl border border-slate-200"
              loading="lazy"
            />
          </div>
        )}

        {/* Disclaimer */}
        <div className="bg-slate-100 rounded-xl p-4">
          <p className="text-xs text-slate-500 leading-relaxed">{resultado.disclaimer}</p>
        </div>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row gap-3">
          {isAuthenticated ? (
            <button onClick={() => navigate('/dashboard')} className="btn-primary flex-1">
              Ver mi historial completo
            </button>
          ) : (
            <button onClick={() => navigate('/registro')} className="btn-primary flex-1">
              Guardar resultado → Crear cuenta
            </button>
          )}
          <button onClick={() => navigate('/formulario')} className="btn-outline flex-1">
            Nueva evaluación
          </button>
        </div>

        <p className="text-center text-xs text-slate-400">
          Evaluación ID: {resultado.session_id?.slice(0, 8)}... ·{' '}
          {new Date(resultado.fecha).toLocaleDateString()}
        </p>
      </div>
    </div>
  )
}
