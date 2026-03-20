import os
import json
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from openai import OpenAI

# ------------------------------------------------------------------------------
# App setup
# ------------------------------------------------------------------------------
APP_TITLE = "Q Assistant API + CSM Dashboard"
app = FastAPI(title=APP_TITLE)

# Static directory for the React build (Vite outputs "dist" by default)
STATIC_DIR = os.getenv("CSM_STATIC_DIR", "dist")

# Optional CORS (comma-separated origins in env, e.g., http://localhost:5173,https://yourdomain)
cors_origins = os.getenv("CSM_CORS_ORIGINS")
if cors_origins:
    origins = [o.strip() for o in cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Serve static assets if the build exists
if os.path.isdir(STATIC_DIR):
    # Vite places static assets in /dist/assets
    assets_path = os.path.join(STATIC_DIR, "assets")
    if os.path.isdir(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

# ------------------------------------------------------------------------------
# Q Assistant (your existing logic, preserved)
# ------------------------------------------------------------------------------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are Q, a high-performance personal AI assistant.
Your role:
- Help Eugene think clearly and act decisively
- Prioritize actions and remove noise
- Balance business execution with personal clarity
Style:
- Direct
- Practical
- Strategic
- No fluff
"""

MEMORY_FILE = "memory.json"

# -------- MEMORY FUNCTIONS --------
def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"personal": [], "work": [], "tasks": []}

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

# -------- INTELLIGENCE LAYER --------
def classify_and_store(message, memory):
    text = message.lower()
    # Detect TASKS (priority)
    if any(word in text for word in ["task", "todo", "remind", "follow up", "prepare", "schedule", "call"]):
        memory["tasks"].append({"text": message, "created": datetime.now().isoformat()})
    # Detect WORK context
    elif any(word in text for word in ["meeting", "client", "site", "project", "demo", "ldv"]):
        memory["work"].append({"text": message, "created": datetime.now().isoformat()})
    # Default → personal
    else:
        memory["personal"].append({"text": message, "created": datetime.now().isoformat()})
    return memory

def extract_recent(memory, key, limit=5):
    return [item["text"] for item in memory.get(key, [])[-limit:]]

# -------- DATA MODEL --------
class ChatRequest(BaseModel):
    message: str

# -------- BASIC ROUTES --------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/debug")
def debug():
    return {"api_key_loaded": bool(os.getenv("OPENAI_API_KEY"))}

@app.get("/manifest.json")
def manifest():
    # Keep your existing manifest route (if you have this file present)
    if os.path.isfile("manifest.json"):
        return FileResponse("manifest.json")
    return {"error": "manifest.json not found"}

# -------- MEMORY --------
@app.post("/remember")
def remember(request: ChatRequest):
    memory = load_memory()
    memory = classify_and_store(request.message, memory)
    save_memory(memory)
    return {"status": "stored"}

# -------- CHAT --------
@app.post("/chat")
def chat(request: ChatRequest):
    try:
        memory = load_memory()
        # Store automatically
        memory = classify_and_store(request.message, memory)
        save_memory(memory)

        tasks = extract_recent(memory, "tasks")
        work = extract_recent(memory, "work")
        personal = extract_recent(memory, "personal")

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "system",
                    "content": f"""
Current Context:
Tasks:
{tasks}
Work:
{work}
Personal:
{personal}
                    """,
                },
                {"role": "user", "content": request.message},
            ],
            temperature=0.6,
        )
        return {"response": response.choices[0].message.content}
    except Exception as e:
        return {"response": f"System error: {str(e)}"}

# -------- DAILY BRIEF --------
@app.get("/daily-brief")
def daily_brief():
    try:
        memory = load_memory()
        tasks = extract_recent(memory, "tasks")
        work = extract_recent(memory, "work")
        prompt = f"""
You are Q.
Generate a sharp daily execution brief.
Tasks:
{tasks}
Work:
{work}
Output:
1. Top 3 Priorities
2. Immediate Risks
3. Next Actions
Keep it concise and actionable.
"""
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        return {"brief": response.choices[0].message.content}
    except Exception as e:
        return {"brief": f"Error: {str(e)}"}

# -------- DASHBOARD (json memory snapshot) --------
@app.get("/dashboard")
def dashboard():
    memory = load_memory()
    return memory

# -------- Q Web UI (kept as-is) --------
@app.get("/q", response_class=HTMLResponse)
def chat_ui():
    return """
<!DOCTYPE html>
<html>
<head>
<title>Q Assistant</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { background:#0f172a; color:white; font-family:Arial; text-align:center; }
#chat { width:90%; max-width:700px; height:70vh; overflow:auto; margin:auto; background:#020617; padding:15px; border-radius:10px;}
.user { color:#38bdf8; }
.q { color:#4ade80; }
input { width:70%; padding:10px; }
button { padding:10px; margin-left:5px; background:#22c55e; color:white; border:none; }
</style>
</head>
<body>
<h2>Q Assistant</h2>
<div id="chat"></div>
<input id="message" placeholder="Ask Q..." />
<button onclick="send()">Send</button>
<button onclick="brief()">Brief</button>
<script>
async function send(){
  let input = document.getElementById("message");
  let chat = document.getElementById("chat");
  let text = input.value;
  if(!text) return;
  chat.innerHTML += `<div class='user'>You: ${text}</div>`;
  input.value = "";
  let res = await fetch("/chat", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({message:text})
  });
  let data = await res.json();
  chat.innerHTML += `<div class='q'>Q: ${data.response}</div>`;
  chat.scrollTop = chat.scrollHeight;
}
async function brief(){
  let chat = document.getElementById("chat");
  let res = await fetch("/daily-brief");
  let data = await res.json();
  chat.innerHTML += `<div class='q'>Q Brief:<br>${data.brief}</div>`;
}
</script>
</body>
</html>
"""

# ------------------------------------------------------------------------------
# CSM Dashboard (React) serving
# - "/" serves React index.html if dist/ exists
# - Any unmatched path falls back to index.html (SPA routing)
# ------------------------------------------------------------------------------
def _index_file():
    index_path = os.path.join(STATIC_DIR, "index.html")
    return index_path if os.path.isfile(index_path) else None

@app.get("/", response_class=FileResponse)
def csm_root():
    """
    Primary UI: CSM Web & Mobile Dashboard (React build in /dist).
    """
    idx = _index_file()
    if idx:
        return FileResponse(idx)
    # If no build yet, show a simple message
    return {"message": f"CSM dashboard build not found. Put your React build in ./{STATIC_DIR} and refresh."}

@app.get("/{full_path:path}", response_class=FileResponse)
def csm_spa_fallback(full_path: str):
    """
    Serve static files or fall back to index.html for client-side routes.
    Specific API routes above will take precedence over this catch-all.
    """
    # If a real file exists (e.g., /assets/...), serve it
    requested = os.path.join(STATIC_DIR, full_path)
    if os.path.isfile(requested):
        return FileResponse(requested)
    # Fallback to index.html (SPA)
    idx = _index_file()
    if idx:
        return FileResponse(idx)
    # No build present
    return {"message": f"CSM dashboard build not found. Put your React build in ./{STATIC_DIR} and refresh."}

# ------------------------------------------------------------------------------
# Run with: uvicorn main:app --host 0.0.0.0 --port 8080 --reload
# ------------------------------------------------------------------------------
