import clsx from 'clsx'

const TREND_CONFIG = {
  up:     { label: '▲', cls: 'text-red-500' },
  down:   { label: '▼', cls: 'text-green-500' },
  stable: { label: '→', cls: 'text-slate-400' },
}

export function KPICard({ icon, label, value, subvalue, trendDirection, trendLabel, accentColor }) {
  const trend = TREND_CONFIG[trendDirection]

  return (
    <div className="card flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span
          className="w-10 h-10 rounded-xl flex items-center justify-center text-xl"
          style={{ background: `${accentColor}18` }}
        >
          {icon}
        </span>
        {trend && (
          <span className={clsx('text-xs font-semibold flex items-center gap-1', trend.cls)}>
            <span>{trend.label}</span>
            <span>{trendLabel}</span>
          </span>
        )}
      </div>

      <div>
        <p className="text-2xl font-bold text-slate-800 font-display leading-none">{value}</p>
        {subvalue && <p className="text-xs text-slate-400 mt-1">{subvalue}</p>}
      </div>

      <p className="text-sm text-slate-500">{label}</p>
    </div>
  )
}
