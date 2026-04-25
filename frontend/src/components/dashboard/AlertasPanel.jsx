import clsx from 'clsx'

const TYPE_CONFIG = {
  danger:  { bg: 'bg-red-50',    border: 'border-red-200',    title: 'text-red-800',    text: 'text-red-600'    },
  warning: { bg: 'bg-amber-50',  border: 'border-amber-200',  title: 'text-amber-800',  text: 'text-amber-600'  },
  success: { bg: 'bg-green-50',  border: 'border-green-200',  title: 'text-green-800',  text: 'text-green-600'  },
  info:    { bg: 'bg-blue-50',   border: 'border-blue-200',   title: 'text-blue-800',   text: 'text-blue-600'   },
}

function AlertItem({ alert }) {
  const cfg = TYPE_CONFIG[alert.type] ?? TYPE_CONFIG.info

  return (
    <div className={clsx('flex gap-3 p-3 rounded-xl border', cfg.bg, cfg.border)}>
      <span className="text-xl leading-none mt-0.5 shrink-0">{alert.icon}</span>
      <div>
        <p className={clsx('text-sm font-semibold', cfg.title)}>{alert.title}</p>
        <p className={clsx('text-xs mt-0.5 leading-relaxed', cfg.text)}>{alert.message}</p>
      </div>
    </div>
  )
}

export function AlertasPanel({ alerts }) {
  if (!alerts?.length) {
    return (
      <div className="card">
        <h2 className="font-bold text-slate-800 mb-4">Alertas y recomendaciones</h2>
        <div className="flex items-center gap-3 p-3 rounded-xl bg-green-50 border border-green-200">
          <span className="text-xl">✅</span>
          <p className="text-sm text-green-700">
            Sin alertas activas. Tu perfil de riesgo está bajo control.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-bold text-slate-800">Alertas y recomendaciones</h2>
        <span className="text-xs bg-slate-100 text-slate-500 px-2 py-1 rounded-full">
          {alerts.length} activa{alerts.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div className="space-y-3">
        {alerts.map((a) => <AlertItem key={a.id} alert={a} />)}
      </div>
    </div>
  )
}
