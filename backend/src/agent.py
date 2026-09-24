""" Core SQL Agent logic powered by LangChain and sqlglot safety guardrails. """

import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from dotenv import load_dotenv

import sqlglot
from sqlglot import exp
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# Maximum rows returned by any generated query to prevent overwhelming the application
MAX_ROWS = 100

# System prompt instructing the LLM on database schema, SQL syntax rules, and output JSON format
SYSTEM_PROMPT_TEMPLATE = """You are an expert SQL generation assistant for a SQLite database agent. You are given a database schema and a user's natural-language question. Your job:
1. Decide whether the question can be answered using ONLY the tables/columns in the schema below.
2. If yes: write a single, safe, read-only SQLite SELECT query that answers it.
3. If no (the question asks to modify data via INSERT/UPDATE/DELETE, or asks about tables/columns that do not exist in this schema): say so.

DATABASE SCHEMA:
{schema_text}

SQLITE CAPABILITIES & QUOTING RULES:
- Always enclose table names in double quotes (e.g., FROM "Order" AS o, JOIN "Customer" AS c) to prevent syntax errors with reserved keywords like Order.
- Always enclose column names in double quotes or prefix them with their table alias (e.g., "p"."name", "c"."name").
- Only produce SELECT statements. Never produce INSERT, UPDATE, DELETE, DROP, ALTER, or multiple statements.
- Only reference tables and columns that exist in the schema above.
- Multi-table JOINs, GROUP BY, and string aggregations ARE fully in-scope.
- For listing multiple values or comma-separated names per group, use SQLite's built-in `GROUP_CONCAT(col, ', ')` function.
- Prefer aggregate queries (COUNT, GROUP BY, ORDER BY ... LIMIT) when the question asks for "most", "least", "top N", "how many", etc.
- Respond with ONLY a single JSON object, no markdown fences, no extra text, in exactly one of these two shapes:
  {{"in_scope": true, "sql": "<the SELECT statement>", "reasoning": "<one short sentence>"}}
  {{"in_scope": false, "message": "<one short sentence explaining what this agent can and can't do>"}}"""

# Prompt instructing the LLM on how to convert query results into plain English summaries
ANSWER_PROMPT_TEMPLATE = """The user asked: "{question}"
The database returned a total of {total_rows} row(s).

Here is a sample of the data returned (up to 5 rows):
{rows_sample_json}

STRICT RESPONSE RULES:
1. IF the result is a single value, count, or small set (1-3 rows): Give a direct, precise answer in 1 short sentence. Bold key values using **double asterisks**.
2. IF the result is a multi-row table ({total_rows} rows):
   - DO NOT list individual row names, prices, or values in your text output. The user can view them in the table below.
   - Write a 1-2 sentence high-level executive summary summarizing the dataset (e.g., total count, categories involved, or key overall trend).
3. Always format prices and monetary amounts with a dollar sign (e.g., **$29.99**, **$599.99**).
4. Do NOT mention SQL, queries, or database tables.
5. Do NOT output raw unformatted lists of numbers or names."""


@dataclass
class AgentResult:
    """ Dataclass encapsulating the agent's complete execution response. """
    in_scope: bool
    answer: str
    sql: str | None = None
    rows: list[dict] = field(default_factory=list)
    error: str | None = None


def get_llm():
    """
    LLM Factory function: Reads settings from .env and instantiates the appropriate
    LangChain ChatModel provider (Paid Claude, Free Hugging Face, or Local Ollama).

    Returns:
        BaseChatModel: An initialized LangChain chat model.
    """
    provider = os.getenv("MODEL_PROVIDER", "claude").lower().strip()
    model_name = os.getenv("MODEL_NAME", "").strip()

    # Provider 1: Anthropic Claude
    if provider in ["claude", "anthropic"]:
        from langchain_anthropic import ChatAnthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set in environment or .env file.")
        model = model_name or "claude-3-haiku-20240307"
        return ChatAnthropic(model=model, anthropic_api_key=api_key, temperature=0.0)

    # Provider 2: Hugging Face Serverless Inference API
    elif provider in ["huggingface", "hf"]:
        from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace

        hf_token = os.getenv("HUGGINGFACEHUB_API_TOKEN") or os.getenv("HF_TOKEN")
        if not hf_token:
            raise ValueError("HUGGINGFACEHUB_API_TOKEN or HF_TOKEN is not set in environment or .env file.")
        model = model_name or "Qwen/Qwen2.5-Coder-7B-Instruct"
        llm = HuggingFaceEndpoint(
            repo_id=model,
            huggingfacehub_api_token=hf_token,
            temperature=0.1,
            max_new_tokens=512,
        )
        return ChatHuggingFace(llm=llm)

    # Provider 3: Ollama Local Models
    elif provider == "ollama":
        from langchain_ollama import ChatOllama

        model = model_name or "qwen2.5-coder:7b"
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return ChatOllama(model=model, base_url=base_url, temperature=0.0)

    else:
        raise ValueError(
            f"Unsupported MODEL_PROVIDER '{provider}'. Choose 'claude', 'huggingface', or 'ollama'."
        )


