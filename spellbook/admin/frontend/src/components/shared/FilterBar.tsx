import { createElement } from 'react'

interface FilterOption {
  label: string
  value: string
}

export interface FilterBarProps {
  type: 'chips' | 'select'
  options: FilterOption[]
  value: string
  onChange: (value: string) => void
}

export function FilterBar({ type, options, value, onChange }: FilterBarProps) {
  if (type === 'chips') {
    return createElement('div', { className: 'flex gap-1' },
      ...options.map((option) =>
        createElement('button', {
          key: option.value,
          type: 'button',
          onClick: () => onChange(option.value),
          className: `px-3 py-1 font-mono text-xs uppercase tracking-widest border transition-colors ${
            value === option.value
              ? 'text-accent-green border-accent-green bg-bg-elevated'
              : 'text-text-secondary border-bg-border hover:text-accent-cyan'
          }`,
        }, option.label)
      )
    )
  }

  // select type
  return createElement('select', {
    value,
    onChange: (e: React.ChangeEvent<HTMLSelectElement>) => onChange(e.target.value),
    className: 'bg-bg-surface border border-bg-border px-3 py-1 font-mono text-xs text-text-primary focus:border-accent-green outline-none',
  },
    ...options.map((option) =>
      createElement('option', { key: option.value, value: option.value }, option.label)
    )
  )
}
