import { useState } from 'react'
import { login } from '../api/client'

type Props = {
  onLoggedIn: (user: { username: string; role: string }) => void
}

export function LoginPage({ onLoggedIn }: Props) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const user = await login(username, password)
      onLoggedIn(user)
    } catch (err) {
      setError('Invalid username or password')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center p-4">
      <form onSubmit={submit} className="bg-white shadow-lg rounded-lg p-6 w-full max-w-sm">
        <h1 className="text-lg font-semibold text-gray-800">Workspace Security Agent Login</h1>
        <div className="mt-4 space-y-3">
          <input
            className="w-full border rounded px-3 py-2"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
          <input
            className="w-full border rounded px-3 py-2"
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="w-full bg-teal-600 text-white rounded px-3 py-2 font-medium disabled:opacity-60"
          >
            {busy ? 'Signing in...' : 'Sign In'}
          </button>
        </div>
      </form>
    </div>
  )
}

