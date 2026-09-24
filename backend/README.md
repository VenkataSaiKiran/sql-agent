# SQL Agent — Ask Your Database

An intelligent database assistant built with **LangChain**, **FastAPI**, and **Tailwind CSS**. It translates plain-English questions into valid SQLite queries, executes them safely, and renders both executive summaries and interactive data tables.

---

## 🏗️ Architecture & Flow
┌──────────────────────────────┐
│  Browser (index.html)        │
└──────────────┬───────────────┘
│ fetch()
▼
┌──────────────────────────────┐
│  FastAPI (main.py)           │
└──────────────┬───────────────┘
│
├── GET  /schema  ──► Introspects DB tables & columns
└── POST /ask     ──► Triggers agent workflow in agent.py
│
┌─────────────────────────────────────────┴─────────────────────────────────────────┐
│                                                                                   │
│  1. LangChain LLM (Claude / Hugging Face / Ollama) generates SQLite query          │
│  2. sqlglot parses AST & enforces safety (read-only SELECT, LIMIT 100, quote fix) │
│  3. SQLite executes safe query against demo.db                                    │
│  4. LLM synthesizes concise executive answer summary                              │
└─────────────────────────────────────────┬─────────────────────────────────────────┘
│
┌───────────────────────────┴───────────────────────────┐
▼                                                       ▼
Executive Summary Text                                   Scrollable Data Table


---

## ✨ Key Features

* **Multi-LLM Flexibility**: Easily switch between **Paid Claude**, **Free Hugging Face Cloud API**, or **Local Offline Ollama** using simple `.env` flags.
* **Robust Safety Guardrails**: AST-level SQL validation using `sqlglot` to strictly enforce single, read-only `SELECT` statements and reject DML/DDL operations (`INSERT`, `UPDATE`, `DELETE`, `DROP`).
* **Reserved Keyword Protection**: Automatic schema-aware double-quoting for tables/columns matching SQL reserved words (e.g., `"Order"`).
* **Automatic Row Limits**: Enforces `LIMIT 100` on queries lacking explicit limits to prevent memory exhaustion.
* **Dual UI Rendering**: Renders a 1–2 sentence executive summary for high-level insight alongside a styled, scrollable dark-mode data table for multi-row records.

---

## 📂 Project Structure

```text
sql-agent/
├── backend/
│   ├── .env                    # Environment variables & provider settings
│   ├── requirements.txt        # Python package dependencies
│   └── src/
│       ├── agent.py            # Core LangChain agent logic, prompts & safety checks
│       ├── main.py             # FastAPI backend server & API endpoints
│       ├── schema.py           # SQLite introspection & prompt schema formatting
│       ├── seed_db.py          # Script to generate & seed demo SQLite database
│       └── demo.db             # SQLite database file (created after seeding)
└── frontend/
    └── index.html              # Modern, single-file Tailwind CSS user interface
```

## Setup

### 1. Install dependencies

```bash
cd /path/to/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Install dependencies & Configure environment 

```bash
pip install -r requirements.txt

## If using local chat, install/start Ollama and pull a model:
brew install ollama
ollama serve
ollama qwen2.5-coder:7b
```

### 3. Seed the demo database

```bash
python3 src/seed_db.py
```

This creates `backend/demo.db` with sample `Customer`, `Product`, and
`Order` tables (matching the reference UI).

### 4. Run the backend

```bash
cd src
python3 -m uvicorn main:app --reload --port 8000
```

### 5. Open the frontend

Just open `frontend/index.html` directly in your browser (no build step
needed — it's a single static file using the Tailwind CDN). It talks to
`http://localhost:8000` by default; change `window.API_BASE` at the top
of the `<script>` block in `index.html` if your backend runs elsewhere.

## How the safety guardrails work

- The LLM is instructed (system prompt) to only ever produce `SELECT`
  statements and to flag out-of-scope questions instead of guessing.
- `sqlglot` independently parses the generated SQL and **rejects** it if
  it's anything other than a single `SELECT` statement — this is a real
  parser-level check, not just trusting the model's instructions.
- A `LIMIT 100` is auto-appended if the model doesn't include one.
- The DB connection should ideally use a **read-only DB user** in a real
  deployment (SQLite doesn't have per-user permissions, so for Postgres/
  MySQL create a role with `SELECT`-only grants as a second layer of
  defense beyond the SQL parser check).

## Extending this

- **Multi-DB support**: add a `db_id` param to `/schema` and `/ask`, keep
  a small registry mapping `db_id → connection string`.
- **Conversation memory**: pass prior Q&A pairs into the system prompt so
  users can ask follow-ups like "what about last month?"
- **Retry on SQL error**: if `run_sql` throws, feed the error back to the
  LLM and ask it to fix the query (one retry, then give up gracefully).
- **Charting**: if a result has 2+ numeric columns, offer a chart instead
  of / alongside the sentence answer.
