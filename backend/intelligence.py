"""Lightweight, dependency-free intelligence helpers used by PDIP routes.

These functions are deliberately heuristic so they remain explainable for an
EU policy audience and so the demo runs offline. They operate on already-stored
Item rows: claims, entities, narrative, scores.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from typing import Dict, Iterable, List, Tuple

from regulations import parse_flag_to_citation


_STOP_TOKENS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "by",
    "with", "from", "is", "are", "was", "were", "be", "been", "being", "as",
    "at", "this", "that", "these", "those", "it", "its", "their", "they",
    "we", "our", "us", "you", "your", "i", "he", "she", "him", "her",
    "https", "http", "www", "com", "org", "eu",
}


def _tokenise(text: str) -> List[str]:
    if not text:
        return []
    raw = re.findall(r"[A-Za-z][A-Za-z\-]{2,}", text.lower())
    return [t for t in raw if t not in _STOP_TOKENS]


def headline_from_narrative(narrative: str, fallback: str = "") -> str:
    """Return a single-sentence editorial headline derived from the narrative."""

    text = (narrative or "").strip()
    if not text:
        text = (fallback or "").strip()
    if not text:
        return "Dossier opened - awaiting analysis"
    sentence = re.split(r"(?<=[.!?])\s+", text)[0]
    sentence = sentence.strip().rstrip(".")
    if len(sentence) > 160:
        sentence = sentence[:157].rstrip() + "..."
    return sentence


def confidence_band(disinfo: float, deepfake: float, coordination: float) -> float:
    """Return a 0-1 confidence value reflecting agreement between the three signals.

    High agreement (all aligned high or low) => high confidence.
    Disagreement => lower confidence, surfaced as a +/- band in the UI.
    """

    values = [max(0.0, min(1.0, v or 0.0)) for v in (disinfo, deepfake, coordination)]
    mean = sum(values) / 3
    variance = sum((v - mean) ** 2 for v in values) / 3
    spread = math.sqrt(variance)
    return round(max(0.45, min(0.97, 1 - spread)), 3)


_LANG_HINTS = {
    "en": ["the", "and", "of", "polling", "voter", "election", "election", "candidate"],
    "fr": ["le", "la", "les", "et", "des", "élection", "vote", "scrutin", "candidat"],
    "de": ["der", "die", "das", "und", "wahl", "wähler", "stimmzettel", "kanzler"],
    "it": ["il", "la", "lo", "gli", "elezione", "voto", "candidato", "campagna"],
    "es": ["el", "la", "los", "elección", "voto", "votante", "candidato", "campaña"],
    "pl": ["wybory", "głosowanie", "kandydat", "kampania", "polski", "polska"],
    "nl": ["verkiezing", "stem", "kandidaat", "campagne", "kiezer"],
}


_COUNTRY_HINTS = {
    "FR": ["france", "french", "paris", "marseille", "lyon", "élysée"],
    "DE": ["germany", "german", "berlin", "munich", "bundestag"],
    "IT": ["italy", "italian", "rome", "milan", "quirinale"],
    "ES": ["spain", "spanish", "madrid", "barcelona", "moncloa"],
    "PL": ["poland", "polish", "warsaw", "krakow", "sejm"],
    "NL": ["netherlands", "dutch", "amsterdam", "the hague"],
    "BE": ["belgium", "belgian", "brussels", "antwerp"],
    "SE": ["sweden", "swedish", "stockholm", "riksdag"],
    "FI": ["finland", "finnish", "helsinki", "eduskunta"],
    "PT": ["portugal", "portuguese", "lisbon", "porto"],
    "AT": ["austria", "austrian", "vienna"],
    "RO": ["romania", "romanian", "bucharest"],
    "EL": ["greece", "greek", "athens"],
    "IE": ["ireland", "irish", "dublin"],
    "EU": ["brussels", "european parliament", "european commission"],
}


def detect_language(text: str) -> str:
    if not text:
        return "en"
    tokens = set(_tokenise(text))
    best_lang, best_score = "en", 0
    for lang, hints in _LANG_HINTS.items():
        score = sum(1 for h in hints if h in tokens)
        if score > best_score:
            best_lang, best_score = lang, score
    return best_lang


def detect_country(text: str) -> str:
    if not text:
        return "EU"
    lowered = (text or "").lower()
    best_country, best_score = "EU", 0
    for country, hints in _COUNTRY_HINTS.items():
        score = sum(lowered.count(h) for h in hints)
        if score > best_score:
            best_country, best_score = country, score
    return best_country


def aggregate_geo(items: Iterable) -> Dict[str, Dict[str, int]]:
    countries: Counter = Counter()
    languages: Counter = Counter()
    for item in items:
        country = item.detected_country or detect_country(item.raw_text or "")
        language = item.detected_language or detect_language(item.raw_text or "")
        countries[country] += 1
        languages[language] += 1
    return {
        "countries": dict(countries),
        "languages": dict(languages),
    }


def _entity_set(item) -> set:
    raw = list(item.entities or [])
    raw += _tokenise(item.narrative or "")[:30]
    return {tok.lower() for tok in raw if tok}


def find_twins(target, others, top_n: int = 3) -> List[Dict]:
    target_set = _entity_set(target)
    twin_results: List[Tuple[float, object, List[str]]] = []
    for candidate in others:
        if candidate.id == target.id:
            continue
        cand_set = _entity_set(candidate)
        if not target_set or not cand_set:
            continue
        intersection = target_set & cand_set
        union = target_set | cand_set
        if not intersection:
            continue
        jaccard = len(intersection) / max(1, len(union))
        twin_results.append((jaccard, candidate, sorted(intersection)[:6]))

    twin_results.sort(key=lambda row: row[0], reverse=True)
    twins = []
    for similarity, candidate, shared in twin_results[:top_n]:
        twins.append({
            "itemId": candidate.id,
            "headline": candidate.headline or headline_from_narrative(candidate.narrative or "", candidate.raw_text or ""),
            "similarity": round(similarity, 3),
            "sharedEntities": shared,
            "disinformationImpact": candidate.disinformation_impact or 0.0,
            "createdAt": candidate.created_at,
        })
    return twins


def build_coordination_graph(target, others, twins: List[Dict]) -> Dict:
    nodes: List[Dict] = []
    edges: List[Dict] = []
    seen_ids: set = set()

    def add_node(node_id: str, label: str, kind: str, weight: float = 1.0):
        if node_id in seen_ids:
            return
        seen_ids.add(node_id)
        nodes.append({"id": node_id, "label": label, "kind": kind, "weight": weight})

    target_node_id = f"dossier:{target.id}"
    add_node(target_node_id, target.headline or "This dossier", "dossier", weight=1.0 + (target.disinformation_impact or 0.0))

    for entity in (target.entities or [])[:12]:
        if not entity:
            continue
        ent_id = f"entity:{entity.lower()}"
        add_node(ent_id, str(entity), "entity")
        edges.append({"source": target_node_id, "target": ent_id, "weight": 1.0, "kind": "mentions"})

    for twin in twins:
        twin_node_id = f"dossier:{twin['itemId']}"
        add_node(twin_node_id, twin["headline"], "dossier", weight=0.6 + twin["similarity"])
        edges.append({
            "source": target_node_id,
            "target": twin_node_id,
            "weight": twin["similarity"],
            "kind": "narrative-twin",
        })
        for shared in twin["sharedEntities"]:
            ent_id = f"entity:{shared.lower()}"
            add_node(ent_id, shared, "entity")
            edges.append({"source": twin_node_id, "target": ent_id, "weight": 0.8, "kind": "mentions"})

    return {"nodes": nodes, "edges": edges}


_COUNTER_TEMPLATES = {
    "en": (
        "We are aware of misleading material circulating about {topic}.\n\n"
        "Verified information from official sources:\n"
        "1) {fact_a}\n"
        "2) {fact_b}\n\n"
        "We will update this notice as new verified information becomes available.\n"
        "Last updated: {timestamp} (CET)."
    ),
    "fr": (
        "Nous avons connaissance d'informations trompeuses circulant au sujet de {topic}.\n\n"
        "Informations vérifiées issues de sources officielles :\n"
        "1) {fact_a}\n"
        "2) {fact_b}\n\n"
        "Cette communication sera mise à jour dès que de nouvelles informations vérifiées seront disponibles.\n"
        "Dernière mise à jour : {timestamp} (CET)."
    ),
    "de": (
        "Uns ist bekannt, dass irreführende Inhalte zu {topic} im Umlauf sind.\n\n"
        "Verifizierte Informationen aus offiziellen Quellen:\n"
        "1) {fact_a}\n"
        "2) {fact_b}\n\n"
        "Diese Mitteilung wird aktualisiert, sobald neue verifizierte Informationen vorliegen.\n"
        "Letzte Aktualisierung: {timestamp} (MEZ)."
    ),
    "it": (
        "Siamo a conoscenza di contenuti fuorvianti che circolano in merito a {topic}.\n\n"
        "Informazioni verificate da fonti ufficiali:\n"
        "1) {fact_a}\n"
        "2) {fact_b}\n\n"
        "Questa nota sarà aggiornata non appena saranno disponibili nuove informazioni verificate.\n"
        "Ultimo aggiornamento: {timestamp} (CET)."
    ),
    "es": (
        "Tenemos conocimiento de contenidos engañosos que circulan sobre {topic}.\n\n"
        "Información verificada de fuentes oficiales:\n"
        "1) {fact_a}\n"
        "2) {fact_b}\n\n"
        "Esta comunicación se actualizará a medida que dispongamos de nueva información verificada.\n"
        "Última actualización: {timestamp} (CET)."
    ),
    "pl": (
        "Mamy świadomość krążących wprowadzających w błąd treści dotyczących {topic}.\n\n"
        "Zweryfikowane informacje z oficjalnych źródeł:\n"
        "1) {fact_a}\n"
        "2) {fact_b}\n\n"
        "Komunikat zostanie zaktualizowany, gdy dostępne będą kolejne zweryfikowane informacje.\n"
        "Ostatnia aktualizacja: {timestamp} (CET)."
    ),
    "nl": (
        "Wij zijn op de hoogte van misleidende content over {topic}.\n\n"
        "Geverifieerde informatie uit officiële bronnen:\n"
        "1) {fact_a}\n"
        "2) {fact_b}\n\n"
        "Deze mededeling wordt bijgewerkt zodra nieuwe geverifieerde informatie beschikbaar is.\n"
        "Laatste update: {timestamp} (CET)."
    ),
}


def build_counter_narrative(item) -> Dict:
    language = item.detected_language or detect_language(item.raw_text or "") or "en"
    template = _COUNTER_TEMPLATES.get(language, _COUNTER_TEMPLATES["en"])

    claims = list(item.claims or [])
    fact_a = "Refer to the official statement from the responsible authority."
    fact_b = "Authoritative source links will be appended once cleared by communications lead."
    if claims:
        fact_a = f"The claim that '{claims[0]}' is not supported by verified evidence at this time."
    if len(claims) > 1:
        fact_b = f"Counter-evidence on '{claims[1]}' is being collected from official sources."

    topic = "this matter"
    if item.entities:
        topic = str(item.entities[0])

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")

    draft = template.format(topic=topic, fact_a=fact_a, fact_b=fact_b, timestamp=timestamp)

    notice_map = {
        "en": "AI-assisted draft - prepared with PDIP under Regulation (EU) 2024/1689 Article 50 transparency. Human review required before publication.",
        "fr": "Brouillon assisté par IA - préparé avec PDIP au titre de l'article 50 du règlement (UE) 2024/1689. Validation humaine requise avant publication.",
        "de": "KI-unterstützter Entwurf - erstellt mit PDIP gemäß Artikel 50 der Verordnung (EU) 2024/1689. Menschliche Prüfung vor Veröffentlichung erforderlich.",
        "it": "Bozza assistita da IA - preparata con PDIP ai sensi dell'articolo 50 del regolamento (UE) 2024/1689. Revisione umana richiesta prima della pubblicazione.",
        "es": "Borrador asistido por IA - preparado con PDIP de conformidad con el artículo 50 del Reglamento (UE) 2024/1689. Revisión humana requerida antes de su publicación.",
        "pl": "Projekt wspomagany sztuczną inteligencją - przygotowany w PDIP zgodnie z art. 50 rozporządzenia (UE) 2024/1689. Weryfikacja człowieka wymagana przed publikacją.",
        "nl": "Door AI ondersteund concept - opgesteld met PDIP onder artikel 50 van Verordening (EU) 2024/1689. Menselijke controle vereist vóór publicatie.",
    }

    citations = []
    for flag in (item.legal_flags or [])[:6]:
        cit = parse_flag_to_citation(flag)
        if cit:
            citations.append(cit)

    return {
        "language": language,
        "draft": draft,
        "transparencyNotice": notice_map.get(language, notice_map["en"]),
        "citations": citations,
    }


def redact_narrative(narrative: str, max_words: int = 40) -> str:
    text = (narrative or "").strip()
    if not text:
        return "Narrative withheld pending review."
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " ..."
