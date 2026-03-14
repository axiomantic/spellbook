import { useState, useCallback } from 'react'
import { useFractalGraphList, useFractalCytoscape } from '../hooks/useFractalGraph'
import { GraphList } from '../components/fractal/GraphList'
import { GraphCanvas } from '../components/fractal/GraphCanvas'
import { GraphControls } from '../components/fractal/GraphControls'
import { NodeDetail } from '../components/fractal/NodeDetail'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { EmptyState } from '../components/shared/EmptyState'

export function FractalExplorer() {
  const [selectedGraphId, setSelectedGraphId] = useState<string | null>(null)
  const [maxDepth, setMaxDepth] = useState<number | undefined>(undefined)
  const [selectedNode, setSelectedNode] = useState<Record<string, unknown> | null>(null)

  const { data: graphListData, isLoading: listLoading } = useFractalGraphList()
  const { data: cytoscapeData, isLoading: graphLoading } = useFractalCytoscape(
    selectedGraphId,
    maxDepth
  )

  const handleNodeClick = useCallback((nodeId: string, nodeData: Record<string, unknown>) => {
    setSelectedNode(nodeData)
  }, [])

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-bg-border">
        <h1 className="font-mono text-xs uppercase tracking-widest text-text-secondary">
          // FRACTAL EXPLORER
        </h1>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar: graph list */}
        <div className="w-64 border-r border-bg-border overflow-y-auto p-3 space-y-3">
          <h2 className="font-mono text-xs uppercase tracking-widest text-text-dim">
            // GRAPHS
          </h2>

          {listLoading ? (
            <LoadingSpinner className="h-32" />
          ) : !graphListData?.graphs.length ? (
            <EmptyState
              title="No Graphs"
              message="No fractal graphs have been created yet."
            />
          ) : (
            <GraphList
              graphs={graphListData.graphs}
              selectedId={selectedGraphId}
              onSelect={setSelectedGraphId}
            />
          )}
        </div>

        {/* Main: graph canvas */}
        <div className="flex-1 relative">
          {!selectedGraphId ? (
            <div className="flex items-center justify-center h-full">
              <EmptyState
                title="Select a Graph"
                message="Choose a fractal graph from the list to visualize it."
              />
            </div>
          ) : graphLoading ? (
            <LoadingSpinner className="h-full" />
          ) : cytoscapeData ? (
            <>
              <GraphCanvas
                data={cytoscapeData}
                onNodeClick={handleNodeClick}
              />
              {selectedNode && (
                <NodeDetail
                  nodeData={selectedNode}
                  onClose={() => setSelectedNode(null)}
                />
              )}
            </>
          ) : null}

          {/* Controls overlay */}
          {selectedGraphId && cytoscapeData && (
            <div className="absolute bottom-4 left-4 w-64 z-10">
              <GraphControls
                maxDepth={maxDepth}
                onMaxDepthChange={setMaxDepth}
                stats={cytoscapeData.stats}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
