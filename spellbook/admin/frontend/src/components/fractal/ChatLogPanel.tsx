import { useState, useEffect, useRef } from 'react'
import { useChatLog } from '../../hooks/useFractalGraph'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import type { ChatLogMessage } from '../../api/types'

interface ChatLogPanelProps {
  graphId: string
  nodeId: string
  nodeLabel?: string
  onClose: () => void
}

const MAX_COLLAPSED_LENGTH = 500

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return ts
  }
}

const ROLE_STYLES: Record<string, { label: string; borderColor: string; textColor: string }> = {
  user: { label: 'User', borderColor: 'border-accent-cyan', textColor: 'text-accent-cyan' },
  assistant: { label: 'Assistant', borderColor: 'border-accent-green', textColor: 'text-accent-green' },
  thinking: { label: 'Thinking', borderColor: 'border-accent-amber', textColor: 'text-accent-amber' },
  tool_use: { label: 'Tool', borderColor: 'border-text-dim', textColor: 'text-text-dim' },
  tool_result: { label: 'Result', borderColor: 'border-text-dim', textColor: 'text-text-dim' },
}

function MessageBubble({ message }: { message: ChatLogMessage }) {
  const [expanded, setExpanded] = useState(false)
  const isLong = message.content.length > MAX_COLLAPSED_LENGTH
  const displayContent = isLong && !expanded
    ? message.content.slice(0, MAX_COLLAPSED_LENGTH) + '...'
    : message.content

  const style = ROLE_STYLES[message.role] || ROLE_STYLES.assistant

  // Tool use messages are compact
  if (message.role === 'tool_use') {
    return (
      <div className="flex items-center gap-2 py-0.5">
        <span className={`inline-block px-1.5 py-0 border font-mono text-[10px] uppercase tracking-widest ${style.textColor} ${style.borderColor}`}>
          {style.label}
        </span>
        <span className="font-mono text-xs text-text-secondary">
          {message.content}
        </span>
        <span className="font-mono text-[10px] text-text-dim">
          {formatTimestamp(message.timestamp)}
        </span>
      </div>
    )
  }

  // Tool result messages are compact with truncated content
  if (message.role === 'tool_result') {
    return (
      <div className="space-y-0.5">
        <div className="flex items-center gap-2">
          <span className={`inline-block px-1.5 py-0 border font-mono text-[10px] uppercase tracking-widest ${style.textColor} ${style.borderColor}`}>
            {style.label}
          </span>
          <span className="font-mono text-[10px] text-text-dim">
            {formatTimestamp(message.timestamp)}
          </span>
        </div>
        <div className="font-mono text-[11px] text-text-dim whitespace-pre-wrap bg-bg-primary p-2 border border-bg-border leading-relaxed max-h-24 overflow-y-hidden hover:overflow-y-auto">
          {displayContent}
        </div>
        {isLong && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="font-mono text-[10px] text-accent-cyan hover:text-text-primary transition-colors"
          >
            {expanded ? '[collapse]' : '[expand]'}
          </button>
        )}
      </div>
    )
  }

  // Thinking blocks have a distinct style
  const isThinking = message.role === 'thinking'

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <span
          className={`inline-block px-2 py-0.5 border font-mono text-xs uppercase tracking-widest ${style.textColor} ${style.borderColor}`}
        >
          {style.label}
        </span>
        <span className="font-mono text-xs text-text-dim">
          {formatTimestamp(message.timestamp)}
        </span>
      </div>
      <div className={`font-mono text-xs whitespace-pre-wrap p-3 border leading-relaxed ${
        isThinking
          ? 'text-text-dim bg-bg-primary border-bg-border italic'
          : 'text-text-primary bg-bg-primary border-bg-border'
      }`}>
        {displayContent}
      </div>
      {isLong && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="font-mono text-xs text-accent-cyan hover:text-text-primary transition-colors"
        >
          {expanded ? '[collapse]' : '[expand]'}
        </button>
      )}
    </div>
  )
}

export function ChatLogPanel({ graphId, nodeId, nodeLabel, onClose }: ChatLogPanelProps) {
  const { data, isLoading, error } = useChatLog(graphId, nodeId)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0
    }
  }, [nodeId])

  return (
    <div className="absolute right-0 top-0 bottom-0 w-[400px] bg-bg-surface border-l border-bg-border flex flex-col z-20">
      {/* Header */}
      <div className="p-4 border-b border-bg-border flex-shrink-0">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-mono text-xs uppercase tracking-widest text-text-secondary">
            // CHAT LOG
          </h3>
          <button
            onClick={onClose}
            className="text-text-dim hover:text-text-primary font-mono text-xs"
          >
            [X]
          </button>
        </div>
        {nodeLabel && (
          <div className="font-mono text-xs text-text-dim truncate">
            {nodeLabel}
          </div>
        )}
      </div>

      {/* Content */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {isLoading ? (
          <LoadingSpinner className="h-32" />
        ) : error ? (
          <div className="font-mono text-xs text-accent-red p-3 border border-accent-red">
            Failed to load chat log: {(error as Error).message}
          </div>
        ) : !data || data.messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="font-mono text-sm text-text-dim mb-2">
              No chat log available
            </div>
            <div className="font-mono text-xs text-text-dim">
              {data?.note || (data?.session_id === null
                ? 'No session ID recorded for this node'
                : 'No messages found in the session log')}
            </div>
          </div>
        ) : (
          <>
            {data.claimed_at && (
              <div className="font-mono text-xs text-text-dim border-b border-bg-border pb-2">
                Session: {data.session_id?.slice(0, 12)}...
                {' | '}
                {data.messages.length} entries
              </div>
            )}
            {data.messages.map((msg, i) => (
              <MessageBubble key={`${msg.timestamp}-${i}`} message={msg} />
            ))}
          </>
        )}
      </div>
    </div>
  )
}
