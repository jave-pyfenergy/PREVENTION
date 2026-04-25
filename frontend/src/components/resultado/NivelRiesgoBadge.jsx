/**
 * PrevencionApp — Componente: NivelRiesgoBadge
 * Badge visual del nivel de riesgo con color semántico.
 */
const CONFIG = {
  bajo:     { label: 'Riesgo Bajo',     cls: 'badge-riesgo-bajo',     icon: '✅' },
  moderado: { label: 'Riesgo Moderado', cls: 'badge-riesgo-moderado', icon: '⚠️' },
  alto:     { label: 'Riesgo Alto',     cls: 'badge-riesgo-alto',     icon: '🔴' },
  critico:  { label: 'Riesgo Crítico',  cls: 'badge-riesgo-critico',  icon: '🚨' },
}

export function NivelRiesgoBadge({ nivel, size = 'md' }) {
  const config = CONFIG[nivel] || CONFIG.bajo
  const sizeClass = size === 'lg' ? 'text-base px-5 py-2' : 'text-sm px-3 py-1.5'

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-semibold ${sizeClass} ${config.cls}`}>
      <span>{config.icon}</span>
      {config.label}
    </span>
  )
}
