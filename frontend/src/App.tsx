import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Sidebar } from './components/Sidebar'
import { Dashboard } from './pages/Dashboard'

function Placeholder({ name }: { name: string }) {
  return (
    <div className="p-8 text-gray-500">
      <h2 className="text-xl font-semibold text-gray-700">{name}</h2>
      <p className="mt-2">This section is not implemented in this demo.</p>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-gray-50">
        <Sidebar />
        <main className="flex-1 flex flex-col">
          <header className="bg-teal-600 text-white px-8 py-4">
            <h1 className="text-lg font-semibold">
              Workspace Security Agent - Suspicious Activity Monitor
            </h1>
          </header>
          <div className="flex-1 p-8">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/account-rules" element={<Placeholder name="Account Rules" />} />
              <Route path="/audit-logs" element={<Placeholder name="Audit Logs" />} />
              <Route path="/settings" element={<Placeholder name="Settings" />} />
            </Routes>
          </div>
        </main>
      </div>
    </BrowserRouter>
  )
}