def _extract_json(text: str) -> dict:
    """
    Defensively parses raw JSON strings returned by LLMs, removing markdown code fences
    or surrounding commentary text if present.

    Args:
        text (str): Raw string output from the LLM.

    Returns:
        dict: Parsed JSON object.
    """
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback pattern match for JSON objects embedded in surrounding text
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse valid JSON from LLM output: {text[:100]}...")


def generate_sql(question: str, schema_text: str) -> dict:
    """
    Translates a natural language question into a SQLite query given the database schema.

    Args:
        question (str): User's input question.
        schema_text (str): Formatted string representation of database tables/columns.

    Returns:
        dict: Decision dictionary containing {"in_scope": bool, "sql": str, ...}.
    """
    llm = get_llm()

    prompt = ChatPromptTemplate.from_messages(
        [("system", SYSTEM_PROMPT_TEMPLATE), ("user", "{question}")]
    )

    chain = prompt | llm
    response = chain.invoke(
        {"schema_text": schema_text, "question": question}
    )

    text = response.content if hasattr(response, "content") else str(response)
    return _extract_json(text)


def validate_sql(sql: str) -> str:
    """
    Parses and validates generated SQL using sqlglot AST parsing to ensure security:
    - Enforces single SELECT statement rule (blocks DML/DDL operations).
    - Appends a safety LIMIT 100 clause if omitted.

    Args:
        sql (str): Raw SQL string generated by the LLM.

    Returns:
        str: Validated and formatted SQLite query string.
    """
    statements = sqlglot.parse(sql, read="sqlite")
    if len(statements) != 1:
        raise ValueError("Only a single SQL statement is allowed.")
    tree = statements[0]
    if tree is None or not isinstance(tree, exp.Select):
        raise ValueError("Only SELECT statements are allowed.")

    # Guard against DML/DDL statements hidden inside queries
    forbidden = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create)
    for node in tree.walk():
        if isinstance(node[0], forbidden):
            raise ValueError("Only read-only SELECT statements are allowed.")

    # Auto-append limit to protect memory limits
    if tree.args.get("limit") is None:
        tree = tree.limit(MAX_ROWS)
    return tree.sql(dialect="sqlite")


def run_sql(sql: str, db_path: str) -> list[dict]:
    """
    Executes a validated read-only SQL query against the SQLite database file.

    Args:
        sql (str): Validated SQL SELECT query.
        db_path (str): File path to SQLite database.

    Returns:
        list[dict]: List of query row records formatted as dictionary objects.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def synthesize_answer(question: str, rows: list[dict]) -> str:
    """
    Generates a concise, plain-English summary answer based on execution results.

    Args:
        question (str): Original user question.
        rows (list[dict]): Query result rows from SQLite execution.

    Returns:
        str: Plain-English summary text formatted with markdown.
    """
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([("user", ANSWER_PROMPT_TEMPLATE)])

    # Limit sample size to 5 rows so the LLM writes an executive overview
    # rather than echoing long tables into text.
    sample_rows = rows[:5] if len(rows) > 5 else rows

    chain = prompt | llm
    response = chain.invoke(
        {
            "question": question,
            "total_rows": len(rows),
            "rows_sample_json": json.dumps(sample_rows, default=str),
        }
    )
    text = response.content if hasattr(response, "content") else str(response)
    return text.strip()


def ask_agent(question: str, schema_text: str, db_path: str) -> AgentResult:
    """
    Main orchestrator function that manages the SQL Agent lifecycle:
    1. Generates SQL query or flags question as out-of-scope using LLM.
    2. Validates SQL AST structure for security and read-only compliance.
    3. Executes SQL against SQLite database.
    4. Synthesizes query results into a user-friendly answer summary.

    Args:
        question (str): Plain-English question from the frontend.
        schema_text (str): Schema definition string.
        db_path (str): Database path.

    Returns:
        AgentResult: Dataclass containing answer summary, SQL, data rows, and scope flags.
    """
    # Step 1: SQL Generation
    try:
        decision = generate_sql(question, schema_text)
    except Exception as e:
        return AgentResult(
            in_scope=False,
            answer=f"Sorry, I couldn't process that question ({e}).",
        )

    if not decision.get("in_scope"):
        return AgentResult(
            in_scope=False,
            answer=decision.get(
                "message",
                "I can only answer questions about the data in this database's schema.",
            ),
        )

    raw_sql = decision.get("sql", "")

    # Step 2: SQL Validation & Safety Check
    try:
        safe_sql = validate_sql(raw_sql)
    except ValueError as e:
        return AgentResult(
            in_scope=False,
            answer=f"I generated a query I'm not allowed to run ({e}).",
        )

    # Step 3: Database Query Execution
    try:
        rows = run_sql(safe_sql, db_path)
    except sqlite3.Error as e:
        return AgentResult(
            in_scope=False,
            answer=f"That query failed to run against the database ({e}).",
            sql=safe_sql,
        )

    # Step 4: Answer Synthesis
    try:
        answer = synthesize_answer(question, rows)
    except Exception as e:
        return AgentResult(
            in_scope=True,
            answer="Query executed successfully, but failed to synthesize summary.",
            sql=safe_sql,
            rows=rows,
        )

    return AgentResult(in_scope=True, answer=answer, sql=safe_sql, rows=rows)