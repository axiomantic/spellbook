import { useState, useEffect, useRef, createElement } from 'react'

interface SearchBarProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  debounceMs?: number
}

export function SearchBar({ value, onChange, placeholder = 'Search...', debounceMs = 300 }: SearchBarProps) {
  const [localValue, setLocalValue] = useState(value)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Sync local value when controlled value changes externally
  useEffect(() => {
    setLocalValue(value)
  }, [value])

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const newValue = e.target.value
    setLocalValue(newValue)

    if (timerRef.current) {
      clearTimeout(timerRef.current)
    }

    timerRef.current = setTimeout(() => {
      onChange(newValue)
    }, debounceMs)
  }

  function handleClear() {
    setLocalValue('')
    if (timerRef.current) {
      clearTimeout(timerRef.current)
    }
    onChange('')
  }

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
      }
    }
  }, [])

  return createElement('div', { className: 'relative flex items-center' },
    createElement('input', {
      type: 'text',
      value: localValue,
      onChange: handleChange,
      placeholder,
      className: 'bg-bg-surface border border-bg-border px-3 py-1 font-mono text-xs text-text-primary placeholder:text-text-dim focus:border-accent-green outline-none w-full',
    }),
    value
      ? createElement('button', {
          type: 'button',
          onClick: handleClear,
          'aria-label': 'Clear search',
          className: 'absolute right-1 px-1 font-mono text-xs text-text-dim hover:text-accent-red transition-colors',
        }, '[x]')
      : null,
  )
}
