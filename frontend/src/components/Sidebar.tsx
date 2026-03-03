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
        <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center text-gray-500 text-lg mb-2" />
        <a href="/api/auth/login" className="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1">
          Log Out <span className="text-xs">→</span>
        </a>
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
