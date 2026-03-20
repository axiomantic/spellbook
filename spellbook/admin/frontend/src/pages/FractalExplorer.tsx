import { useState, useCallback, useRef, useEffect } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useFractalCytoscape, useFractalGraphDetail } from '../hooks/useFractalGraph'
import { GraphTable } from '../components/fractal/GraphTable'
import { GraphDetailsSidebar } from '../components/fractal/GraphDetailsSidebar'
import { GraphCanvas } from '../components/fractal/GraphCanvas'
import { GraphControls } from '../components/fractal/GraphControls'
import { NodeDetail } from '../components/fractal/NodeDetail'
import { ChatLogPanel } from '../components/fractal/ChatLogPanel'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { PageLayout } from '../components/layout/PageLayout'

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
  const showChatLog = window.location.pathname.endsWith('/chat')
  const chatLogNodeId = showChatLog && urlNodeId ? urlNodeId : null

  const { data: graphDetailData } = useFractalGraphDetail(selectedGraphId)
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

  // Extract seed for breadcrumb display
  const graphSeed = graphDetailData ? String(graphDetailData.seed || '') : null

  // Build breadcrumb segments (same logic as Breadcrumb component)
  const truncate = (text: string, max: number) => text.length <= max ? text : text.slice(0, max) + '...'
  const segments: { label: string; path?: string }[] = [
    { label: 'FRACTAL', path: selectedGraphId ? '/fractal' : undefined },
  ]
  if (selectedGraphId) {
    const seedLabel = graphSeed ? truncate(graphSeed, 40) : selectedGraphId.slice(0, 12) + '...'
    segments.push({
      label: `Graph "${seedLabel}"`,
      path: urlNodeId ? `/fractal/${selectedGraphId}` : undefined,
    })
  }
  if (urlNodeId) {
    segments.push({
      label: `Node #${urlNodeId}`,
      path: showChatLog ? `/fractal/${selectedGraphId}/${urlNodeId}` : undefined,
    })
  }
  if (showChatLog) {
    segments.push({ label: 'Chat Log' })
  }

  // ── LIST VIEW: no graph selected ──
  if (!selectedGraphId) {
    return (
      <PageLayout segments={segments} fullHeight>
        <GraphTable />
      </PageLayout>
    )
  }

  // ── GRAPH VIEW: graph selected ──
  return (
    <PageLayout segments={segments} fullHeight>

      <div className="flex flex-1 overflow-hidden">
        {/* Main: graph canvas */}
        <div className="flex-1 relative">
          {graphLoading ? (
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
          {cytoscapeData && (
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

        {/* Right pane: graph details sidebar */}
        {graphDetailData && (
          <div className="w-80 border-l border-bg-border overflow-y-auto p-4 flex-shrink-0">
            <GraphDetailsSidebar
              graph={graphDetailData}
              stats={cytoscapeData?.stats ?? null}
            />
          </div>
        )}
      </div>
    </PageLayout>
  )
}
