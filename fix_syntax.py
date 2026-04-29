with open("backend/analysis.py", "r") as f:
    text = f.read()

text = text.replace(
    '"8. \'recommended_actions\': A list of strings with concrete compliance actions, each linked to at least one cited legal article.\\\\n\\\\n"\\n        f"Context from the Governance Layer (use but incorporate subtly):\\\\n{GOVERNANCE_CONTEXT}\\\\n\\\\n"\\n        f"Text:\\\\n{text}"',
    '"8. \'recommended_actions\': A list of strings with concrete compliance actions, each linked to at least one cited legal article.\\n\\n"\n        f"Context from the Governance Layer (use but incorporate subtly):\\n{GOVERNANCE_CONTEXT}\\n\\n"\n        f"Text:\\n{text}"'
)

with open("backend/analysis.py", "w") as f:
    f.write(text)
