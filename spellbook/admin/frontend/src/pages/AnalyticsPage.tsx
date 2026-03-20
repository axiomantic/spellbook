import { useState } from 'react'
import {
  useToolFrequency,
  useErrorRates,
  useAnalyticsSummary,
} from '../hooks/useAnalytics'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { EmptyState } from '../components/shared/EmptyState'
import { PageLayout } from '../components/layout/PageLayout'
import type { ToolFrequencyItem, ErrorRateItem } from '../api/types'

const PERIODS = [
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
  { value: '90d', label: '90 days' },
  { value: 'all', label: 'All time' },
] as const

function PeriodSelector({
  value,
  onChange,
}: {
  value: string
  onChange: (period: string) => void
}) {
  return (
    <div className="flex gap-1">
      {PERIODS.map((p) => (
        <button
          key={p.value}
          onClick={() => onChange(p.value)}
          className={`px-2 font-mono text-xs uppercase tracking-widest transition-colors ${
            value === p.value
              ? 'text-accent-green'
              : 'text-text-dim hover:text-accent-cyan'
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  )
}

function SummaryCards({
  totalEvents,
  uniqueTools,
  errorRate,
  eventsToday,
}: {
  totalEvents: number
  uniqueTools: number
  errorRate: number
  eventsToday: number
}) {
  const cards = [
    { label: 'Total Calls', value: totalEvents.toLocaleString() },
    { label: 'Unique Tools', value: String(uniqueTools) },
    { label: 'Error Rate', value: `${errorRate.toFixed(2)}%` },
    { label: 'Today', value: eventsToday.toLocaleString() },
  ]

  return (
    <div className="grid grid-cols-4 gap-4 mb-6">
      {cards.map((card) => (
        <div key={card.label} className="card">
          <div className="font-mono text-xs text-text-dim uppercase tracking-widest mb-1">
            {card.label}
          </div>
          <div className="font-mono text-2xl text-text-primary">{card.value}</div>
        </div>
      ))}
    </div>
  )
}

function ToolFrequencyTable({ tools }: { tools: ToolFrequencyItem[] }) {
  const maxCount = Math.max(...tools.map((t) => t.count), 1)

  return (
    <div className="card mb-6">
      <h2 className="font-mono text-xs uppercase tracking-widest text-text-dim mb-4">
        Tool Frequency
      </h2>
      <table className="w-full text-sm">
        <thead className="font-mono text-xs uppercase tracking-widest text-text-dim border-b border-bg-border">
          <tr>
            <th className="px-3 py-2 text-left">Tool</th>
            <th className="px-3 py-2 text-right w-24">Calls</th>
            <th className="px-3 py-2 text-right w-24">Errors</th>
            <th className="px-3 py-2 text-left w-1/3">Distribution</th>
          </tr>
        </thead>
        <tbody>
          {tools.map((tool) => (
            <tr
              key={tool.tool_name}
              className="border-b border-bg-border hover:bg-bg-elevated transition-colors"
            >
              <td className="px-3 py-2 font-mono text-text-primary">
                {tool.tool_name}
              </td>
              <td className="px-3 py-2 font-mono text-text-secondary text-right">
                {tool.count.toLocaleString()}
              </td>
              <td className="px-3 py-2 font-mono text-right">
                <span className={tool.errors > 0 ? 'text-accent-red' : 'text-text-dim'}>
                  {tool.errors}
                </span>
              </td>
              <td className="px-3 py-2">
                <div className="w-full bg-bg-surface h-3 border border-bg-border">
                  <div
                    className="h-full bg-accent-green"
                    style={{ width: `${(tool.count / maxCount) * 100}%` }}
                  />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ErrorRatesTable({ tools }: { tools: ErrorRateItem[] }) {
  return (
    <div className="card">
      <h2 className="font-mono text-xs uppercase tracking-widest text-text-dim mb-4">
        Error Rates by Tool
      </h2>
      {tools.length === 0 ? (
        <p className="font-mono text-xs text-text-dim">No errors in this period.</p>
      ) : (
        <table className="w-full text-sm">
          <thead className="font-mono text-xs uppercase tracking-widest text-text-dim border-b border-bg-border">
            <tr>
              <th className="px-3 py-2 text-left">Tool</th>
              <th className="px-3 py-2 text-right w-24">Total</th>
              <th className="px-3 py-2 text-right w-24">Errors</th>
              <th className="px-3 py-2 text-right w-24">Rate</th>
              <th className="px-3 py-2 text-left w-1/4">Error Bar</th>
            </tr>
          </thead>
          <tbody>
            {tools.map((tool) => (
              <tr
                key={tool.tool_name}
                className="border-b border-bg-border hover:bg-bg-elevated transition-colors"
              >
                <td className="px-3 py-2 font-mono text-text-primary">
                  {tool.tool_name}
                </td>
                <td className="px-3 py-2 font-mono text-text-secondary text-right">
                  {tool.total.toLocaleString()}
                </td>
                <td className="px-3 py-2 font-mono text-accent-red text-right">
                  {tool.errors}
                </td>
                <td className="px-3 py-2 font-mono text-accent-red text-right">
                  {tool.error_rate.toFixed(2)}%
                </td>
                <td className="px-3 py-2">
                  <div className="w-full bg-bg-surface h-3 border border-bg-border">
                    <div
                      className="h-full bg-accent-red"
                      style={{ width: `${Math.min(tool.error_rate, 100)}%` }}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export function AnalyticsPage() {
  const [period, setPeriod] = useState('7d')

  const { data: summary, isLoading: summaryLoading } = useAnalyticsSummary({ period })
  const { data: frequency, isLoading: frequencyLoading } = useToolFrequency({ period })
  const { data: errors, isLoading: errorsLoading } = useErrorRates({ period })

  const isLoading = summaryLoading || frequencyLoading || errorsLoading

  return (
    <PageLayout
      segments={[{ label: 'ANALYTICS' }]}
      headerRight={<PeriodSelector value={period} onChange={setPeriod} />}
    >
      {isLoading && !summary && <LoadingSpinner className="py-16" />}

      {summary && (
        <SummaryCards
          totalEvents={summary.total_events}
          uniqueTools={summary.unique_tools}
          errorRate={summary.error_rate}
          eventsToday={summary.events_today}
        />
      )}

      {frequency && frequency.tools.length === 0 && (
        <EmptyState
          title="No tool calls"
          message="No tool call data for the selected period."
        />
      )}

      {frequency && frequency.tools.length > 0 && (
        <ToolFrequencyTable tools={frequency.tools} />
      )}

      {errors && <ErrorRatesTable tools={errors.tools} />}
    </PageLayout>
  )
}
