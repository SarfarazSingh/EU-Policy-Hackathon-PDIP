from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

import analysis
import intelligence
import schemas
from database import Base, engine, get_db
from models import AppSetting, AuditEvent, Item, ToolkitIncident
from pdf_export import render_brief
from regulations import REGULATIONS, list_citation_keys, lookup, parse_flag_to_citation


Base.metadata.create_all(bind=engine)


def ensure_items_table_columns() -> None:
    inspector = inspect(engine)
    with engine.begin() as conn:
        if "items" in inspector.get_table_names():
            existing = {c["name"] for c in inspector.get_columns("items")}
            additions = [
                ("recommended_actions", "JSON"),
                ("policy_recommendations", "JSON"),
                ("disinformation_impact", "FLOAT"),
                ("headline", "TEXT"),
                ("confidence", "FLOAT"),
                ("detected_language", "VARCHAR"),
                ("detected_country", "VARCHAR"),
                ("counter_narrative", "TEXT"),
                ("transparency_published", "VARCHAR"),
            ]
            for column_name, column_type in additions:
                if column_name in existing:
                    continue
                if engine.dialect.name == "postgresql" and column_type == "JSON":
                    conn.execute(text(f"ALTER TABLE items ADD COLUMN {column_name} JSON DEFAULT '[]'::json"))
                else:
                    conn.execute(text(f"ALTER TABLE items ADD COLUMN {column_name} {column_type}"))


ensure_items_table_columns()

