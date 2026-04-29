import re

with open("backend/analysis.py", "r") as f:
    content = f.read()

old_prompt = """        "Analyze the following text and provide a strict JSON response with exactly seven keys:\\n"
        "1. 'ai_probability': a float between 0.0 and 1.0 indicating how likely the text is AI-generated (e.g., bot-like behavior, synthetic text).\\n"
        "2. 'coordination_score': a float between 0.0 and 1.0 showing the likelihood of coordinated inauthentic behavior.\\n"
        "3. 'synopsis': A brief summary of the main points in the text.\\n"
        "4. 'threat_level': Threat level assignment as per the EU AI Act.\\n"
        "5. 'narrative': A clear 1-2 sentence description explaining the core narrative.\\n"
        "6. 'legal_flags': A list of strings, each being a legal regulation flag or violation detected in the text based on EU AI Act, DSA, GDPR, or Political Ads Regs.\\n"
        "7. 'recommended_actions': A list of strings, providing action items or next steps based on the threat level, compliance issues, and risk.\\n\\n"
        f"Text:\\n{text}" """

new_prompt = """        "Analyze the following text using the principles of the EU Digital Services Act (DSA), "
        "the EU AI Act (Regulation (EU) 2024/1689), and GDPR. You MUST actively cite specific articles, risk tiers, and concepts from these regulations. Provide a strict JSON response with exactly seven keys:\\n"
        "1. 'ai_probability': a float between 0.0 and 1.0 indicating how likely the text is AI-generated (e.g., bot-like behavior, synthetic text).\\n"
        "2. 'coordination_score': a float between 0.0 and 1.0 showing the likelihood of coordinated inauthentic behavior.\\n"
        "3. 'synopsis': A brief summary of the main points in the text, evaluating whether it qualifies as systemic risk under the DSA or a prohibited AI practice under the AI Act.\\n"
        "4. 'threat_level': Threat level assignment as per the EU AI Act (Unacceptable Risk, High Risk, Limited Risk, Minimal Risk). Include an explanation citing the relevant article.\\n"
        "5. 'narrative': A clear 1-2 sentence description explaining the core narrative and any risk of disinformation.\\n"
        "6. 'legal_flags': A list of strings. Each string MUST cite a specific legal regulation (e.g., 'DSA Article 35 - Systemic Risk', 'EU AI Act Article 50 - Transparency obligation', 'GDPR Article 5').\\n"
        "7. 'recommended_actions': A list of strings, providing actionable next steps for a compliance officer based strictly on these regulations.\\n\\n"
        f"Text:\\n{text}" """

content = content.replace(old_prompt, new_prompt)

old_system_prompt = """messages=[{"role": "system", "content": "You are a professional EU policy, disinformation, and cybersecurity AI analyst."},"""

new_system_prompt = """messages=[{"role": "system", "content": "You are a professional EU policy, disinformation, and cybersecurity AI analyst. You have deep knowledge of the Digital Services Act (DSA) and the new Regulation (EU) 2024/1689 (Artificial Intelligence Act). Your analysis must directly apply and reference these texts as the primary feedback."},"""

content = content.replace(old_system_prompt, new_system_prompt)

with open("backend/analysis.py", "w") as f:
    f.write(content)

