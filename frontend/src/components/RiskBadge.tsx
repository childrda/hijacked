type Props = { level: string }

const styles: Record<string, string> = {
  CRITICAL: 'bg-red-600 text-white',
  HIGH: 'bg-red-500 text-white',
  MEDIUM: 'bg-orange-500 text-white',
  LOW: 'bg-amber-400 text-white',
}

export function RiskBadge({ level }: Props) {
  const key = (level || 'LOW').toUpperCase()
  const cls = styles[key] || 'bg-gray-400 text-white'
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium uppercase ${cls}`}>
      {key}
    </span>
  )
}
