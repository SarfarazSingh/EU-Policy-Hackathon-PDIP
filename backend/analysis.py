import json
import os
import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Tuple
try:
    from .governance import GOVERNANCE_CONTEXT
except ImportError:
    from governance import GOVERNANCE_CONTEXT

from dotenv import load_dotenv
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "")) if OpenAI else None

CORE_LEGAL_ANCHORS = {
    "ai_act": [
        "Regulation (EU) 2024/1689 Article 5 - prohibited AI practices",
        "Regulation (EU) 2024/1689 Article 9 - risk management system",
        "Regulation (EU) 2024/1689 Article 10 - data and data governance",
        "Regulation (EU) 2024/1689 Article 14 - human oversight",
        "Regulation (EU) 2024/1689 Article 50 - transparency obligations for certain AI systems",
    ],
    "dsa": [
        "Regulation (EU) 2022/2065 Article 26 - advertising transparency",
        "Regulation (EU) 2022/2065 Article 34 - systemic risk assessment",
        "Regulation (EU) 2022/2065 Article 35 - risk mitigation measures",
        "Regulation (EU) 2022/2065 Article 40 - vetted researcher data access",
    ],
    "gdpr": [
        "Regulation (EU) 2016/679 Article 5 - data processing principles",
        "Regulation (EU) 2016/679 Article 6 - lawfulness of processing",
        "Regulation (EU) 2016/679 Article 9 - special categories of personal data",
        "Regulation (EU) 2016/679 Article 22 - automated individual decision-making",
        "Regulation (EU) 2016/679 Article 25 - data protection by design and by default",
    ],
    "political_ads": [
        "Regulation (EU) 2024/900 - political advertising transparency and targeting restrictions",
    ],
}

POLICY_RECOMMENDATION_FRAMEWORK = {
    "phase_1": "Days 1-15: designate policy owner and operations owner, define escalation ownership, and align workflow protocol.",
    "phase_2": "Days 16-45: run supervised pilot handling live incidents with weekly reporting cadence and legal citation checks.",
    "phase_3": "Days 46-75: expand training for policy, communications, and operations teams; calibrate thresholds and response templates.",
    "phase_4": "Days 76-90: evaluate KPI results, publish policy recommendation memo, and make scale-up decision.",
}

def scrape_url(url: str) -> str:
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]):
            script.extract()
        text = soup.get_text(separator=' ')
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        return text[:4000]
    except Exception as e:
        return f"Failed to scrape URL {url}: {str(e)}"

def extract_claims(text: str) -> Dict[str, List[str]]:
    if not os.getenv("OPENAI_API_KEY") or client is None:
        return {"claims": ["Placeholder"], "entities": ["Placeholder"]}
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Extract claims and entities. Return JSON with 'claims' and 'entities'."},
                      {"role": "user", "content": text}],
            response_format={ "type": "json_object" },
            temperature=0,
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        claims = parsed.get("claims", [])
        entities = parsed.get("entities", [])
        
        # Ensure they are lists of strings
        safe_claims = [str(c) if not isinstance(c, dict) else str(c.get('claim', c.get('name', c))) for c in claims]
        safe_entities = [str(e) if not isinstance(e, dict) else str(e.get('name', e.get('entity', e))) for e in entities]
        return {"claims": safe_claims, "entities": safe_entities}
    except Exception:
        return {"claims": ["LLM failed"], "entities": []}

def assess_deepfake(content: str) -> float:
    # Retained for fallback, but AI detection is now handled by analyze_ai_and_threat
    lowered = (content or "").lower()
    if "deepfake" in lowered or "ai generated" in lowered:
        return 0.85
    return 0.2


