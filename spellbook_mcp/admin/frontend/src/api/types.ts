// Pagination
export interface PaginatedResponse {
  total: number
  page: number
  per_page: number
  pages: number
}

// Dashboard
export interface HealthStatus {
  status: string
  version: string
  uptime_seconds: number
  db_size_bytes: number
  event_bus_subscribers: number
  event_bus_dropped_events: number
}

export interface DashboardCounts {
  active_sessions: number
  total_memories: number
  security_events_24h: number
  running_swarms: number
  open_experiments: number
  fractal_graphs: number
}

export interface ActivityItem {
  type: string
  timestamp: string
  summary: string
}

export interface DashboardResponse {
  health: HealthStatus
  counts: DashboardCounts
  recent_activity: ActivityItem[]
}

// Memory
export interface MemoryItem {
  id: string
  content: string
  memory_type: string | null
  namespace: string
  branch: string
  importance: number
  created_at: string
  accessed_at: string | null
  status: string
  meta: Record<string, unknown>
  citation_count: number
}

export interface MemoryListResponse extends PaginatedResponse {
  memories: MemoryItem[]
}

export interface MemoryUpdateRequest {
  content?: string
  importance?: number
  meta?: Record<string, unknown>
}

// Security
export interface SecurityEvent {
  id: number
  event_type: string
  severity: string
  source: string | null
  detail: string | null
  session_id: string | null
  tool_name: string | null
  action_taken: string | null
  created_at: string
}

export interface SecurityEventListResponse extends PaginatedResponse {
  events: SecurityEvent[]
}

export interface SecurityDashboardResponse {
  mode: string
  events_24h: Record<string, number>
  top_event_types: Array<{ event_type: string; count: number }>
  active_canaries: number
  trust_registry_size: number
}

// Sessions
export interface SessionItem {
  id: string
  project_path: string
  session_id: string | null
  bound_at: string | null
  persona: string | null
  active_skill: string | null
  skill_phase: string | null
  workflow_pattern: string | null
  summoned_at: string | null
}

export interface SessionListResponse extends PaginatedResponse {
  sessions: SessionItem[]
}

// Config
export interface ConfigResponse {
  config: Record<string, unknown>
}

// Fractal
export interface FractalGraphSummary {
  id: string
  seed: string
  intensity: string
  status: string
  total_nodes: number
  created_at: string
}

export interface FractalGraphListResponse extends PaginatedResponse {
  graphs: FractalGraphSummary[]
}

export interface CytoscapeNode {
  data: Record<string, unknown>
  classes: string
}

export interface CytoscapeEdge {
  data: Record<string, unknown>
  classes: string
}

export interface CytoscapeResponse {
  elements: {
    nodes: CytoscapeNode[]
    edges: CytoscapeEdge[]
  }
  stats: {
    total_nodes: number
    saturated: number
    pending: number
    max_depth: number
    convergences: number
    contradictions: number
  }
}

// WebSocket
export interface WSEvent {
  type: 'event'
  subsystem: string
  event: string
  data: Record<string, unknown>
  timestamp: string
}

export interface WSControl {
  type: 'ping' | 'pong' | 'subscribe' | 'unsubscribe'
  subsystems?: string[]
}

// Errors
export interface ErrorDetail {
  code: string
  message: string
  details?: Array<Record<string, unknown>>
}

export interface ErrorResponse {
  error: ErrorDetail
}
