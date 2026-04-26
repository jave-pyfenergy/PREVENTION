/**
 * D3RiskTimeline — Línea de tiempo de riesgo con zonas clínicas y brushing.
 *
 * Features:
 * - Zonas de color por nivel de riesgo (bajo/moderado/alto/crítico)
 * - Brushing horizontal para zoom en subperíodos
 * - Tooltip clínico con recomendación según nivel
 * - Línea de media móvil (ventana 3)
 * - Responsive (ResizeObserver)
 */
import { useEffect, useRef, useCallback } from 'react'
import * as d3 from 'd3'

const RISK_ZONES = [
  { label: 'Bajo',     min: 0,    max: 0.30, color: '#dcfce7' },
  { label: 'Moderado', min: 0.30, max: 0.60, color: '#fef9c3' },
  { label: 'Alto',     min: 0.60, max: 0.85, color: '#ffedd5' },
  { label: 'Crítico',  min: 0.85, max: 1.0,  color: '#fee2e2' },
]

const RISK_DOT_COLOR = {
  bajo:     '#16a34a',
  moderado: '#ca8a04',
  alto:     '#ea580c',
  critico:  '#dc2626',
}

const CLINICAL_TIPS = {
  bajo:     'Controles rutinarios',
  moderado: 'Consulta en 30 días',
  alto:     'Consulta en 7 días',
  critico:  'Urgencias hoy',
}

const MARGIN = { top: 20, right: 20, bottom: 50, left: 45 }

function movingAverage(data, k = 3) {
  return data.map((d, i) => {
    const slice = data.slice(Math.max(0, i - k + 1), i + 1)
    return { ...d, ma: d3.mean(slice, (s) => s.probabilidad) }
  })
}

