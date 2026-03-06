import { Link, useLocation } from 'react-router-dom'

const nav = [
  { to: '/', label: 'Dashboard', icon: '▦' },
  { to: '/account-rules', label: 'Account Rules', icon: '≡' },
  { to: '/audit-logs', label: 'Audit Logs', icon: '▤' },
  { to: '/settings', label: 'Settings', icon: '⚙' },
]

export function Sidebar() {
  const location = useLocation()
  return (
    <aside className="w-56 min-h-screen bg-white border-r border-gray-200 flex flex-col">
      <div className="p-4 border-b border-gray-100">
        <img src="/wasp-logo.png" alt="WASP" className="h-10 w-auto object-contain mb-2" />
        <span className="text-sm text-gray-600 font-medium">WASP</span>
      </div>
      <nav className="flex-1 p-3">
        {nav.map(({ to, label, icon }) => (
          <Link
            key={to}
            to={to}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-gray-700 text-sm ${
              location.pathname === to ? 'bg-gray-100 font-medium' : 'hover:bg-gray-50'
            }`}
          >
            <span className="text-gray-500 w-5 text-center">{icon}</span>
            {label}
          </Link>
        ))}
      </nav>
    </aside>
  )
}
