import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { Dashboard } from './pages/Dashboard'
import { LoginPage } from './pages/Login'
import { MailboxFiltersPage } from './pages/MailboxFilters'
import { IngestLogsPage } from './pages/IngestLogs'
import { FilterScanLogPage } from './pages/FilterScanLog'
import { me, logout } from './api/client'

function Placeholder({ name }: { name: string }) {
  return (
    <div className="p-8 text-gray-500">
      <h2 className="text-xl font-semibold text-gray-700">{name}</h2>
      <p className="mt-2">This section is not implemented in this demo.</p>
    </div>
  )
}

export default function App() {
  const [user, setUser] = useState<{ username: string; role: string } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    me()
      .then((u) => setUser(u))
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  const doLogout = async () => {
    await logout()
    setUser(null)
  }

  if (loading) {
    return <div className="min-h-screen bg-gray-50" />
  }

  return (
    <BrowserRouter>
      {!user ? (
        <Routes>
          <Route path="/login" element={<LoginPage onLoggedIn={(u) => { setUser(u); window.location.href = '/' }} />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      ) : (
      <div className="flex min-h-screen bg-gray-50">
        <Sidebar />
        <main className="flex-1 flex flex-col">
          <header className="bg-teal-600 text-white px-8 py-4 flex justify-between items-center">
            <div className="flex items-center gap-3">
              <img src="/wasp-logo.png" alt="WASP" className="h-8 w-auto object-contain" />
              <h1 className="text-lg font-semibold">WASP – Workspace Account Security Patrol</h1>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <span>{user.username} ({user.role})</span>
              <button type="button" onClick={doLogout} className="bg-teal-700 px-3 py-1 rounded">Logout</button>
            </div>
          </header>
          <div className="flex-1 p-8">
            <Routes>
              <Route path="/" element={<Dashboard user={user} />} />
              <Route path="/mailbox-filters" element={<MailboxFiltersPage user={user} />} />
              <Route path="/filter-scan-log" element={<FilterScanLogPage user={user} />} />
              <Route path="/logs/ingest" element={<IngestLogsPage user={user} />} />
              <Route path="/account-rules" element={<Placeholder name="Account Rules" />} />
              <Route path="/audit-logs" element={<Placeholder name="Audit Logs" />} />
              <Route path="/settings" element={<Placeholder name="Settings" />} />
              <Route path="/login" element={<Navigate to="/" replace />} />
            </Routes>
          </div>
        </main>
      </div>
      )}
    </BrowserRouter>
  )
}
