import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, String, Text

from database import Base


class Item(Base):
    __tablename__ = "items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    url = Column(String, nullable=True)
    content_type = Column(String, nullable=False)
    raw_text = Column(Text, nullable=True)

    narrative = Column(Text, nullable=True)
    headline = Column(Text, nullable=True)
    entities = Column(JSON, default=list)
    claims = Column(JSON, default=list)
    deepfake_risk = Column(Float, nullable=True)
    coordination_score = Column(Float, nullable=True)
    disinformation_impact = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    detected_language = Column(String, nullable=True)
    detected_country = Column(String, nullable=True)
    counter_narrative = Column(Text, nullable=True)
    brief = Column(Text, nullable=True)
    legal_flags = Column(JSON, default=list)
    recommended_actions = Column(JSON, default=list)
    policy_recommendations = Column(JSON, default=list)
    status = Column(String, default="pending")
    transparency_published = Column(String, default="false")

    created_at = Column(DateTime, default=datetime.utcnow)


class ToolkitIncident(Base):
    __tablename__ = "toolkit_incidents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    what_happened = Column(Text, nullable=False)
    spread_channels = Column(Text, nullable=True)
    targeted_groups = Column(Text, nullable=True)
    claim_summary = Column(Text, nullable=True)
    confidence_evidence = Column(Text, nullable=True)
    owner_deadline = Column(Text, nullable=True)
    recommended_action = Column(String, nullable=True)
    triage_flags = Column(JSON, default=list)
    notes = Column(Text, nullable=True)

    risk_likelihood = Column(Float, nullable=False)
    risk_reach = Column(Float, nullable=False)
    risk_urgency = Column(Float, nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_band = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    item_id = Column(String, nullable=True, index=True)
    actor = Column(String, nullable=False, default="system")
    action = Column(String, nullable=False)
    detail = Column(Text, nullable=True)
    legal_basis = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
