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
  project: string
  slug: string | null
  custom_title: string | null
  first_user_message: string | null
  created_at: string | null
  last_activity: string | null
  message_count: number
  size_bytes: number
}

// Session Detail
export interface SessionDetail {
  id: string
  project: string
  project_decoded: string
  slug: string | null
  custom_title: string | null
  created_at: string | null
  last_activity: string | null
  message_count: number
  size_bytes: number
  first_user_message: string | null
}

// Session Messages
export interface SessionMessage {
  line_number: number
  type: string
  timestamp: string | null
  content: string
  is_compact_summary: boolean
  raw: Record<string, unknown> | null
}

export interface SessionMessagesResponse {
  messages: SessionMessage[]
  total_lines: number
  page: number
  per_page: number
  pages: number
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
  updated_at: string
  project_dir: string | null
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

export interface ChatLogMessage {
  role: 'user' | 'assistant' | 'thinking' | 'tool_use' | 'tool_result'
  content: string
  timestamp: string
  tool_use_id?: string
}

export interface ChatLogResponse {
  messages: ChatLogMessage[]
  node_id: string
  session_id: string | null
  claimed_at?: string | null
  synthesized_at?: string | null
  note?: string
}

// Fractal Graph Management
export interface GraphStatusUpdateRequest {
  status: string
  reason?: string
}

export interface GraphDeleteResponse {
  deleted: boolean
  graph_id: string
}

export interface GraphStatusUpdateResponse {
  graph_id: string
  status: string
  previous_status: string
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

// Analytics
export interface ToolFrequencyItem {
  tool_name: string
  count: number
  errors: number
}

export interface ToolFrequencyResponse {
  tools: ToolFrequencyItem[]
}

export interface ErrorRateItem {
  tool_name: string
  total: number
  errors: number
  error_rate: number
}

export interface ErrorRateResponse {
  tools: ErrorRateItem[]
}

export interface TimelineItem {
  bucket: string
  count: number
  errors: number
}

export interface TimelineResponse {
  timeline: TimelineItem[]
}

export interface AnalyticsSummary {
  total_events: number
  unique_tools: number
  error_rate: number
  events_today: number
}

// Health Matrix
export interface TableHealth {
  name: string
  row_count: number
  last_activity: string | null
  error_count: number | null
}

export interface SubsystemHealth {
  name: string
  status: 'healthy' | 'idle' | 'error' | 'missing'
  size_bytes: number
  tables: TableHealth[]
}

export interface HealthMatrixResponse {
  databases: SubsystemHealth[]
  generated_at: string
}

// Zeigarnik Focus Tracking
export interface StintEntry {
  name: string
  purpose: string
  behavioral_mode: string
  metadata: Record<string, unknown>
  entered_at: string
  // Legacy fields (may exist on old entries, not used by new code)
  type?: string
  parent?: string | null
  exited_at?: string | null
  success_criteria?: string
}

export interface StintStack {
  project_path: string
  session_id: string | null
  stack: StintEntry[]
  depth: number
  updated_at: string
}

export interface CorrectionEvent {
  id: number
  project_path: string
  session_id: string | null
  correction_type: 'llm_wrong' | 'mcp_wrong'
  old_stack: StintEntry[]
  new_stack: StintEntry[]
  diff_summary: string | null
  created_at: string
}

export interface FocusSummary {
  active_projects: number
  total_corrections_24h: number
  llm_wrong_24h: number
  mcp_wrong_24h: number
  max_depth: number
}

// Generic list response for useListPage
export interface ListResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
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
