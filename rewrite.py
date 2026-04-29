import json

code = """import json
import os
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Tuple

from dotenv import load_dotenv
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "")) if OpenAI else None

def scrape_url(url: str) -> str:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]):
            script.extract()
        text = soup.get_text(separator=' ')
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\\n'.join(chunk for chunk in chunks if chunk)
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
        return {"claims": parsed.get("claims", []), "entities": parsed.get("entities", [])}
    except Exception:
        return {"claims": ["LLM failed"], "entities": []}

def assess_deepfake(content: str) -> float:
    # Retained for fallback, but AI detection is now handled by analyze_ai_and_threat
    lowered = (content or "").lower()
    if "deepfake" in lowered or "ai generated" in lowered:
        return 0.85
    return 0.2

def analyze_ai_and_threat(text: str) -> Tuple[float, str, str]:
    if not os.getenv("OPENAI_API_KEY") or client is None:
        return 0.5, "Placeholder synopsis", "Unknown Risk"
        
    prompt = (
        "Analyze the following text and provide a strict JSON response with three keys:\\n"
        "1. 'ai_probability': a float between 0.0 and 1.0 indicating how likely the text is AI-generated.\\n"
        "2. 'synopsis': A brief summary of the text.\\n"
        "3. 'threat_level': Threat level assessment based on the EU AI Act (e.g. Unacceptable Risk, High Risk, Limited Risk, Minimal Risk).\\n\\n"
        f"Text:\\n{text}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={ "type": "json_object" },
            messages=[{"role": "system", "content": "You are a policy/cybersecurity AI analyzing EU AI Act compliance."},
                      {"role": "user", "content": prompt}],
            temperature=0,
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        return (
            float(parsed.get("ai_probability", 0.5)),
            str(parsed.get("synopsis", "Synopsis failed.")),
            str(parsed.get("threat_level", "Unknown threat level"))
        )
    except Exception:
        return 0.5, "LLM analysis failed.", "Unknown"

def generate_brief(narrative: str, entities: List[str], claims: List[str], synopsis: str = "", threat_level: str = "") -> str:
    return (
        f"EU AI Act Threat Level: {threat_level}\\n\\n"
        f"Synopsis: {synopsis}\\n\\n"
        "AI-assisted analysis (EU AI Act Article 50 transparency).\\n\\n"
        f"Narrative: {narrative}\\n\\n"
        f"Entities: {', '.join(entities) if entities else 'None'}\\n\\n"
        "Claims:\\n" + "\\n".join([f"- {c}" for c in claims])
    )
"""

with open("backend/analysis.py", "w") as f:
    f.write(code)
