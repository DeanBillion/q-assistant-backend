from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import HTMLResponse
from openai import OpenAI
import os

app = FastAPI(title="Q Assistant API")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are Q.
A warm, growth-oriented personal AI companion.
Help Eugene plan clearly, think strategically,
and balance business and family life.
"""

class ChatRequest(BaseModel):
    message: str


@app.get("/health")
def health():
    return {"status": "Q backend running"}


@app.get("/debug")
def debug():
    return {"api_key_loaded": bool(os.getenv("OPENAI_API_KEY"))}


@app.post("/chat")
def chat(request: ChatRequest):
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": request.message}
        ],
        temperature=0.7
    )

    return {"response": response.choices[0].message.content}


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
    font-family: Arial, sans-serif;
    background:#0f172a;
    color:white;
    display:flex;
    flex-direction:column;
    align-items:center;
    margin:0;
}
#chat {
    width:90%;
    max-width:700px;
    height:70vh;
    overflow-y:auto;
    border:1px solid #334155;
    padding:15px;
    margin-top:20px;
    background:#020617;
    border-radius:10px;
}
.message { margin-bottom:12px; }
.user { color:#38bdf8; }
.q { color:#4ade80; }

#inputArea {
    display:flex;
    width:90%;
    max-width:700px;
    margin-top:10px;
}

input {
    flex:1;
    padding:10px;
    font-size:16px;
    border-radius:6px;
    border:none;
}

button {
    padding:10px 15px;
    margin-left:6px;
    border:none;
    background:#22c55e;
    color:white;
    border-radius:6px;
    cursor:pointer;
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
async function send() {
    const input = document.getElementById("message");
    const chat = document.getElementById("chat");

    const text = input.value;
    if (!text) return;

    chat.innerHTML += `<div class='message user'><b>You:</b> ${text}</div>`;
    input.value = "";

    const response = await fetch("/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({message: text})
    });

    const data = await response.json();

    chat.innerHTML += `<div class='message q'><b>Q:</b> ${data.response}</div>`;
    chat.scrollTop = chat.scrollHeight;
}
</script>

</body>
</html>
"""
