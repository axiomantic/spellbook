import { NavLink } from 'react-router-dom'

const navItems = [
  { to: '/', label: '// DASHBOARD' },
  { to: '/memory', label: '// MEMORY' },
  { to: '/security', label: '// SECURITY' },
  { to: '/sessions', label: '// SESSIONS' },
  { to: '/config', label: '// CONFIG' },
  { to: '/fractal', label: '// FRACTAL' },
]

export function Sidebar() {
  return (
    <aside className="w-56 border-r border-bg-border bg-bg-surface flex flex-col">
      <div className="p-4 border-b border-bg-border">
        <h1 className="font-mono text-sm uppercase tracking-widest text-accent-green">
          Spellbook
        </h1>
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
    </aside>
  )
}
