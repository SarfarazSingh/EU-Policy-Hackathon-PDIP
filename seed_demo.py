import ast
import os
from datetime import datetime

# Read the demo scenarios directly from backend/main.py without importing main
root = os.getcwd()
main_path = os.path.join(root, "backend", "main.py")
with open(main_path, "r") as f:
    src = f.read()

start = src.find("_DEMO_SCENARIOS")
if start == -1:
    raise SystemExit("_DEMO_SCENARIOS not found in backend/main.py")

bracket = src.find("[", start)
count = 0
end = bracket
for i, ch in enumerate(src[bracket:], start=bracket):
    if ch == "[":
        count += 1
    elif ch == "]":
        count -= 1
        if count == 0:
            end = i + 1
            break

list_src = src[bracket:end]
scenarios = ast.literal_eval(list_src)

# Ensure backend directory is on the import path so backend modules import cleanly
import sys
sys.path.insert(0, os.path.join(root, "backend"))

# Now import DB and models (use sqlite DB for local seeding)
from backend.database import engine, SessionLocal, Base
from backend.models import Item
import backend.intelligence as intelligence

# Ensure tables exist for sqlite fallback
Base.metadata.create_all(bind=engine)

DB = SessionLocal()
seeded = []

for scenario in scenarios:
    existing = DB.query(Item).filter(Item.headline == scenario.get("headline")).first()
    if existing:
        continue

    item = Item(
        content_type="text",
        raw_text=scenario.get("narrative"),
        narrative=scenario.get("narrative"),
        headline=scenario.get("headline"),
        entities=scenario.get("entities"),
        claims=scenario.get("claims"),
        deepfake_risk=scenario.get("deepfake"),
        coordination_score=scenario.get("coordination"),
        disinformation_impact=scenario.get("disinfo"),
        confidence=intelligence.confidence_band(
            scenario.get("disinfo"), scenario.get("deepfake"), scenario.get("coordination")
        ),
        detected_country=scenario.get("country"),
        detected_language=scenario.get("language"),
        legal_flags=scenario.get("legal_flags"),
        recommended_actions=scenario.get("actions"),
        policy_recommendations=[
            "Days 1-15: assign duty owner and finalise escalation path.",
            "Days 16-45: run live pilot with weekly cadence.",
            "Days 46-75: expand cross-team training and calibrate thresholds.",
            "Days 76-90: publish KPI memo and scale-up decision.",
        ],
        brief=(
            f"EU AI Act Threat Level: High Risk\n\n"
            f"Synopsis: {scenario.get('narrative')}\n\n"
            "AI-assisted analysis (EU AI Act Article 50 transparency).\n\n"
            f"Narrative: {scenario.get('narrative')}\n\n"
            f"Entities: {', '.join(scenario.get('entities', []))}\n\n"
            "Claims:\n" + "\n".join([f"- {c}" for c in scenario.get('claims', [])])
        ),
        status="escalated" if scenario.get("disinfo", 0) >= 0.85 else "done",
        transparency_published="true",
        created_at=datetime.utcnow(),
    )

    DB.add(item)
    DB.commit()
    DB.refresh(item)
    seeded.append(item.id)

print(f"Seeded {len(seeded)} new demo dossiers: {seeded}")
