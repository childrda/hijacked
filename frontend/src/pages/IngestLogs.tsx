import React, { useEffect, useState } from 'react'
import { getIngestLogs, type IngestLogRow, type AuthUser } from '../api/client'

type Props = { user: AuthUser }

function formatRegionState(region: string | null, subdivision: string | null): string {
  if (!region && !subdivision) return '—'
  // subdivision often looks like "US-VA"; show as "VA" or full
  const statePart = subdivision ? (subdivision.includes('-') ? subdivision.split('-').pop() : subdivision) : ''
  if (region && statePart) return `${region} / ${statePart}`
  return region || statePart || '—'
}

function IngestLogDetailRow({ row, colSpan }: { row: IngestLogRow; colSpan: number }) {
  const regionState = formatRegionState(row.region_code, row.subdivision_code)
  const ipDisplay = row.ip_address ?? row.ip ?? '—'
  return (
    <tr className="bg-gray-50 border-t border-gray-200">
      <td colSpan={colSpan} className="p-0 align-top">
        <div className="p-4 text-sm">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-1 mb-3 text-gray-600">
            <span><strong>Event ID:</strong> {row.id}</span>
            <span><strong>Source:</strong> {row.source}</span>
            <span><strong>Time:</strong> {row.event_time ? new Date(row.event_time).toLocaleString() : '—'}</span>
            <span><strong>Actor:</strong> {row.actor_email || '—'}</span>
            <span><strong>Target:</strong> {row.target_email || '—'}</span>
            <span><strong>IP:</strong> {ipDisplay}</span>
            <span><strong>Region / State:</strong> {regionState}</span>
            {row.ip_asn != null && <span><strong>ASN:</strong> {String(row.ip_asn)}</span>}
          </div>
          <div>
            <span className="font-medium text-gray-600">Full payload (payload_json)</span>
            <pre className="mt-1 p-3 bg-white border rounded overflow-auto max-h-64 text-gray-800 font-mono text-xs whitespace-pre-wrap">
              {JSON.stringify(row.payload_json ?? {}, null, 2)}
            </pre>
          </div>
        </div>
      </td>
    </tr>
  )
}

const COLUMN_COUNT = 7

export function IngestLogsPage({ user: _user }: Props) {
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

  const toggleExpand = (id: number) => {
    setExpandedId((prev) => (prev === id ? null : id))
  }

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
                <th className="text-left p-2">IP Address</th>
                <th className="text-left p-2">Region / State</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={COLUMN_COUNT} className="p-4 text-gray-500 text-center">
                    No ingest logs found. Run the poller to pull data from Google.
                  </td>
                </tr>
              ) : (
                logs.map((r) => (
                  <React.Fragment key={r.id}>
                    <tr
                      className={expandedId === r.id ? 'bg-teal-50' : ''}
                    >
                      <td
                        className="p-2 cursor-pointer hover:bg-gray-50 align-middle"
                        onClick={() => toggleExpand(r.id)}
                        title={expandedId === r.id ? 'Collapse' : 'Expand'}
                      >
                        <span className="inline-block text-teal-600 font-bold">{expandedId === r.id ? '▼' : '▶'}</span>
                      </td>
                      <td
                        className="p-2 cursor-pointer hover:bg-gray-50"
                        onClick={() => toggleExpand(r.id)}
                      >
                        {r.source}
                      </td>
                      <td
                        className="p-2 text-gray-600 cursor-pointer hover:bg-gray-50"
                        onClick={() => toggleExpand(r.id)}
                      >
                        {r.event_time ? new Date(r.event_time).toLocaleString() : '—'}
                      </td>
                      <td
                        className="p-2 truncate max-w-[140px] cursor-pointer hover:bg-gray-50"
                        title={r.actor_email ?? ''}
                        onClick={() => toggleExpand(r.id)}
                      >
                        {r.actor_email || '—'}
                      </td>
                      <td
                        className="p-2 truncate max-w-[140px] cursor-pointer hover:bg-gray-50"
                        title={r.target_email ?? ''}
                        onClick={() => toggleExpand(r.id)}
                      >
                        {r.target_email || '—'}
                      </td>
                      <td className="p-2 text-gray-600">
                        {r.ip_address ?? r.ip ?? '—'}
                      </td>
                      <td className="p-2 text-gray-600">
                        {formatRegionState(r.region_code, r.subdivision_code)}
                      </td>
                    </tr>
                    {expandedId === r.id && <IngestLogDetailRow row={r} colSpan={COLUMN_COUNT} />}
                  </React.Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
