import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  listFilters,
  getFilter,
  approveFilter,
  ignoreFilter,
  blockFilter,
  resetFilterStatus,
  rescanFilters,
  disableAccountByEmail,
  type MailboxFilterRow,
  type AuthUser,
} from '../api/client'

type Props = { user: AuthUser }

export function MailboxFiltersPage({ user }: Props) {
  const [filters, setFilters] = useState<MailboxFilterRow[]>([])
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState<MailboxFilterRow | null>(null)
  const [riskyOnly, setRiskyOnly] = useState(false)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [rescanEmail, setRescanEmail] = useState('')
  const [rescanBusy, setRescanBusy] = useState(false)
  const [disableBusy, setDisableBusy] = useState(false)

  const load = () => {
    setLoading(true)
    listFilters({ risky_only: riskyOnly, status: statusFilter || undefined })
      .then(setFilters)
      .catch(() => setFilters([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [riskyOnly, statusFilter])

  const openDetail = (id: number) => {
    getFilter(id).then(setDetail).catch(() => setDetail(null))
  }

  const updateFilter = (updated: MailboxFilterRow) => {
    setFilters((prev) => prev.map((f) => (f.id === updated.id ? updated : f)))
    if (detail?.id === updated.id) setDetail(updated)
  }

  const handleApprove = (id: number) => {
    approveFilter(id).then(updateFilter).then(() => setDetail(null)).catch(alert)
  }
  const handleIgnore = (id: number) => {
    ignoreFilter(id).then(updateFilter).then(() => setDetail(null)).catch(alert)
  }
  const handleBlock = (id: number) => {
    blockFilter(id).then(updateFilter).then(() => setDetail(null)).catch(alert)
  }
  const handleResetStatus = (id: number) => {
    resetFilterStatus(id).then(updateFilter).then(() => setDetail(null)).catch(alert)
  }

  const handleRescan = () => {
    if (!rescanEmail.trim()) return
    setRescanBusy(true)
    rescanFilters(rescanEmail.trim())
      .then(() => { load(); setRescanEmail('') })
      .catch((e) => alert(e?.message || 'Rescan failed'))
      .finally(() => setRescanBusy(false))
  }

  const handleDisableAccount = (userEmail: string) => {
    if (!userEmail || !window.confirm(`Disable account and revoke sessions for ${userEmail}? This will suspend the user in Google (and AD if configured).`)) return
    setDisableBusy(true)
    disableAccountByEmail(userEmail)
      .then((r) => {
        const actions = r.actions || []
        const a = actions[0] as { message?: string; result?: string; error?: string } | undefined
        const msg = a?.message || (r.mode === 'TAKEN' ? 'Account disabled and sessions revoked.' : 'Action recorded (proposed).')
        if (a?.result === 'FAILED' || a?.error) {
          alert(`Disable failed:\n\n${msg}`)
        } else if (a?.result === 'SKIPPED') {
          alert(`Skipped (e.g. protected list):\n\n${msg}`)
        } else {
          alert(msg)
        }
      })
      .catch((e) => alert(e?.message || 'Failed to disable account'))
      .finally(() => setDisableBusy(false))
  }

  const isResponder = user?.role === 'responder'

  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-800 mb-4">Mailbox Filters</h2>
      <p className="text-sm text-gray-600 mb-4">
        Gmail filter inspection: risky filters (delete, archive, mark read, forward externally, or security-related criteria) are listed. Use &quot;View alerts&quot; to see alerts for that user and take containment actions on the dashboard; responders can Approve/Block here or Disable account to suspend the user and revoke sessions.
      </p>

      <div className="flex flex-wrap items-center gap-4 mb-4">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={riskyOnly}
            onChange={(e) => setRiskyOnly(e.target.checked)}
          />
          Risky only
        </label>
        <label className="flex items-center gap-2 text-sm">
          <span>Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border rounded px-2 py-1 text-sm"
          >
            <option value="">All</option>
            <option value="new">new</option>
            <option value="ignored">ignored</option>
            <option value="approved">approved</option>
            <option value="blocked">blocked</option>
          </select>
        </label>
        {isResponder && (
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="user@domain.com"
              value={rescanEmail}
              onChange={(e) => setRescanEmail(e.target.value)}
              className="border rounded px-2 py-1 text-sm w-48"
            />
            <button
              type="button"
              onClick={handleRescan}
              disabled={rescanBusy}
              className="bg-teal-600 text-white text-sm px-3 py-1 rounded disabled:opacity-60"
            >
              {rescanBusy ? 'Scanning…' : 'Rescan'}
            </button>
          </div>
        )}
      </div>

      {loading ? (
        <p className="text-gray-500">Loading…</p>
      ) : (
        <div className="border rounded overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left p-2">User</th>
                <th className="text-left p-2">Risky</th>
                <th className="text-left p-2">Status</th>
                <th className="text-left p-2">First seen</th>
                <th className="text-left p-2">Last seen</th>
                <th className="text-left p-2">Summary</th>
                <th className="text-left p-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filters.map((f) => (
                <tr key={f.id} className="border-t">
                  <td className="p-2">{f.user_email}</td>
                  <td className="p-2">
                    {f.is_risky ? (
                      <span className="text-red-600 font-medium">Yes</span>
                    ) : (
                      <span className="text-gray-500">No</span>
                    )}
                  </td>
                  <td className="p-2">{f.status}</td>
                  <td className="p-2 text-gray-600">{f.first_seen_at ? new Date(f.first_seen_at).toLocaleString() : '—'}</td>
                  <td className="p-2 text-gray-600">{f.last_seen_at ? new Date(f.last_seen_at).toLocaleString() : '—'}</td>
                  <td className="p-2 max-w-xs truncate">
                    {[f.criteria_json?.query, f.criteria_json?.subject, f.action_json?.forward].filter(Boolean).join(' · ') || '—'}
                  </td>
                  <td className="p-2">
                    <button
                      type="button"
                      onClick={() => openDetail(f.id)}
                      className="text-teal-600 hover:underline mr-2"
                    >
                      Detail
                    </button>
                    <Link
                      to={`/?search=${encodeURIComponent(f.user_email)}`}
                      className="text-teal-600 hover:underline mr-2"
                    >
                      View alerts
                    </Link>
                    {f.status === 'ignored' && isResponder && (
                      <button type="button" onClick={() => handleResetStatus(f.id)} className="text-teal-600 hover:underline mr-2">Un-ignore</button>
                    )}
                    {isResponder && (
                      <>
                        <button type="button" onClick={() => handleApprove(f.id)} className="text-green-600 hover:underline mr-2">Approve</button>
                        <button type="button" onClick={() => handleIgnore(f.id)} className="text-gray-600 hover:underline mr-2">Ignore</button>
                        <button type="button" onClick={() => handleBlock(f.id)} className="text-red-600 hover:underline mr-2">Block</button>
                        <button
                          type="button"
                          onClick={() => handleDisableAccount(f.user_email)}
                          disabled={disableBusy}
                          className="text-red-600 hover:underline font-medium"
                          title="Disable account and revoke sessions"
                        >
                          Disable account
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filters.length === 0 && (
            <p className="p-4 text-gray-500 text-center">No filters found. Enable Gmail filter inspection and add users to FILTER_SCAN_USER_SCOPE.</p>
          )}
        </div>
      )}

      {detail && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-10 p-4" onClick={() => setDetail(null)}>
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-auto p-6" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-2">Filter detail</h3>
            <dl className="grid grid-cols-[auto_1fr] gap-2 text-sm">
              <dt className="text-gray-500">User</dt><dd>{detail.user_email}</dd>
              <dt className="text-gray-500">Gmail ID</dt><dd>{detail.gmail_filter_id}</dd>
              <dt className="text-gray-500">Fingerprint</dt><dd className="font-mono text-xs break-all">{detail.fingerprint}</dd>
              <dt className="text-gray-500">Risky</dt><dd>{detail.is_risky ? 'Yes' : 'No'}</dd>
              <dt className="text-gray-500">Status</dt><dd>{detail.status}</dd>
              <dt className="text-gray-500">Risk reasons</dt><dd>{(detail.risk_reasons_json || []).join(', ') || '—'}</dd>
              <dt className="text-gray-500">Criteria</dt><dd><pre className="bg-gray-50 p-2 rounded text-xs overflow-auto">{JSON.stringify(detail.criteria_json, null, 2)}</pre></dd>
              <dt className="text-gray-500">Action</dt><dd><pre className="bg-gray-50 p-2 rounded text-xs overflow-auto">{JSON.stringify(detail.action_json, null, 2)}</pre></dd>
              <dt className="text-gray-500">Approved by</dt><dd>{detail.approved_by || '—'} {detail.approved_at ? `at ${new Date(detail.approved_at).toLocaleString()}` : ''}</dd>
            </dl>
            <div className="mt-4 flex flex-wrap gap-2 items-center">
              <Link
                to={`/?search=${encodeURIComponent(detail.user_email)}`}
                className="bg-teal-600 text-white px-3 py-1 rounded text-sm hover:bg-teal-700"
                onClick={() => setDetail(null)}
              >
                View alerts for this user
              </Link>
              {detail.status === 'ignored' && user?.role === 'responder' && (
                <button type="button" onClick={() => handleResetStatus(detail.id)} className="bg-teal-600 text-white px-3 py-1 rounded text-sm hover:bg-teal-700">Un-ignore</button>
              )}
              {user?.role === 'responder' && (
                <>
                  <button type="button" onClick={() => handleApprove(detail.id)} className="bg-green-600 text-white px-3 py-1 rounded text-sm">Approve</button>
                  <button type="button" onClick={() => handleIgnore(detail.id)} className="bg-gray-500 text-white px-3 py-1 rounded text-sm">Ignore</button>
                  <button type="button" onClick={() => handleBlock(detail.id)} className="bg-red-600 text-white px-3 py-1 rounded text-sm">Block</button>
                  <button
                    type="button"
                    onClick={() => { handleDisableAccount(detail.user_email); setDetail(null); }}
                    disabled={disableBusy}
                    className="bg-red-700 text-white px-3 py-1 rounded text-sm hover:bg-red-800 disabled:opacity-60"
                    title="Disable account and revoke sessions"
                  >
                    Disable account
                  </button>
                </>
              )}
              <button type="button" onClick={() => setDetail(null)} className="bg-gray-200 px-3 py-1 rounded text-sm">Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
