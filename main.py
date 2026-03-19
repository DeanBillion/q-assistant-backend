from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import HTMLResponse, FileResponse
from openai import OpenAI
import os
import json
from datetime import datetime

app = FastAPI(title="Q Assistant API")

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
    except:
        return {
            "personal": [],
            "work": [],
            "tasks": []
        }


def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


# -------- INTELLIGENCE LAYER --------

def classify_and_store(message, memory):
    text = message.lower()

    # Detect TASKS (priority)
    if any(word in text for word in [
        "task", "todo", "remind", "follow up", "prepare", "schedule", "call"
    ]):
        memory["tasks"].append({
            "text": message,
            "created": datetime.now().isoformat()
        })

    # Detect WORK context
    elif any(word in text for word in [
        "meeting", "client", "site", "project", "demo", "ldv"
    ]):
        memory["work"].append({
            "text": message,
            "created": datetime.now().isoformat()
        })

    # Default → personal
    else:
        memory["personal"].append({
            "text": message,
            "created": datetime.now().isoformat()
        })

    return memory


def extract_recent(memory, key, limit=5):
    return [item["text"] for item in memory.get(key, [])[-limit:]]


# -------- DATA MODEL --------

class ChatRequest(BaseModel):
    message: str


# -------- BASIC ROUTES --------

@app.get("/")
def root():
    return {"message": "Q Assistant is running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/debug")
def debug():
    return {"api_key_loaded": bool(os.getenv("OPENAI_API_KEY"))}

@app.get("/manifest.json")
def manifest():
    return FileResponse("manifest.json")


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
                    """
                },
                {"role": "user", "content": request.message}
            ],
            temperature=0.6
        )

        return {
            "response": response.choices[0].message.content
        }

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
            temperature=0.4
        )

        return {"brief": response.choices[0].message.content}

    except Exception as e:
        return {"brief": f"Error: {str(e)}"}


# -------- DASHBOARD --------

@app.get("/dashboard")
def dashboard():
    memory = load_memory()
    return memory


# -------- WEB UI --------

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
