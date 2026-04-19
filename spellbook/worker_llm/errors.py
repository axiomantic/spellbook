"""Exception hierarchy for worker-LLM calls.

Integrations catch ``WorkerLLMError`` to surface worker failures loudly without
masking unrelated bugs. The four subclasses narrow the failure mode for
observability and per-integration policy (e.g. tool-safety fails open on
``WorkerLLMTimeout``).
"""


class WorkerLLMError(Exception):
    """Base class for all worker-LLM failures. Catch this to surface loudly."""


class WorkerLLMNotConfigured(WorkerLLMError):
    """``worker_llm_base_url`` empty. Raised on first call."""


class WorkerLLMTimeout(WorkerLLMError):
    """Request exceeded configured timeout. Tool-safety handler fails OPEN here."""


class WorkerLLMUnreachable(WorkerLLMError):
    """Connection refused / DNS failure / 5xx."""


class WorkerLLMBadResponse(WorkerLLMError):
    """200 OK but schema mismatch, JSON parse failure, truncated output."""
