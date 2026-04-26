/**
 * D3FeatureImportance — Barras horizontales de importancia de features (XAI).
 *
 * Muestra la contribución de cada síntoma a la predicción ML.
 * - Coloreado por umbral de contribución (alto/medio/bajo)
 * - Animación de entrada (transición de izquierda a derecha)
 * - Tooltip con descripción clínica del síntoma
 * - Responsive via ResizeObserver
 */
import { useEffect, useRef, useCallback } from 'react'
import * as d3 from 'd3'

const CLINICAL_DESCRIPTIONS = {
  dolor_articular:          'Principal criterio diagnóstico de artritis',
  rigidez_matutina:         'Criterio ACR/EULAR — inflamatoria si ≥60 min',
  duracion_rigidez_minutos: 'Duración de la rigidez matutina en minutos',
  inflamacion_visible:      'Signos objetivos de sinovitis activa',
  calor_local:              'Indica actividad inflamatoria local',
  limitacion_movimiento:    'Refleja daño estructural o inflamación severa',
  num_localizaciones:       'Afectación poliarticular → patrón RA',
  edad:                     'Factor de riesgo — mayor prevalencia AR 30-60 años',
}

const LABEL_MAP = {
  dolor_articular:          'Dolor articular',
  rigidez_matutina:         'Rigidez matutina',
  duracion_rigidez_minutos: 'Duración rigidez',
  inflamacion_visible:      'Inflamación visible',
  calor_local:              'Calor local',
  limitacion_movimiento:    'Lim. movimiento',
  num_localizaciones:       'N.º articulaciones',
  edad:                     'Edad',
}

const MARGIN = { top: 8, right: 60, bottom: 8, left: 140 }
const ROW_HEIGHT = 28

function barColor(value) {
  if (value >= 0.25) return '#dc2626'
  if (value >= 0.12) return '#ea580c'
  return '#2563eb'
}

export function D3FeatureImportance({ features }) {
  const svgRef = useRef(null)
  const wrapperRef = useRef(null)

  const draw = useCallback(() => {
    if (!features || !svgRef.current || !wrapperRef.current) return

    const entries = Object.entries(features)
      .filter(([k]) => k in LABEL_MAP)
      .map(([key, value]) => ({ key, label: LABEL_MAP[key] ?? key, value }))
      .sort((a, b) => b.value - a.value)

    if (!entries.length) return

    const totalWidth = wrapperRef.current.clientWidth
    const innerW = totalWidth - MARGIN.left - MARGIN.right
    const innerH = entries.length * ROW_HEIGHT
    const svgHeight = innerH + MARGIN.top + MARGIN.bottom

    const xScale = d3.scaleLinear()
      .domain([0, Math.max(d3.max(entries, (d) => d.value), 0.01)])
      .range([0, innerW])

    d3.select(svgRef.current).selectAll('*').remove()
    const svg = d3.select(svgRef.current)
      .attr('width', totalWidth).attr('height', svgHeight)

    const g = svg.append('g').attr('transform', `translate(${MARGIN.left},${MARGIN.top})`)

    // ── Grid ──────────────────────────────────────────────────────────────────
    g.append('g').attr('class', 'grid')
      .attr('transform', `translate(0,${innerH})`)
      .call(
        d3.axisBottom(xScale).ticks(4).tickFormat((d) => `${Math.round(d * 100)}%`).tickSize(-innerH)
      )
      .call((a) => a.select('.domain').remove())
      .call((a) => a.selectAll('line').attr('stroke', '#f3f4f6'))
      .call((a) => a.selectAll('text').attr('font-size', 9).attr('fill', '#9ca3af'))

    // ── Tooltip ───────────────────────────────────────────────────────────────
    const tooltip = d3.select(wrapperRef.current)
      .selectAll('.fi-tooltip').data([null]).join('div')
      .attr('class', 'fi-tooltip')
      .style('position', 'absolute').style('pointer-events', 'none')
      .style('background', 'white').style('border', '1px solid #e5e7eb')
      .style('border-radius', '8px').style('padding', '8px 12px')
      .style('font-size', '11px').style('box-shadow', '0 2px 8px rgba(0,0,0,0.1)')
      .style('max-width', '220px').style('opacity', 0).style('z-index', 50)

    // ── Rows ──────────────────────────────────────────────────────────────────
    const rows = g.selectAll('.row').data(entries).join('g')
      .attr('class', 'row')
      .attr('transform', (_, i) => `translate(0,${i * ROW_HEIGHT})`)
      .style('cursor', 'pointer')

    // Background hover
    rows.append('rect')
      .attr('x', -MARGIN.left).attr('width', totalWidth)
      .attr('y', 2).attr('height', ROW_HEIGHT - 4)
      .attr('fill', 'transparent').attr('rx', 4)
      .on('mouseenter', function (event, d) {
        d3.select(this).attr('fill', '#f8fafc')
        const rect = wrapperRef.current.getBoundingClientRect()
        tooltip.style('opacity', 1)
          .style('left', `${event.clientX - rect.left + 12}px`)
          .style('top', `${event.clientY - rect.top - 40}px`)
          .html(`
            <div style="font-weight:600;color:#1e3a5f">${d.label}</div>
            <div style="color:#6b7280;margin-top:2px">${CLINICAL_DESCRIPTIONS[d.key] ?? ''}</div>
            <div style="color:#374151;margin-top:4px">Contribución: <b>${Math.round(d.value * 100)}%</b></div>
          `)
      })
      .on('mousemove', (event) => {
        const rect = wrapperRef.current.getBoundingClientRect()
        tooltip.style('left', `${event.clientX - rect.left + 12}px`)
          .style('top', `${event.clientY - rect.top - 40}px`)
      })
      .on('mouseleave', function () {
        d3.select(this).attr('fill', 'transparent')
        tooltip.style('opacity', 0)
      })

    // Label
    rows.append('text')
      .attr('x', -8).attr('y', ROW_HEIGHT / 2 + 1)
      .attr('text-anchor', 'end').attr('dominant-baseline', 'middle')
      .attr('font-size', 11).attr('fill', '#374151')
      .text((d) => d.label)

    // Bar (animado)
    rows.append('rect')
      .attr('y', 6).attr('height', ROW_HEIGHT - 12).attr('rx', 4)
      .attr('fill', (d) => barColor(d.value))
      .attr('x', 0).attr('width', 0)
      .transition().duration(600).delay((_, i) => i * 40)
      .attr('width', (d) => Math.max(xScale(d.value), 2))

    // Value label
    rows.append('text')
      .attr('y', ROW_HEIGHT / 2 + 1)
      .attr('dominant-baseline', 'middle')
      .attr('font-size', 10).attr('font-weight', '600')
      .attr('fill', (d) => barColor(d.value))
      .attr('x', 0).attr('opacity', 0)
      .transition().duration(600).delay((_, i) => i * 40)
      .attr('x', (d) => xScale(d.value) + 6)
      .attr('opacity', 1)
      .text((d) => `${Math.round(d.value * 100)}%`)
  }, [features])

  useEffect(() => {
    draw()
    const observer = new ResizeObserver(draw)
    if (wrapperRef.current) observer.observe(wrapperRef.current)
    return () => observer.disconnect()
  }, [draw])

  return (
    <div ref={wrapperRef} style={{ position: 'relative', width: '100%' }}>
      <svg ref={svgRef} style={{ display: 'block', overflow: 'visible' }} />
    </div>
  )
}
