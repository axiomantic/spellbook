import { PageHeader } from '../layout/PageHeader'

interface BreadcrumbProps {
  graphId?: string | null
  graphSeed?: string | null
  nodeId?: string | null
  showChatLog?: boolean
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text
  return text.slice(0, max) + '...'
}

export function Breadcrumb({ graphId, graphSeed, nodeId, showChatLog }: BreadcrumbProps) {
  const segments: { label: string; path?: string }[] = [
    { label: 'FRACTAL', path: graphId ? '/fractal' : undefined },
  ]

  if (graphId) {
    const seedLabel = graphSeed ? truncate(graphSeed, 40) : graphId.slice(0, 12) + '...'
    segments.push({
      label: `Graph "${seedLabel}"`,
      path: nodeId ? `/fractal/${graphId}` : undefined,
    })
  }

  if (nodeId) {
    segments.push({
      label: `Node #${nodeId}`,
      path: showChatLog ? `/fractal/${graphId}/${nodeId}` : undefined,
    })
  }

  if (showChatLog) {
    segments.push({ label: 'Chat Log' })
  }

  return <PageHeader segments={segments} />
}
