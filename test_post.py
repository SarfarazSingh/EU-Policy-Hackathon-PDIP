import requests
import time
payload = {"url": "https://en.wikipedia.org/wiki/Artificial_intelligence_act", "type": "url"}
r = requests.post("http://localhost:8000/api/items", json=payload)
print(r.json())
item_id = r.json()["itemId"]

for _ in range(15):
    time.sleep(2)
    resp = requests.get(f"http://localhost:8000/api/items/{item_id}").json()
    if resp.get("status") == "done":
        print(resp)
        break
    else:
        print(resp.get("status"))

