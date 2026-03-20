import { ReactNode } from 'react'
import { PageHeader, PageHeaderSegment } from './PageHeader'

interface PageLayoutProps {
  segments: PageHeaderSegment[]
  headerRight?: ReactNode
  children: ReactNode
  fullHeight?: boolean
}

export function PageLayout({ segments, headerRight, children, fullHeight }: PageLayoutProps) {
  return (
    <div className={fullHeight ? 'flex flex-col h-full' : 'flex flex-col h-full'}>
      <PageHeader segments={segments} right={headerRight} />
      <div className={fullHeight ? 'flex-1 overflow-auto' : 'flex-1 overflow-auto p-6'}>
        {children}
      </div>
    </div>
  )
}
