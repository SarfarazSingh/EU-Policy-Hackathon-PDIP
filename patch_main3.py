import re

with open("backend/main.py", "r") as f:
    content = f.read()

# Remove the check_compliance from imports
content = content.replace("from rules_engine import check_compliance\n", "")

# Change the unpack of analyze_content inside process_item
old_process_item_logic = """        ai_prob, coord_score, synopsis, threat_level, narrative = analysis.analyze_content(source_text)
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
        item.brief = analysis.generate_brief(item.narrative, item.entities, item.claims, synopsis, threat_level)"""

new_process_item_logic = """        ai_prob, coord_score, synopsis, threat_level, narrative, legal_flags, rec_actions = analysis.analyze_content(source_text)
        item.deepfake_risk = ai_prob
        item.coordination_score = coord_score
        item.narrative = narrative
        item.legal_flags = legal_flags
        item.recommended_actions = rec_actions
        item.brief = analysis.generate_brief(item.narrative, item.entities, item.claims, synopsis, threat_level)"""

content = content.replace(old_process_item_logic, new_process_item_logic)

# Replace build_recommended_actions call
content = content.replace("recommendedActions=build_recommended_actions(item),", "recommendedActions=item.recommended_actions or [],")

# Remove build_recommended_actions function
content = re.sub(r"def build_recommended_actions.*?\n    return actions\n", "", content, flags=re.DOTALL)

with open("backend/main.py", "w") as f:
    f.write(content)
