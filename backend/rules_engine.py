from typing import Dict, List

import yaml


def load_rules(path: str = "rules.yaml") -> Dict:
    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def check_compliance(item: Dict) -> List[str]:
    rules = load_rules()
    flags: List[str] = []

    ai_act = rules.get("AI_Act", {})
    deepfake_threshold = ai_act.get("deepfake_threshold", 0.7)
    deepfake_risk = float(item.get("deepfake_risk", 0.0) or 0.0)
    if deepfake_risk > deepfake_threshold:
        flags.append("Regulation (EU) 2024/1689 Article 50 - deepfake disclosure likely required.")

    text = (item.get("raw_text") or "").lower()
    prohibited_patterns = ai_act.get("prohibited_patterns", [])
    for pattern in prohibited_patterns:
        if pattern.lower() in text:
            flags.append(f"Regulation (EU) 2024/1689 Article 5 - prohibited pattern detected ({pattern}).")

    if "paid" in text and "sponsor" not in text:
        flags.append("Regulation (EU) 2024/900 and Regulation (EU) 2022/2065 Article 26 - possible undeclared sponsored political content.")

    if "polling station" in text and any(k in text for k in ["closed", "moved", "cancelled"]):
        flags.append("Regulation (EU) 2022/2065 Articles 34-35 - election-integrity systemic risk requires verification and mitigation workflow.")

    if "ai generated" in text and "label" not in text:
        flags.append("Regulation (EU) 2024/1689 Article 50 - AI-generated public-interest text appears unlabeled.")

    if len(item.get("entities", [])) > 5:
        flags.append("Regulation (EU) 2016/679 Article 5 - review data minimisation for personal data exposure.")

    return flags
