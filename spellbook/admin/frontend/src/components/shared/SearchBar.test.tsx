import { render, screen, act, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createElement } from 'react'
import { SearchBar } from './SearchBar'

describe('SearchBar', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders an input with monospace font and border styling', () => {
    render(createElement(SearchBar, { value: '', onChange: vi.fn() }))

    const input = screen.getByRole('textbox')
    expect(input.className).toContain('font-mono')
    expect(input.className).toContain('border-bg-border')
  })

  it('displays the controlled value in the input', () => {
    render(createElement(SearchBar, { value: 'hello', onChange: vi.fn() }))

    const input = screen.getByRole('textbox') as HTMLInputElement
    expect(input.value).toBe('hello')
  })

  it('renders with custom placeholder text', () => {
    render(createElement(SearchBar, { value: '', onChange: vi.fn(), placeholder: 'Search events...' }))

    const input = screen.getByPlaceholderText('Search events...')
    expect(input).toBeInTheDocument()
  })

  it('renders with default placeholder when none provided', () => {
    render(createElement(SearchBar, { value: '', onChange: vi.fn() }))

    const input = screen.getByPlaceholderText('Search...')
    expect(input).toBeInTheDocument()
  })

  it('calls onChange after debounce delay when user types', () => {
    const onChange = vi.fn()

    render(createElement(SearchBar, { value: '', onChange, debounceMs: 300 }))

    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: 'test' } })

    // onChange should not have been called yet (debounce pending)
    expect(onChange).not.toHaveBeenCalled()

    // Advance past the debounce delay
    act(() => { vi.advanceTimersByTime(300) })

    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith('test')
  })

  it('does not show clear button when value is empty', () => {
    render(createElement(SearchBar, { value: '', onChange: vi.fn() }))

    const clearButton = screen.queryByRole('button', { name: /clear/i })
    expect(clearButton).toBeNull()
  })

  it('shows clear button when value is non-empty', () => {
    render(createElement(SearchBar, { value: 'something', onChange: vi.fn() }))

    const clearButton = screen.getByRole('button', { name: /clear/i })
    expect(clearButton).toBeInTheDocument()
  })

  it('calls onChange with empty string when clear button is clicked', () => {
    const onChange = vi.fn()

    render(createElement(SearchBar, { value: 'something', onChange }))

    const clearButton = screen.getByRole('button', { name: /clear/i })
    fireEvent.click(clearButton)

    // Clear should fire immediately, not debounced
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith('')
  })

  it('uses custom debounce delay', () => {
    const onChange = vi.fn()

    render(createElement(SearchBar, { value: '', onChange, debounceMs: 500 }))

    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: 'x' } })

    // At 300ms, should NOT have fired (custom delay is 500)
    act(() => { vi.advanceTimersByTime(300) })
    expect(onChange).not.toHaveBeenCalled()

    // At 500ms total, should fire
    act(() => { vi.advanceTimersByTime(200) })
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith('x')
  })
})
