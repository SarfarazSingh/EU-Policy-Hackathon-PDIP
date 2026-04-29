import sys

with open("backend/main.py", "r") as f:
    content = f.read()

new_scenarios = """
    {
        "narrative": "AI-generated fake EU Directive draft circulating on messaging apps claims an immediate 60% tax on farm diesel starting Monday, igniting calls for tractor blockades across all major ports.",
        "claims": [
            "EU passed a surprise 60% tax increase on agricultural diesel effective Monday",
            "Emergency tractor blockades ordered at Rotterdam and Antwerp ports"
        ],
        "entities": ["EU Commission", "Port of Rotterdam", "Port of Antwerp", "Farmers Union"],
        "country": "NL", "language": "nl",
        "disinfo": 0.96, "deepfake": 0.70, "coordination": 0.93,
        "headline": "Fabricated EU Directive on diesel tax sparks coordinated port blockade threats",
        "legal_flags": [
            "Regulation (EU) 2022/2065 Article 34 - systemic risk to public security and critical infrastructure",
            "Regulation (EU) 2024/1689 Article 50 - AI-generated official document without disclosure",
            "National law - incitement to disrupt critical economic infrastructure"
        ],
        "actions": [
            "Activate EU civil protection mechanism for port coordination (Critical Infrastructure).",
            "Demand immediate platform takedown of the fake directive PDF via DSA Art. 16.",
            "Commission spokesperson to issue debunking statement directly to agricultural press.",
        ],
    },
    {
        "narrative": "A network of bot accounts on a major social media platform is aggressively amplifying a deepfake video of a prominent civil rights leader urging supporters to boycott upcoming national elections, claiming electronic voting machines are rigged.",
        "claims": [
            "Leading civil rights advocate tells followers to boycott the elections",
            "Electronic voting machines have been pre-programmed to rig the outcome"
        ],
        "entities": ["Civil Rights Leader ID", "National Electoral Commission", "Electronic Voting Machines"],
        "country": "ES", "language": "es",
        "disinfo": 0.88, "deepfake": 0.95, "coordination": 0.98,
        "headline": "Botnet driving deepfake boycott campaign targeting minority voting districts",
        "legal_flags": [
            "Regulation (EU) 2024/1689 Article 50 - malicious use of synthetic media in electoral context",
            "Regulation (EU) 2022/2065 Article 35 - crisis protocol required for election manipulation",
            "Article 14 - coordinated inauthentic behavior"
        ],
        "actions": [
            "Invoke DSA crisis protocol (Art. 36) for immediate bot network suspension.",
            "Coordinate with national cyber police to trace botnet origin.",
            "Publish verified repudiation video from the targeted civil rights leader.",
        ],
    }
]
"""

old_snippet = """        "actions": [
            "Request platform to apply Art. 35 mitigation: demote, label and notify exposed users.",
            "Refer the asset to the national audiovisual regulator for provenance review.",
            "Brief candidate office and prepare correction with C2PA-verified statement.",
        ],
    },
]"""

new_snippet = """        "actions": [
            "Request platform to apply Art. 35 mitigation: demote, label and notify exposed users.",
            "Refer the asset to the national audiovisual regulator for provenance review.",
            "Brief candidate office and prepare correction with C2PA-verified statement.",
        ],
    },""" + new_scenarios

if old_snippet not in content:
    print("Snippet not found!")
    sys.exit(1)

content = content.replace(old_snippet, new_snippet)

with open("backend/main.py", "w") as f:
    f.write(content)

print("Scenarios updated")
