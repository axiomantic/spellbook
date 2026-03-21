import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { createElement } from 'react'
import { FilterBar } from './FilterBar'

describe('FilterBar', () => {
  describe('chips type', () => {
    const chipOptions = [
      { label: 'All', value: 'all' },
      { label: 'Error', value: 'error' },
      { label: 'Warning', value: 'warning' },
    ]

    it('renders all chip options as buttons', () => {
      render(createElement(FilterBar, {
        type: 'chips',
        options: chipOptions,
        value: 'all',
        onChange: vi.fn(),
      }))

      const buttons = screen.getAllByRole('button')
      expect(buttons).toHaveLength(3)
      expect(buttons[0].textContent).toBe('All')
      expect(buttons[1].textContent).toBe('Error')
      expect(buttons[2].textContent).toBe('Warning')
    })

    it('applies active styling to the selected chip', () => {
      render(createElement(FilterBar, {
        type: 'chips',
        options: chipOptions,
        value: 'error',
        onChange: vi.fn(),
      }))

      const activeButton = screen.getByRole('button', { name: 'Error' })
      expect(activeButton.className).toContain('text-accent-green')
      expect(activeButton.className).toContain('border-accent-green')
      expect(activeButton.className).toContain('bg-bg-elevated')
    })

    it('applies inactive styling to non-selected chips', () => {
      render(createElement(FilterBar, {
        type: 'chips',
        options: chipOptions,
        value: 'error',
        onChange: vi.fn(),
      }))

      const inactiveButton = screen.getByRole('button', { name: 'All' })
      expect(inactiveButton.className).toContain('text-text-secondary')
      expect(inactiveButton.className).toContain('border-bg-border')
      expect(inactiveButton.className).not.toContain('text-accent-green')
    })

    it('calls onChange with the clicked chip value', async () => {
      const onChange = vi.fn()
      const user = userEvent.setup()

      render(createElement(FilterBar, {
        type: 'chips',
        options: chipOptions,
        value: 'all',
        onChange,
      }))

      await user.click(screen.getByRole('button', { name: 'Warning' }))

      expect(onChange).toHaveBeenCalledTimes(1)
      expect(onChange).toHaveBeenCalledWith('warning')
    })

    it('applies monospace font and uppercase tracking to chips', () => {
      render(createElement(FilterBar, {
        type: 'chips',
        options: chipOptions,
        value: 'all',
        onChange: vi.fn(),
      }))

      const button = screen.getByRole('button', { name: 'All' })
      expect(button.className).toContain('font-mono')
      expect(button.className).toContain('uppercase')
      expect(button.className).toContain('tracking-widest')
    })
  })

  describe('select type', () => {
    const selectOptions = [
      { label: 'All Types', value: '' },
      { label: 'Login', value: 'login' },
      { label: 'Logout', value: 'logout' },
    ]

    it('renders a select element with all options', () => {
      render(createElement(FilterBar, {
        type: 'select',
        options: selectOptions,
        value: '',
        onChange: vi.fn(),
      }))

      screen.getByRole('combobox')
      const options = screen.getAllByRole('option')
      expect(options).toHaveLength(3)
      expect(options[0].textContent).toBe('All Types')
      expect((options[0] as HTMLOptionElement).value).toBe('')
      expect(options[1].textContent).toBe('Login')
      expect((options[1] as HTMLOptionElement).value).toBe('login')
      expect(options[2].textContent).toBe('Logout')
      expect((options[2] as HTMLOptionElement).value).toBe('logout')
    })

    it('selects the correct option based on value prop', () => {
      render(createElement(FilterBar, {
        type: 'select',
        options: selectOptions,
        value: 'login',
        onChange: vi.fn(),
      }))

      const select = screen.getByRole('combobox') as HTMLSelectElement
      expect(select.value).toBe('login')
    })

    it('calls onChange when selection changes', async () => {
      const onChange = vi.fn()
      const user = userEvent.setup()

      render(createElement(FilterBar, {
        type: 'select',
        options: selectOptions,
        value: '',
        onChange,
      }))

      await user.selectOptions(screen.getByRole('combobox'), 'logout')

      expect(onChange).toHaveBeenCalledTimes(1)
      expect(onChange).toHaveBeenCalledWith('logout')
    })

    it('applies monospace font styling to the select', () => {
      render(createElement(FilterBar, {
        type: 'select',
        options: selectOptions,
        value: '',
        onChange: vi.fn(),
      }))

      const select = screen.getByRole('combobox')
      expect(select.className).toContain('font-mono')
    })
  })
})
