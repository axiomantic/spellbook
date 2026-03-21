"""Pydantic models for admin API request/response schemas."""

from pydantic import BaseModel, Field
from typing import Generic, Optional, TypeVar, Any

T = TypeVar("T")


# --- Pagination ---
class PaginatedRequest(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=50, ge=1, le=200)


class PaginatedResponse(BaseModel):
    total: int
    page: int
    per_page: int
    pages: int


class ListResponse(BaseModel, Generic[T]):
    """Standard list response envelope for all admin list endpoints.

    This is the unified response shape that replaces per-endpoint
    response types (MemoryListResponse, SecurityEventListResponse, etc.)
    """

    items: list[T]
    total: int
    page: int
    per_page: int
    pages: int


# --- Dashboard ---
class HealthStatus(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    db_size_bytes: int
    event_bus_subscribers: int
    event_bus_dropped_events: int


class DashboardCounts(BaseModel):
    active_sessions: int
    total_memories: int
    security_events_24h: int
    running_swarms: int
    open_experiments: int
    fractal_graphs: int


class ActivityItem(BaseModel):
    type: str
    timestamp: str
    summary: str


class DashboardResponse(BaseModel):
    health: HealthStatus
    counts: DashboardCounts
    recent_activity: list[ActivityItem]


# --- Memory ---
class MemoryItem(BaseModel):
    id: str
    content: str
    memory_type: Optional[str]
    namespace: str
    branch: str
    importance: float
    created_at: str
    accessed_at: Optional[str]
    status: str
    meta: dict[str, Any]
    citation_count: int = 0


class MemoryListResponse(PaginatedResponse):
    memories: list[MemoryItem]


class MemoryUpdateRequest(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=50000)
    importance: Optional[float] = Field(None, ge=0.0, le=10.0)
    meta: Optional[dict[str, Any]] = None  # JSON serialized must be < 64KB


class ConsolidateRequest(BaseModel):
    namespace: str
    max_events: int = Field(default=50, ge=1, le=500)


# --- Security ---
class SecurityEvent(BaseModel):
    id: int
    event_type: str
    severity: str
    source: Optional[str]
    detail: Optional[str]
    session_id: Optional[str]
    tool_name: Optional[str]
    action_taken: Optional[str]
    created_at: str


class SecurityEventListResponse(PaginatedResponse):
    events: list[SecurityEvent]


class SecurityDashboardResponse(BaseModel):
    mode: str
    events_24h: dict[str, int]
    top_event_types: list[dict[str, Any]]
    active_canaries: int
    trust_registry_size: int


# --- Sessions ---
class SessionItem(BaseModel):
    id: str
    project_path: str
    session_id: Optional[str]
    bound_at: Optional[str]
    persona: Optional[str]
    active_skill: Optional[str]
    skill_phase: Optional[str]
    workflow_pattern: Optional[str]
    summoned_at: Optional[str]


class SessionListResponse(PaginatedResponse):
    sessions: list[SessionItem]


# --- Config ---
class ConfigResponse(BaseModel):
    config: dict[str, Any]


class ConfigSetRequest(BaseModel):
    value: Any


class ConfigBatchRequest(BaseModel):
    updates: dict[str, Any]


# --- Fractal ---
class GraphStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern=r"^[a-z_]+$", max_length=30)
    reason: Optional[str] = None


class FractalGraphSummary(BaseModel):
    id: str
    seed: str
    intensity: str
    status: str
    total_nodes: int
    created_at: str


class FractalGraphListResponse(PaginatedResponse):
    graphs: list[FractalGraphSummary]


class CytoscapeNode(BaseModel):
    data: dict[str, Any]
    classes: str = ""


class CytoscapeEdge(BaseModel):
    data: dict[str, Any]
    classes: str = ""


class CytoscapeElements(BaseModel):
    nodes: list[CytoscapeNode]
    edges: list[CytoscapeEdge]


class FractalGraphStats(BaseModel):
    total_nodes: int
    saturated: int
    pending: int
    max_depth: int
    convergences: int
    contradictions: int


class CytoscapeResponse(BaseModel):
    elements: CytoscapeElements
    stats: FractalGraphStats


# --- Citations ---
class CitationItem(BaseModel):
    id: int
    memory_id: str
    file_path: str
    line_range: Optional[str] = None
    content_snippet: Optional[str] = None


# --- Namespace/Stats ---
class NamespaceListResponse(BaseModel):
    namespaces: list[str]


class MemoryStatsResponse(BaseModel):
    total: int
    by_type: dict[str, int]
    by_status: dict[str, int]
    by_namespace: dict[str, int]


# --- Fractal Convergence/Contradictions ---
class ConvergenceCluster(BaseModel):
    nodes: list[dict[str, Any]]  # Each: {node_id: str, text: str, depth: int}
    insight: str
    edge_count: int


class ConvergenceResponse(BaseModel):
    clusters: list[ConvergenceCluster]
    count: int


class ContradictionPair(BaseModel):
    node_a: dict[str, Any]  # {node_id: str, text: str}
    node_b: dict[str, Any]  # {node_id: str, text: str}
    tension: str


class ContradictionResponse(BaseModel):
    pairs: list[ContradictionPair]
    count: int


# --- Consolidation ---
class ConsolidateResponse(BaseModel):
    memories_created: int
    events_consolidated: int


# --- Errors ---
class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


# Error codes:
# | Code                       | HTTP | Description                                |
# |----------------------------|------|--------------------------------------------|
# | MEMORY_NOT_FOUND           | 404  | Memory ID does not exist                   |
# | INVALID_FTS_QUERY          | 400  | FTS5 search query syntax error             |
# | CONFIG_KEY_UNKNOWN         | 404  | Config key not recognized                  |
# | AUTH_EXPIRED               | 401  | Session cookie or token has expired        |
# | AUTH_INVALID               | 401  | Invalid credentials or signature           |
# | GRAPH_NOT_FOUND            | 404  | Fractal graph ID does not exist            |
# | CONSOLIDATION_IN_PROGRESS  | 409  | Consolidation already running              |

# --- WebSocket ---
class WSEvent(BaseModel):
    type: str = "event"
    subsystem: str
    event: str
    data: dict[str, Any]
    timestamp: str


class WSControl(BaseModel):
    type: str  # ping, pong, subscribe, unsubscribe
    subsystems: Optional[list[str]] = None
