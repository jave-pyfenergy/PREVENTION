import { useState, useEffect } from 'react'
import { useNavigate, NavLink } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useHistorial } from '../hooks/useEvaluacion'
import { useDashboardStats } from '../hooks/useDashboardStats'
import { KPICard } from '../components/dashboard/KPICard'
import { AlertasPanel } from '../components/dashboard/AlertasPanel'
import { RiskDistributionChart } from '../components/dashboard/RiskDistributionChart'
import { EvaluacionesTable } from '../components/dashboard/EvaluacionesTable'
import { SkeletonDashboard } from '../components/dashboard/SkeletonDashboard'
import { RiesgoChart } from '../components/historial/RiesgoChart'
import clsx from 'clsx'

// ─── Sidebar ──────────────────────────────────────────────────────────────────

function Sidebar({ open, onClose, user, onSignOut }) {
  return (
    <>
      {/* Mobile backdrop */}
      {open && (
        <div
          className="fixed inset-0 bg-black/30 z-20 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={clsx(
          'fixed top-0 left-0 h-full w-60 bg-white border-r border-slate-100 z-30',
          'flex flex-col transition-transform duration-200',
          'lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        {/* Logo */}
        <div className="px-5 py-5 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-primary-800 rounded-xl flex items-center justify-center shrink-0">
              <span className="text-white text-xs font-bold">PA</span>
            </div>
            <div>
              <p className="font-bold text-primary-900 text-sm leading-none">PrevencionApp</p>
              <p className="text-xs text-slate-400 mt-0.5">Panel de control</p>
            </div>
          </div>
        </div>

        {/* Nav items */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          <SidebarItem icon="📊" label="Dashboard" to="/dashboard" onClick={onClose} />
          <SidebarItem icon="➕" label="Nueva evaluación" to="/formulario" onClick={onClose} />
        </nav>

        {/* User block */}
        <div className="px-4 py-4 border-t border-slate-100">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center shrink-0">
              <span className="text-primary-800 text-xs font-bold uppercase">
                {user?.email?.[0] ?? '?'}
              </span>
            </div>
            <p className="text-xs text-slate-500 truncate">{user?.email}</p>
          </div>
          <button
            onClick={onSignOut}
            className="w-full text-left text-xs text-slate-400 hover:text-red-500 transition-colors px-2 py-1.5 rounded-lg hover:bg-red-50"
          >
            Cerrar sesión
          </button>
        </div>
      </aside>
    </>
  )
}

function SidebarItem({ icon, label, to, onClick }) {
  return (
    <NavLink
      to={to}
      onClick={onClick}
      className={({ isActive }) =>
        clsx(
          'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-colors',
          isActive
            ? 'bg-primary-50 text-primary-800 font-semibold'
            : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700',
        )
      }
    >
      <span className="text-base leading-none">{icon}</span>
      {label}
    </NavLink>
  )
}

// ─── Mobile Header ─────────────────────────────────────────────────────────────

function MobileHeader({ onMenuOpen, navigate }) {
  return (
    <header className="lg:hidden sticky top-0 z-10 bg-white border-b border-slate-100 px-4 py-3 flex items-center justify-between">
      <button
        onClick={onMenuOpen}
        className="p-2 rounded-lg hover:bg-slate-100 transition-colors"
        aria-label="Abrir menú"
      >
        <span className="text-slate-600 text-lg leading-none">☰</span>
      </button>
      <div className="flex items-center gap-2">
        <div className="w-6 h-6 bg-primary-800 rounded-md flex items-center justify-center">
          <span className="text-white text-[10px] font-bold">PA</span>
        </div>
        <span className="font-bold text-primary-900 text-sm">PrevencionApp</span>
      </div>
      <button
        onClick={() => navigate('/formulario')}
        className="btn-primary text-xs py-1.5 px-3"
      >
        + Nueva
      </button>
    </header>
  )
}

// ─── Desktop Header ─────────────────────────────────────────────────────────────

function DesktopHeader({ navigate }) {
  return (
    <div className="hidden lg:flex items-center justify-between mb-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-800 font-display">Dashboard</h1>
        <p className="text-slate-400 text-sm mt-0.5">Resumen de tu historial de evaluaciones</p>
      </div>
      <button
        onClick={() => navigate('/formulario')}
        className="btn-primary"
      >
        + Nueva evaluación
      </button>
    </div>
  )
}

// ─── Empty state ───────────────────────────────────────────────────────────────

function EmptyState({ navigate }) {
  return (
    <div className="card text-center py-20 max-w-md mx-auto">
      <div className="text-5xl mb-4">📋</div>
      <h2 className="text-xl font-bold text-slate-700 mb-2">Sin evaluaciones aún</h2>
      <p className="text-slate-400 text-sm mb-6 leading-relaxed">
        Completa tu primera evaluación para comenzar a visualizar tu historial de riesgo.
      </p>
      <button onClick={() => navigate('/formulario')} className="btn-primary">
        Iniciar primera evaluación →
      </button>
    </div>
  )
}

// ─── KPI helpers ──────────────────────────────────────────────────────────────

const NIVEL_ACCENT = {
  bajo:     '#22c55e',
  moderado: '#f59e0b',
  alto:     '#ef4444',
  critico:  '#7c3aed',
}

const NIVEL_LABEL = {
  bajo: 'Bajo', moderado: 'Moderado', alto: 'Alto', critico: 'Crítico',
}

// ─── Main component ────────────────────────────────────────────────────────────

export default function Dashboard() {
  const navigate = useNavigate()
  const { user, signOut } = useAuth()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [page, setPage] = useState(1)
  const [allItems, setAllItems] = useState([])

  const { data: historial, isLoading } = useHistorial({ page, pageSize: 20 })

  // Accumulate items across pages
  useEffect(() => {
    if (!historial?.items) return
    setAllItems((prev) =>
      page === 1 ? historial.items : [...prev, ...historial.items],
    )
  }, [historial, page])

  const combinedHistorial = historial
    ? { ...historial, items: allItems }
    : null

  const stats = useDashboardStats(combinedHistorial)

  const trendDirection =
    !stats ? undefined :
    stats.trend > 0.08  ? 'up' :
    stats.trend < -0.08 ? 'down' :
    'stable'

  const trendLabel =
    trendDirection === 'up'    ? `+${Math.round(stats.trend * 100)}%` :
    trendDirection === 'down'  ? `${Math.round(stats.trend * 100)}%` :
    'Estable'

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        user={user}
        onSignOut={signOut}
      />

      {/* Content area pushed right of sidebar on desktop */}
      <div className="lg:ml-60">
        <MobileHeader
          onMenuOpen={() => setSidebarOpen(true)}
          navigate={navigate}
        />

        <main className="px-4 lg:px-8 py-6 lg:py-8 max-w-6xl mx-auto">
          <DesktopHeader navigate={navigate} />

          {isLoading && allItems.length === 0 ? (
            <SkeletonDashboard />
          ) : !stats ? (
            <EmptyState navigate={navigate} />
          ) : (
            <div className="space-y-6">

              {/* ── KPI Cards ──────────────────────────────────────── */}
              <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <KPICard
                  icon="📋"
                  label="Total evaluaciones"
                  value={stats.total}
                  subvalue={`${stats.withImageCount} con imagen`}
                  accentColor="#0f4c81"
                />
                <KPICard
                  icon="📊"
                  label="Riesgo promedio"
                  value={`${Math.round(stats.avgProbability * 100)}%`}
                  subvalue="últimas evaluaciones"
                  accentColor={NIVEL_ACCENT[stats.highestNivel]}
                />
                <KPICard
                  icon="🔍"
                  label="Última evaluación"
                  value={NIVEL_LABEL[stats.latest.nivel_inflamacion]}
                  subvalue={new Date(stats.latest.fecha).toLocaleDateString('es', {
                    day: 'numeric', month: 'short', year: 'numeric',
                  })}
                  accentColor={NIVEL_ACCENT[stats.latest.nivel_inflamacion]}
                />
                <KPICard
                  icon="📈"
                  label="Tendencia"
                  value={trendDirection === 'stable' ? 'Estable' : trendLabel}
                  subvalue="vs. período anterior"
                  trendDirection={trendDirection}
                  trendLabel=""
                  accentColor={
                    trendDirection === 'up' ? '#ef4444' :
                    trendDirection === 'down' ? '#22c55e' :
                    '#64748b'
                  }
                />
              </section>

              {/* ── Charts row ─────────────────────────────────────── */}
              <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="lg:col-span-2 card">
                  <RiesgoChart evaluaciones={allItems} />
                  {allItems.length < 2 && (
                    <p className="text-center text-slate-400 text-sm py-6">
                      Necesitas al menos 2 evaluaciones para ver la evolución temporal.
                    </p>
                  )}
                </div>
                <RiskDistributionChart data={stats.distributionChartData} />
              </section>

              {/* ── Alerts ─────────────────────────────────────────── */}
              {stats.alerts.length > 0 && (
                <section>
                  <AlertasPanel alerts={stats.alerts} />
                </section>
              )}

              {/* ── Evaluations table ──────────────────────────────── */}
              <section>
                <EvaluacionesTable
                  items={allItems}
                  hasNext={historial?.has_next ?? false}
                  onLoadMore={() => setPage((p) => p + 1)}
                  isLoadingMore={isLoading && page > 1}
                />
              </section>

            </div>
          )}
        </main>
      </div>
    </div>
  )
}
