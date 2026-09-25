""" FastAPI REST server providing schema introspection and natural language SQL query endpoints. """

import os
import sys

# Vercel's Python runtime imports this file directly without adding its
# own folder to sys.path, so sibling imports (agent, schema) fail unless
# we add it explicitly.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import ask_agent
from schema import get_schema, schema_as_prompt_text

load_dotenv()

# Absolute path resolution for Vercel deployment bundle
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "demo.db"))

app = FastAPI(title="SQL Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


@app.get("/schema")
def schema_endpoint():
    if not os.path.exists(DB_PATH):
        raise HTTPException(
            status_code=500, detail="Database not found. Run seed_db.py first."
        )
    try:
        return get_schema(DB_PATH)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schema error: {e}")


@app.post("/ask")
def ask_endpoint(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(
            status_code=400, detail="Question cannot be empty."
        )
    if not os.path.exists(DB_PATH):
        raise HTTPException(
            status_code=500, detail="Database not found. Run seed_db.py first."
        )

    try:
        schema = get_schema(DB_PATH)
        schema_text = schema_as_prompt_text(schema)
        result = ask_agent(req.question, schema_text, DB_PATH)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

    return {
        "in_scope": result.in_scope,
        "answer": result.answer,
        "sql": result.sql,
        "rows": result.rows,
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "provider": os.getenv("MODEL_PROVIDER", "claude"),
        "model": os.getenv("MODEL_NAME", "default"),
    }