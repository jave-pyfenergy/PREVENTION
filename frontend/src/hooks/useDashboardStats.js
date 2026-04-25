import { useMemo } from 'react'

const NIVEL_ORDER = { bajo: 0, moderado: 1, alto: 2, critico: 3 }

function calcTrend(items) {
  if (items.length < 2) return 0
  // Items newest-first: compare first half avg vs second half avg (chronological order)
  const sorted = [...items].sort((a, b) => new Date(a.fecha) - new Date(b.fecha))
  const mid = Math.floor(sorted.length / 2)
  const firstHalf = sorted.slice(0, mid)
  const secondHalf = sorted.slice(mid)
  const avg = (arr) => arr.reduce((s, i) => s + i.probabilidad, 0) / arr.length
  return avg(secondHalf) - avg(firstHalf)
}

function buildAlerts(items, trend) {
  const alerts = []
  if (!items.length) return alerts

  const latest = [...items].sort((a, b) => new Date(b.fecha) - new Date(a.fecha))[0]

  if (latest.nivel_inflamacion === 'critico') {
    alerts.push({
      id: 'latest-critico',
      type: 'danger',
      title: 'Riesgo crítico detectado',
      message: 'Tu evaluación más reciente indica riesgo crítico. Consulta un reumatólogo urgentemente.',
      icon: '🚨',
    })
  } else if (latest.nivel_inflamacion === 'alto') {
    alerts.push({
      id: 'latest-alto',
      type: 'warning',
      title: 'Riesgo alto en última evaluación',
      message: 'Se recomienda agendar una consulta médica en los próximos 7 días.',
      icon: '⚠️',
    })
  }

  if (trend > 0.12) {
    alerts.push({
      id: 'trend-up',
      type: 'warning',
      title: 'Tendencia al alza',
      message: `Tu riesgo promedio ha aumentado ${Math.round(trend * 100)} puntos en el período analizado.`,
      icon: '📈',
    })
  } else if (trend < -0.12) {
    alerts.push({
      id: 'trend-down',
      type: 'success',
      title: 'Tendencia positiva',
      message: `Tu riesgo promedio ha disminuido ${Math.round(Math.abs(trend) * 100)} puntos. Sigue con tus hábitos actuales.`,
      icon: '📉',
    })
  }

  const highCount = items.filter((i) => ['alto', 'critico'].includes(i.nivel_inflamacion)).length
  if (highCount >= 3 && !alerts.find((a) => a.id === 'latest-critico')) {
    alerts.push({
      id: 'recurrent-high',
      type: 'info',
      title: 'Episodios recurrentes de riesgo elevado',
      message: `Registras ${highCount} evaluaciones con riesgo alto o crítico. Considera seguimiento médico periódico.`,
      icon: '🔁',
    })
  }

  const withImage = items.filter((i) => i.tiene_imagen).length
  if (items.length >= 3 && withImage === 0) {
    alerts.push({
      id: 'no-image',
      type: 'info',
      title: 'Mejora la precisión del análisis',
      message: 'Añadir fotografías de las articulaciones puede aumentar la confianza del modelo hasta en un 40%.',
      icon: '📷',
    })
  }

  return alerts
}

export function useDashboardStats(historial) {
  return useMemo(() => {
    const items = historial?.items ?? []
    if (!items.length) return null

    const sorted = [...items].sort((a, b) => new Date(b.fecha) - new Date(a.fecha))
    const latest = sorted[0]

    const avgProbability = items.reduce((s, i) => s + i.probabilidad, 0) / items.length

    const distribution = { bajo: 0, moderado: 0, alto: 0, critico: 0 }
    items.forEach((i) => {
      if (distribution[i.nivel_inflamacion] !== undefined) {
        distribution[i.nivel_inflamacion]++
      }
    })

    const trend = calcTrend(items)

    const chartData = [...items]
      .sort((a, b) => new Date(a.fecha) - new Date(b.fecha))
      .map((item) => ({
        fecha: new Date(item.fecha).toLocaleDateString('es', { month: 'short', day: 'numeric' }),
        probabilidad: Math.round(item.probabilidad * 100),
        nivel: item.nivel_inflamacion,
        id: item.evaluacion_id,
      }))

    const distributionChartData = Object.entries(distribution).map(([nivel, count]) => ({
      nivel: nivel.charAt(0).toUpperCase() + nivel.slice(1),
      nivelKey: nivel,
      count,
    }))

    const alerts = buildAlerts(items, trend)

    const highestNivel = items.reduce((max, i) => {
      return NIVEL_ORDER[i.nivel_inflamacion] > NIVEL_ORDER[max] ? i.nivel_inflamacion : max
    }, 'bajo')

    return {
      total: historial.total,
      avgProbability,
      latest,
      trend,
      distribution,
      chartData,
      distributionChartData,
      alerts,
      highestNivel,
      withImageCount: items.filter((i) => i.tiene_imagen).length,
    }
  }, [historial])
}
