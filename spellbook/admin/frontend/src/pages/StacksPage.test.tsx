import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'

// Mock the hook used by StacksPage
vi.mock('../hooks/useFocus', () => ({
  useStintStacks: vi.fn(),
}))

import { StacksPage } from './StacksPage'
import { useStintStacks } from '../hooks/useFocus'

const mockUseStintStacks = useStintStacks as Mock

const mockStack = {
  project_path: '/Users/alice/projects/myapp',
  session_id: 'sess-001',
  stack: [
    {
      type: 'skill',
      name: 'develop',
      parent: null,
      purpose: 'Building feature X',
      behavioral_mode: 'tdd',
      entered_at: '2026-03-20T10:00:00Z',
      exited_at: null,
    },
    {
      type: 'subagent',
      name: 'test-runner',
      parent: 'develop',
      purpose: 'Running tests',
      behavioral_mode: 'execute',
      entered_at: '2026-03-20T10:05:00Z',
      exited_at: null,
    },
  ],
  depth: 2,
  updated_at: '2026-03-20T10:05:00Z',
}

function renderStacksPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })

  return render(
    createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(
        MemoryRouter,
        { initialEntries: ['/stacks'] },
        createElement(StacksPage)
      )
    )
  )
}

describe('StacksPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('page layout', () => {
    it('renders with ACTIVE STACKS header segment', () => {
      mockUseStintStacks.mockReturnValue({
        data: [],
        isLoading: false,
      })

      renderStacksPage()

      expect(screen.getByText('ACTIVE STACKS')).toBeInTheDocument()
    })
  })

  describe('loading state', () => {
    it('shows loading spinner when data is loading', () => {
      mockUseStintStacks.mockReturnValue({
        data: undefined,
        isLoading: true,
      })

      const { container } = renderStacksPage()

      // LoadingSpinner renders a div with animate-spin class
      const spinner = container.querySelector('.animate-spin')
      expect(spinner).toBeInTheDocument()
    })
  })

  describe('empty state', () => {
    it('shows empty state when no stacks exist', () => {
      mockUseStintStacks.mockReturnValue({
        data: [],
        isLoading: false,
      })

      renderStacksPage()

      expect(screen.getByText('No active stacks')).toBeInTheDocument()
      expect(
        screen.getByText('No sessions currently have an active stint stack.')
      ).toBeInTheDocument()
    })
  })

  describe('stack cards', () => {
    it('renders a card for each stack showing project path and depth', () => {
      mockUseStintStacks.mockReturnValue({
        data: [mockStack],
        isLoading: false,
      })

      renderStacksPage()

      expect(screen.getByText('projects/myapp')).toBeInTheDocument()
      expect(screen.getByText('depth 2')).toBeInTheDocument()
    })

    it('shows the top stint name and type badge', () => {
      mockUseStintStacks.mockReturnValue({
        data: [mockStack],
        isLoading: false,
      })

      renderStacksPage()

      // Top stint is the last in the array (test-runner)
      expect(screen.getByText('test-runner')).toBeInTheDocument()
      expect(screen.getByText('subagent')).toBeInTheDocument()
    })

    it('shows collapsed state by default with [+] indicator', () => {
      mockUseStintStacks.mockReturnValue({
        data: [mockStack],
        isLoading: false,
      })

      renderStacksPage()

      expect(screen.getByText('[+]')).toBeInTheDocument()
      // Table headers should NOT be visible when collapsed
      expect(screen.queryByText('Name')).not.toBeInTheDocument()
    })

    it('expands to show full stack table on click', async () => {
      const user = userEvent.setup()

      mockUseStintStacks.mockReturnValue({
        data: [mockStack],
        isLoading: false,
      })

      renderStacksPage()

      // Click the card header to expand
      await user.click(screen.getByText('[+]'))

      // Should show [-] when expanded
      expect(screen.getByText('[-]')).toBeInTheDocument()

      // Table headers visible
      expect(screen.getByText('Name')).toBeInTheDocument()
      expect(screen.getByText('Type')).toBeInTheDocument()
      expect(screen.getByText('Mode')).toBeInTheDocument()
      expect(screen.getByText('Entered')).toBeInTheDocument()

      // Both stints shown in the table (reversed order: top of stack first)
      const rows = screen.getAllByRole('row')
      // 1 header row + 2 data rows = 3
      expect(rows).toHaveLength(3)

      // First data row should be test-runner (top of stack, shown first due to reverse)
      const firstDataRow = rows[1]
      expect(within(firstDataRow).getByText('test-runner')).toBeInTheDocument()
      expect(within(firstDataRow).getByText('execute')).toBeInTheDocument()

      // Second data row should be develop (bottom of stack)
      const secondDataRow = rows[2]
      expect(within(secondDataRow).getByText('develop')).toBeInTheDocument()
      expect(within(secondDataRow).getByText('tdd')).toBeInTheDocument()
    })

    it('renders depth gauge with correct color for low depth', () => {
      mockUseStintStacks.mockReturnValue({
        data: [mockStack], // depth 2
        isLoading: false,
      })

      const { container } = renderStacksPage()

      // Depth 2 should use green
      const gauge = container.querySelector('.bg-accent-green')
      expect(gauge).toBeInTheDocument()
    })

    it('renders multiple stack cards', () => {
      const secondStack = {
        ...mockStack,
        project_path: '/Users/alice/projects/other',
        depth: 5,
        stack: [
          {
            type: 'custom',
            name: 'review',
            parent: null,
            purpose: 'Code review',
            behavioral_mode: 'careful',
            entered_at: '2026-03-20T09:00:00Z',
            exited_at: null,
          },
        ],
      }

      mockUseStintStacks.mockReturnValue({
        data: [mockStack, secondStack],
        isLoading: false,
      })

      renderStacksPage()

      expect(screen.getByText('projects/myapp')).toBeInTheDocument()
      expect(screen.getByText('projects/other')).toBeInTheDocument()
      expect(screen.getByText('depth 2')).toBeInTheDocument()
      expect(screen.getByText('depth 5')).toBeInTheDocument()
    })
  })
})
