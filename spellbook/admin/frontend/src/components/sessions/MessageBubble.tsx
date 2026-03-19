import { useState } from 'react'
import type { SessionMessage } from '../../api/types'

function formatTimestamp(ts: string | null): string {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleTimeString()
  } catch {
    return ts
  }
}

interface MessageBubbleProps {
  message: SessionMessage
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const [expanded, setExpanded] = useState(false)

  // Compact summary: collapsed by default
  if (message.is_compact_summary) {
    return (
      <div className="w-full my-2">
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full bg-yellow-900/10 border border-yellow-800/30 px-4 py-2 font-mono text-xs text-yellow-400 flex items-center justify-between hover:bg-yellow-900/20 transition-colors"
        >
          <span className="flex items-center gap-2">
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
              <path fillRule="evenodd" d="M4 4a2 2 0 012-2h8a2 2 0 012 2v12a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 0h8v12H6V4z" clipRule="evenodd" />
            </svg>
            Compacted summary
          </span>
          <span>{expanded ? '\u25B2' : '\u25BC'}</span>
        </button>
        {expanded && (
          <div className="bg-yellow-900/5 border border-t-0 border-yellow-800/20 px-4 py-3 font-mono text-xs text-text-secondary whitespace-pre-wrap max-h-96 overflow-y-auto">
            {message.content}
          </div>
        )}
      </div>
    )
  }

  // Type-based styling
  const typeConfig: Record<string, { align: string; bg: string; accent: string; icon?: string }> = {
    user: {
      align: 'justify-end',
      bg: 'bg-blue-900/20',
      accent: 'border-l-2 border-blue-500',
    },
    assistant: {
      align: 'justify-start',
      bg: 'bg-bg-elevated',
      accent: 'border-l-2 border-text-dim',
    },
    system: {
      align: 'justify-center',
      bg: 'bg-bg-surface',
      accent: 'text-text-dim italic',
      icon: 'info',
    },
    progress: {
      align: 'justify-center',
      bg: 'bg-bg-surface',
      accent: 'text-text-dim',
      icon: 'spinner',
    },
    'custom-title': {
      align: 'justify-center',
      bg: 'bg-accent-green/10',
      accent: 'text-accent-green',
      icon: 'tag',
    },
    'last-prompt': {
      align: 'justify-center',
      bg: 'bg-bg-surface',
      accent: 'text-text-dim',
    },
    'queue-operation': {
      align: 'justify-center',
      bg: 'bg-bg-surface',
      accent: 'text-text-dim text-xs',
    },
    'file-history-snapshot': {
      align: 'justify-center',
      bg: 'bg-bg-surface',
      accent: 'text-text-dim text-xs',
    },
    'pr-link': {
      align: 'justify-center',
      bg: 'bg-bg-surface',
      accent: 'text-text-dim',
      icon: 'link',
    },
    error: {
      align: 'justify-center',
      bg: 'bg-red-900/20',
      accent: 'text-red-400',
      icon: 'warning',
    },
  }

  const config = typeConfig[message.type] || {
    align: 'justify-center',
    bg: 'bg-bg-surface',
    accent: 'text-text-dim text-xs',
  }

  const isConversational = message.type === 'user' || message.type === 'assistant'
  const maxWidth = isConversational ? 'max-w-[75%]' : 'max-w-full'

  return (
    <div className={`flex ${config.align} my-1`}>
      <div className={`${config.bg} ${config.accent} ${maxWidth} px-4 py-2 font-mono text-xs`}>
        <div className="flex items-center justify-between gap-4 mb-1">
          <span className="text-text-dim uppercase text-[10px] tracking-wider">
            {config.icon && <IconFor icon={config.icon} />}
            {message.type}
          </span>
          {message.timestamp && (
            <span className="text-text-dim text-[10px]">
              {formatTimestamp(message.timestamp)}
            </span>
          )}
        </div>
        <div className="text-text-secondary whitespace-pre-wrap break-words">
          {message.content || <span className="text-text-dim">(empty)</span>}
        </div>
        <div className="text-text-dim text-[10px] mt-1">
          Line {message.line_number}
        </div>
      </div>
    </div>
  )
}

function IconFor({ icon }: { icon: string }) {
  const cls = "w-3 h-3 inline-block mr-1 -mt-0.5"
  switch (icon) {
    case 'info':
      return (
        <svg viewBox="0 0 20 20" fill="currentColor" className={cls}>
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
        </svg>
      )
    case 'spinner':
      return (
        <svg viewBox="0 0 20 20" fill="currentColor" className={`${cls} animate-spin`}>
          <path d="M10 3a7 7 0 100 14 7 7 0 000-14zm0 2a5 5 0 110 10 5 5 0 010-10z" opacity="0.25" />
          <path d="M10 3a7 7 0 017 7h-2a5 5 0 00-5-5V3z" />
        </svg>
      )
    case 'tag':
      return (
        <svg viewBox="0 0 20 20" fill="currentColor" className={cls}>
          <path fillRule="evenodd" d="M17.707 9.293a1 1 0 010 1.414l-7 7a1 1 0 01-1.414 0l-7-7A.997.997 0 012 10V5a3 3 0 013-3h5c.256 0 .512.098.707.293l7 7zM5 6a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
        </svg>
      )
    case 'link':
      return (
        <svg viewBox="0 0 20 20" fill="currentColor" className={cls}>
          <path fillRule="evenodd" d="M12.586 4.586a2 2 0 112.828 2.828l-3 3a2 2 0 01-2.828 0 1 1 0 00-1.414 1.414 4 4 0 005.656 0l3-3a4 4 0 00-5.656-5.656l-1.5 1.5a1 1 0 101.414 1.414l1.5-1.5zm-5 5a2 2 0 012.828 0 1 1 0 101.414-1.414 4 4 0 00-5.656 0l-3 3a4 4 0 105.656 5.656l1.5-1.5a1 1 0 10-1.414-1.414l-1.5 1.5a2 2 0 11-2.828-2.828l3-3z" clipRule="evenodd" />
        </svg>
      )
    case 'warning':
      return (
        <svg viewBox="0 0 20 20" fill="currentColor" className={cls}>
          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
      )
    default:
      return null
  }
}
