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
    response types (e.g. SessionListResponse).
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
# | CONFIG_KEY_UNKNOWN         | 404  | Config key not recognized                  |
# | AUTH_EXPIRED               | 401  | Session cookie or token has expired        |
# | AUTH_INVALID               | 401  | Invalid credentials or signature           |
# | GRAPH_NOT_FOUND            | 404  | Fractal graph ID does not exist            |

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
