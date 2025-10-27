# api/ai/analyze.py (FastAPI)
from fastapi import FastAPI, Request
from transformers import pipeline

app = FastAPI()
nlp = pipeline("text-generation", model="mistralai/Mistral-7B-Instruct-v0.2")

@app.post("/api/ai/analyze")
async def analyze(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "")
    result = nlp(prompt, max_new_tokens=400, temperature=0.6)
    return {"response": result[0]["generated_text"]}
