import type { DashboardMetrics } from '../api/client'

type Props = { metrics: DashboardMetrics | null }

export function MetricCards({ metrics }: Props) {
  if (!metrics) return null
  const trend = metrics.trend_points || []
  const trendCounts = trend.map((p) => p.count)
  const maxCount = Math.max(1, ...trendCounts)

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div className="bg-gray-100 rounded-lg p-4 border-l-4 border-red-500">
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Critical Alerts</div>
        <div className="text-2xl font-bold text-red-600 mt-1">{metrics.critical_alerts_count}</div>
      </div>
      <div className="bg-gray-100 rounded-lg p-4 border-l-4 border-amber-500">
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Recent Events</div>
        <div className="text-2xl font-bold text-amber-600 mt-1">{metrics.recent_events_count}</div>
      </div>
      <div className="bg-gray-100 rounded-lg p-4 border-l-4 border-green-500">
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Historical Trends</div>
        <div className="mt-2 flex items-end gap-0.5 h-8">
          {trendCounts.map((c, i) => (
            <div
              key={i}
              className="flex-1 bg-green-500 rounded-t min-w-[4px]"
              style={{ height: `${(c / maxCount) * 100}%` }}
              title={`${c}`}
            />
          ))}
        </div>
        <div className="text-xs text-gray-500 mt-1">Rule detections</div>
      </div>
      <div className="bg-gray-100 rounded-lg p-4 border-l-4 border-green-500">
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Agent Status</div>
        <div className="text-xl font-bold text-green-600 mt-1">{metrics.agent_status}</div>
      </div>
    </div>
  )
}
