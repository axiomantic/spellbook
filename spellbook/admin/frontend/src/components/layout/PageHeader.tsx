import { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

export interface PageHeaderSegment {
  label: string
  path?: string
}

interface PageHeaderProps {
  segments: PageHeaderSegment[]
  right?: ReactNode
}

export function PageHeader({ segments, right }: PageHeaderProps) {
  const navigate = useNavigate()

  return (
    <div className="flex items-center justify-between px-6 py-3 border-b border-bg-border">
      <h1 className="font-mono text-xs uppercase tracking-widest text-text-secondary flex items-center gap-0">
        <span className="mr-1">//</span>
        {segments.map((seg, i) => (
          <span key={i} className="flex items-center gap-0 whitespace-nowrap">
            {i > 0 && <span className="mx-1">//</span>}
            {seg.path ? (
              <button
                onClick={() => navigate(seg.path!)}
                className="uppercase tracking-widest hover:text-accent-cyan transition-colors"
              >
                {seg.label}
              </button>
            ) : (
              <span>{seg.label}</span>
            )}
          </span>
        ))}
      </h1>
      {right && <div className="font-mono text-xs text-text-dim">{right}</div>}
    </div>
  )
}
