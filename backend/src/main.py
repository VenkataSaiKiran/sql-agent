""" FastAPI REST server providing schema introspection and natural language SQL query endpoints. """

import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import ask_agent
from schema import get_schema, schema_as_prompt_text

load_dotenv()

# Absolute path to SQLite demo database
DB_PATH = os.path.join(os.path.dirname(__file__), "demo.db")

app = FastAPI(title="SQL Agent")

# Enable CORS middleware to allow requests from browser frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    """ Request schema model for natural language questions. """
    question: str


@app.get("/schema")
def schema_endpoint():
    """
    GET /schema: Returns database table and column structures to populate UI sidebar.
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(
            status_code=500, detail="Database not found. Run seed_db.py first."
        )
    return get_schema(DB_PATH)


@app.post("/ask")
def ask_endpoint(req: AskRequest):
    """
    POST /ask: Receives a user question, processes it through the SQL Agent workflow,
    and returns generated SQL, plain-English answer summary, and raw row data.
    """
    if not req.question.strip():
        raise HTTPException(
            status_code=400, detail="Question cannot be empty."
        )
    if not os.path.exists(DB_PATH):
        raise HTTPException(
            status_code=500, detail="Database not found. Run seed_db.py first."
        )

    schema = get_schema(DB_PATH)
    schema_text = schema_as_prompt_text(schema)
    result = ask_agent(req.question, schema_text, DB_PATH)

    return {
        "in_scope": result.in_scope,
        "answer": result.answer,
        "sql": result.sql,
        "rows": result.rows,
    }


@app.get("/health")
def health():
    """
    GET /health: Returns current backend health status and active model provider info.
    """
    return {
        "status": "ok",
        "provider": os.getenv("MODEL_PROVIDER", "claude"),
        "model": os.getenv("MODEL_NAME", "default"),
    }