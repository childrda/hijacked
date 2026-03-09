import { useState, useMemo } from 'react'
import type { FlaggedRow } from '../api/client'
import { dismissAlert, bulkDismiss, disableAccount, getAlertDetail, updateAlertStatus, updateAlertNotes } from '../api/client'
import { RiskBadge } from './RiskBadge'
import { ConfirmModal } from './ConfirmModal'

function relativeTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  const now = Date.now()
  const diff = Math.floor((now - d.getTime()) / 60000)
  if (diff < 1) return 'Just now'
  if (diff < 60) return `${diff} mins ago`
  const h = Math.floor(diff / 60)
  if (h < 24) return `${h} hours ago`
  return `${Math.floor(h / 24)} days ago`
}

function avatarPlaceholder(email: string): string {
  if (/bot|admin_logins/i.test(email)) return '🤖'
  return email.charAt(0).toUpperCase()
}

type Props = {
  rows: FlaggedRow[]
  loading: boolean
  search: string
  onSearchChange: (v: string) => void
  statusFilter: string
  onStatusFilterChange: (v: string) => void
  refresh: () => void
  user: { username: string; role: string }
}

export function FlaggedTable({ rows, loading, search, onSearchChange, statusFilter, onStatusFilterChange, refresh, user }: Props) {
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [busy, setBusy] = useState(false)
  const [modal, setModal] = useState<'disable-one' | 'disable-bulk' | 'dismiss-bulk' | null>(null)
  const [modalPayload, setModalPayload] = useState<number | number[] | null>(null)
  const [detail, setDetail] = useState<any | null>(null)
  const [notes, setNotes] = useState('')

  const selectAll = useMemo(() => rows.length > 0 && selected.size === rows.length, [rows.length, selected.size])
  const toggleAll = () => {
    if (selectAll) setSelected(new Set())
    else setSelected(new Set(rows.map((r) => r.id)))
  }
  const toggle = (id: number) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }

  const doDismiss = async (ids: number[]) => {
    setBusy(true)
    try {
      await bulkDismiss(ids)
      setSelected(new Set())
      refresh()
      setModal(null)
      setModalPayload(null)
    } finally {
      setBusy(false)
    }
  }

  const doDisable = async (ids: number[]) => {
    setBusy(true)
    try {
      const result = await disableAccount(ids)
      setSelected(new Set())
      refresh()
      setModal(null)
      setModalPayload(null)
      const failed = (result.actions || []).filter((a: any) => a.result === 'FAILED' || a.error)
      if (failed.length > 0) {
        alert(`Disable completed with issues: ${failed.length} failed. Check backend logs (e.g. API permissions, protected list).`)
      } else if (result.mode === 'PROPOSED') {
        alert('Action was recorded only (no changes in Google). Contact admin if this was unexpected.')
      }
    } catch (e) {
      alert((e as Error)?.message || 'Failed to disable account')
    } finally {
      setBusy(false)
    }
  }

  const handleDismissOne = async (id: number) => {
    setBusy(true)
    try {
      await dismissAlert(id)
      refresh()
    } finally {
      setBusy(false)
    }
  }

  const openDetail = async (id: number) => {
    const d = await getAlertDetail(id)
    setDetail(d)
    setNotes(d?.notes || '')
  }

  const canRespond = user.role === 'responder'

  return (
    <>
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <h2 className="text-xl font-bold text-gray-800 px-6 py-4">Flagged Accounts (Last 24 Hours)</h2>
        <div className="px-6 pb-4 flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-sm font-medium text-gray-700 shrink-0">
            <span>Filter by status:</span>
            <select
              value={statusFilter}
              onChange={(e) => onStatusFilterChange(e.target.value)}
              className="border-2 border-gray-400 rounded-lg px-3 py-2 bg-white min-w-[180px] focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
              title="Show Open, Closed, Contained, etc."
            >
              <option value="OPEN">Open (new + triage)</option>
              <option value="NEW">New</option>
              <option value="TRIAGE">Triage</option>
              <option value="CONTAINED">Contained</option>
              <option value="CLOSED">Closed</option>
              <option value="FALSE_POSITIVE">False positive</option>
            </select>
          </label>
          <div className="relative flex-1 min-w-[200px]">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">🔍</span>
            <input
              type="text"
              placeholder="Search"
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
            />
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={selected.size === 0 || busy || !canRespond}
              onClick={() => {
                setModalPayload(Array.from(selected))
                setModal('disable-bulk')
              }}
              className="px-4 py-2 rounded-lg bg-red-600 text-white font-medium uppercase text-sm hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Bulk Disable
            </button>
            <button
              type="button"
              disabled={selected.size === 0 || busy}
              onClick={() => {
                setModalPayload(Array.from(selected))
                setModal('dismiss-bulk')
              }}
              className="px-4 py-2 rounded-lg bg-gray-500 text-white font-medium uppercase text-sm hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Bulk Dismiss
            </button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-y border-gray-200">
                <th className="text-left py-3 px-4 w-10">
                  <input
                    type="checkbox"
                    checked={selectAll}
                    onChange={toggleAll}
                    className="rounded border-gray-300"
                  />
                </th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Username / Email</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Detection Time</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Event Type</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Details</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Risk Level</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Status</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Assigned</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-gray-500">
                    Loading…
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-gray-500">
                    No flagged accounts in the last 24 hours.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <input
                        type="checkbox"
                        checked={selected.has(row.id)}
                        onChange={() => toggle(row.id)}
                        className="rounded border-gray-300"
                      />
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <span className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-gray-600 text-xs">
                          {avatarPlaceholder(row.target_email)}
                        </span>
                        <span className="text-gray-800">{row.target_email}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-gray-600">{relativeTime(row.detection_time)}</td>
                    <td className="py-3 px-4 text-gray-800">{row.event_type}</td>
                    <td className="py-3 px-4 text-gray-600 max-w-xs truncate" title={row.details}>
                      {row.details || '—'}
                    </td>
                    <td className="py-3 px-4">
                      <RiskBadge level={row.risk_level} />
                    </td>
                    <td className="py-3 px-4 text-gray-700">{row.status}</td>
                    <td className="py-3 px-4 text-gray-700">{row.assigned_to || '—'}</td>
                    <td className="py-3 px-4">
                      <div className="flex gap-2">
                        <button
                          type="button"
                          disabled={!canRespond}
                          onClick={() => {
                            setModalPayload(row.id)
                            setModal('disable-one')
                          }}
                          className="px-3 py-1.5 rounded bg-red-600 text-white text-xs font-medium uppercase hover:bg-red-700 disabled:opacity-50"
                        >
                          Disable Account
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDismissOne(row.id)}
                          disabled={busy}
                          className="px-3 py-1.5 rounded bg-gray-500 text-white text-xs font-medium uppercase hover:bg-gray-600 disabled:opacity-50"
                        >
                          Dismiss Alert
                        </button>
                        <button
                          type="button"
                          onClick={() => openDetail(row.id)}
                          className="px-3 py-1.5 rounded bg-teal-600 text-white text-xs font-medium uppercase hover:bg-teal-700"
                        >
                          Details
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <ConfirmModal
        open={modal === 'disable-one'}
        title="Disable account"
        message="Are you sure you want to disable this account and revoke sessions?"
        confirmLabel="Disable Account"
        cancelLabel="Cancel"
        danger
        onConfirm={() => {
          if (typeof modalPayload === 'number') doDisable([modalPayload])
        }}
        onCancel={() => {
          setModal(null)
          setModalPayload(null)
        }}
      />
      <ConfirmModal
        open={modal === 'disable-bulk'}
        title="Bulk disable accounts"
        message={
          Array.isArray(modalPayload)
            ? `Disable ${modalPayload.length} selected account(s) and revoke their sessions?`
            : ''
        }
        confirmLabel="Bulk Disable"
        cancelLabel="Cancel"
        danger
        onConfirm={() => {
          if (Array.isArray(modalPayload)) doDisable(modalPayload)
        }}
        onCancel={() => {
          setModal(null)
          setModalPayload(null)
        }}
      />
      <ConfirmModal
        open={modal === 'dismiss-bulk'}
        title="Bulk dismiss alerts"
        message={
          Array.isArray(modalPayload)
            ? `Dismiss ${modalPayload.length} selected alert(s)?`
            : ''
        }
        confirmLabel="Bulk Dismiss"
        cancelLabel="Cancel"
        danger={false}
        onConfirm={() => {
          if (Array.isArray(modalPayload)) doDismiss(modalPayload)
        }}
        onCancel={() => {
          setModal(null)
          setModalPayload(null)
        }}
      />
      {detail && (
        <div className="fixed inset-0 bg-black/40 z-40 flex justify-end" onClick={() => setDetail(null)}>
          <div className="w-full max-w-2xl h-full bg-white shadow-xl p-6 overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold">Alert #{detail.id} - {detail.target_email}</h3>
            <p className="text-sm text-gray-600 mt-1">Status: {detail.status} | Score: {detail.score} ({detail.risk_level})</p>
            <div className="mt-4">
              <h4 className="font-medium">Evidence & Rule Hits</h4>
              <pre className="text-xs bg-gray-100 p-3 rounded mt-2 overflow-auto">{JSON.stringify(detail.rule_hits, null, 2)}</pre>
            </div>
            <div className="mt-4">
              <h4 className="font-medium">Timeline</h4>
              <pre className="text-xs bg-gray-100 p-3 rounded mt-2 overflow-auto">{JSON.stringify(detail.timeline, null, 2)}</pre>
            </div>
            <div className="mt-4">
              <h4 className="font-medium">Audit Log</h4>
              <pre className="text-xs bg-gray-100 p-3 rounded mt-2 overflow-auto">{JSON.stringify(detail.audit_log, null, 2)}</pre>
            </div>
            <div className="mt-4">
              <h4 className="font-medium">Notes</h4>
              <textarea className="w-full border rounded p-2 text-sm mt-2" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} />
              <div className="flex gap-2 mt-2">
                <button
                  type="button"
                  onClick={async () => {
                    await updateAlertNotes(detail.id, notes)
                    refresh()
                  }}
                  className="px-3 py-1.5 rounded bg-gray-700 text-white text-xs uppercase"
                >
                  Save Notes
                </button>
                {canRespond && (
                  <>
                    <button
                      type="button"
                      onClick={async () => { await updateAlertStatus(detail.id, 'TRIAGE'); setDetail(await getAlertDetail(detail.id)); refresh() }}
                      className="px-3 py-1.5 rounded bg-amber-600 text-white text-xs uppercase"
                    >
                      Mark Triage
                    </button>
                    <button
                      type="button"
                      onClick={async () => { await updateAlertStatus(detail.id, 'CLOSED'); setDetail(await getAlertDetail(detail.id)); refresh() }}
                      className="px-3 py-1.5 rounded bg-gray-600 text-white text-xs uppercase"
                    >
                      Close
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
