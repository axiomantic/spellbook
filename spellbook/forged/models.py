"""Data models for the Forged autonomous development system.

These dataclasses represent the core domain objects used for tracking
autonomous development workflows with validator-based feedback loops.
"""

from dataclasses import dataclass, field
from typing import Optional


# Constants
SCHEMA_VERSION = 1

VALID_STAGES = ["DISCOVER", "DESIGN", "PLAN", "IMPLEMENT", "COMPLETE", "ESCALATED"]

VALID_SEVERITIES = ["blocking", "significant", "minor"]

VALID_VERDICTS = ["APPROVED", "FEEDBACK", "ABSTAIN", "ERROR"]


@dataclass
class Feedback:
    """Validator feedback for an artifact.

    Represents structured feedback from a validator about work product quality,
    including the severity level and suggested resolution path.

    Attributes:
        source: Identifier of the validator that generated this feedback
        stage: The workflow stage where the feedback was generated
        return_to: The stage to return to for resolution
        critique: Human-readable description of the issue
        evidence: Specific evidence supporting the critique
        suggestion: Recommended action to resolve the issue
        severity: Impact level - "blocking", "significant", or "minor"
        iteration: The iteration number when this feedback was generated
    """

    source: str
    stage: str
    return_to: str
    critique: str
    evidence: str
    suggestion: str
    severity: str
    iteration: int

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary.

        Returns:
            Dictionary with all feedback fields
        """
        return {
            "source": self.source,
            "stage": self.stage,
            "return_to": self.return_to,
            "critique": self.critique,
            "evidence": self.evidence,
            "suggestion": self.suggestion,
            "severity": self.severity,
            "iteration": self.iteration,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Feedback":
        """Reconstruct Feedback from dictionary.

        Args:
            data: Dictionary containing feedback fields

        Returns:
            Reconstructed Feedback instance
        """
        return cls(
            source=data["source"],
            stage=data["stage"],
            return_to=data["return_to"],
            critique=data["critique"],
            evidence=data["evidence"],
            suggestion=data["suggestion"],
            severity=data["severity"],
            iteration=data["iteration"],
        )


@dataclass
class ValidatorResult:
    """Result from a validator execution.

    Represents the outcome of running a validator against an artifact,
    including the verdict, any feedback, and transformation information.

    Attributes:
        verdict: "APPROVED", "FEEDBACK", "ABSTAIN", or "ERROR"
        feedback: Optional Feedback object if verdict is FEEDBACK
        transformed: Whether the validator transformed the artifact
        artifact_path: Path to the validated artifact
        artifact_hash: Hash of the artifact for change detection
        transform_description: Description of any transformation applied
        error: Error message if verdict is ERROR
    """

    verdict: str
    feedback: Optional[Feedback]
    transformed: bool
    artifact_path: str
    artifact_hash: str
    transform_description: Optional[str]
    error: Optional[str]

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary.

        Returns:
            Dictionary with all result fields, feedback nested as dict
        """
        return {
            "verdict": self.verdict,
            "feedback": self.feedback.to_dict() if self.feedback else None,
            "transformed": self.transformed,
            "artifact_path": self.artifact_path,
            "artifact_hash": self.artifact_hash,
            "transform_description": self.transform_description,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ValidatorResult":
        """Reconstruct ValidatorResult from dictionary.

        Args:
            data: Dictionary containing result fields

        Returns:
            Reconstructed ValidatorResult instance
        """
        feedback_data = data.get("feedback")
        feedback = Feedback.from_dict(feedback_data) if feedback_data else None

        return cls(
            verdict=data["verdict"],
            feedback=feedback,
            transformed=data["transformed"],
            artifact_path=data["artifact_path"],
            artifact_hash=data["artifact_hash"],
            transform_description=data.get("transform_description"),
            error=data.get("error"),
        )


@dataclass
class IterationState:
    """State tracking for a single feature's development iteration.

    Represents the accumulated state across iterations of developing a feature,
    including feedback history, learned knowledge, and user preferences.

    Attributes:
        iteration_number: Current iteration count (1-indexed)
        current_stage: Current workflow stage
        feedback_history: List of all feedback received
        accumulated_knowledge: Knowledge accumulated during development
        artifacts_produced: List of artifact paths produced
        preferences: User preferences learned during development
        started_at: ISO timestamp when iteration started
    """

    iteration_number: int
    current_stage: str
    feedback_history: list = field(default_factory=list)
    accumulated_knowledge: dict = field(default_factory=dict)
    artifacts_produced: list = field(default_factory=list)
    preferences: dict = field(default_factory=dict)
    started_at: str = ""

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary.

        Returns:
            Dictionary with all state fields, feedback list as dicts
        """
        return {
            "iteration_number": self.iteration_number,
            "current_stage": self.current_stage,
            "feedback_history": [f.to_dict() for f in self.feedback_history],
            "accumulated_knowledge": self.accumulated_knowledge,
            "artifacts_produced": self.artifacts_produced,
            "preferences": self.preferences,
            "started_at": self.started_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IterationState":
        """Reconstruct IterationState from dictionary.

        Args:
            data: Dictionary containing state fields

        Returns:
            Reconstructed IterationState instance
        """
        feedback_history = [
            Feedback.from_dict(f) for f in data.get("feedback_history", [])
        ]

        return cls(
            iteration_number=data["iteration_number"],
            current_stage=data["current_stage"],
            feedback_history=feedback_history,
            accumulated_knowledge=data.get("accumulated_knowledge", {}),
            artifacts_produced=data.get("artifacts_produced", []),
            preferences=data.get("preferences", {}),
            started_at=data.get("started_at", ""),
        )
