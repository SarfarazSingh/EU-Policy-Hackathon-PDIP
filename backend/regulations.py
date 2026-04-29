"""Curated regulation excerpts used for the inline citation slide-over.

Excerpts are intentionally short, paraphrased-but-faithful summaries of the cited
articles so the UI can present a defensible, readable explanation without
shipping the full PDFs at runtime. Source PDFs are bundled at the repo root.
"""

from typing import Dict, List


REGULATIONS: Dict[str, Dict[str, str]] = {
    "2024/1689:5": {
        "title": "AI Act - Article 5: Prohibited AI practices",
        "excerpt": (
            "Bans AI systems that materially distort behaviour in ways that cause "
            "significant harm, exploit vulnerabilities, perform social scoring, or "
            "carry out untargeted scraping of facial images. Relevant when an asset "
            "appears designed to manipulate voters or specific vulnerable groups."
        ),
        "sourceDocument": "REGULATION (EU) 2024_1689 OF THE EUROPEAN PARLIAMENT AND OF THE COUNCIL.pdf",
    },
    "2024/1689:9": {
        "title": "AI Act - Article 9: Risk-management system",
        "excerpt": (
            "Providers of high-risk AI systems must operate a documented, "
            "iterative risk-management process across the lifecycle: identification, "
            "estimation, evaluation, and mitigation of foreseeable risks to health, "
            "safety, and fundamental rights."
        ),
        "sourceDocument": "REGULATION (EU) 2024_1689 OF THE EUROPEAN PARLIAMENT AND OF THE COUNCIL.pdf",
    },
    "2024/1689:14": {
        "title": "AI Act - Article 14: Human oversight",
        "excerpt": (
            "High-risk AI systems must be designed for effective human oversight: "
            "operators must be able to understand outputs, decide whether to act, "
            "and intervene or stop the system. Anchors PDIP's human-in-the-loop "
            "escalation requirement."
        ),
        "sourceDocument": "REGULATION (EU) 2024_1689 OF THE EUROPEAN PARLIAMENT AND OF THE COUNCIL.pdf",
    },
    "2024/1689:50": {
        "title": "AI Act - Article 50: Transparency for AI-generated content",
        "excerpt": (
            "Deployers of AI systems that generate or manipulate image, audio, or "
            "video content (including deep fakes) must disclose that the content "
            "is artificially generated or manipulated. Text intended to inform the "
            "public on matters of public interest carries the same disclosure duty."
        ),
        "sourceDocument": "REGULATION (EU) 2024_1689 OF THE EUROPEAN PARLIAMENT AND OF THE COUNCIL.pdf",
    },
    "2022/2065:26": {
        "title": "DSA - Article 26: Advertising transparency",
        "excerpt": (
            "Online platforms must clearly label advertisements, identify the "
            "natural or legal person on whose behalf the ad is presented, and the "
            "person who paid for it, plus the parameters used to target the user."
        ),
        "sourceDocument": "Digital Services Act.pdf",
    },
    "2022/2065:34": {
        "title": "DSA - Article 34: Systemic risk assessment",
        "excerpt": (
            "Very large online platforms must annually identify, analyse and assess "
            "systemic risks stemming from the design or functioning of their service, "
            "including risks to civic discourse, electoral processes, and public "
            "security from disinformation."
        ),
        "sourceDocument": "Digital Services Act.pdf",
    },
    "2022/2065:35": {
        "title": "DSA - Article 35: Risk mitigation measures",
        "excerpt": (
            "Platforms must put in place reasonable, proportionate and effective "
            "mitigation measures tailored to the systemic risks identified, including "
            "adapting recommender systems, content moderation, and crisis protocols."
        ),
        "sourceDocument": "Digital Services Act.pdf",
    },
    "2022/2065:40": {
        "title": "DSA - Article 40: Vetted-researcher data access",
        "excerpt": (
            "Provides vetted researchers with access to platform data necessary "
            "to study systemic risks in the EU, supporting independent oversight "
            "of disinformation dynamics."
        ),
        "sourceDocument": "Digital Services Act.pdf",
    },
    "2016/679:5": {
        "title": "GDPR - Article 5: Principles relating to processing",
        "excerpt": (
            "Personal data must be processed lawfully, fairly and transparently; "
            "collected for specified, explicit purposes; minimised; accurate; kept "
            "no longer than necessary; and processed with integrity and "
            "confidentiality. Controllers must be able to demonstrate compliance."
        ),
        "sourceDocument": "DATA REGULATION.pdf",
    },
    "2016/679:6": {
        "title": "GDPR - Article 6: Lawfulness of processing",
        "excerpt": (
            "Processing is lawful only if at least one of the listed grounds "
            "applies (consent, contract, legal obligation, vital interests, public "
            "task, or legitimate interests balanced against the data subject)."
        ),
        "sourceDocument": "DATA REGULATION.pdf",
    },
    "2016/679:9": {
        "title": "GDPR - Article 9: Special-category data",
        "excerpt": (
            "Processing of data revealing racial or ethnic origin, political "
            "opinions, religion, biometrics for unique identification, or health "
            "is prohibited unless a narrow exception applies."
        ),
        "sourceDocument": "DATA REGULATION.pdf",
    },
    "2016/679:22": {
        "title": "GDPR - Article 22: Automated individual decision-making",
        "excerpt": (
            "Data subjects have the right not to be subject to a decision based "
            "solely on automated processing, including profiling, that produces "
            "legal or similarly significant effects, with safeguards including the "
            "right to obtain human intervention."
        ),
        "sourceDocument": "DATA REGULATION.pdf",
    },
    "2016/679:25": {
        "title": "GDPR - Article 25: Data protection by design and by default",
        "excerpt": (
            "Controllers must implement appropriate technical and organisational "
            "measures, both at the time of determination of the means for "
            "processing and at the time of processing itself."
        ),
        "sourceDocument": "DATA REGULATION.pdf",
    },
    "2024/900:7": {
        "title": "Political Advertising Regulation - Article 7",
        "excerpt": (
            "Sponsors of political advertising must provide clear, prominent and "
            "machine-readable transparency notices identifying the sponsor, the "
            "election or referendum concerned, the amounts paid, and the targeting "
            "or ad-delivery techniques used."
        ),
        "sourceDocument": "Policy recommendations for platform accountability, electoral integrity, and parliamentary oversight.pdf",
    },
    "2024/900:0": {
        "title": "Political Advertising Regulation - Overview",
        "excerpt": (
            "Establishes EU-wide transparency and targeting rules for political "
            "advertising in order to protect the integrity of democratic processes "
            "and the right to receive impartial information."
        ),
        "sourceDocument": "Policy recommendations for platform accountability, electoral integrity, and parliamentary oversight.pdf",
    },
}