def _clamp_score(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _impact_signal_profile(text: str) -> Dict[str, object]:
    lowered = (text or "").lower()

    election_terms = [
        "election", "ballot", "vote", "voter", "polling station", "constituency",
        "parliament", "candidate", "campaign", "electoral",
    ]
    democratic_harm_terms = [
        "mislead", "fraud", "rigged", "cancelled", "moved", "suppressed",
        "boycott", "illegitimate", "fake result", "disenfranchise",
    ]
    amplification_terms = [
        "viral", "share now", "trending", "network", "bot", "coordinated", "amplif",
    ]
    synthetic_terms = [
        "deepfake", "synthetic", "ai-generated", "ai generated", "voice clone", "impersonat",
    ]
    benign_context_terms = [
        "report", "analysis", "hearing", "committee", "press release", "statement",
        "interview", "coverage", "briefing", "explainer", "proposal", "debate",
    ]

    election_hits = sum(1 for t in election_terms if t in lowered)
    harm_hits = sum(1 for t in democratic_harm_terms if t in lowered)
    amp_hits = sum(1 for t in amplification_terms if t in lowered)
    synth_hits = sum(1 for t in synthetic_terms if t in lowered)
    benign_hits = sum(1 for t in benign_context_terms if t in lowered)

    harm_signal = harm_hits > 0
    amp_signal = amp_hits > 0
    synth_signal = synth_hits > 0
    topic_signal = election_hits > 0
    benign_context = benign_hits > 0 and not (harm_signal or amp_signal or synth_signal)

    return {
        "lowered": lowered,
        "election_hits": election_hits,
        "harm_hits": harm_hits,
        "amp_hits": amp_hits,
        "synth_hits": synth_hits,
        "harm_signal": harm_signal,
        "amp_signal": amp_signal,
        "synth_signal": synth_signal,
        "topic_signal": topic_signal,
        "benign_context": benign_context,
    }


def _estimate_disinformation_impact(text: str, synthetic_risk: float, coordination_score: float) -> float:
    signals = _impact_signal_profile(text)
    lowered = str(signals["lowered"])
    election_hits = int(signals["election_hits"])
    harm_hits = int(signals["harm_hits"])
    amp_hits = int(signals["amp_hits"])
    synth_hits = int(signals["synth_hits"])
    harm_signal = bool(signals["harm_signal"])
    amp_signal = bool(signals["amp_signal"])
    synth_signal = bool(signals["synth_signal"])
    topic_signal = bool(signals["topic_signal"])
    benign_context = bool(signals["benign_context"])

    # Prioritize democratic harm and election manipulation impact over synthetic origin alone.
    score = 0.02
    score += min(0.16, election_hits * 0.04)
    score += min(0.38, harm_hits * 0.12)
    score += min(0.22, amp_hits * 0.08)
    score += min(0.18, synth_hits * 0.07)

    score += 0.10 * _clamp_score(coordination_score)
    score += 0.05 * _clamp_score(synthetic_risk)

    if topic_signal and not (harm_signal or amp_signal or synth_signal):
        score = min(score, 0.22)

    if benign_context:
        score = min(score, 0.15)

    if "polling station" in lowered and any(k in lowered for k in ["moved", "closed", "cancelled"]):
        score = max(score, 0.92)
    if any(k in lowered for k in ["do not vote", "voting postponed", "election cancelled"]):
        score = max(score, 0.95)

    return _clamp_score(score)


def _contains_policy_citation(text: str) -> bool:
    if not text:
        return False
    citation_pattern = re.compile(
        r"(Regulation \(EU\) \d{4}/\d+|AI Act|DSA|GDPR).{0,120}?(Article|Art\.)\s*\d+[a-zA-Z-]*",
        re.IGNORECASE,
    )
    return bool(citation_pattern.search(text))


def _has_article_citation(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r"(Article|Art\.)\s*\d+[a-zA-Z-]*", text, re.IGNORECASE))


