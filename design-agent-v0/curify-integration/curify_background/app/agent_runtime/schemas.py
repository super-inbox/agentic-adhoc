from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentTaskType(str, Enum):
    AUTO = "auto"
    DESIGN_VOTE = "design_vote"
    TRYON_POSTER = "tryon_poster"


class AgentRunStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ABSTAINED = "ABSTAINED"
    FAILED = "FAILED"


class AgentStage(str, Enum):
    UNDERSTAND = "UNDERSTAND"
    PLAN = "PLAN"
    GENERATE = "GENERATE"
    VERIFY = "VERIFY"
    PRESENT = "PRESENT"


class AgentStepStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentArtifactKind(str, Enum):
    IMAGE = "image"
    REPORT = "report"
    MANIFEST = "manifest"


class AgentRunRequest(BaseModel):
    """One user turn. Images are uploaded first through the existing image API.

    For ``tryon_poster`` image 0 is the selfie and optional image 1 is the
    product/garment reference. Four-image ``design_vote`` requests map to A-D;
    a single image is treated as a four-panel comparison board.
    """

    task_type: AgentTaskType = AgentTaskType.AUTO
    prompt: str = Field(min_length=1, max_length=2_000)
    image_urls: List[str] = Field(min_length=1, max_length=4)
    locale: str = Field(default="zh", min_length=2, max_length=16)
    output_count: int = Field(default=3, ge=1, le=4)
    max_iterations: int = Field(default=1, ge=0, le=2)
    allow_paid_generation: bool = False
    constraints: Dict[str, Any] = Field(default_factory=dict)


class AgentCapabilityDecision(BaseModel):
    supported: bool
    code: str = "SUPPORTED"
    message: str = ""


class AgentToolCall(BaseModel):
    tool: str
    purpose: str


class AgentPlan(BaseModel):
    skill_id: str
    iteration: int
    calls: List[AgentToolCall]
    repair_instruction: Optional[str] = None


class AgentArtifact(BaseModel):
    artifact_id: str
    kind: AgentArtifactKind
    label: str
    object_path: str
    media_type: str
    url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VerificationVerdict(BaseModel):
    passed: bool = False
    scores: Dict[str, float] = Field(default_factory=dict)
    hard_failures: List[str] = Field(default_factory=list)
    repairable_failures: List[str] = Field(default_factory=list)
    repair_instruction: Optional[str] = None
    retry_scope: List[str] = Field(default_factory=list)


class AgentTraceStep(BaseModel):
    step_id: str
    stage: AgentStage
    name: str
    status: AgentStepStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    latency_ms: Optional[int] = None
    tool_name: Optional[str] = None
    model: Optional[str] = None
    input_summary: Dict[str, Any] = Field(default_factory=dict)
    output_summary: Any = Field(default_factory=dict)
    metrics: Dict[str, float] = Field(default_factory=dict)
    error: Optional[str] = None


class AgentRunResult(BaseModel):
    run_id: str
    status: AgentRunStatus
    task_type: Optional[AgentTaskType] = None
    skill_id: Optional[str] = None
    summary: str
    code: Optional[str] = None
    artifacts: List[AgentArtifact] = Field(default_factory=list)
    verdict: Optional[VerificationVerdict] = None
    iterations: int = 0
    trace: List[AgentTraceStep] = Field(default_factory=list)


class VoteVariant(BaseModel):
    id: str
    design_language: str
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)


class VoteSegmentDraft(BaseModel):
    name: str
    share: float
    votes: Dict[str, float]
    rationale: str


class VoteDraft(BaseModel):
    valid_variants: bool = True
    issues: List[str] = Field(default_factory=list)
    # Defaults let the model return a small, honest invalid-input response;
    # the runtime abstains before aggregation when ``valid_variants`` is false.
    product: str = ""
    category: str = ""
    axis: str = ""
    variants: List[VoteVariant] = Field(default_factory=list)
    segments: List[VoteSegmentDraft] = Field(default_factory=list)
    recommendation: str = ""
    confidence: float = 0.7


class VoteSegment(BaseModel):
    name: str
    share: float
    votes: Dict[str, int]
    rationale: str


class VoteAnalysis(BaseModel):
    product: str
    category: str
    axis: str
    variants: List[VoteVariant]
    segments: List[VoteSegment]
    overall: Dict[str, int]
    winner: str
    recommendation: str
    confidence: float
    simulated_disclaimer: str = "AI 模拟投票 · 加权合成，并非真实消费者调研"


class TryOnPosterScore(BaseModel):
    index: int
    identity: float = Field(ge=0.0, le=5.0)
    product_fidelity: Optional[float] = Field(default=None, ge=0.0, le=5.0)
    anatomy: float = Field(ge=0.0, le=5.0)
    instruction_following: float = Field(ge=0.0, le=5.0)
    layout: float = Field(ge=0.0, le=5.0)
    failures: List[str] = Field(default_factory=list)


class TryOnReview(BaseModel):
    posters: List[TryOnPosterScore]


class CreateAgentRunResponse(BaseModel):
    run_id: str
    status: AgentRunStatus = AgentRunStatus.QUEUED


class AgentRunStatusResponse(BaseModel):
    run_id: str
    status: AgentRunStatus
    task_type: Optional[AgentTaskType] = None
    skill_id: Optional[str] = None
    summary: Optional[str] = None
    code: Optional[str] = None
    current_stage: Optional[AgentStage] = None
    artifacts: List[AgentArtifact] = Field(default_factory=list)
    verdict: Optional[VerificationVerdict] = None
    iterations: int = 0
    trace: List[AgentTraceStep] = Field(default_factory=list)
