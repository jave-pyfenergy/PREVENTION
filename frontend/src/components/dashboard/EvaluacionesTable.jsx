import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import clsx from 'clsx'

const NIVEL_BADGE = {
  bajo:     { label: 'Bajo',     cls: 'badge-riesgo-bajo' },
  moderado: { label: 'Moderado', cls: 'badge-riesgo-moderado' },
  alto:     { label: 'Alto',     cls: 'badge-riesgo-alto' },
  critico:  { label: 'Crítico',  cls: 'badge-riesgo-critico' },
}

const FILTERS = [
  { value: 'todos',    label: 'Todos' },
  { value: 'bajo',     label: 'Bajo' },
  { value: 'moderado', label: 'Moderado' },
  { value: 'alto',     label: 'Alto' },
  { value: 'critico',  label: 'Crítico' },
]

function ProbBar({ value }) {
  const pct = Math.round(value * 100)
  const color =
    pct >= 85 ? 'bg-riesgo-critico' :
    pct >= 60 ? 'bg-riesgo-alto' :
    pct >= 30 ? 'bg-riesgo-moderado' :
    'bg-riesgo-bajo'

  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div className={clsx('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-slate-600 tabular-nums">{pct}%</span>
    </div>
  )
}

export function EvaluacionesTable({ items, hasNext, onLoadMore, isLoadingMore }) {
  const navigate = useNavigate()
  const [filter, setFilter] = useState('todos')

  const filtered = filter === 'todos'
    ? items
    : items.filter((i) => i.nivel_inflamacion === filter)

  const sorted = [...filtered].sort((a, b) => new Date(b.fecha) - new Date(a.fecha))

  return (
    <div className="card">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
        <div>
          <h2 className="font-bold text-slate-800">Evaluaciones recientes</h2>
          <p className="text-xs text-slate-400 mt-0.5">{sorted.length} resultado{sorted.length !== 1 ? 's' : ''}</p>
        </div>

        {/* Filter pills */}
        <div className="flex gap-1 flex-wrap">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={clsx(
                'px-3 py-1 rounded-full text-xs font-medium transition-colors',
                filter === f.value
                  ? 'bg-primary-800 text-white'
                  : 'bg-slate-100 text-slate-500 hover:bg-slate-200',
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {sorted.length === 0 ? (
        <p className="text-center text-slate-400 text-sm py-8">
          No hay evaluaciones con nivel "{filter}".
        </p>
      ) : (
        <>
          {/* Desktop table header */}
          <div className="hidden sm:grid grid-cols-[1fr_1fr_1fr_auto] gap-4 px-3 pb-2 text-xs text-slate-400 uppercase tracking-wider border-b border-slate-100">
            <span>Fecha</span>
            <span>Nivel</span>
            <span>Probabilidad</span>
            <span>Imagen</span>
          </div>

          <div className="divide-y divide-slate-50">
            {sorted.map((item) => {
              const badge = NIVEL_BADGE[item.nivel_inflamacion] ?? NIVEL_BADGE.bajo
              return (
                <button
                  key={item.evaluacion_id}
                  onClick={() => navigate(`/resultado/${item.session_id}`)}
                  className="w-full text-left hover:bg-slate-50 transition-colors rounded-xl group"
                >
                  {/* Mobile layout */}
                  <div className="sm:hidden flex items-center gap-3 p-3">
                    <span className={clsx('px-2.5 py-1 rounded-full text-xs font-semibold shrink-0', badge.cls)}>
                      {badge.label}
                    </span>
                    <div className="flex-1 min-w-0">
                      <ProbBar value={item.probabilidad} />
                      <p className="text-xs text-slate-400 mt-1">
                        {new Date(item.fecha).toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' })}
                      </p>
                    </div>
                    <span className="text-slate-300 group-hover:text-slate-500 transition-colors text-sm">→</span>
                  </div>

                  {/* Desktop layout */}
                  <div className="hidden sm:grid grid-cols-[1fr_1fr_1fr_auto] gap-4 items-center px-3 py-3">
                    <p className="text-sm text-slate-600">
                      {new Date(item.fecha).toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' })}
                    </p>
                    <span className={clsx('px-2.5 py-1 rounded-full text-xs font-semibold w-fit', badge.cls)}>
                      {badge.label}
                    </span>
                    <ProbBar value={item.probabilidad} />
                    <span className="text-slate-300 text-sm">
                      {item.tiene_imagen ? '📷' : '—'}
                    </span>
                  </div>
                </button>
              )
            })}
          </div>

          {hasNext && (
            <div className="mt-5 text-center">
              <button
                onClick={onLoadMore}
                disabled={isLoadingMore}
                className="btn-outline text-sm"
              >
                {isLoadingMore ? 'Cargando...' : 'Cargar más evaluaciones'}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
