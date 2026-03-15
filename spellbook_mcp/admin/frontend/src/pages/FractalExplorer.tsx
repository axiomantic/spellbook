import { useState, useCallback, useRef, useEffect } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useFractalGraphList, useFractalCytoscape } from '../hooks/useFractalGraph'
import { GraphList } from '../components/fractal/GraphList'
import { GraphCanvas } from '../components/fractal/GraphCanvas'
import { GraphControls } from '../components/fractal/GraphControls'
import { NodeDetail } from '../components/fractal/NodeDetail'
import { ChatLogPanel } from '../components/fractal/ChatLogPanel'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { EmptyState } from '../components/shared/EmptyState'

export function FractalExplorer() {
  const { graphId: urlGraphId, nodeId: urlNodeId } = useParams<{
    graphId?: string
    nodeId?: string
  }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const [maxDepth, setMaxDepth] = useState<number | undefined>(undefined)
  const [selectedNode, setSelectedNode] = useState<Record<string, unknown> | null>(null)
  const [graphTrueMaxDepth, setGraphTrueMaxDepth] = useState<number>(0)

  // Derive state from URL params
  const selectedGraphId = urlGraphId || null
  // Check if the current URL ends with /chat
  const showChatLog = window.location.pathname.endsWith('/chat')
  const chatLogNodeId = showChatLog && urlNodeId ? urlNodeId : null

  const { data: graphListData, isLoading: listLoading } = useFractalGraphList()
  const { data: cytoscapeData, isLoading: graphLoading } = useFractalCytoscape(
    selectedGraphId,
    maxDepth
  )

  // When cytoscape data loads and we have a urlNodeId, find and select that node
  const prevCytoscapeDataRef = useRef(cytoscapeData)
  const prevUrlNodeIdRef = useRef(urlNodeId)
  const prevGraphIdRef = useRef(selectedGraphId)

  useEffect(() => {
    if (
      cytoscapeData &&
      urlNodeId &&
      !selectedNode &&
      (cytoscapeData !== prevCytoscapeDataRef.current || urlNodeId !== prevUrlNodeIdRef.current)
    ) {
      const node = cytoscapeData.elements.nodes.find(
        (n) => n.data.id === urlNodeId
      )
      if (node) {
        setSelectedNode(node.data)
      }
    }
    prevCytoscapeDataRef.current = cytoscapeData
    prevUrlNodeIdRef.current = urlNodeId
  }, [cytoscapeData, urlNodeId, selectedNode])

  // Track the true max depth of the graph (only increases, resets on graph change)
  useEffect(() => {
    if (cytoscapeData?.stats.max_depth != null) {
      setGraphTrueMaxDepth((prev) => Math.max(prev, cytoscapeData.stats.max_depth))
    }
  }, [cytoscapeData])

  // Clear selected node and reset true max depth when graph changes
  useEffect(() => {
    if (selectedGraphId !== prevGraphIdRef.current) {
      setSelectedNode(null)
      setGraphTrueMaxDepth(0)
    }
    prevGraphIdRef.current = selectedGraphId
  }, [selectedGraphId])

  // Preserve viewport query params (z, px, py) across navigations
  const viewportQuery = useCallback(() => {
    const z = searchParams.get('z')
    const px = searchParams.get('px')
    const py = searchParams.get('py')
    if (z && px && py) return `?z=${z}&px=${px}&py=${py}`
    return ''
  }, [searchParams])

  const setSelectedGraphId = useCallback((graphId: string | null) => {
    if (graphId) {
      navigate(`/fractal/${graphId}`)
    } else {
      navigate('/fractal')
    }
    setSelectedNode(null)
  }, [navigate])

  const handleNodeClick = useCallback((_nodeId: string, nodeData: Record<string, unknown>) => {
    setSelectedNode(nodeData)
    if (selectedGraphId) {
      navigate(`/fractal/${selectedGraphId}/${_nodeId}${viewportQuery()}`)
    }
  }, [selectedGraphId, navigate, viewportQuery])

  const handleViewChatLog = useCallback(() => {
    if (selectedNode?.id && selectedGraphId) {
      navigate(`/fractal/${selectedGraphId}/${selectedNode.id}/chat${viewportQuery()}`)
    }
  }, [selectedNode, selectedGraphId, navigate, viewportQuery])

  const handleCloseChatLog = useCallback(() => {
    if (selectedGraphId && urlNodeId) {
      navigate(`/fractal/${selectedGraphId}/${urlNodeId}${viewportQuery()}`)
    } else if (selectedGraphId) {
      navigate(`/fractal/${selectedGraphId}${viewportQuery()}`)
    }
  }, [selectedGraphId, urlNodeId, navigate, viewportQuery])

  const handleCloseNodeDetail = useCallback(() => {
    setSelectedNode(null)
    if (selectedGraphId) {
      navigate(`/fractal/${selectedGraphId}${viewportQuery()}`)
    }
  }, [selectedGraphId, navigate, viewportQuery])

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
              {selectedNode && !chatLogNodeId && (
                <NodeDetail
                  nodeData={selectedNode}
                  onClose={handleCloseNodeDetail}
                  onViewChatLog={handleViewChatLog}
                />
              )}
              {chatLogNodeId && selectedGraphId && (
                <ChatLogPanel
                  graphId={selectedGraphId}
                  nodeId={chatLogNodeId}
                  nodeLabel={selectedNode ? String(selectedNode.label || '') : undefined}
                  onClose={handleCloseChatLog}
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
                graphMaxDepth={graphTrueMaxDepth}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