app = FastAPI(title="PDIP API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Audit / settings helpers
# ---------------------------------------------------------------------------


def record_event(db: Session, item_id: Optional[str], action: str, detail: str = "", actor: str = "duty desk", legal_basis: Optional[str] = None) -> None:
    event = AuditEvent(
        item_id=item_id,
        action=action,
        detail=detail,
        actor=actor,
        legal_basis=legal_basis,
    )
    db.add(event)
    db.commit()


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return row.value if row else default


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row is None:
        row = AppSetting(key=key, value=value, updated_at=datetime.utcnow())
        db.add(row)
    else:
        row.value = value
        row.updated_at = datetime.utcnow()
    db.commit()


# ---------------------------------------------------------------------------
# Item processing
# ---------------------------------------------------------------------------


def process_item(item_id: str) -> None:
    db = next(get_db())
    try:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item or item.status == "stopped":
            return

        source_text = item.raw_text or ""
        if item.url and not source_text:
            source_text = analysis.scrape_url(item.url)
            item.raw_text = source_text

        db.refresh(item)
        if item.status == "stopped":
            return

        extraction = analysis.extract_claims(source_text)
        item.claims = extraction.get("claims", [])
        item.entities = extraction.get("entities", [])

        ai_prob, coord_score, disinfo_impact, synopsis, threat_level, narrative, legal_flags, rec_actions, policy_recs = (
            analysis.analyze_content(source_text)
        )

        item.deepfake_risk = ai_prob
        item.coordination_score = coord_score
        item.disinformation_impact = disinfo_impact
        item.narrative = narrative
        item.legal_flags = legal_flags
        item.recommended_actions = rec_actions
        item.policy_recommendations = policy_recs

        item.headline = intelligence.headline_from_narrative(narrative, source_text)
        item.confidence = intelligence.confidence_band(disinfo_impact, ai_prob, coord_score)
        item.detected_language = intelligence.detect_language(source_text)
        item.detected_country = intelligence.detect_country(source_text)

        item.brief = analysis.generate_brief(
            item.narrative,
            item.entities,
            item.claims,
            synopsis,
            threat_level,
            policy_recs,
        )
        item.status = "done"
        db.commit()

        record_event(
            db,
            item_id=item.id,
            action="analysis.completed",
            detail=f"Threat level {threat_level}; mislead-citizens risk {int((disinfo_impact or 0) * 100)}%",
            actor="analysis engine",
            legal_basis="AI Act Art. 50",
        )

        if (item.disinformation_impact or 0) >= 0.85:
            item.status = "escalated"
            db.commit()
            record_event(
                db,
                item_id=item.id,
                action="auto.escalated",
                detail="Auto-escalation triggered by election-emergency threshold.",
                actor="analysis engine",
                legal_basis="DSA Art. 35",
            )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Item routes
# ---------------------------------------------------------------------------


@app.post("/api/items", response_model=schemas.ItemSummary)
async def create_item(
    payload: schemas.ItemCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> schemas.ItemSummary:
    if not payload.text and not payload.url:
        raise HTTPException(status_code=400, detail="Either text or url is required")

    item = Item(
        url=payload.url,
        raw_text=payload.text,
        content_type=payload.type,
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    record_event(
        db,
        item_id=item.id,
        action="dossier.created",
        detail=f"Source type {payload.type}; intake by duty desk",
        actor="duty desk",
        legal_basis="GDPR Art. 5",
    )

    background_tasks.add_task(process_item, item.id)

    return schemas.ItemSummary(
        itemId=item.id,
        status=item.status,
        createdAt=item.created_at,
        headline=item.headline,
        disinformationImpact=item.disinformation_impact or 0.0,
    )


@app.get("/api/items", response_model=List[schemas.ItemSummary])
async def list_items(db: Session = Depends(get_db)) -> List[schemas.ItemSummary]:
    items = db.query(Item).order_by(Item.created_at.desc()).all()
    return [
        schemas.ItemSummary(
            itemId=i.id,
            status=i.status,
            createdAt=i.created_at,
            headline=i.headline,
            disinformationImpact=i.disinformation_impact or 0.0,
        )
        for i in items
    ]


def _to_detail(item: Item) -> schemas.ItemDetail:
    return schemas.ItemDetail(
        itemId=item.id,
        headline=item.headline or "",
        narrative=item.narrative or "",
        entities=item.entities or [],
        claims=item.claims or [],
        deepfakeRisk=item.deepfake_risk or 0.0,
        coordinationScore=item.coordination_score or 0.0,
        disinformationImpact=item.disinformation_impact or 0.0,
        confidence=item.confidence or 0.0,
        detectedLanguage=item.detected_language,
        detectedCountry=item.detected_country,
        legalFlags=item.legal_flags or [],
        brief=item.brief or "",
        status=item.status,
        recommendedActions=item.recommended_actions or [],
        policyRecommendations=item.policy_recommendations or [],
        counterNarrative=item.counter_narrative,
        createdAt=item.created_at,
    )


@app.get("/api/items/{item_id}", response_model=schemas.ItemDetail)
async def get_item(item_id: str, db: Session = Depends(get_db)) -> schemas.ItemDetail:
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return _to_detail(item)


@app.post("/api/items/{item_id}/stop")
async def stop_item(item_id: str, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if item.status == "pending":
        item.status = "stopped"
        db.commit()
        record_event(db, item_id=item.id, action="dossier.halted", detail="Manual halt by duty desk")
    return {"status": item.status}


@app.post("/api/items/{item_id}/escalate")
async def escalate_item(item_id: str, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if item.status == "pending":
        raise HTTPException(status_code=409, detail="Cannot escalate while assessment is running")

    item.status = "escalated"
    db.commit()
    record_event(
        db,
        item_id=item.id,
        action="dossier.escalated",
        detail="Escalation issued to electoral integrity desk",
        legal_basis="DSA Art. 35",
    )
    return {"status": item.status}


@app.delete("/api/items/{item_id}")
async def delete_item(item_id: str, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    db.delete(item)
    db.commit()
    record_event(db, item_id=item_id, action="dossier.deleted", detail="Permanent deletion by duty desk", legal_basis="GDPR Art. 5(e)")
    return {"deleted": True, "itemId": item_id}


@app.get("/api/items/{item_id}/export")
async def export_item(item_id: str, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    record_event(db, item_id=item.id, action="brief.exported", detail="Memorandum exported (JSON)", legal_basis="AI Act Art. 50")
    return {
        "itemId": item.id,
        "format": "text",
        "brief": item.brief or "",
        "label": "AI-assisted analysis (EU AI Act Article 50 transparency)",
        "policyRecommendations": item.policy_recommendations or [],
    }


@app.get("/api/items/{item_id}/pdf")
async def export_item_pdf(item_id: str, request: Request, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    base_url = str(request.base_url).rstrip("/")
    qr_url = f"{base_url}/api/items/{item.id}"

    pdf_bytes = render_brief(
        item_id=item.id,
        headline=item.headline or intelligence.headline_from_narrative(item.narrative or "", item.raw_text or ""),
        narrative=item.narrative or "",
        threat_level=(item.brief.split("\n")[0].replace("EU AI Act Threat Level:", "").strip() if item.brief else ""),
        disinfo_pct=int(round((item.disinformation_impact or 0) * 100)),
        deepfake_pct=int(round((item.deepfake_risk or 0) * 100)),
        coordination_pct=int(round((item.coordination_score or 0) * 100)),
        legal_flags=item.legal_flags or [],
        recommended_actions=item.recommended_actions or [],
        qr_url=qr_url,
    )

    record_event(db, item_id=item.id, action="brief.pdf_exported", detail="One-page PDF brief generated", legal_basis="AI Act Art. 50")

    headers = {
        "Content-Disposition": f'attachment; filename="pdip-brief-{item.id[:8]}.pdf"',
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@app.get("/api/items/{item_id}/twins", response_model=List[schemas.TwinDossier])
async def get_twins(item_id: str, db: Session = Depends(get_db)) -> List[schemas.TwinDossier]:
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    others = db.query(Item).filter(Item.id != item_id).all()
    twins = intelligence.find_twins(item, others, top_n=3)
    return [schemas.TwinDossier(**twin) for twin in twins]


@app.get("/api/items/{item_id}/graph", response_model=schemas.CoordinationGraph)
async def get_graph(item_id: str, db: Session = Depends(get_db)) -> schemas.CoordinationGraph:
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    others = db.query(Item).filter(Item.id != item_id).all()
    twins = intelligence.find_twins(item, others, top_n=4)
    graph = intelligence.build_coordination_graph(item, others, twins)
    return schemas.CoordinationGraph(**graph)


@app.post("/api/items/{item_id}/counter-narrative", response_model=schemas.CounterNarrativeOut)
async def generate_counter_narrative(item_id: str, db: Session = Depends(get_db)) -> schemas.CounterNarrativeOut:
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    payload = intelligence.build_counter_narrative(item)
    item.counter_narrative = payload["draft"]
    db.commit()
    record_event(
        db,
        item_id=item.id,
        action="counter_narrative.drafted",
        detail=f"Facts-first response drafted in {payload['language'].upper()}",
        legal_basis="AI Act Art. 50",
    )
    return schemas.CounterNarrativeOut(itemId=item.id, **payload)


@app.get("/api/items/{item_id}/audit", response_model=List[schemas.AuditEventOut])
async def get_item_audit(item_id: str, db: Session = Depends(get_db)) -> List[schemas.AuditEventOut]:
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.item_id == item_id)
        .order_by(AuditEvent.created_at.asc())
        .all()
    )
    return [
        schemas.AuditEventOut(
            id=e.id,
            itemId=e.item_id,
            actor=e.actor,
            action=e.action,
            detail=e.detail,
            legalBasis=e.legal_basis,
            createdAt=e.created_at,
        )
        for e in events
    ]


@app.post("/api/items/{item_id}/transparency", response_model=schemas.TransparencyEntry)
async def publish_transparency(item_id: str, db: Session = Depends(get_db)) -> schemas.TransparencyEntry:
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status not in ("escalated", "done"):
        raise HTTPException(status_code=409, detail="Only completed or escalated dossiers can be published")
    item.transparency_published = "true"
    db.commit()
    record_event(
        db,
        item_id=item.id,
        action="transparency.published",
        detail="Dossier published to public transparency ledger",
        legal_basis="DSA Art. 24",
    )
    return _transparency_entry(item)


def _transparency_entry(item: Item) -> schemas.TransparencyEntry:
    headline = item.headline or intelligence.headline_from_narrative(item.narrative or "", item.raw_text or "")
    action = "Escalated to electoral integrity desk." if item.status == "escalated" else "Closed without escalation."
    return schemas.TransparencyEntry(
        itemId=item.id,
        headline=headline,
        legalBasis=(item.legal_flags or [])[:3],
        actionTaken=action,
        redactedNarrative=intelligence.redact_narrative(item.narrative or ""),
        createdAt=item.created_at,
        publishedAt=item.created_at,
    )


@app.get("/api/transparency", response_model=List[schemas.TransparencyEntry])
async def list_transparency(db: Session = Depends(get_db)) -> List[schemas.TransparencyEntry]:
    items = (
        db.query(Item)
        .filter(Item.transparency_published == "true")
        .order_by(Item.created_at.desc())
        .limit(50)
        .all()
    )
    return [_transparency_entry(i) for i in items]


# ---------------------------------------------------------------------------
# Election mode
# ---------------------------------------------------------------------------


@app.get("/api/election-mode", response_model=schemas.ElectionModeState)
async def election_mode(db: Session = Depends(get_db)) -> schemas.ElectionModeState:
    enabled = get_setting(db, "election_mode", "false") == "true"
    activated_at_raw = get_setting(db, "election_mode_activated_at", "")
    activated_at = None
    if activated_at_raw:
        try:
            activated_at = datetime.fromisoformat(activated_at_raw)
        except ValueError:
            activated_at = None
    sla_minutes = int(get_setting(db, "election_mode_sla_minutes", "30") or 30)
    return schemas.ElectionModeState(enabled=enabled, activatedAt=activated_at, slaMinutes=sla_minutes)


@app.post("/api/election-mode", response_model=schemas.ElectionModeState)
async def set_election_mode(payload: schemas.ElectionModeState, db: Session = Depends(get_db)) -> schemas.ElectionModeState:
    set_setting(db, "election_mode", "true" if payload.enabled else "false")
    if payload.enabled:
        set_setting(db, "election_mode_activated_at", datetime.utcnow().isoformat())
    set_setting(db, "election_mode_sla_minutes", str(payload.slaMinutes or 30))
    record_event(
        db,
        item_id=None,
        action="election_mode.toggled",
        detail=f"Election mode {'enabled' if payload.enabled else 'disabled'}; SLA {payload.slaMinutes} min",
        legal_basis="DSA Art. 35 (crisis protocol)",
    )
    return await election_mode(db)


# ---------------------------------------------------------------------------
# Regulation library
# ---------------------------------------------------------------------------


@app.get("/api/regulations")
async def list_regulations() -> Dict[str, List[str]]:
    return {"citations": list_citation_keys()}


@app.get("/api/regulations/{citation:path}", response_model=schemas.RegulationExcerpt)
async def get_regulation(citation: str) -> schemas.RegulationExcerpt:
    data = lookup(citation)
    return schemas.RegulationExcerpt(**data)


# ---------------------------------------------------------------------------
# Dashboard / geo / audit feed
# ---------------------------------------------------------------------------


@app.get("/api/dashboard/stats")
async def dashboard_stats(db: Session = Depends(get_db)) -> Dict:
    def escalation_profile(impact: float) -> Dict[str, str]:
        if impact >= 0.85:
            return {
                "level": "ELECTORAL EMERGENCY",
                "rationale": "High probability of misleading citizens or election stakeholders at scale; immediate cross-institution response advised.",
                "legalBasis": "Regulation (EU) 2022/2065 Articles 34-35; Regulation (EU) 2024/900",
            }
        if impact >= 0.65:
            return {
                "level": "SEVERE INTEGRITY THREAT",
                "rationale": "Material risk of coordinated narrative manipulation with democratic-process impact; accelerated mitigation required.",
                "legalBasis": "Regulation (EU) 2022/2065 Article 34; Regulation (EU) 2024/1689 Article 50",
            }
        if impact >= 0.45:
            return {
                "level": "HEIGHTENED MONITORING",
                "rationale": "Credible risk indicators are present; structured verification and proportional response should begin.",
                "legalBasis": "Regulation (EU) 2022/2065 Article 26; Regulation (EU) 2016/679 Article 5",
            }
        return {
            "level": "ROUTINE SURVEILLANCE",
            "rationale": "No high-confidence democratic impact signal currently detected.",
            "legalBasis": "Regulation (EU) 2016/679 Article 5",
        }

    items = db.query(Item).order_by(Item.created_at.desc()).all()
    total = len(items)
    done = sum(1 for i in items if i.status == "done")
    pending = sum(1 for i in items if i.status == "pending")
    escalated = sum(1 for i in items if i.status == "escalated")

    avg_deepfake = 0.0
    avg_disinfo_impact = 0.0
    if total:
        avg_deepfake = sum((i.deepfake_risk or 0.0) for i in items) / total
        avg_disinfo_impact = sum((i.disinformation_impact or 0.0) for i in items) / total

    election_enabled = get_setting(db, "election_mode", "false") == "true"
    threshold = 0.30 if election_enabled else 0.45

    high_risk = [
        {
            **escalation_profile(i.disinformation_impact or 0.0),
            "itemId": i.id,
            "headline": i.headline or intelligence.headline_from_narrative(i.narrative or "", i.raw_text or ""),
            "deepfakeRisk": i.deepfake_risk or 0.0,
            "coordinationScore": i.coordination_score or 0.0,
            "disinformationImpact": i.disinformation_impact or 0.0,
            "createdAt": i.created_at,
            "status": i.status,
        }
        for i in sorted(items, key=lambda row: (row.disinformation_impact or 0.0), reverse=True)
        if (i.disinformation_impact or 0.0) >= threshold
    ][:6]

    return {
        "totalItems": total,
        "processedItems": done,
        "pendingItems": pending,
        "escalatedItems": escalated,
        "averageDeepfakeRisk": round(avg_deepfake, 3),
        "averageDisinformationImpact": round(avg_disinfo_impact, 3),
        "highRiskQueue": high_risk,
        "electionMode": election_enabled,
        "policyFrame": [
            "Regulation (EU) 2024/1689 Article 50: transparency notice required for synthetic or AI-manipulated content.",
            "Regulation (EU) 2024/1689 Article 5: prohibited-practice checks (including social scoring and sensitive biometric misuse).",
            "Regulation (EU) 2016/679 Articles 5-6: data minimisation, purpose limitation, and lawful basis must be documented.",
            "Regulation (EU) 2022/2065 Articles 26 and 34-35 plus Regulation (EU) 2024/900: sponsor transparency and systemic-risk mitigation for political content.",
        ],
    }


@app.get("/api/dashboard/geo", response_model=schemas.GeoBreakdown)
async def dashboard_geo(db: Session = Depends(get_db)) -> schemas.GeoBreakdown:
    items = db.query(Item).all()
    breakdown = intelligence.aggregate_geo(items)
    return schemas.GeoBreakdown(
        countries=breakdown["countries"],
        languages=breakdown["languages"],
        total=len(items),
    )


@app.get("/api/audit", response_model=List[schemas.AuditEventOut])
async def list_audit(limit: int = 25, db: Session = Depends(get_db)) -> List[schemas.AuditEventOut]:
    events = (
        db.query(AuditEvent)
        .order_by(AuditEvent.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )
    return [
        schemas.AuditEventOut(
            id=e.id,
            itemId=e.item_id,
            actor=e.actor,
            action=e.action,
            detail=e.detail,
            legalBasis=e.legal_basis,
            createdAt=e.created_at,
        )
        for e in events
    ]


# ---------------------------------------------------------------------------
# Demo replay - seeds three scripted dossiers for risk-free pitch demos
# ---------------------------------------------------------------------------


_DEMO_SCENARIOS = [
    {
        "narrative": "AI generated speech impersonating Minister Marin claims new emergency tax law was approved in Brussels yesterday and instructs voters to skip Sunday's polling.",
        "claims": [
            "Minister Marin announced a new emergency tax law passed in Brussels",
            "Voters are instructed to skip Sunday's parliamentary election",
        ],
        "entities": ["Minister Marin", "Brussels", "Parliamentary Election", "Sunday Vote"],
        "country": "FI", "language": "en",
        "disinfo": 0.94, "deepfake": 0.88, "coordination": 0.71,
        "headline": "Synthetic audio impersonating Minister Marin urges voters to skip Sunday's election",
        "legal_flags": [
            "Regulation (EU) 2024/1689 Article 50 - undisclosed synthetic audio violates transparency duty",
            "Regulation (EU) 2022/2065 Article 34 - systemic risk to electoral process from coordinated amplification",
            "Regulation (EU) 2022/2065 Article 35 - mitigation measures must be triggered without delay",
            "Regulation (EU) 2024/900 - undisclosed political message lacks sponsor transparency",
        ],
        "actions": [
            "Issue rapid facts-first statement in EN/FI within 30 minutes (AI Act Art. 50).",
            "File DSA Art. 16 trusted-flagger notice to all amplifying platforms (DSA Art. 22).",
            "Notify national electoral integrity desk and Europol IRU (DSA Art. 35).",
        ],
    },
    {
        "narrative": "Coordinated network of accounts in three languages claims polling stations in Marseille have been moved to a different district and shares fake municipal letterhead.",
        "claims": [
            "Polling stations in Marseille have been relocated",
            "Citizens must use a new fake address provided in the post",
        ],
        "entities": ["Marseille", "Polling Stations", "Municipal Authority"],
        "country": "FR", "language": "fr",
        "disinfo": 0.91, "deepfake": 0.42, "coordination": 0.84,
        "headline": "Coordinated multi-language network claims Marseille polling stations have moved",
        "legal_flags": [
            "Regulation (EU) 2022/2065 Article 34 - coordinated inauthentic behaviour targeting elections",
            "Regulation (EU) 2024/900 Article 7 - sponsor transparency missing on amplified posts",
            "Regulation (EU) 2016/679 Article 5 - personal data of citizens used without lawful basis",
        ],
        "actions": [
            "Publish authoritative polling-station map with QR-verified municipal source.",
            "Open DSA Art. 22 trusted-flagger reports across the four amplifying platforms.",
            "Engage EDMO French hub for cross-checking and corrective amplification.",
        ],
    },
    {
        "narrative": "Paid promoted clip alleges opposition candidate confessed to election fraud in a leaked video; provenance metadata is missing and audio waveform shows splice artefacts.",
        "claims": [
            "Opposition candidate confessed to election fraud on a leaked video",
        ],
        "entities": ["Opposition Candidate", "Leaked Video", "Election Fraud"],
        "country": "DE", "language": "de",
        "disinfo": 0.78, "deepfake": 0.81, "coordination": 0.53,
        "headline": "Promoted deepfake clip falsely shows opposition candidate confessing to fraud",
        "legal_flags": [
            "Regulation (EU) 2024/1689 Article 50 - manipulated audio without disclosure",
            "Regulation (EU) 2022/2065 Article 26 - paid political ad lacks proper labelling",
            "Regulation (EU) 2024/900 - sponsor identity and amount disclosure missing",
        ],
        "actions": [
            "Request platform to apply Art. 35 mitigation: demote, label and notify exposed users.",
            "Refer the asset to the national audiovisual regulator for provenance review.",
            "Brief candidate office and prepare correction with C2PA-verified statement.",
        ],
    },
    {
        "narrative": "AI-generated fake EU Directive draft circulating on messaging apps claims an immediate 60% tax on farm diesel starting Monday, igniting calls for tractor blockades across all major ports.",
        "claims": [
            "EU passed a surprise 60% tax increase on agricultural diesel effective Monday",
            "Emergency tractor blockades ordered at Rotterdam and Antwerp ports"
        ],
        "entities": ["EU Commission", "Port of Rotterdam", "Port of Antwerp", "Farmers Union"],
        "country": "NL", "language": "nl",
        "disinfo": 0.96, "deepfake": 0.70, "coordination": 0.93,
        "headline": "Fabricated EU Directive on diesel tax sparks coordinated port blockade threats",
        "legal_flags": [
            "Regulation (EU) 2022/2065 Article 34 - systemic risk to public security and critical infrastructure",
            "Regulation (EU) 2024/1689 Article 50 - AI-generated official document without disclosure",
            "National law - incitement to disrupt critical economic infrastructure"
        ],
        "actions": [
            "Activate EU civil protection mechanism for port coordination (Critical Infrastructure).",
            "Demand immediate platform takedown of the fake directive PDF via DSA Art. 16.",
            "Commission spokesperson to issue debunking statement directly to agricultural press.",
        ],
    },
    {
        "narrative": "A network of bot accounts on a major social media platform is aggressively amplifying a deepfake video of a prominent civil rights leader urging supporters to boycott upcoming national elections, claiming electronic voting machines are rigged.",
        "claims": [
            "Leading civil rights advocate tells followers to boycott the elections",
            "Electronic voting machines have been pre-programmed to rig the outcome"
        ],
        "entities": ["Civil Rights Leader ID", "National Electoral Commission", "Electronic Voting Machines"],
        "country": "ES", "language": "es",
        "disinfo": 0.88, "deepfake": 0.95, "coordination": 0.98,
        "headline": "Botnet driving deepfake boycott campaign targeting minority voting districts",
        "legal_flags": [
            "Regulation (EU) 2024/1689 Article 50 - malicious use of synthetic media in electoral context",
            "Regulation (EU) 2022/2065 Article 35 - crisis protocol required for election manipulation",
            "Article 14 - coordinated inauthentic behavior"
        ],
        "actions": [
            "Invoke DSA crisis protocol (Art. 36) for immediate bot network suspension.",
            "Coordinate with national cyber police to trace botnet origin.",
            "Publish verified repudiation video from the targeted civil rights leader.",
        ],
    }
]



@app.post("/api/demo/replay", response_model=schemas.DemoReplayResult)
async def demo_replay(db: Session = Depends(get_db)) -> schemas.DemoReplayResult:
    seeded_ids = []
    for scenario in _DEMO_SCENARIOS:
        item = Item(
            content_type="text",
            raw_text=scenario["narrative"],
            narrative=scenario["narrative"],
            headline=scenario["headline"],
            entities=scenario["entities"],
            claims=scenario["claims"],
            deepfake_risk=scenario["deepfake"],
            coordination_score=scenario["coordination"],
            disinformation_impact=scenario["disinfo"],
            confidence=intelligence.confidence_band(
                scenario["disinfo"], scenario["deepfake"], scenario["coordination"],
            ),
            detected_country=scenario["country"],
            detected_language=scenario["language"],
            legal_flags=scenario["legal_flags"],
            recommended_actions=scenario["actions"],
            policy_recommendations=[
                "Days 1-15: assign duty owner and finalise escalation path.",
                "Days 16-45: run live pilot with weekly cadence.",
                "Days 46-75: expand cross-team training and calibrate thresholds.",
                "Days 76-90: publish KPI memo and scale-up decision.",
            ],
            brief=(
                f"EU AI Act Threat Level: High Risk\n\n"
                f"Synopsis: {scenario['narrative']}\n\n"
                "AI-assisted analysis (EU AI Act Article 50 transparency).\n\n"
                f"Narrative: {scenario['narrative']}\n\n"
                f"Entities: {', '.join(scenario['entities'])}\n\n"
                "Claims:\n" + "\n".join([f"- {c}" for c in scenario['claims']])
            ),
            status="escalated" if scenario["disinfo"] >= 0.85 else "done",
            transparency_published="true",
            created_at=datetime.utcnow(),
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        seeded_ids.append(item.id)

        record_event(db, item_id=item.id, action="dossier.created", detail="Seeded by red-team replay", actor="red team")
        record_event(db, item_id=item.id, action="analysis.completed", detail=f"Mislead-citizens risk {int(scenario['disinfo']*100)}%", legal_basis="AI Act Art. 50")
        if item.status == "escalated":
            record_event(db, item_id=item.id, action="auto.escalated", detail="Auto-escalation on emergency threshold", legal_basis="DSA Art. 35")
        record_event(db, item_id=item.id, action="transparency.published", detail="Mirrored to public transparency ledger", legal_basis="DSA Art. 24")

    return schemas.DemoReplayResult(seeded=len(seeded_ids), itemIds=seeded_ids)


@app.delete("/api/demo/replay")
async def clear_demo(db: Session = Depends(get_db)):
    items = db.query(Item).all()
    deleted = 0
    for item in items:
        if (item.headline or "").startswith((
            "Synthetic audio impersonating Minister Marin",
            "Coordinated multi-language network",
            "Promoted deepfake clip falsely",
        )):
            db.delete(item)
            deleted += 1
    db.commit()
    record_event(db, item_id=None, action="demo.cleared", detail=f"Removed {deleted} seeded dossiers")
    return {"deleted": deleted}


# ---------------------------------------------------------------------------
# Toolkit
# ---------------------------------------------------------------------------


@app.post("/api/toolkit/incidents", response_model=schemas.ToolkitIncidentSummary)
async def create_toolkit_incident(
    payload: schemas.ToolkitIncidentCreate,
    db: Session = Depends(get_db),
) -> schemas.ToolkitIncidentSummary:
    incident = ToolkitIncident(
        what_happened=payload.whatHappened.strip(),
        spread_channels=(payload.spreadChannels or "").strip(),
        targeted_groups=(payload.targetedGroups or "").strip(),
        claim_summary=(payload.claimSummary or "").strip(),
        confidence_evidence=(payload.confidenceEvidence or "").strip(),
        owner_deadline=(payload.ownerDeadline or "").strip(),
        recommended_action=(payload.recommendedAction or "").strip(),
        triage_flags=payload.triageFlags,
        notes=(payload.notes or "").strip(),
        risk_likelihood=payload.riskLikelihood,
        risk_reach=payload.riskReach,
        risk_urgency=payload.riskUrgency,
        risk_score=payload.riskScore,
        risk_band=payload.riskBand,
        created_at=datetime.utcnow(),
    )

    db.add(incident)
    db.commit()
    db.refresh(incident)

    record_event(db, item_id=None, action="toolkit.incident_logged", detail=incident.what_happened[:120])

    return schemas.ToolkitIncidentSummary(
        incidentId=incident.id,
        whatHappened=incident.what_happened,
        riskScore=incident.risk_score,
        riskBand=incident.risk_band,
        recommendedAction=incident.recommended_action,
        createdAt=incident.created_at,
    )


@app.get("/api/toolkit/incidents", response_model=List[schemas.ToolkitIncidentSummary])
async def list_toolkit_incidents(db: Session = Depends(get_db)) -> List[schemas.ToolkitIncidentSummary]:
    incidents = db.query(ToolkitIncident).order_by(ToolkitIncident.created_at.desc()).limit(25).all()
    return [
        schemas.ToolkitIncidentSummary(
            incidentId=i.id,
            whatHappened=i.what_happened,
            riskScore=i.risk_score,
            riskBand=i.risk_band,
            recommendedAction=i.recommended_action,
            createdAt=i.created_at,
        )
        for i in incidents
    ]


@app.get("/api/toolkit/incidents/{incident_id}", response_model=schemas.ToolkitIncidentDetail)
async def get_toolkit_incident(incident_id: str, db: Session = Depends(get_db)) -> schemas.ToolkitIncidentDetail:
    incident = db.query(ToolkitIncident).filter(ToolkitIncident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    return schemas.ToolkitIncidentDetail(
        incidentId=incident.id,
        whatHappened=incident.what_happened,
        spreadChannels=incident.spread_channels or "",
        targetedGroups=incident.targeted_groups or "",
        claimSummary=incident.claim_summary or "",
        confidenceEvidence=incident.confidence_evidence or "",
        ownerDeadline=incident.owner_deadline or "",
        recommendedAction=incident.recommended_action or "",
        triageFlags=incident.triage_flags or [],
        notes=incident.notes or "",
        riskLikelihood=incident.risk_likelihood,
        riskReach=incident.risk_reach,
        riskUrgency=incident.risk_urgency,
        riskScore=incident.risk_score,
        riskBand=incident.risk_band,
        createdAt=incident.created_at,
    )
