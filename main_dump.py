from datetime import datetime
from typing import Dict, List

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import analysis
import schemas
from database import Base, engine, get_db
from models import Item
from rules_engine import check_compliance

Base.metadata.create_all(bind=engine)

app = FastAPI(title="PDIP API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def process_item(item_id: str) -> None:
    db = next(get_db())
    try:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            return

        source_text = item.raw_text or ""
        if item.url and not source_text:
            source_text = analysis.scrape_url(item.url)
            item.raw_text = source_text

        extraction = analysis.extract_claims(source_text)

        item.claims = extraction.get("claims", [])
        item.entities = extraction.get("entities", [])
        
        ai_prob, coord_score, synopsis, threat_level, narrative = analysis.analyze_content(source_text)
        
        item.deepfake_risk = ai_prob
        item.coordination_score = coord_score
        item.narrative = narrative
        item.legal_flags = check_compliance(
            {
                "deepfake_risk": item.deepfake_risk,
                "raw_text": item.raw_text or "",
                "entities": item.entities or [],
            }
        )
        item.brief = analysis.generate_brief(item.narrative, item.entities, item.claims, synopsis, threat_level)
        item.status = "done"
        db.commit()
    finally:
        db.close()


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

    background_tasks.add_task(process_item, item.id)

    return schemas.ItemSummary(itemId=item.id, status=item.status, createdAt=item.created_at)


@app.get("/api/items", response_model=List[schemas.ItemSummary])
async def list_items(db: Session = Depends(get_db)) -> List[schemas.ItemSummary]:
    items = db.query(Item).order_by(Item.created_at.desc()).all()
    return [
        schemas.ItemSummary(itemId=i.id, status=i.status, createdAt=i.created_at) for i in items
    ]


@app.get("/api/items/{item_id}", response_model=schemas.ItemDetail)
async def get_item(item_id: str, db: Session = Depends(get_db)) -> schemas.ItemDetail:
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    return schemas.ItemDetail(
        itemId=item.id,
        narrative=item.narrative or "",
        entities=item.entities or [],
        claims=item.claims or [],
        deepfakeRisk=item.deepfake_risk or 0.0,
        coordinationScore=item.coordination_score or 0.0,
        legalFlags=item.legal_flags or [],
        brief=item.brief or "",
        status=item.status,
        recommendedActions=build_recommended_actions(item),
    )


@app.get("/api/items/{item_id}/export")
async def export_item(item_id: str, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return {
        "itemId": item.id,
        "format": "text",
        "brief": item.brief or "",
        "label": "AI-assisted analysis (EU AI Act Article 50 transparency)",
    }


@app.get("/api/dashboard/stats")
async def dashboard_stats(db: Session = Depends(get_db)) -> Dict:
    items = db.query(Item).order_by(Item.created_at.desc()).all()
    total = len(items)
    done = sum(1 for i in items if i.status == "done")
    pending = total - done

    avg_deepfake = 0.0
    if total:
        avg_deepfake = sum((i.deepfake_risk or 0.0) for i in items) / total

    high_risk = [
        {
            "itemId": i.id,
            "deepfakeRisk": i.deepfake_risk or 0.0,
            "coordinationScore": i.coordination_score or 0.0,
            "createdAt": i.created_at,
            "status": i.status,
        }
        for i in items
        if (i.deepfake_risk or 0.0) >= 0.7 or (i.coordination_score or 0.0) >= 0.7
    ][:5]

    return {
        "totalItems": total,
        "processedItems": done,
        "pendingItems": pending,
        "averageDeepfakeRisk": round(avg_deepfake, 3),
        "highRiskQueue": high_risk,
        "policyFrame": [
            "EU AI Act Article 50 transparency notice required for synthetic content.",
            "AI Act Article 5 prohibited use checks: no biometric inference/social scoring.",
            "GDPR data minimisation and storage limitation must be enforced.",
            "DSA and Political Ads Reg checks for sponsor disclosure.",
        ],
    }


def build_recommended_actions(item: Item) -> List[str]:
    actions: List[str] = []

    if (item.deepfake_risk or 0.0) >= 0.7:
        actions.append("Trigger media verification workflow and include AI-generated content disclosure.")
    if (item.coordination_score or 0.0) >= 0.7:
        actions.append("Escalate to platform integrity liaison for suspected coordinated amplification.")
    if any("Political Ads" in flag or "DSA" in flag for flag in (item.legal_flags or [])):
        actions.append("Cross-check sponsor transparency in EU political advertising repository.")

    if not actions:
        actions.append("Monitor and archive; no urgent regulatory escalation required at this stage.")

    actions.append("Keep human review in the loop before any public communication or escalation.")
    return actions

