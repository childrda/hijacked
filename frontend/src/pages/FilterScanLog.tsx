import { useEffect, useState } from 'react'
import { getFilterScanLog, type FilterScanLogRow, type AuthUser } from '../api/client'
import { Link } from 'react-router-dom'

type Props = { user: AuthUser }

export function FilterScanLogPage({ user: _user }: Props) {
  const [rows, setRows] = useState<FilterScanLogRow[]>([])
  const [loading, setLoading] = useState(true)
  const [userFilter, setUserFilter] = useState('')

  const load = () => {
    setLoading(true)
    getFilterScanLog({ user_email: userFilter || undefined, limit: 200 })
      .then(setRows)
      .catch(() => setRows([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleApply = () => { load() }

  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-800 mb-2">Filter scan log</h2>
      <p className="text-sm text-gray-600 mb-4">
        Log of each Gmail filter scan run: when we ran a scan and what we got (count, success/error). This is separate from the current filter state shown on{' '}
        <Link to="/mailbox-filters" className="text-teal-600 hover:underline">Mailbox Filters</Link>.
      </p>

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <input
          type="text"
          placeholder="Filter by user email"
          value={userFilter}
          onChange={(e) => setUserFilter(e.target.value)}
          className="border rounded px-2 py-1 text-sm w-48"
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
                <th className="text-left p-2">User</th>
                <th className="text-left p-2">Scanned at</th>
                <th className="text-left p-2">Filters count</th>
                <th className="text-left p-2">Success</th>
                <th className="text-left p-2">Error</th>
                <th className="text-left p-2">Created</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t">
                  <td className="p-2">{r.user_email}</td>
                  <td className="p-2 text-gray-600">{r.scanned_at ? new Date(r.scanned_at).toLocaleString() : '—'}</td>
                  <td className="p-2">{r.filters_count}</td>
                  <td className="p-2">
                    {r.success ? (
                      <span className="text-green-600">Yes</span>
                    ) : (
                      <span className="text-red-600">No</span>
                    )}
                  </td>
                  <td className="p-2 max-w-xs truncate text-red-600" title={r.error_message ?? ''}>{r.error_message || '—'}</td>
                  <td className="p-2 text-gray-500">{r.created_at ? new Date(r.created_at).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && (
            <p className="p-4 text-gray-500 text-center">No scan log entries yet. Run a rescan from Mailbox Filters or wait for scheduled scans.</p>
          )}
        </div>
      )}
    </div>
  )
}