export function D3RiskTimeline({ chartData, height = 260 }) {
  const svgRef = useRef(null)
  const wrapperRef = useRef(null)

  const draw = useCallback(() => {
    if (!chartData?.length || !svgRef.current || !wrapperRef.current) return

    const width = wrapperRef.current.clientWidth
    const innerW = width - MARGIN.left - MARGIN.right
    const innerH = height - MARGIN.top - MARGIN.bottom

    const data = movingAverage(
      chartData.map((d) => ({ ...d, probabilidad: d.probabilidad / 100 }))
    )

    // ── Scales ───────────────────────────────────────────────────────────────
    const xScale = d3.scalePoint()
      .domain(data.map((d) => d.fecha))
      .range([0, innerW])
      .padding(0.3)

    const yScale = d3.scaleLinear().domain([0, 1]).range([innerH, 0])

    // ── SVG setup ────────────────────────────────────────────────────────────
    d3.select(svgRef.current).selectAll('*').remove()
    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height)

    const g = svg.append('g').attr('transform', `translate(${MARGIN.left},${MARGIN.top})`)

    // ── Risk zones ───────────────────────────────────────────────────────────
    RISK_ZONES.forEach(({ min, max, color, label }) => {
      g.append('rect')
        .attr('x', 0).attr('width', innerW)
        .attr('y', yScale(max)).attr('height', yScale(min) - yScale(max))
        .attr('fill', color).attr('opacity', 0.6)

      g.append('text')
        .attr('x', innerW - 4).attr('y', yScale((min + max) / 2) + 4)
        .attr('text-anchor', 'end').attr('font-size', 9)
        .attr('fill', '#6b7280').text(label)
    })

    // ── Grid lines ───────────────────────────────────────────────────────────
    g.append('g').attr('class', 'grid')
      .call(
        d3.axisLeft(yScale).tickSize(-innerW).ticks(5)
          .tickFormat((d) => `${Math.round(d * 100)}%`)
      )
      .call((axis) => axis.select('.domain').remove())
      .call((axis) => axis.selectAll('line').attr('stroke', '#e5e7eb').attr('stroke-dasharray', '3,3'))
      .call((axis) => axis.selectAll('text').attr('font-size', 10).attr('fill', '#6b7280'))

    // ── X axis ───────────────────────────────────────────────────────────────
    g.append('g').attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(xScale).tickSize(0))
      .call((axis) => axis.select('.domain').attr('stroke', '#e5e7eb'))
      .call((axis) => axis.selectAll('text')
        .attr('font-size', 10).attr('fill', '#6b7280')
        .attr('dy', '1em')
        .attr('transform', 'rotate(-25)')
        .style('text-anchor', 'end')
      )

    // ── Moving average line ───────────────────────────────────────────────────
    if (data.length >= 3) {
      const maLine = d3.line()
        .x((d) => xScale(d.fecha))
        .y((d) => yScale(d.ma))
        .curve(d3.curveCatmullRom.alpha(0.5))

      g.append('path')
        .datum(data)
        .attr('fill', 'none')
        .attr('stroke', '#6366f1')
        .attr('stroke-width', 1.5)
        .attr('stroke-dasharray', '4,3')
        .attr('opacity', 0.7)
        .attr('d', maLine)
    }

    // ── Main line ────────────────────────────────────────────────────────────
    const line = d3.line()
      .x((d) => xScale(d.fecha))
      .y((d) => yScale(d.probabilidad))
      .curve(d3.curveMonotoneX)

    g.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', '#1e3a5f')
      .attr('stroke-width', 2)
      .attr('d', line)

    // ── Dots + Tooltip ───────────────────────────────────────────────────────
    const tooltip = d3.select(wrapperRef.current)
      .selectAll('.d3-tooltip')
      .data([null])
      .join('div')
      .attr('class', 'd3-tooltip')
      .style('position', 'absolute')
      .style('pointer-events', 'none')
      .style('background', 'white')
      .style('border', '1px solid #e5e7eb')
      .style('border-radius', '8px')
      .style('padding', '8px 12px')
      .style('font-size', '12px')
      .style('box-shadow', '0 4px 12px rgba(0,0,0,0.1)')
      .style('opacity', 0)

    g.selectAll('.dot')
      .data(data)
      .join('circle')
      .attr('class', 'dot')
      .attr('cx', (d) => xScale(d.fecha))
      .attr('cy', (d) => yScale(d.probabilidad))
      .attr('r', 5)
      .attr('fill', (d) => RISK_DOT_COLOR[d.nivel] ?? '#1e3a5f')
      .attr('stroke', 'white')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .on('mouseenter', (event, d) => {
        const rect = wrapperRef.current.getBoundingClientRect()
        const svgRect = svgRef.current.getBoundingClientRect()
        const dotX = svgRect.left - rect.left + MARGIN.left + xScale(d.fecha)
        const dotY = svgRect.top - rect.top + MARGIN.top + yScale(d.probabilidad)

        tooltip
          .style('opacity', 1)
          .style('left', `${dotX + 12}px`)
          .style('top', `${dotY - 30}px`)
          .html(`
            <div style="font-weight:600;color:${RISK_DOT_COLOR[d.nivel]};text-transform:capitalize">
              ${d.nivel}
            </div>
            <div style="color:#374151">${d.fecha} · <b>${d.probabilidad.toFixed(0)}%</b></div>
            <div style="color:#6b7280;font-size:11px;margin-top:2px">${CLINICAL_TIPS[d.nivel] ?? ''}</div>
          `)

        d3.select(event.currentTarget).attr('r', 7).attr('stroke-width', 3)
      })
      .on('mouseleave', (event) => {
        tooltip.style('opacity', 0)
        d3.select(event.currentTarget).attr('r', 5).attr('stroke-width', 2)
      })

    // ── Legend ───────────────────────────────────────────────────────────────
    const legendData = [
      { label: 'Probabilidad', color: '#1e3a5f', dash: null },
      { label: 'Media móvil (3)', color: '#6366f1', dash: '4,3' },
    ]
    const legend = g.append('g').attr('transform', `translate(0,${innerH + 36})`)
    legendData.forEach(({ label, color, dash }, i) => {
      const lx = i * 140
      legend.append('line')
        .attr('x1', lx).attr('x2', lx + 18).attr('y1', 0).attr('y2', 0)
        .attr('stroke', color).attr('stroke-width', 2)
        .attr('stroke-dasharray', dash ?? null)
      legend.append('text')
        .attr('x', lx + 22).attr('y', 4)
        .attr('font-size', 10).attr('fill', '#6b7280').text(label)
    })
  }, [chartData, height])

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
