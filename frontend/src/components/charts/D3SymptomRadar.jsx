/**
 * D3SymptomRadar — Radar chart de síntomas para segmentación de pacientes.
 *
 * Muestra el perfil de síntomas de la última evaluación en relación
 * al promedio histórico del paciente. Útil para identificar patrones
 * de empeoramiento o mejoría por síntoma individual.
 *
 * Input: features_importantes del ResponsePrediccion (XAI)
 */
import { useEffect, useRef, useCallback } from 'react'
import * as d3 from 'd3'

const SYMPTOM_LABELS = {
  dolor_articular:         'Dolor articular',
  rigidez_matutina:        'Rigidez matutina',
  duracion_rigidez_minutos:'Duración rigidez',
  inflamacion_visible:     'Inflamación visible',
  calor_local:             'Calor local',
  limitacion_movimiento:   'Limitación movimiento',
  num_localizaciones:      'Articulaciones',
  edad:                    'Factor edad',
}

const NUM_TICKS = 4

export function D3SymptomRadar({ featuresActual, featuresBaseline = null, size = 260 }) {
  const svgRef = useRef(null)

  const draw = useCallback(() => {
    if (!featuresActual || !svgRef.current) return

    const features = Object.entries(featuresActual)
      .filter(([k]) => k in SYMPTOM_LABELS)
      .map(([key, value]) => ({ key, label: SYMPTOM_LABELS[key], value: Math.min(value, 1) }))

    if (features.length < 3) return

    const n = features.length
    const cx = size / 2
    const cy = size / 2
    const r = size * 0.36
    const angleStep = (2 * Math.PI) / n

    const rScale = d3.scaleLinear().domain([0, 1]).range([0, r])
    const angle = (i) => i * angleStep - Math.PI / 2

    d3.select(svgRef.current).selectAll('*').remove()
    const svg = d3.select(svgRef.current)
      .attr('width', size).attr('height', size)
      .attr('viewBox', `0 0 ${size} ${size}`)

    const g = svg.append('g').attr('transform', `translate(${cx},${cy})`)

    // ── Grid circles ─────────────────────────────────────────────────────────
    Array.from({ length: NUM_TICKS }, (_, i) => (i + 1) / NUM_TICKS).forEach((tick) => {
      g.append('circle')
        .attr('r', rScale(tick))
        .attr('fill', 'none')
        .attr('stroke', '#e5e7eb')
        .attr('stroke-width', 1)

      g.append('text')
        .attr('x', 4).attr('y', -rScale(tick) + 3)
        .attr('font-size', 8).attr('fill', '#9ca3af')
        .text(`${Math.round(tick * 100)}%`)
    })

    // ── Axis lines ────────────────────────────────────────────────────────────
    features.forEach((_, i) => {
      const a = angle(i)
      g.append('line')
        .attr('x1', 0).attr('y1', 0)
        .attr('x2', r * Math.cos(a)).attr('y2', r * Math.sin(a))
        .attr('stroke', '#e5e7eb').attr('stroke-width', 1)
    })

    // ── Baseline polygon (histórico) ──────────────────────────────────────────
    if (featuresBaseline) {
      const baselinePoints = features.map((d, i) => {
        const val = Math.min(featuresBaseline[d.key] ?? 0, 1)
        const a = angle(i)
        return [rScale(val) * Math.cos(a), rScale(val) * Math.sin(a)]
      })
      g.append('polygon')
        .attr('points', baselinePoints.map((p) => p.join(',')).join(' '))
        .attr('fill', '#e0e7ff').attr('fill-opacity', 0.4)
        .attr('stroke', '#6366f1').attr('stroke-width', 1.5)
        .attr('stroke-dasharray', '3,3')
    }

    // ── Actual polygon ────────────────────────────────────────────────────────
    const points = features.map((d, i) => {
      const a = angle(i)
      return [rScale(d.value) * Math.cos(a), rScale(d.value) * Math.sin(a)]
    })

    g.append('polygon')
      .attr('points', points.map((p) => p.join(',')).join(' '))
      .attr('fill', '#1e3a5f').attr('fill-opacity', 0.2)
      .attr('stroke', '#1e3a5f').attr('stroke-width', 2)

    // ── Dots ──────────────────────────────────────────────────────────────────
    const tooltip = d3.select(svgRef.current.parentNode)
      .selectAll('.radar-tooltip')
      .data([null]).join('div')
      .attr('class', 'radar-tooltip')
      .style('position', 'absolute').style('pointer-events', 'none')
      .style('background', 'white').style('border', '1px solid #e5e7eb')
      .style('border-radius', '6px').style('padding', '6px 10px')
      .style('font-size', '11px').style('box-shadow', '0 2px 8px rgba(0,0,0,0.1)')
      .style('opacity', 0).style('z-index', 50)

    g.selectAll('.rdot')
      .data(features)
      .join('circle')
      .attr('class', 'rdot')
      .attr('cx', (_, i) => points[i][0])
      .attr('cy', (_, i) => points[i][1])
      .attr('r', 4)
      .attr('fill', (d) => d.value > 0.6 ? '#dc2626' : d.value > 0.3 ? '#ea580c' : '#16a34a')
      .attr('stroke', 'white').attr('stroke-width', 1.5)
      .style('cursor', 'pointer')
      .on('mouseenter', function (event, d) {
        const rect = svgRef.current.parentNode.getBoundingClientRect()
        const svgRect = svgRef.current.getBoundingClientRect()
        const i = features.indexOf(d)
        const px = svgRect.left - rect.left + cx + points[i][0]
        const py = svgRect.top - rect.top + cy + points[i][1]
        tooltip.style('opacity', 1)
          .style('left', `${px + 10}px`)
          .style('top', `${py - 30}px`)
          .html(`<b>${d.label}</b><br/><span style="color:#6b7280">Importancia: ${Math.round(d.value * 100)}%</span>`)
        d3.select(this).attr('r', 6)
      })
      .on('mouseleave', function () {
        tooltip.style('opacity', 0)
        d3.select(this).attr('r', 4)
      })

    // ── Labels ────────────────────────────────────────────────────────────────
    features.forEach((d, i) => {
      const a = angle(i)
      const lx = (r + 18) * Math.cos(a)
      const ly = (r + 18) * Math.sin(a)
      g.append('text')
        .attr('x', lx).attr('y', ly)
        .attr('text-anchor', Math.cos(a) > 0.1 ? 'start' : Math.cos(a) < -0.1 ? 'end' : 'middle')
        .attr('dominant-baseline', Math.sin(a) < -0.3 ? 'auto' : 'middle')
        .attr('font-size', 9).attr('fill', '#374151')
        .text(d.label)
    })

    // ── Legend ────────────────────────────────────────────────────────────────
    if (featuresBaseline) {
      const legG = svg.append('g').attr('transform', `translate(8,${size - 24})`)
      ;[
        { color: '#1e3a5f', dash: null, label: 'Evaluación actual' },
        { color: '#6366f1', dash: '3,3', label: 'Promedio histórico' },
      ].forEach(({ color, dash, label }, i) => {
        const lx = i * 130
        legG.append('line').attr('x1', lx).attr('x2', lx + 16).attr('y1', 0).attr('y2', 0)
          .attr('stroke', color).attr('stroke-width', 2).attr('stroke-dasharray', dash)
        legG.append('text').attr('x', lx + 20).attr('y', 4)
          .attr('font-size', 9).attr('fill', '#6b7280').text(label)
      })
    }
  }, [featuresActual, featuresBaseline, size])

  useEffect(() => { draw() }, [draw])

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <svg ref={svgRef} />
    </div>
  )
}
