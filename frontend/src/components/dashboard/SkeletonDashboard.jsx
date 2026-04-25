function Bone({ className }) {
  return (
    <div
      className={`bg-slate-200 rounded-lg animate-pulse ${className ?? ''}`}
    />
  )
}

function KPISkeleton() {
  return (
    <div className="card flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <Bone className="w-10 h-10 rounded-xl" />
        <Bone className="w-14 h-4" />
      </div>
      <Bone className="w-20 h-7" />
      <Bone className="w-32 h-4" />
    </div>
  )
}

function ChartSkeleton({ height = 'h-48' }) {
  return (
    <div className="card space-y-3">
      <Bone className="w-40 h-5" />
      <Bone className={`w-full ${height}`} />
    </div>
  )
}

function RowSkeleton() {
  return (
    <div className="card flex items-center gap-4 py-3">
      <Bone className="w-16 h-6 rounded-full" />
      <div className="flex-1 space-y-2">
        <Bone className="w-32 h-4" />
        <Bone className="w-24 h-3" />
      </div>
      <Bone className="w-8 h-4" />
    </div>
  )
}

export function SkeletonDashboard() {
  return (
    <div className="space-y-8">
      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => <KPISkeleton key={i} />)}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <ChartSkeleton height="h-52" />
        </div>
        <ChartSkeleton height="h-52" />
      </div>

      {/* Alerts row */}
      <div className="card space-y-3">
        <Bone className="w-36 h-5" />
        {[...Array(2)].map((_, i) => (
          <div key={i} className="flex gap-3">
            <Bone className="w-8 h-8 rounded-xl shrink-0" />
            <div className="flex-1 space-y-2">
              <Bone className="w-48 h-4" />
              <Bone className="w-full h-3" />
            </div>
          </div>
        ))}
      </div>

      {/* Table rows */}
      <div className="space-y-2">
        {[...Array(5)].map((_, i) => <RowSkeleton key={i} />)}
      </div>
    </div>
  )
}
