import { Component, type ReactNode, type ErrorInfo } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[ErrorBoundary]', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback
      return (
        <div className="p-6">
          <div className="bg-bg-surface border border-accent-red p-4">
            <div className="font-mono text-xs uppercase tracking-widest text-accent-red mb-2">
              // RENDER ERROR
            </div>
            <p className="text-text-primary text-sm font-mono mb-2">
              {this.state.error?.message || 'An unexpected error occurred'}
            </p>
            <pre className="text-xs text-text-dim font-mono overflow-auto max-h-40 mt-2 p-2 bg-bg-base border border-bg-border">
              {this.state.error?.stack}
            </pre>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="mt-3 px-3 py-1 border border-accent-green text-accent-green font-mono text-xs uppercase tracking-widest hover:bg-accent-green hover:text-bg-base transition-colors"
            >
              Retry
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
