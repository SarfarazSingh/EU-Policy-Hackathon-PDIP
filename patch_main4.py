import re

with open("backend/main.py", "r") as f:
    content = f.read()

stop_endpoint = """
@app.post("/api/items/{item_id}/stop")
async def stop_item(item_id: str, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    if item.status == "pending":
        item.status = "stopped"
        db.commit()
    return {"status": item.status}
"""

if "/api/items/{item_id}/stop" not in content:
    # Insert before export_item
    content = content.replace('@app.get("/api/items/{item_id}/export")', stop_endpoint + '\n@app.get("/api/items/{item_id}/export")')

with open("backend/main.py", "w") as f:
    f.write(content)

