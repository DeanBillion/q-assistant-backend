from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import HTMLResponse, FileResponse
from openai import OpenAI
import os
import json

app = FastAPI(title="Q Assistant API")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are Q.
A warm, growth-oriented personal AI companion.
Help Eugene plan clearly, think strategically,
and balance business and family life.
"""

MEMORY_FILE = "memory.json"


# -------- MEMORY FUNCTIONS --------

def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except:
        return {"personal": [], "work": [], "tasks": []}


def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


# -------- AUTO CLASSIFIER --------

def classify_and_store(message, memory):
    text = message.lower()

    if any(word in text for word in ["meeting", "client", "site", "project"]):
        memory["work"].append(message)

    elif any(word in text for word in ["task", "todo", "remind", "follow up"]):
        memory["tasks"].append(message)

    else:
        memory["personal"].append(message)

    return memory


# -------- DATA MODEL --------

class ChatRequest(BaseModel):
    message: str


# -------- BASIC ROUTES --------

@app.get("/health")
def health():
    return {"status": "Q backend running"}


@app.get("/debug")
def debug():
    return {"api_key_loaded": bool(os.getenv("OPENAI_API_KEY"))}


@app.get("/manifest.json")
def manifest():
    return FileResponse("manifest.json")


# -------- MEMORY SAVE --------

@app.post("/remember")
def remember(request: ChatRequest):

    memory = load_memory()
    memory = classify_and_store(request.message, memory)
    save_memory(memory)

    return {"status": "saved", "memory": memory}


# -------- CHAT ENGINE --------

@app.post("/chat")
def chat(request: ChatRequest):

    memory = load_memory()

    # Auto-store every message
    memory = classify_and_store(request.message, memory)
    save_memory(memory)

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "system",
                "content": f"""
                Known Personal Info: {memory['personal']}
                Work Context: {memory['work']}
                Tasks: {memory['tasks']}
                """
            },
            {"role": "user", "content": request.message}
        ],
        temperature=0.7
    )

    return {"response": response.choices[0].message.content}


# -------- WEB INTERFACE --------

@app.get("/q", response_class=HTMLResponse)
def chat_ui():
    return """
<!DOCTYPE html>
<html>
<head>
<title>Q Assistant</title>

<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#0f172a">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<style>
body {
    font-family: Arial;
    background:#0f172a;
    color:white;
    display:flex;
    flex-direction:column;
    align-items:center;
}

#chat{
    width:90%;
    max-width:700px;
    height:70vh;
    overflow-y:auto;
    background:#020617;
    border-radius:10px;
    padding:15px;
}

.message{margin-bottom:10px;}
.user{color:#38bdf8;}
.q{color:#4ade80;}

#inputArea{
    display:flex;
    width:90%;
    max-width:700px;
    margin-top:10px;
}

input{
    flex:1;
    padding:10px;
}

button{
    padding:10px;
    background:#22c55e;
    border:none;
    color:white;
}
</style>

</head>

<body>

<h2>Q Assistant</h2>

<div id="chat"></div>

<div id="inputArea">
<input id="message" placeholder="Ask Q something..." />
<button onclick="send()">Send</button>
</div>

<script>
async function send(){

    const input = document.getElementById("message")
    const chat = document.getElementById("chat")

    const text = input.value
    if(!text) return

    chat.innerHTML += `<div class='message user'><b>You:</b> ${text}</div>`
    input.value=""

    const response = await fetch("/chat",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({message:text})
    })

    const data = await response.json()

    chat.innerHTML += `<div class='message q'><b>Q:</b> ${data.response}</div>`
    chat.scrollTop = chat.scrollHeight
}
</script>

</body>
</html>
"""


# -------- DASHBOARD --------

@app.get("/dashboard")
def dashboard():
    memory = load_memory()
    return {
        "tasks": memory["tasks"],
        "work": memory["work"],
        "personal": memory["personal"]
    }
