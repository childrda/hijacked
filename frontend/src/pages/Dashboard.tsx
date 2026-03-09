import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getMetrics, getAlerts } from '../api/client'
import type { DashboardMetrics, FlaggedRow } from '../api/client'
import { MetricCards } from '../components/MetricCards'
import { FlaggedTable } from '../components/FlaggedTable'

export function Dashboard({ user }: { user: { username: string; role: string } }) {
  const [searchParams] = useSearchParams()
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [alerts, setAlerts] = useState<FlaggedRow[]>([])
  const [loadingMetrics, setLoadingMetrics] = useState(true)
  const [loadingAlerts, setLoadingAlerts] = useState(true)
  const [search, setSearch] = useState(() => searchParams.get('search') ?? '')

  const fetchMetrics = async () => {
    setLoadingMetrics(true)
    try {
      const m = await getMetrics('24h')
      setMetrics(m)
    } finally {
      setLoadingMetrics(false)
    }
  }

  const fetchAlerts = async () => {
    setLoadingAlerts(true)
    try {
      const a = await getAlerts({ status: 'OPEN', window: '24h', search: search || undefined })
      setAlerts(a)
    } finally {
      setLoadingAlerts(false)
    }
  }

  useEffect(() => {
    fetchMetrics()
  }, [])

  useEffect(() => {
    fetchAlerts()
  }, [search])

  return (
    <div className="space-y-6">
      {loadingMetrics ? (
        <div className="h-32 bg-gray-100 rounded-lg animate-pulse" />
      ) : (
        <MetricCards metrics={metrics} />
      )}
      <FlaggedTable
        rows={alerts}
        loading={loadingAlerts}
        search={search}
        onSearchChange={setSearch}
        refresh={fetchAlerts}
        user={user}
      />
    </div>
  )
}
