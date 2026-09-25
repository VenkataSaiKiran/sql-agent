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
