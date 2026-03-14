import { useEffect, useRef, useCallback } from 'react'
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

// Node type to shape
const TYPE_SHAPES: Record<string, string> = {
  question: 'ellipse',
  answer: 'rectangle',
}

interface GraphCanvasProps {
  data: CytoscapeResponse | undefined
  onNodeClick?: (nodeId: string, nodeData: Record<string, unknown>) => void
  className?: string
}

export function GraphCanvas({ data, onNodeClick, className = '' }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)

  const initCytoscape = useCallback(() => {
    if (!containerRef.current || !data) return

    // Destroy previous instance
    if (cyRef.current) {
      cyRef.current.destroy()
    }

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
            'text-max-width': '120px',
            'font-size': '10px',
            'font-family': 'ui-monospace, monospace',
            color: '#e2e8f0',
            'text-valign': 'center' as const,
            'text-halign': 'center' as const,
            'background-color': '#1e293b',
            'border-width': 2,
            width: 80,
            height: 40,
            padding: '8px',
          },
        },
        // Status-based border colors
        ...Object.entries(STATUS_COLORS).map(([status, color]) => ({
          selector: `node.${status}`,
          style: { 'border-color': color },
        })),
        // Type-based shapes
        ...Object.entries(TYPE_SHAPES).map(([type, shape]) => ({
          selector: `node.${type}`,
          style: { shape: shape as 'ellipse' | 'rectangle' },
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
      layout: {
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

    // Node click handler
    cy.on('tap', 'node', (evt) => {
      const node = evt.target as NodeSingular
      if (onNodeClick) {
        onNodeClick(node.id(), node.data())
      }
    })

    cyRef.current = cy
  }, [data, onNodeClick])

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
