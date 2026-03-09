from fastapi import FastAPI
from pydantic import BaseModel
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

@app.post("/chat")
def chat(request: ChatRequest):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": request.message}
        ],
        temperature=0.7
    )

    return {"response": response.choices[0].message.content}
/debug
