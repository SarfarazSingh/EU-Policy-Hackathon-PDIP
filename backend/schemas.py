from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class ItemCreate(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None
    type: str  # 'url', 'text', 'image', 'video'

class ItemSummary(BaseModel):
    itemId: str
    status: str
    createdAt: datetime
    headline: Optional[str] = None
    disinformationImpact: Optional[float] = None

class ItemDetail(BaseModel):
    itemId: str
    headline: str = ""
    narrative: str
    entities: List[str]
    claims: List[str]
    deepfakeRisk: float
    coordinationScore: float
    disinformationImpact: float
    confidence: float = 0.0
    detectedLanguage: Optional[str] = None
    detectedCountry: Optional[str] = None
    legalFlags: List[str]
    brief: str
    status: str
    recommendedActions: List[str] = []
    policyRecommendations: List[str] = []
    counterNarrative: Optional[str] = None
    createdAt: Optional[datetime] = None


class ToolkitIncidentCreate(BaseModel):
    whatHappened: str
    spreadChannels: Optional[str] = None
    targetedGroups: Optional[str] = None
    claimSummary: Optional[str] = None
    confidenceEvidence: Optional[str] = None
    ownerDeadline: Optional[str] = None
    recommendedAction: Optional[str] = None
    triageFlags: List[str] = []
    notes: Optional[str] = None
    riskLikelihood: float
    riskReach: float
    riskUrgency: float
    riskScore: float
    riskBand: str


class ToolkitIncidentSummary(BaseModel):
    incidentId: str
    whatHappened: str
    riskScore: float
    riskBand: str
    recommendedAction: Optional[str] = None
    createdAt: datetime


class ToolkitIncidentDetail(BaseModel):
    incidentId: str
    whatHappened: str
    spreadChannels: str
    targetedGroups: str
    claimSummary: str
    confidenceEvidence: str
    ownerDeadline: str
    recommendedAction: str
    triageFlags: List[str]
    notes: str
    riskLikelihood: float
    riskReach: float
    riskUrgency: float
    riskScore: float
    riskBand: str
    createdAt: datetime


class AuditEventOut(BaseModel):
    id: str
    itemId: Optional[str] = None
    actor: str
    action: str
    detail: Optional[str] = None
    legalBasis: Optional[str] = None
    createdAt: datetime


class TwinDossier(BaseModel):
    itemId: str
    headline: str
    similarity: float
    sharedEntities: List[str]
    disinformationImpact: float
    createdAt: datetime


class GraphNode(BaseModel):
    id: str
    label: str
    kind: str  # 'dossier' | 'entity' | 'channel'
    weight: float = 1.0


class GraphEdge(BaseModel):
    source: str
    target: str
    weight: float = 1.0
    kind: str = "mentions"


class CoordinationGraph(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class CounterNarrativeOut(BaseModel):
    itemId: str
    language: str
    draft: str
    transparencyNotice: str
    citations: List[str]


class ElectionModeState(BaseModel):
    enabled: bool
    activatedAt: Optional[datetime] = None
    slaMinutes: int = 30


class TransparencyEntry(BaseModel):
    itemId: str
    headline: str
    legalBasis: List[str]
    actionTaken: str
    redactedNarrative: str
    createdAt: datetime
    publishedAt: datetime


class GeoBreakdown(BaseModel):
    countries: Dict[str, int]
    languages: Dict[str, int]
    total: int


class RegulationExcerpt(BaseModel):
    citation: str
    title: str
    excerpt: str
    sourceDocument: str


class DemoReplayResult(BaseModel):
    seeded: int
    itemIds: List[str]
