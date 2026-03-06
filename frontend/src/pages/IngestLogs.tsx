import { useEffect, useState } from 'react'
import { getIngestLogs, type IngestLogRow, type AuthUser } from '../api/client'

type Props = { user: AuthUser }

export function IngestLogsPage({ user }: Props) {
  const [logs, setLogs] = useState<IngestLogRow[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [source, setSource] = useState('')
  const [targetEmail, setTargetEmail] = useState('')
  const [since, setSince] = useState('')

  const load = () => {
    setLoading(true)
    getIngestLogs({
      source: source || undefined,
      target_email: targetEmail || undefined,
      since: since || undefined,
      limit: 200,
    })
      .then(setLogs)
      .catch(() => setLogs([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleApply = () => { load() }

  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-800 mb-2">Google audit logs (ingest)</h2>
      <p className="text-sm text-gray-600 mb-4">
        Raw events we pulled from Google Reports API. Use this to verify exactly what the app is ingesting while testing.
      </p>

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <input
          type="text"
          placeholder="Source (gmail, login, admin…)"
          value={source}
          onChange={(e) => setSource(e.target.value)}
          className="border rounded px-2 py-1 text-sm w-40"
        />
        <input
          type="text"
          placeholder="Target email"
          value={targetEmail}
          onChange={(e) => setTargetEmail(e.target.value)}
          className="border rounded px-2 py-1 text-sm w-48"
        />
        <input
          type="text"
          placeholder="Since (ISO, e.g. 2026-03-01T00:00:00Z)"
          value={since}
          onChange={(e) => setSince(e.target.value)}
          className="border rounded px-2 py-1 text-sm w-56"
        />
        <button
          type="button"
          onClick={handleApply}
          className="bg-teal-600 text-white text-sm px-3 py-1 rounded"
        >
          Apply
        </button>
      </div>

      {loading ? (
        <p className="text-gray-500">Loading…</p>
      ) : (
        <div className="border rounded overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left p-2 w-8" />
                <th className="text-left p-2">Source</th>
                <th className="text-left p-2">Event time</th>
                <th className="text-left p-2">Actor</th>
                <th className="text-left p-2">Target</th>
                <th className="text-left p-2">IP / Geo</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((r) => (
                <tr
                  key={r.id}
                  className={expandedId === r.id ? 'bg-teal-50' : ''}
                >
                  <td
                    className="p-2 cursor-pointer hover:bg-gray-50"
                    onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                  >
                    {expandedId === r.id ? '▼' : '▶'}
                  </td>
                  <td
                    className="p-2 cursor-pointer hover:bg-gray-50"
                    onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                  >
                    {r.source}
                  </td>
                  <td
                    className="p-2 text-gray-600 cursor-pointer hover:bg-gray-50"
                    onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                  >
                    {r.event_time ? new Date(r.event_time).toLocaleString() : '—'}
                  </td>
                  <td
                    className="p-2 truncate max-w-[140px] cursor-pointer hover:bg-gray-50"
                    title={r.actor_email ?? ''}
                    onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                  >
                    {r.actor_email || '—'}
                  </td>
                  <td
                    className="p-2 truncate max-w-[140px] cursor-pointer hover:bg-gray-50"
                    title={r.target_email ?? ''}
                    onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                  >
                    {r.target_email || '—'}
                  </td>
                  <td
                    className="p-2 text-gray-600 cursor-pointer hover:bg-gray-50"
                    onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                  >
                    {[r.ip, r.geo].filter(Boolean).join(' · ') || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {expandedId != null && (() => {
            const r = logs.find((x) => x.id === expandedId)
            if (!r) return null
            return (
              <div className="border-t bg-gray-50 p-4">
                <div className="text-xs">
                  <span className="font-medium text-gray-600">Full payload (payload_json) for event {r.id}:</span>
                  <pre className="mt-1 p-3 bg-white border rounded overflow-auto max-h-64 text-gray-800">
                    {JSON.stringify(r.payload_json ?? {}, null, 2)}
                  </pre>
                </div>
              </div>
            )
          })()}
          {logs.length === 0 && (
            <p className="p-4 text-gray-500 text-center">No ingest logs found. Run the poller to pull data from Google.</p>
          )}
        </div>
      )}
    </div>
  )
}
