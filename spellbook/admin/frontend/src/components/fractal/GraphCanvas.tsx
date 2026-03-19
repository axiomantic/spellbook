import { useEffect, useRef, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import cytoscape, { Core, NodeSingular } from 'cytoscape'
import type { CytoscapeResponse } from '../../api/types'

// Status-to-color mapping
const STATUS_COLORS: Record<string, string> = {
  open: '#06b6d4',       // cyan
  claimed: '#f59e0b',    // amber
  answered: '#22c55e',   // green
  synthesized: '#4ade80', // bright green
  saturated: '#6b7280',  // gray/dim
  error: '#ef4444',      // red
}

interface GraphCanvasProps {
  data: CytoscapeResponse | undefined
  onNodeClick?: (nodeId: string, nodeData: Record<string, unknown>) => void
  className?: string
}

function parseViewport(searchParams: URLSearchParams) {
  const zoom = searchParams.get('z')
  const panX = searchParams.get('px')
  const panY = searchParams.get('py')
  if (zoom && panX && panY) {
    return { zoom: parseFloat(zoom), pan: { x: parseFloat(panX), y: parseFloat(panY) } }
  }
  return null
}

export function GraphCanvas({ data, onNodeClick, className = '' }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const onNodeClickRef = useRef(onNodeClick)
  const [searchParams, setSearchParams] = useSearchParams()

  // Keep callback ref current without triggering re-init
  useEffect(() => {
    onNodeClickRef.current = onNodeClick
  }, [onNodeClick])

  // Persist viewport to URL query params on zoom/pan
  const syncViewportToUrl = useCallback((cy: Core) => {
    const zoom = cy.zoom()
    const pan = cy.pan()
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('z', zoom.toFixed(3))
      next.set('px', Math.round(pan.x).toString())
      next.set('py', Math.round(pan.y).toString())
      return next
    }, { replace: true })
  }, [setSearchParams])

  const initCytoscape = useCallback(() => {
    if (!containerRef.current || !data) return

    // Destroy previous instance
    if (cyRef.current) {
      cyRef.current.destroy()
    }

    const savedViewport = parseViewport(searchParams)

    const cy = cytoscape({
      container: containerRef.current,
      elements: [
        ...data.elements.nodes.map((n) => ({
          group: 'nodes' as const,
          data: n.data,
          classes: n.classes,
        })),
        ...data.elements.edges.map((e) => ({
          group: 'edges' as const,
          data: e.data,
          classes: e.classes,
        })),
      ],
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'text-wrap': 'wrap' as const,
            'text-max-width': '160px',
            'font-size': '12px',
            'font-family': 'ui-monospace, monospace',
            color: '#e2e8f0',
            'text-valign': 'center' as const,
            'text-halign': 'center' as const,
            'background-color': '#1e293b',
            'border-width': 2,
            width: 140,
            height: 60,
            padding: '14px',
            shape: 'round-rectangle',
          },
        },
        // Question nodes: ellipse, slightly larger
        {
          selector: 'node.question',
          style: {
            shape: 'ellipse',
            width: 160,
            height: 70,
            padding: '16px',
          },
        },
        // Answer nodes: rectangle
        {
          selector: 'node.answer',
          style: {
            shape: 'round-rectangle',
            width: 140,
            height: 60,
          },
        },
        // Status-based border colors
        ...Object.entries(STATUS_COLORS).map(([status, color]) => ({
          selector: `node.${status}`,
          style: { 'border-color': color },
        })),
        // Edge base style
        {
          selector: 'edge',
          style: {
            width: 1,
            'line-color': '#475569',
            'target-arrow-color': '#475569',
            'target-arrow-shape': 'triangle' as const,
            'curve-style': 'bezier' as const,
            'arrow-scale': 0.6,
          },
        },
        // Convergence edges
        {
          selector: 'edge.convergence',
          style: {
            'line-color': '#06b6d4',
            'target-arrow-color': '#06b6d4',
            'line-style': 'dashed' as const,
          },
        },
        // Contradiction edges
        {
          selector: 'edge.contradiction',
          style: {
            'line-color': '#ef4444',
            'target-arrow-color': '#ef4444',
            'line-style': 'dashed' as const,
          },
        },
        // Selected node
        {
          selector: 'node:selected',
          style: {
            'border-width': 3,
            'border-color': '#22c55e',
            'background-color': '#334155',
          },
        },
      ],
      layout: savedViewport
        ? { name: 'preset' }
        : {
            name: 'breadthfirst',
            directed: true,
            spacingFactor: 1.5,
            roots: data.elements.nodes
              .filter((n) => !n.data.parent_id)
              .map((n) => n.data.id as string),
          },
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
    })

    // If we have saved viewport params but used preset layout (no positions),
    // run breadthfirst first then apply saved viewport
    if (savedViewport) {
      cy.layout({
        name: 'breadthfirst',
        directed: true,
        spacingFactor: 1.5,
        roots: data.elements.nodes
          .filter((n) => !n.data.parent_id)
          .map((n) => n.data.id as string),
      }).run()
      cy.zoom(savedViewport.zoom)
      cy.pan(savedViewport.pan)
    }

    // Node click handler uses ref so it doesn't cause re-init
    cy.on('tap', 'node', (evt) => {
      const node = evt.target as NodeSingular
      onNodeClickRef.current?.(node.id(), node.data())
    })

    // Pointer cursor on node hover
    cy.on('mouseover', 'node', () => {
      if (containerRef.current) containerRef.current.style.cursor = 'pointer'
    })
    cy.on('mouseout', 'node', () => {
      if (containerRef.current) containerRef.current.style.cursor = ''
    })

    // Debounced viewport sync to URL
    let viewportTimer: ReturnType<typeof setTimeout> | null = null
    const handleViewportChange = () => {
      if (viewportTimer) clearTimeout(viewportTimer)
      viewportTimer = setTimeout(() => syncViewportToUrl(cy), 300)
    }
    cy.on('zoom pan', handleViewportChange)

    cyRef.current = cy
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, syncViewportToUrl])
  // Note: searchParams intentionally excluded - we only read initial values on init

  useEffect(() => {
    initCytoscape()
    return () => {
      if (cyRef.current) {
        cyRef.current.destroy()
        cyRef.current = null
      }
    }
  }, [initCytoscape])

  return (
    <div
      ref={containerRef}
      className={`w-full h-full min-h-[400px] bg-bg-primary ${className}`}
    />
  )
}