def lookup(citation: str) -> Dict[str, str]:
    """Return excerpt metadata for a citation key like '2024/1689:50'."""

    if citation in REGULATIONS:
        data = REGULATIONS[citation]
        return {
            "citation": citation,
            "title": data["title"],
            "excerpt": data["excerpt"],
            "sourceDocument": data["sourceDocument"],
        }
    return {
        "citation": citation,
        "title": "Citation not in onboarded library",
        "excerpt": (
            "PDIP keeps a curated, EU-only excerpt library. To add this citation, "
            "extend backend/regulations.py with the article summary and the source "
            "PDF filename present at the repo root."
        ),
        "sourceDocument": "(unmapped)",
    }


def parse_flag_to_citation(flag: str) -> str:
    """Turn 'Regulation (EU) 2024/1689 Article 50 - ...' into '2024/1689:50'."""

    import re

    flag = flag or ""
    reg_match = re.search(r"(\d{4}/\d{2,4})", flag)
    art_match = re.search(r"Article\s*(\d+)", flag, re.IGNORECASE)
    if not reg_match:
        return ""
    reg = reg_match.group(1)
    article = art_match.group(1) if art_match else "0"
    return f"{reg}:{article}"


def list_citation_keys() -> List[str]:
    return sorted(REGULATIONS.keys())
