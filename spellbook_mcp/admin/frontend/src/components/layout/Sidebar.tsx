import { NavLink } from 'react-router-dom'
import { useDashboard } from '../../hooks/useDashboard'

function SpellbookIcon({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Open book */}
      <path
        d="M4 5h6c1.5 0 3 1.2 3 2.8V20c0-1.2-1.2-2.4-2.8-2.4H4V5z"
        fill="currentColor"
        opacity="0.85"
      />
      <path
        d="M20 5h-6c-1.5 0-3 1.2-3 2.8V20c0-1.2 1.2-2.4 2.8-2.4H20V5z"
        fill="currentColor"
        opacity="0.6"
      />
      {/* Small sparkle above book */}
      <path
        d="M12 1.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"
        fill="currentColor"
        opacity="0.7"
      />
    </svg>
  )
}

const navItems = [
  { to: '/', label: '// DASHBOARD' },
  { to: '/memory', label: '// MEMORY' },
  { to: '/security', label: '// SECURITY' },
  { to: '/sessions', label: '// SESSIONS' },
  { to: '/analytics', label: '// ANALYTICS' },
  { to: '/health', label: '// HEALTH' },
  { to: '/events', label: '// EVENTS' },
  { to: '/focus', label: '// FOCUS' },
  { to: '/config', label: '// CONFIG' },
  { to: '/fractal', label: '// FRACTAL' },
]

export function Sidebar() {
  const { data } = useDashboard()
  const version = data?.health?.version

  return (
    <aside className="w-56 border-r border-bg-border bg-bg-surface flex flex-col">
      <div className="p-4 border-b border-bg-border">
        <div className="flex items-center gap-2">
          <SpellbookIcon className="w-6 h-6 text-accent-green" />
          <h1 className="font-mono text-sm uppercase tracking-widest text-accent-green">
            Spellbook
          </h1>
        </div>
        <p className="font-mono text-xs text-text-dim mt-1">Admin Interface</p>
      </div>
      <nav className="flex-1 p-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `block px-3 py-2 my-0.5 font-mono text-xs uppercase tracking-widest transition-colors ${
                isActive
                  ? 'text-accent-green border-l-2 border-accent-green bg-bg-elevated'
                  : 'text-text-secondary hover:text-accent-cyan'
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      {version && (
        <div className="p-4 border-t border-bg-border">
          <p className="font-mono text-xs text-text-dim">v{version}</p>
        </div>
      )}
    </aside>
  )
}
