import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CanvasDecisionContext, useCanvasDecision } from '../CanvasDecisionContext'

function Probe() {
  const { canvasName } = useCanvasDecision()
  return <span>{canvasName}</span>
}

describe('CanvasDecisionContext', () => {
  it('provides canvasName/decision/submit to consumers', () => {
    const value = {
      canvasName: 'plan-x',
      decision: null,
      submit: { mutate: () => {}, status: 'idle' as const, error: null, lastFreeText: null },
      reauthenticate: () => {},
    }
    render(
      <CanvasDecisionContext.Provider value={value}>
        <Probe />
      </CanvasDecisionContext.Provider>,
    )
    expect(screen.getByText('plan-x')).toBeInTheDocument()
  })

  it('useCanvasDecision throws outside provider', () => {
    const Bad = () => {
      useCanvasDecision()
      return null
    }
    expect(() => render(<Bad />)).toThrow(/outside CanvasDecisionProvider/)
  })
})