def _append_unique(items: List[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _augment_legal_flags(legal_flags: List[str], text: str) -> List[str]:
    flags = [str(flag).strip() for flag in (legal_flags or []) if str(flag).strip()]
    lowered = (text or "").lower()

    has_ai = any("2024/1689" in f or "ai act" in f.lower() for f in flags)
    has_dsa = any("2022/2065" in f or "dsa" in f.lower() for f in flags)
    has_gdpr = any("2016/679" in f or "gdpr" in f.lower() for f in flags)

    if not has_ai:
        if any(token in lowered for token in ["deepfake", "synthetic", "ai generated"]):
            _append_unique(flags, "Regulation (EU) 2024/1689 Article 50 - AI-generated or manipulated content may trigger transparency duties")
        else:
            _append_unique(flags, "Regulation (EU) 2024/1689 Article 9 - risk-management controls should be documented for high-risk deployment scenarios")

    if not has_dsa:
        if any(token in lowered for token in ["platform", "viral", "amplification", "recommendation"]):
            _append_unique(flags, "Regulation (EU) 2022/2065 Article 34 - potential systemic-risk vector requiring assessment")
            _append_unique(flags, "Regulation (EU) 2022/2065 Article 35 - mitigation measures may be required for identified systemic risks")
        else:
            _append_unique(flags, "Regulation (EU) 2022/2065 Article 26 - ad/transparency disclosures should be assessed")

    if not has_gdpr:
        _append_unique(flags, "Regulation (EU) 2016/679 Article 5 - data minimisation and purpose limitation review required")
        if any(token in lowered for token in ["biometric", "ethnicity", "religion", "health"]):
            _append_unique(flags, "Regulation (EU) 2016/679 Article 9 - special-category data processing safeguards may apply")

    if any(token in lowered for token in ["election", "campaign", "candidate", "political ad", "sponsor"]):
        _append_unique(flags, CORE_LEGAL_ANCHORS["political_ads"][0])

    final_flags = []
    for flag in flags:
        if _has_article_citation(flag) or "2024/900" in flag:
            final_flags.append(flag)

    if not final_flags:
        final_flags = [
            CORE_LEGAL_ANCHORS["ai_act"][4],
            CORE_LEGAL_ANCHORS["dsa"][1],
            CORE_LEGAL_ANCHORS["gdpr"][0],
        ]
    return final_flags[:8]


def _augment_recommended_actions(actions: List[str], legal_flags: List[str]) -> List[str]:
    final_actions = [str(action).strip() for action in (actions or []) if str(action).strip()]
    joined_flags = " ".join(legal_flags).lower()

    if "article 50" in joined_flags:
        _append_unique(final_actions, "Add prominent AI-content disclosure and provenance labeling controls (Regulation (EU) 2024/1689 Article 50).")
    if "article 34" in joined_flags or "article 35" in joined_flags:
        _append_unique(final_actions, "Run and document systemic risk assessment plus mitigation plan for distribution vectors (Regulation (EU) 2022/2065 Articles 34-35).")
    if "article 5" in joined_flags and "2016/679" in joined_flags:
        _append_unique(final_actions, "Apply data-minimisation and lawful-basis checks before retention or enrichment of personal data (Regulation (EU) 2016/679 Articles 5-6).")
    if "2024/900" in joined_flags:
        _append_unique(final_actions, "Verify political-ad sponsor transparency and targeting compliance under Regulation (EU) 2024/900 before amplification.")

    if not final_actions:
        final_actions = [
            "Document legal basis and transparency posture before publication (Regulation (EU) 2024/1689 Article 50; Regulation (EU) 2016/679 Article 5).",
            "Escalate to policy/compliance review for systemic-risk screening (Regulation (EU) 2022/2065 Articles 34-35).",
        ]

    return final_actions[:8]


def _enforce_policy_synopsis(synopsis: str, legal_flags: List[str], threat_level: str) -> str:
    clean_synopsis = (synopsis or "").strip()
    if _contains_policy_citation(clean_synopsis):
        return clean_synopsis

    cited_flags = [flag.strip() for flag in (legal_flags or []) if "article" in flag.lower()]
    cited_flags = cited_flags[:4]

    policy_basis = (
        "; ".join(cited_flags)
        if cited_flags
        else "Regulation (EU) 2024/1689 Article 50; Regulation (EU) 2022/2065 Article 34; Regulation (EU) 2016/679 Article 5"
    )

    if clean_synopsis:
        return (
            "Policy synopsis: "
            f"{clean_synopsis} "
            f"Legal basis: {policy_basis}. "
            f"Risk posture: {threat_level}."
        )

    return (
        "Policy synopsis unavailable from model output. "
        f"Legal basis: {policy_basis}. "
        f"Risk posture: {threat_level}."
    )


def _build_policy_recommendations(
    text: str,
    disinformation_impact: float,
    coordination_score: float,
    legal_flags: List[str],
    recommended_actions: List[str],
) -> List[str]:
    lowered = (text or "").lower()
    recommendations: List[str] = [
        POLICY_RECOMMENDATION_FRAMEWORK["phase_1"],
        POLICY_RECOMMENDATION_FRAMEWORK["phase_2"],
        POLICY_RECOMMENDATION_FRAMEWORK["phase_3"],
        POLICY_RECOMMENDATION_FRAMEWORK["phase_4"],
        "KPI baseline should include alert-to-triage time, decision-to-publication time, citation completeness, and recurrence reduction.",
    ]

    if disinformation_impact >= 0.85:
        _append_unique(
            recommendations,
            "Immediate emergency recommendation: activate cross-unit crisis response cell, issue holding statement, and trigger election-integrity escalation protocol.",
        )
    elif disinformation_impact >= 0.65:
        _append_unique(
            recommendations,
            "Priority recommendation: begin accelerated mitigation workflow, publish corrective narrative rapidly, and start daily monitoring brief.",
        )

    if coordination_score >= 0.65:
        _append_unique(
            recommendations,
            "Coordination recommendation: include network-amplification mapping and partner platform engagement in the incident response package.",
        )

    if any(token in lowered for token in ["election", "polling station", "vote", "candidate", "campaign"]):
        _append_unique(
            recommendations,
            "Election recommendation: apply election-specific transparency checks and notify relevant electoral integrity stakeholders before amplification occurs.",
        )

    joined_flags = " ".join(legal_flags).lower()
    if "article 50" in joined_flags:
        _append_unique(
            recommendations,
            "Transparency recommendation: ensure visible AI-content labeling and provenance explanation in outward communications.",
        )
    if "article 34" in joined_flags or "article 35" in joined_flags:
        _append_unique(
            recommendations,
            "Systemic-risk recommendation: document mitigation plan with distribution controls and post-action audit evidence.",
        )
    if "2016/679" in joined_flags:
        _append_unique(
            recommendations,
            "Data-protection recommendation: enforce purpose limitation, minimization, and retention checks before storing sensitive incident data.",
        )

    for action in recommended_actions[:3]:
        _append_unique(recommendations, f"Operational action: {action}")

    return recommendations[:12]

def analyze_content(text: str) -> Tuple[float, float, float, str, str, str, List[str], List[str], List[str]]:
    if not os.getenv("OPENAI_API_KEY") or client is None:
        fallback_flags = [
            CORE_LEGAL_ANCHORS["ai_act"][4],
            CORE_LEGAL_ANCHORS["dsa"][1],
            CORE_LEGAL_ANCHORS["gdpr"][0],
        ]
        fallback_synopsis = (
            "Policy synopsis: Content requires structured compliance screening under "
            "Regulation (EU) 2024/1689 Article 50 (AI transparency), "
            "Regulation (EU) 2022/2065 Article 34 (systemic-risk assessment), and "
            "Regulation (EU) 2016/679 Article 5 (data minimisation and purpose limitation)."
        )
        fallback_actions = _augment_recommended_actions([], fallback_flags)
        fallback_impact = _estimate_disinformation_impact(text, 0.5, 0.2)
        fallback_policy_recs = _build_policy_recommendations(
            text,
            fallback_impact,
            0.2,
            fallback_flags,
            fallback_actions,
        )
        return 0.5, 0.2, fallback_impact, fallback_synopsis, "Limited Risk", "Fallback narrative pending model analysis.", fallback_flags, fallback_actions, fallback_policy_recs
    
    prompt = (
        "Analyze the following text as an EU policy compliance memo. "
        "You MUST ground your assessment in named legal texts: Regulation (EU) 2024/1689 (AI Act), "
        "Regulation (EU) 2022/2065 (Digital Services Act), GDPR (Regulation (EU) 2016/679), "
        "and where relevant Regulation (EU) 2024/900 on political advertising transparency. "
        "Provide a strict JSON response with exactly eight keys:\n"
        "1. 'ai_probability': a float between 0.0 and 1.0 indicating how likely the text is AI-generated (e.g., bot-like behavior, synthetic text).\n"
        "2. 'coordination_score': a float between 0.0 and 1.0 showing the likelihood of coordinated inauthentic behavior.\n"
        "3. 'disinformation_impact': a float between 0.0 and 1.0 indicating democratic-impact severity, "
        "prioritizing potential to mislead citizens, voters, parliamentarians, or other election stakeholders at scale. "
        "This score must weigh electoral harm and amplification potential more heavily than synthetic-origin evidence alone.\n"
        "4. 'synopsis': A policy-heavy synopsis (4-7 sentences), not a general summary. "
        "It MUST explicitly quote at least two article-level citations in text, for example: "
        "'Regulation (EU) 2024/1689, Article 50' and 'Regulation (EU) 2022/2065, Article 34'. "
        "Explain legal exposure, compliance obligations, and likely enforcement relevance.\n"
        "5. 'threat_level': Threat level assignment as per the EU AI Act (Unacceptable Risk, High Risk, Limited Risk, Minimal Risk). "
        "Justify with article citations from the AI Act and at least one cross-reference to DSA or GDPR where relevant.\n"
        "6. 'narrative': A clear 1-2 sentence description explaining the core narrative and any risk of disinformation.\n"
        "7. 'legal_flags': A list of strings. Each string MUST include regulation number, article number, and a short compliance finding "
        "(e.g., 'Regulation (EU) 2024/1689 Article 50 - transparency disclosure likely required').\n"
        "8. 'recommended_actions': A list of strings with concrete compliance actions, each linked to at least one cited legal article.\n\n"
        f"Context from the Governance Layer (use but incorporate subtly):\n{GOVERNANCE_CONTEXT}\n\n"
        f"Text:\n{text}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={ "type": "json_object" },
            messages=[{"role": "system", "content": "You are a professional EU policy, disinformation, and cybersecurity AI analyst. Write in a policy-legal register suitable for a regulator briefing. Prioritize legal reasoning, obligations, and article-level citations over technical storytelling. Always cite the act and article when making a compliance claim. Subtly incorporate the provided Governance Layer context (including Code of Practice and EDMO/EFCSN info) without making it look forced."},
                      {"role": "user", "content": prompt}],
            temperature=0,
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        
        legal_flags = parsed.get("legal_flags", ["No legal flags assigned"])
        if not isinstance(legal_flags, list): legal_flags = [str(legal_flags)]
        safe_flags = [str(f) if not isinstance(f, dict) else str(f.get('flag', f.get('name', f))) for f in legal_flags]
        safe_flags = _augment_legal_flags(safe_flags, text)
        
        rec_actions = parsed.get("recommended_actions", ["No actions recommended"])
        if not isinstance(rec_actions, list): rec_actions = [str(rec_actions)]
        safe_actions = [str(a) if not isinstance(a, dict) else str(a.get('action', a.get('name', a))) for a in rec_actions]
        safe_actions = _augment_recommended_actions(safe_actions, safe_flags)

        threat_level = str(parsed.get("threat_level", "Unknown threat level"))
        synopsis = _enforce_policy_synopsis(
            str(parsed.get("synopsis", "Synopsis analysis failed.")),
            safe_flags,
            threat_level,
        )

        ai_probability = _clamp_score(parsed.get("ai_probability", 0.5))
        coordination_score = _clamp_score(parsed.get("coordination_score", 0.2))
        model_impact = parsed.get("disinformation_impact", None)
        if model_impact is None:
            model_impact = parsed.get("democratic_impact", None)
        heuristic_impact = _estimate_disinformation_impact(text, ai_probability, coordination_score)
        signals = _impact_signal_profile(text)
        low_signal_context = not any(
            bool(signals[key]) for key in ["harm_signal", "amp_signal", "synth_signal"]
        )
        if model_impact is None:
            disinformation_impact = heuristic_impact
        else:
            disinformation_impact = _clamp_score(
                (0.35 * _clamp_score(model_impact)) + (0.65 * heuristic_impact)
            )
            if low_signal_context:
                disinformation_impact = min(disinformation_impact, 0.25)

        policy_recommendations = _build_policy_recommendations(
            text,
            disinformation_impact,
            coordination_score,
            safe_flags,
            safe_actions,
        )

        return (
            ai_probability,
            coordination_score,
            disinformation_impact,
            synopsis,
            threat_level,
            str(parsed.get("narrative", "Failed to determine narrative.")),
            safe_flags,
            safe_actions,
            policy_recommendations,
        )
    except Exception as e:
        fallback_impact = _estimate_disinformation_impact(text, 0.5, 0.2)
        fallback_flags = ["LLM Failure"]
        fallback_actions = ["LLM Failure"]
        fallback_policy_recs = _build_policy_recommendations(
            text,
            fallback_impact,
            0.2,
            fallback_flags,
            fallback_actions,
        )
        return 0.5, 0.2, fallback_impact, "LLM analysis failed.", "Unknown Threat", f"Analysis failed: {str(e)}", fallback_flags, fallback_actions, fallback_policy_recs

def generate_brief(
    narrative: str,
    entities: List,
    claims: List,
    synopsis: str = "",
    threat_level: str = "",
    policy_recommendations: List[str] = None,
) -> str:
    # Ensure entities and claims are strings to avoid TypeError during join
    safe_entities = [str(e) if not isinstance(e, dict) else str(e.get('name', e)) for e in entities]
    safe_claims = [str(c) if not isinstance(c, dict) else str(c.get('claim', c)) for c in claims]
    safe_policy_recs = [str(rec) for rec in (policy_recommendations or []) if str(rec).strip()]
    
    return (
        f"EU AI Act Threat Level: {threat_level}\n\n"
        f"Synopsis: {synopsis}\n\n"
        "AI-assisted analysis (EU AI Act Article 50 transparency).\n\n"
        f"Narrative: {narrative}\n\n"
        f"Entities: {', '.join(safe_entities) if safe_entities else 'None'}\n\n"
        "Claims:\n" + "\n".join([f"- {c}" for c in safe_claims]) +
        "\n\nPolicy Recommendations:\n" +
        ("\n".join([f"- {rec}" for rec in safe_policy_recs]) if safe_policy_recs else "- No policy recommendations generated")
    )
