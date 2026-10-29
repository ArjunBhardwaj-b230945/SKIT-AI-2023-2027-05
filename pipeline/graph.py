"""
pipeline/graph.py
================================================================================
Single unified TaxSathi LangGraph graph.

Implements the exact architecture from the project design:

         START
           ↓
    [intent_router]
    /              \\
chatbot path      itr generation path
    ↓                    ↓
[rewrite_query]   [collect_user_input]
    ↓                    ↓
[retrieve]        [receive_ocr_output]
    ↓                    ↓
[build_prompt]    [cross_validation]
    ↓                    ↓
[gemini_call]     [tax_computation]
    ↓                    ↓
[format_response] [itr_field_mapper]
    ↓                    ↓
   END            [cbdt_validation]
                  /              \\
                NO               YES
                ↓                 ↓
         [show_errors]     [pdf_generation]
                ↓                 ↓
         user corrects           END
                ↓
       [collect_user_input]  ← loop back

NODE STATUS
-----------
✅ intent_router          — routes based on uploaded documents vs text query
✅ rewrite_query_node     — Gemini rewrites query for better RAG retrieval
✅ build_prompt_node      — assembles system + context + query for Gemini
✅ gemini_call_node       — calls Gemini API
✅ format_response_node   — appends assistant reply to messages
✅ collect_user_input_node — validates UserProvidedInfo mandatory fields
✅ cross_validation_node  — PAN match, TDS match, AY check, HITL on PAN mismatch
✅ tax_computation_node   — reconciles Form 16 + 26AS; computes GTI/tax/rebate/cess
✅ itr_field_mapper_node  — maps computed values to ITR-1 fields (B1→D14)
✅ cbdt_validation_node   — runs CBDT Category A rules (partial; Sprint 3)
✅ show_errors_node       — surfaces errors to user via interrupt; loops back
✅ pdf_generation_node    — WeasyPrint HTML → PDF (stub; Sprint 5)
🔧 retrieve_node          — STUB: Kushal's RAG vector DB (Sprint 4)

ENVIRONMENT VARIABLES
---------------------
  GOOGLE_API_KEY — required for rewrite_query_node and gemini_call_node
================================================================================
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from pipeline.state import TaxSathiState
from tax_schemas import (
    FlagSeverity,
    ValidationFlag,
    map_to_itr1,
    reconcile_tax_data,
)
from tax_computation import compute_part_d


# ================================================================================
# GEMINI CLIENT
# ================================================================================

def _gemini(temperature: float = 0.2) -> ChatGoogleGenerativeAI:
    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        raise EnvironmentError("GOOGLE_API_KEY environment variable is not set.")
    return ChatGoogleGenerativeAI(
        model="gemma-4-31b-it",
        google_api_key=key,
        temperature=temperature,
        max_output_tokens=1024,
    )


# ================================================================================
# SYSTEM PROMPTS
# ================================================================================

REWRITE_PROMPT = """You are a search query optimizer for an Indian income tax retrieval system.
Your job is to convert a user's casual question into a precise retrieval query
for searching the Income Tax Act 2025 and Income Tax Rules 2026.

ABBREVIATION EXPANSION TABLE — always expand these:
  HRA   → House Rent Allowance u/s 10(13A)
  LTA   → Leave Travel Concession u/s 10(5)
  TDS   → Tax Deducted at Source
  TCS   → Tax Collected at Source
  NPS   → National Pension Scheme u/s 80CCD
  ELSS  → Equity Linked Saving Scheme u/s 80C
  PPF   → Public Provident Fund u/s 80C
  EPF   → Employee Provident Fund u/s 80C
  GTI   → Gross Total Income
  ITR   → Income Tax Return
  AY    → Assessment Year
  PY    → Previous Year / Financial Year
  STD   → Standard Deduction u/s 16(ia)
  87A   → Rebate u/s 87A
  234A  → Interest for late filing u/s 234A
  234B  → Interest for advance tax default u/s 234B
  234C  → Interest for deferred installment u/s 234C
  234F  → Fee for belated return u/s 234F

RULES:
1. Output ONLY the rewritten query. No explanation, no preamble, no punctuation at end.
2. Keep it under 35 words.
3. Always include the relevant Section number if you can infer it.
4. If the user mentions "new regime" add "u/s 115BAC Finance Act 2025 AY 2026-27".
5. If the user mentions "old regime" add "opted out u/s 115BAC(6) Form 10IEA AY 2026-27".
6. If no regime is mentioned, do not assume one — keep the query regime-neutral.
7. If the question involves a monetary limit, add "limit threshold eligibility".
8. If the question involves a form (Form 16, 26AS, ITR-1), include the form name.

EXAMPLES:
  User: "can I claim both HRA and 80GG?"
  Output: Can individual simultaneously claim House Rent Allowance exemption u/s 10(13A) and deduction u/s 80GG for rent paid eligibility conditions AY 2026-27

  User: "what's the 80C limit under new regime?"
  Output: Section 80C deduction limit u/s 115BAC new regime Finance Act 2025 AY 2026-27 eligibility

  User: "standard deduction for salaried"
  Output: Standard deduction u/s 16(ia) salaried employees new regime old regime limit AY 2026-27

  User: "penalty for late filing"
  Output: Fee for belated return u/s 234F late filing penalty income limit AY 2026-27"""


ANSWER_PROMPT = """You are TaxSathi, an expert AI assistant specialising in Indian income tax for AY 2026-27 (FY 2025-26) under the Income Tax Act 2025 and Income Tax Rules 2026 as amended by Finance Act 2025.

═══════════════════════════════════════════════
IDENTITY AND BOUNDARIES
═══════════════════════════════════════════════
- You are a tax information assistant, NOT a Chartered Accountant or legal advisor.
- You answer ONLY from the retrieved context provided to you.
- You NEVER invent section numbers, monetary limits, or eligibility conditions.
- If the context does not contain the answer, say exactly:
  "The retrieved sections from the Income Tax Act 2025 and Rules 2026 do not cover this specific query. I recommend consulting a Chartered Accountant or the official Income Tax portal at incometax.gov.in."
- You do NOT answer questions outside Indian income tax scope.

═══════════════════════════════════════════════
CRITICAL AY 2026-27 CONTEXT (Finance Act 2025)
═══════════════════════════════════════════════
Always keep these in mind when answering — these are the key changes that users get confused about:

NEW REGIME (Default u/s 115BAC):
  - Basic exemption: ₹4,00,000 (was ₹3,00,000 in AY 2025-26)
  - Rebate u/s 87A: ₹60,000 for income ≤ ₹12,00,000 (effectively tax-free)
  - Standard deduction: ₹75,000 (salaried employees and pensioners)
  - Most deductions (80C, 80D, HRA, LTA etc.) are NOT available
  - This is the DEFAULT regime — taxpayer must file Form 10IEA to opt out

OLD REGIME (Opt-out via Form 10IEA before due date):
  - Basic exemption: ₹2,50,000 (regular), ₹3,00,000 (senior citizen 60-79 yrs), ₹5,00,000 (super senior ≥ 80 yrs)
  - Rebate u/s 87A: ₹12,500 for income ≤ ₹5,00,000
  - Standard deduction: ₹50,000
  - All deductions (80C, 80D, HRA, LTA etc.) ARE available

═══════════════════════════════════════════════
CITATION FORMAT — MANDATORY
═══════════════════════════════════════════════
Every factual statement MUST be followed by its source in this format:
  [Section X of Income Tax Act 2025]
  [Rule X of Income Tax Rules 2026]
  [Circular No. X / Notification No. X]

If a limit or condition comes from Finance Act 2025, write:
  [Section X as amended by Finance Act 2025]

NEVER give a monetary limit or eligibility condition without citing its source.

═══════════════════════════════════════════════
MONETARY FORMATTING — MANDATORY
═══════════════════════════════════════════════
Always use Indian number formatting with ₹ symbol:
  CORRECT:   ₹1,50,000  ₹12,00,000  ₹75,000  ₹50 crore
  INCORRECT: Rs. 150000  INR 1500000  150,000

═══════════════════════════════════════════════
RESPONSE STRUCTURE
═══════════════════════════════════════════════
Structure your answer clearly based on query type:

FOR DEDUCTION / EXEMPTION QUESTIONS:
  1. Direct answer (yes/no/amount) in the first sentence
  2. Eligibility conditions
  3. Monetary limit with citation
  4. Regime applicability (new vs old)
  5. Any important restrictions or exceptions

FOR COMPUTATION QUESTIONS:
  1. Formula or step-by-step calculation
  2. Each step cited to its section
  3. Example if helpful (use round numbers)
  4. Final answer

FOR FORM / DEADLINE QUESTIONS:
  1. Form name and purpose
  2. Who must file it
  3. Due date with citation
  4. Consequences of not filing

FOR ELIGIBILITY QUESTIONS:
  1. Conditions list (numbered)
  2. Each condition cited
  3. Disqualifying conditions
  4. Regime-specific note if applicable

═══════════════════════════════════════════════
RESPONSE LENGTH AND TONE
═══════════════════════════════════════════════
- Use plain, simple English. Avoid legal jargon where possible.
- 3-5 sentences for simple queries. More only when computation or multi-condition answers require it.
- Use bullet points for lists of conditions or steps — never for simple answers.
- End every response with this exact line:
  "⚠️ This is AI-generated tax information for AY 2026-27. Verify with a Chartered Accountant before filing."

═══════════════════════════════════════════════
REGIME AMBIGUITY HANDLING
═══════════════════════════════════════════════
If the user does not specify old or new regime:
  1. Answer for BOTH regimes side by side
  2. Clearly label each: "Under New Regime:" and "Under Old Regime:"
  3. Remind the user that new regime is the default for AY 2026-27

IF THE USER ASKS WHICH REGIME IS BETTER:
  Do NOT give a direct recommendation — tax planning is personal.
  Instead say: "The better regime depends on your total deductions. New regime is beneficial if your total Chapter VI-A deductions are less than approximately ₹X (calculated based on your income slab). A Chartered Accountant can run the exact comparison for your situation."

═══════════════════════════════════════════════
EXAMPLES OF GOOD RESPONSES
═══════════════════════════════════════════════
User: "Can I claim 80C under the new regime?"
Good: "No. Under the New Tax Regime u/s 115BAC (default from AY 2024-25), deductions under Section 80C are not available [Section 115BAC(2) as amended by Finance Act 2025]. This includes investments in PPF, ELSS, LIC premiums, and EPF contributions. To claim 80C, you must opt out of the new regime by filing Form 10IEA before the due date of filing your return [Section 115BAC(6)]. Under the Old Regime, 80C deductions up to ₹1,50,000 are available [Section 80C].
⚠️ This is AI-generated tax information for AY 2026-27. Verify with a Chartered Accountant before filing."

User: "Is my ₹12 lakh salary tax-free?"
Good: "Yes, for a salaried employee under the New Regime with gross salary of ₹12,75,000 or less, the effective tax liability is nil for AY 2026-27. After the standard deduction of ₹75,000 [Section 16(ia)], your taxable income becomes ₹12,00,000 or less, which qualifies for the full rebate of ₹60,000 u/s 87A [Section 87A as amended by Finance Act 2025], wiping out the entire tax liability. This benefit applies only under the New Regime — under the Old Regime, a salary of ₹12,75,000 would attract tax.
⚠️ This is AI-generated tax information for AY 2026-27. Verify with a Chartered Accountant before filing."
"""


# ================================================================================
# SHARED HELPER
# ================================================================================

def _parse_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


# ================================================================================
# ── ROUTING FUNCTIONS ──────────────────────────────────────────────────────────
# ================================================================================

def intent_router(state: TaxSathiState) -> str:
    """
    Entry point router — decides which path to take.

    Routes to ITR generation if both Form 16 and Form 26AS are present
    in state (uploaded by the user). Otherwise routes to chatbot.

    The FastAPI layer sets form16_list + form26as in state when the user
    uploads documents, and sets messages when the user sends a text query.
    """
    has_docs = (
        bool(state.get("form16_list")) and
        state.get("form26as") is not None
    )

    # Explicit intent overrides document detection
    explicit = state.get("intent")
    if explicit == "chatbot":
        return "rewrite_query"
    if explicit == "itr_generation":
        return "collect_user_input"

    # Auto-detect
    return "collect_user_input" if has_docs else "rewrite_query"


def route_after_user_input(state: TaxSathiState) -> str:
    if state.get("errors"):
        return END
    return "receive_ocr_output"


def route_after_ocr(state: TaxSathiState) -> str:
    if state.get("errors"):
        return END
    return "cross_validation"


def route_after_cross_validation(state: TaxSathiState) -> str:
    if state.get("errors"):
        return END
    return "tax_computation"


def route_after_tax_computation(state: TaxSathiState) -> str:
    if state.get("errors"):
        return END
    return "itr_field_mapper"


def route_after_itr_field_mapper(state: TaxSathiState) -> str:
    if state.get("errors"):
        return END
    return "cbdt_validation"


def route_after_cbdt_validation(state: TaxSathiState) -> str:
    """
    Core branching point — YES path goes to PDF, NO path shows errors
    and loops back to collect_user_input via show_errors_node.
    """
    draft = state.get("draft_itr1")
    if state.get("errors") or draft is None:
        return END

    category_a_errors = [
        f for f in draft.flags
        if f.severity == FlagSeverity.ERROR and f.stage == "itr_validation"
    ]

    if category_a_errors:
        return "show_errors"     # → NO path → user corrects → loop back

    return "pdf_generation"      # → YES path → generate PDF


def route_after_show_errors(state: TaxSathiState) -> str:
    """
    After show_errors_node resumes from interrupt, check loop count.
    If under max_loops, go back to collect_user_input.
    If over limit, stop to prevent infinite loops.
    """
    if state.get("loop_count", 0) >= state.get("max_loops", 3):
        return END
    return "collect_user_input"


# ================================================================================
# ── CHATBOT PATH NODES ─────────────────────────────────────────────────────────
# ================================================================================

def rewrite_query_node(state: TaxSathiState) -> TaxSathiState:
    """
    Rewrites the user's casual question into a precise retrieval query.

    Example:
      Input : "can I claim HRA and 80GG both?"
      Output: "Can an individual simultaneously claim HRA exemption u/s 10(13A)
               and deduction u/s 80GG for rent paid?"

    Falls back to the original message if Gemini is unavailable.
    """
    messages = state.get("messages", [])
    last_user_msg = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"),
        None,
    )

    if not last_user_msg:
        return {"errors": ["rewrite_query_node: no user message found in state."]}

    try:
        response = _gemini().invoke([
            SystemMessage(content=REWRITE_PROMPT),
            HumanMessage(content=last_user_msg),
        ])
        return {"query": response.content.strip()}
    except Exception as e:
        # Graceful fallback — don't block the pipeline
        return {
            "query": last_user_msg,
            "errors": [f"rewrite_query_node: Gemini unavailable ({e}). Using original query."],
        }


def retrieve_node(state: TaxSathiState) -> TaxSathiState:
    """
    STUB — Sprint 4 (16 Nov – 20 Dec 2026).
    Calls Kushal's RAG vector DB to fetch relevant chunks from
    Income Tax Act 2025 + Income Tax Rules 2026.

    Integration (Kushal):
        from rag.retriever import retrieve_tax_context
        chunks = retrieve_tax_context(query=state["query"], top_k=5)
        rag_context = "\\n\\n---\\n\\n".join(chunks)
    """
    # TODO (Kushal - Sprint 4): replace stub with real RAG retrieval
    query = state.get("query", "")
    stub_context = (
        f"[RAG STUB — Kushal's vector DB not connected yet]\n"
        f"Query: '{query}'\n"
        f"In production this returns chunks from IT Act 2025 + IT Rules 2026."
    )
    return {"rag_context": stub_context}


def build_prompt_node(state: TaxSathiState) -> TaxSathiState:
    """
    Assembles the full prompt: retrieved context + original user question.
    Injects context as a structured message so Gemini has a clear boundary
    between reference material and the question.
    """
    rag_context = state.get("rag_context", "No context retrieved.")
    messages = state.get("messages", [])

    original_question = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"),
        "",
    )

    combined = (
        f"REFERENCE CONTEXT (Income Tax Act 2025 + Rules 2026):\n"
        f"{'─' * 60}\n"
        f"{rag_context}\n"
        f"{'─' * 60}\n\n"
        f"USER QUESTION:\n{original_question}"
    )

    context_message = {"role": "user", "content": combined}
    return {"messages": [context_message]}


def gemini_call_node(state: TaxSathiState) -> TaxSathiState:
    """
    Sends the assembled prompt to Gemini and stores the raw answer.
    """
    messages = state.get("messages", [])
    last_content = messages[-1]["content"] if messages else ""

    try:
        response = _gemini(temperature=0.1).invoke([
            SystemMessage(content=ANSWER_PROMPT),
            HumanMessage(content=last_content),
        ])
        return {"chat_response": response.content.strip()}
    except Exception as e:
        return {
            "chat_response": (
                "I encountered an error generating your answer. "
                "Please try again or rephrase your question."
            ),
            "errors": [f"gemini_call_node: Gemini API failed — {e}"],
        }


def format_response_node(state: TaxSathiState) -> TaxSathiState:
    """
    Appends a disclaimer to the Gemini response and writes it as
    the assistant reply in the conversation history.
    """
    raw = state.get("chat_response", "")
    disclaimer = (
        "\n\n---\n"
        "⚠️ *AI-generated from Income Tax Act 2025 and Rules 2026. "
        "Verify with a qualified Chartered Accountant before filing.*"
    )
    assistant_msg = {"role": "assistant", "content": raw + disclaimer}
    return {"messages": [assistant_msg], "pipeline_complete": True}


# ================================================================================
# ── ITR GENERATION PATH NODES ──────────────────────────────────────────────────
# ================================================================================

def collect_user_input_node(state: TaxSathiState) -> TaxSathiState:
    """
    Validates UserProvidedInfo — checks that all fields ITR-1 requires
    (but Form 16/26AS cannot provide) are present.

    Mandatory:
      first_name, last_name, date_of_birth, aadhaar_number,
      primary_mobile, primary_email, filed_under_section,
      nature_of_employment, at least one bank account with refund selected.

    Also resets cbdt_error_summary so the UI can show fresh errors
    on each loop iteration.
    """
    user = state.get("user_input")
    missing = []

    if user is None:
        return {
            "errors": ["UserProvidedInfo is None — must be provided before ITR generation."],
            "cbdt_error_summary": None,
        }

    if not user.first_name or not user.last_name:
        missing.append("Name (first_name and last_name)")
    if not user.date_of_birth:
        missing.append("Date of birth (DD/MM/YYYY) — needed for tax slab selection")
    if not user.aadhaar_number:
        missing.append("Aadhaar number (12 digits) — mandatory u/s 139AA")
    if not user.primary_mobile:
        missing.append("Primary mobile number")
    if not user.primary_email:
        missing.append("Primary email address")
    if not user.filed_under_section:
        missing.append("Filing section (e.g. 139(1))")
    if not user.nature_of_employment:
        missing.append("Nature of employment (Central Govt / State Govt / PSU / Others)")
    if not user.bank_accounts:
        missing.append("At least one bank account for refund credit")
    elif not any(acc.selected_for_refund for acc in user.bank_accounts):
        missing.append("At least one bank account must be selected for refund")

    if missing:
        return {
            "errors": [f"collect_user_input: Missing required fields — {'; '.join(missing)}."],
            "cbdt_error_summary": None,
        }

    return {"cbdt_error_summary": None}


def receive_ocr_output_node(state: TaxSathiState) -> TaxSathiState:
    """
    STUB — verifies that Kushal's LlamaParser output is present in state.

    In production Kushal's parser runs before the graph and populates
    state["form16_list"] and state["form26as"] via the FastAPI upload
    endpoint. This node validates they arrived correctly.

    TODO (Kushal): if parser runs inside the graph, call it here.
    """
    form16_list = state.get("form16_list", [])
    form26as    = state.get("form26as")
    missing     = []

    if not form16_list:
        missing.append("Form 16 (no documents in form16_list)")
    if form26as is None:
        missing.append("Form 26AS (form26as is None)")

    if missing:
        return {"errors": [f"receive_ocr_output: Missing parsed documents — {'; '.join(missing)}."]}

    return {}


def cross_validation_node(state: TaxSathiState) -> TaxSathiState:
    """
    Cross-validates Form 16 and Form 26AS before computation.

    Checks:
      1. PAN consistency across all Form 16 documents and Form 26AS.
         → HITL interrupt on mismatch: pauses graph, asks user for corrected docs.
      2. Assessment year consistency.
      3. TDS amount: Form 16 Part A total TDS vs Form 26AS Part A total TDS.
      4. At least one Form 16 has a computable salary income figure.

    HITL Pattern (PAN mismatch):
      Graph pauses via interrupt(), surfaces mismatch message to user.
      FastAPI resumes with: Command(resume={"form16_list": [...], "form26as": ...})
    """
    form16_list = state.get("form16_list", [])
    form26as    = state.get("form26as")
    errors      = []

    if not form16_list or form26as is None:
        return {}  # already caught by receive_ocr_output_node

    # ── Check 1: PAN consistency ──────────────────────────────────────────────
    f16_pans = {
        f.details.employee_pan.strip().upper()
        for f in form16_list if f.details.employee_pan
    }
    f26_pan = form26as.pan.strip().upper() if form26as.pan else None

    pan_ok = (len(f16_pans) == 1 and f26_pan and next(iter(f16_pans)) == f26_pan)

    if not pan_ok:
        mismatch_msg = (
            f"PAN Mismatch Detected.\n"
            f"  Form 16 PAN(s) : {sorted(f16_pans) if f16_pans else 'not found'}\n"
            f"  Form 26AS PAN  : {f26_pan or 'not found'}\n"
            f"Please re-upload the correct documents."
        )
        # ── HITL interrupt ────────────────────────────────────────────────────
        correction = interrupt(payload=mismatch_msg)
        return {
            "form16_list": correction.get("form16_list", form16_list),
            "form26as":    correction.get("form26as", form26as),
            "errors":      [],
        }

    # ── Check 2: Assessment Year ──────────────────────────────────────────────
    f16_ays = {f.details.assessment_year for f in form16_list if f.details.assessment_year}
    if form26as.assessment_year and f16_ays and form26as.assessment_year not in f16_ays:
        errors.append(
            f"cross_validation: AY mismatch — Form 26AS AY ({form26as.assessment_year}) "
            f"does not match Form 16 AY ({f16_ays}). Verify uploaded documents."
        )

    # ── Check 3: TDS cross-check ──────────────────────────────────────────────
    # Sum of TDS across all Form 16 Part A totals vs Form 26AS Part A total
    f16_tds_list = [
        f.tax_computation.tds_per_12baa_19
        for f in form16_list
        if f.tax_computation.tds_per_12baa_19 is not None
    ]
    if f16_tds_list and form26as.total_tds_salary is not None:
        f16_tds_total = round(sum(f16_tds_list), 2)
        f26_tds_total = form26as.total_tds_salary
        if abs(f16_tds_total - f26_tds_total) > 1.0:
            errors.append(
                f"cross_validation: TDS mismatch — Form 16 total TDS (₹{f16_tds_total:,.2f}) "
                f"does not match Form 26AS Part A total TDS (₹{f26_tds_total:,.2f}). "
                f"Verify with employer before filing."
            )

    # ── Check 4: Usable salary figure ────────────────────────────────────────
    if not any(f.income_chargeable_salaries_6 is not None for f in form16_list):
        errors.append(
            "cross_validation: Could not compute 'Income chargeable under Salaries' "
            "from any Form 16. LlamaParser extraction may be incomplete."
        )

    return {"errors": errors}


def tax_computation_node(state: TaxSathiState) -> TaxSathiState:
    """
    Reconciles Form 16 + Form 26AS and computes:
      - Gross Total Income (GTI)
      - Chapter VI-A deductions
      - Net taxable income
      - Slab tax (new/old regime)
      - Rebate u/s 87A + marginal relief
      - Health & Education Cess (4%)

    Calls reconcile_tax_data() from tax_schemas.py which handles:
      - Multi-employer salary summing
      - Deduction double-count prevention
      - Interest income from Form 26AS Part A1
      - Property transaction eligibility check
    """
    try:
        reconciled = reconcile_tax_data(
            form16_documents=state.get("form16_list", []),
            form26as=state.get("form26as"),
        )

        # Block if ITR-1 ineligible (property transaction, etc.)
        if reconciled.itr1_eligible is False:
            reasons = [
                f.issue for f in reconciled.flags
                if f.severity == FlagSeverity.ERROR
            ]
            return {
                "reconciled": reconciled,
                "errors": [
                    "tax_computation: ITR-1 ineligibility detected. "
                    f"Reasons: {'; '.join(reasons)}"
                ],
            }

        return {"reconciled": reconciled}

    except Exception as e:
        return {"errors": [f"tax_computation_node crashed: {str(e)}"]}


def itr_field_mapper_node(state: TaxSathiState) -> TaxSathiState:
    """
    Maps all computed values to the exact ITR-1 field codes (B1, B2, C1...D14).

    Step 1: map_to_itr1() — populates:
      Part A (identity + regime from UserProvidedInfo + Form 16)
      Part B (B1 salary, B2 house property, B3 other sources, B4 GTI)
      Part C (C1 deductions, C2 total income)
      Schedule IT (advance tax entries from Form 26AS Part C)
      Schedule TDS (TDS entries from Form 26AS Part A + A1)

    Step 2: compute_part_d() — populates:
      Part D (D1 tax, D2 rebate, D3 after rebate, D4 cess, D5 total,
              D7 234A, D8 234B, D9 234C, D10 234F, D11 total fees,
              D12 taxes paid, D13 payable, D14 refund)
    """
    reconciled = state.get("reconciled")
    user       = state.get("user_input")

    if reconciled is None:
        return {"errors": ["itr_field_mapper: reconciled data is None."]}

    try:
        # Step 1 — map to ITR-1 structure
        draft_itr1 = map_to_itr1(reconciled=reconciled, user_input=user)

        # Step 2 — fill Part D tax computation
        filing_date = _parse_date(state.get("filing_date_str")) or date.today()
        dob         = user.date_of_birth if user else None

        draft_itr1 = compute_part_d(
            itr=draft_itr1,
            reconciled=reconciled,
            filing_date=filing_date,
            date_of_birth=dob,
        )

        return {"draft_itr1": draft_itr1}

    except Exception as e:
        return {"errors": [f"itr_field_mapper_node crashed: {str(e)}"]}


"""
CBDT ITR-1 validation (AY 2025-26, rules V1.1, 279 rules).

Design:
  * Each CBDT rule is one small function registered with @rule(...).
  * run_rules() executes every registered rule and returns ValidationFlags.
  * cbdt_validation_node() is the LangGraph node: idempotent, fails closed,
    and returns a state update instead of mutating shared objects.

Adding a rule = writing one function. Sprint 3 (279 rules) needs no
changes to the node or the runner.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

# Adjust to your project layout:
# from taxsathi.state import TaxSathiState
# from taxsathi.models import ValidationFlag, FlagSeverity

log = logging.getLogger(__name__)

STAGE = "itr_validation"

# Rule 24 tolerance in rupees. Check the CBDT PDF: if total income is rounded
# (s.288A, nearest ₹10), widen this to match the rounding the portal applies.
TOTAL_INCOME_TOLERANCE = 1

ITR1_INCOME_CEILING = 5_000_000  # ₹50,00,000


class Category(str, Enum):
    A = "A"  # blocks PDF generation
    B = "B"  # warning only


@dataclass(frozen=True)
class Rule:
    rule_id: int
    field: str
    description: str
    category: Category
    check: Callable[[object], Optional[str]]  # returns message if violated, else None


RULES: list[Rule] = []


def rule(rule_id: int, field: str, description: str, category: Category = Category.A):
    """Register a CBDT rule. The function returns an error message or None."""
    def decorator(fn: Callable[[object], Optional[str]]):
        if any(r.rule_id == rule_id for r in RULES):
            raise ValueError(f"Duplicate CBDT rule id: {rule_id}")
        RULES.append(Rule(rule_id, field, description, category, fn))
        return fn
    return decorator


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _inr(x) -> str:
    return f"₹{x:,.0f}"


def _all_present(*values) -> bool:
    return all(v is not None for v in values)


# --------------------------------------------------------------------------- #
# rules  (Sprint 3: add the remaining rules below, one function each)
# --------------------------------------------------------------------------- #
@rule(17, "part_c.total_deductions_C1", "Chapter VI-A deductions must not exceed GTI")
def rule_17(draft) -> Optional[str]:
    b4 = draft.part_b.gross_total_income_B4
    c1 = draft.part_c.total_deductions_C1
    if _all_present(b4, c1) and c1 > b4:
        return f"Deductions ({_inr(c1)}) exceed GTI ({_inr(b4)})."
    return None


@rule(24, "part_c.total_income_C2", "Total income must equal max(0, GTI − deductions)")
def rule_24(draft) -> Optional[str]:
    b4 = draft.part_b.gross_total_income_B4
    c1 = draft.part_c.total_deductions_C1
    c2 = draft.part_c.total_income_C2
    if _all_present(b4, c1, c2):
        expected = max(0, b4 - c1)
        if abs(c2 - expected) > TOTAL_INCOME_TOLERANCE:
            return f"Total income ({_inr(c2)}) ≠ GTI − Deductions ({_inr(expected)})."
    return None


@rule(117, "part_c.total_income_C2", "ITR-1 is not allowed above ₹50,00,000 total income")
def rule_117(draft) -> Optional[str]:
    c2 = draft.part_c.total_income_C2
    if c2 is not None and c2 > ITR1_INCOME_CEILING:
        return f"Income ({_inr(c2)}) exceeds the ITR-1 ceiling of ₹50,00,000. Use ITR-2."
    return None


# --------------------------------------------------------------------------- #
# runner
# --------------------------------------------------------------------------- #
def run_rules(draft) -> list:
    """Run every registered rule against the draft and return ValidationFlags."""
    flags = []
    for r in sorted(RULES, key=lambda r: r.rule_id):
        severity = FlagSeverity.ERROR if r.category is Category.A else FlagSeverity.WARNING
        try:
            message = r.check(draft)
        except Exception:
            # Fail closed: a rule we could not evaluate must not silently pass.
            log.exception("CBDT rule %s crashed", r.rule_id)
            message = "Could not be evaluated. Please review this field manually."
            severity = FlagSeverity.ERROR
        if message:
            flags.append(ValidationFlag(
                stage=STAGE,
                field=r.field,
                issue=f"Rule {r.rule_id}: {message}",
                severity=severity,
            ))
    return flags


def build_error_summary(flags: list) -> Optional[str]:
    """Human-readable summary of blocking (Category A) errors, or None."""
    blocking = [f for f in flags if f.stage == STAGE and f.severity == FlagSeverity.ERROR]
    if not blocking:
        return None
    lines = "\n".join(f"  • {f.issue}" for f in blocking)
    return f"The following issues must be fixed before generating your ITR-1:\n{lines}"


# --------------------------------------------------------------------------- #
# LangGraph node + router
# --------------------------------------------------------------------------- #
def cbdt_validation_node(state: "TaxSathiState") -> dict:
    """Validate the ITR-1 draft against CBDT rules. Category A errors block PDF generation."""
    draft = state.get("draft_itr1")
    if draft is None:
        return {"errors": ["cbdt_validation: draft_itr1 is None."]}

    # Idempotent: drop flags from a previous validation pass before re-running,
    # so loops (user fixes -> re-validate) don't pile up duplicates.
    kept = [f for f in draft.flags if f.stage != STAGE]
    all_flags = kept + run_rules(draft)

    # Assumes a pydantic v2 model. For a dataclass use dataclasses.replace(...).
    new_draft = draft.model_copy(update={"flags": all_flags})

    return {
        "draft_itr1": new_draft,
        "cbdt_error_summary": build_error_summary(all_flags),
    }


def route_after_cbdt_validation(state: "TaxSathiState") -> str:
    """Conditional edge. Rename the targets to match your graph."""
    return "show_errors" if state.get("cbdt_error_summary") else "generate_pdf"

def show_errors_node(state: TaxSathiState) -> TaxSathiState:
    """
    Surfaces CBDT Category A validation errors to the user and pauses
    the graph via interrupt() until the user provides corrected input.

    Loop mechanism:
      1. Graph pauses here with interrupt().
      2. FastAPI shows errors to the user (from cbdt_error_summary).
      3. User uploads corrected documents / updates UserProvidedInfo.
      4. FastAPI resumes with Command(resume={corrected state fields}).
      5. route_after_show_errors() sends graph back to collect_user_input.

    Circuit breaker: if loop_count reaches max_loops, graph routes to END
    instead of looping again, preventing infinite retry cycles.
    """
    error_summary = state.get("cbdt_error_summary", "Validation errors found. Please review and correct your information.")
    current_loop  = state.get("loop_count", 0)
    max_loops     = state.get("max_loops", 3)

    if current_loop >= max_loops:
        return {
            "errors": [
                f"show_errors: Maximum retry limit ({max_loops}) reached. "
                f"Please consult a Chartered Accountant for manual assistance."
            ],
        }

    payload = {
        "errors":     error_summary,
        "loop_count": current_loop,
        "max_loops":  max_loops,
    }

    # Graph pauses here — FastAPI must call resume with corrected data
    correction = interrupt(payload=payload)

    # Apply corrections returned by the user
    updates = {}
    if "user_input" in correction:
        updates["user_input"] = correction["user_input"]
    if "form16_list" in correction:
        updates["form16_list"] = correction["form16_list"]
    if "form26as" in correction:
        updates["form26as"] = correction["form26as"]

    updates["loop_count"]  = current_loop + 1
    updates["draft_itr1"]  = None   # reset draft — will be recomputed
    updates["reconciled"]  = None   # reset reconciled — will be recomputed

    return updates


def pdf_generation_node(state: TaxSathiState) -> dict:
    # WeasyPrint is imported lazily so it is only required when this node runs.
    import os
    import re
    import html as _html
    from datetime import datetime, date
    from enum import Enum
    from pathlib import Path
 
    # ── Guard: nothing to render ──────────────────────────────────────────────
    draft = state.get("draft_itr1")
    if draft is None:
        return {
            "errors":            ["pdf_generation: draft_itr1 is None — nothing to render."],
            "pipeline_complete": False,
        }
 
    try:
        from weasyprint import HTML
    except ImportError:
        return {
            "errors":            ["pdf_generation: WeasyPrint is not installed. Run: pip install weasyprint"],
            "pipeline_complete": False,
        }
 
    mask_pii = os.getenv("PDF_MASK_PII", "").strip() == "1"
 
    # ════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ════════════════════════════════════════════════════════════════════════
 
    def unwrap(value):
        """Return Enum.value for enums, otherwise the value unchanged."""
        return value.value if isinstance(value, Enum) else value
 
    def esc(value) -> str:
        """HTML-escape any value safely (enums unwrapped, None -> '')."""
        value = unwrap(value)
        return _html.escape(str(value) if value is not None else "")
 
    def to_num(value, default=0):
        """Coerce int/float/Decimal/numeric-str to a number; else default."""
        if value is None or isinstance(value, bool):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
 
    def inr(value) -> str:
        """
        Indian currency format with ₹ and lakh/crore grouping; handles negatives.
        1500000 -> ₹15,00,000 | -25000 -> -₹25,000
        """
        if value is None:
            return "—"
        try:
            n = int(round(float(value)))
        except (TypeError, ValueError):
            return str(value)
        prefix = "-₹" if n < 0 else "₹"
        s = str(abs(n))
        if len(s) > 3:
            s = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", s[:-3]) + "," + s[-3:]
        return f"{prefix}{s}"
 
    _ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ].*)?$")
 
    def fmt_date(value) -> str:
        """datetime/date or ISO string -> dd/mm/yyyy; anything else -> str."""
        if hasattr(value, "strftime"):
            return value.strftime("%d/%m/%Y")
        m = _ISO_DATE.match(str(value))
        if m:
            return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
        return str(value)
 
    def mask_account(acno: str) -> str:
        acno = str(acno or "")
        return ("X" * (len(acno) - 4) + acno[-4:]) if len(acno) > 4 else acno
 
    def mask_pan(s: str) -> str:
        return ("XXXXXX" + s[-4:]) if len(s) >= 10 else s
 
    def mask_mobile(s: str) -> str:
        digits = re.sub(r"\D", "", s)
        return ("XXXXXX" + digits[-4:]) if len(digits) >= 4 else s
 
    def mask_email(s: str) -> str:
        if "@" not in s:
            return s
        user, domain = s.split("@", 1)
        return (user[:1] + "***@" + domain) if user else s
 
    MONEY_KEYS = (
        "salary", "income", "deduction", "tax", "cess", "rebate",
        "interest", "fee", "refund", "payable", "credit", "tds",
        "tcs", "hra", "allowance", "perquisite", "profit", "total",
        "gross", "net", "sec_80", "relief", "pension", "rent",
    )
    NON_MONEY_KEYS = (
        "pan", "tan", "aadhaar", "mobile", "phone", "pin", "ifsc",
        "account_number", "year", "count", "number", "code", "loop",
        "max", "section", "serial", "bsr",
    )
 
    def fmt_field(key: str, value) -> str:
        """Format one value by key name and type (masking, dates, INR)."""
        value = unwrap(value)
        if value is None or value == "":
            return "Not provided"
        if isinstance(value, bool):
            return "Yes" if value else "No"
 
        k = key.lower()
        s = str(value)
 
        # Sensitive-field masking
        if "aadhaar" in k:
            digits = re.sub(r"\D", "", s)
            return ("XXXX XXXX " + digits[-4:]) if len(digits) >= 4 else "XXXX XXXX XXXX"
        if "account_number" in k:
            return mask_account(s)
        if mask_pii:
            if k == "pan":
                return mask_pan(s)
            if "mobile" in k or "phone" in k:
                return mask_mobile(s)
            if "email" in k:
                return mask_email(s)
 
        # Dates
        if hasattr(value, "strftime") or "date" in k:
            return fmt_date(value)
 
        # Numbers
        if isinstance(value, (int, float)) or type(value).__name__ == "Decimal":
            if any(m in k for m in NON_MONEY_KEYS):
                return s
            if any(m in k for m in MONEY_KEYS):
                return inr(value)
        return s
 
    def row(label: str, value, money: bool = False, key: str | None = None) -> str:
        """Two-column row. `key` (schema-style name) drives masking/format."""
        if money and value is not None:
            display = inr(value)
        else:
            display = fmt_field(key or label, value)
        cls = " class='money'" if money else ""
        return f"<tr><td class='lbl'>{esc(label)}</td><td{cls}>{esc(display)}</td></tr>"
 
    def section(title: str, rows_html: str, warn: bool = False, keep: bool = True) -> str:
        """Labelled key/value section. keep=True avoids splitting it over pages."""
        if not rows_html.strip():
            return ""
        cls = ("warn " if warn else "") + ("keep" if keep else "")
        return (
            f"<div class='section {cls.strip()}'>"
            f"<div class='sec-title'>{esc(title)}</div>"
            f"<table>{rows_html}</table>"
            f"</div>"
        )
 
    def th_row(*cols: str) -> str:
        return "<tr>" + "".join(f"<th>{esc(c)}</th>" for c in cols) + "</tr>"
 
    def data_section(title: str, header_html: str, body_html: str, warn: bool = False) -> str:
        """Multi-column table that may split across pages; header repeats."""
        cls = "section warn" if warn else "section"
        return (
            f"<div class='{cls}'>"
            f"<div class='sec-title'>{esc(title)}</div>"
            f"<table><thead>{header_html}</thead><tbody>{body_html}</tbody></table>"
            f"</div>"
        )
 
    # ════════════════════════════════════════════════════════════════════════
    # EXTRACT SCHEMA OBJECTS
    # ════════════════════════════════════════════════════════════════════════
 
    def g(obj, *attrs, default=None):
        """Safe nested attribute getter; returns default for missing/None."""
        for attr in attrs:
            if obj is None:
                return default
            obj = getattr(obj, attr, None)
        return obj if obj is not None else default
 
    def g_any(obj, *names, default=None):
        """First non-None attribute among several candidate names."""
        for name in names:
            val = getattr(obj, name, None) if obj is not None else None
            if val is not None:
                return val
        return default
 
    pa    = getattr(draft, "part_a", None)
    pb    = getattr(draft, "part_b", None)
    pc    = getattr(draft, "part_c", None)
    part_d = getattr(draft, "part_d", None)
    ded   = getattr(pc, "deductions", None) if pc is not None else None
    sits  = getattr(draft, "schedule_it", None) or []
    stds  = getattr(draft, "schedule_tds", None) or []
    banks = getattr(draft, "bank_accounts", None) or []
    flags = getattr(draft, "flags", None) or []
 
    # ════════════════════════════════════════════════════════════════════════
    # PART A — GENERAL INFORMATION
    # ════════════════════════════════════════════════════════════════════════
 
    regime_raw = unwrap(g(pa, "opting_out_115bac"))
    regime_display = (
        "Old Regime (opted out u/s 115BAC via Form 10IEA)"
        if str(regime_raw).upper() == "YES"
        else "New Regime (default u/s 115BAC — Finance Act 2025)"
    )
 
    full_name = " ".join(str(p) for p in (
        g(pa, "first_name"), g(pa, "middle_name"), g(pa, "last_name")
    ) if p) or "Not provided"
 
    part_a_rows = (
        row("Full Name",              full_name)
        + row("PAN",                  g(pa, "pan"),              key="pan")
        + row("Aadhaar Number",       g(pa, "aadhaar_number"),   key="aadhaar_number")
        + row("Date of Birth",        g(pa, "date_of_birth"),    key="date_of_birth")
        + row("Primary Mobile",       g(pa, "primary_mobile"),   key="primary_mobile")
        + row("Primary Email",        g(pa, "primary_email"),    key="primary_email")
        + row("Address",              g(pa, "address_line"),     key="address_line")
        + row("Town / City",          g(pa, "town_city"),        key="town_city")
        + row("State",                g(pa, "state"),            key="state")
        + row("PIN Code",             g(pa, "pin_code"),         key="pin_code")
        + row("Filed Under Section",  g(pa, "filed_under_section"),  key="filed_under_section")
        + row("Nature of Employment", g(pa, "nature_of_employment"), key="nature_of_employment")
        + row("Tax Regime",           regime_display)
        + row("Assessment Year",      "2026-27")
    )
 
    # ════════════════════════════════════════════════════════════════════════
    # PART B — GROSS TOTAL INCOME
    # ════════════════════════════════════════════════════════════════════════
 
    part_b_rows = (
        row("B1 — Income from Salaries",            g(pb, "salary_gross_B1"),          money=True)
        + row("B2 — Income from House Property",    g(pb, "house_property_income_B2"), money=True)
        + row("B3 — Income from Other Sources",     g(pb, "other_sources_income_B3"),  money=True)
        + row("B4 — Gross Total Income (B1+B2+B3)", g(pb, "gross_total_income_B4"),    money=True)
    )
    if g(pb, "gross_total_income_B4_is_partial"):
        part_b_rows += row("⚠ Note", "B4 is a partial total — house property income not confirmed")
 
    # ════════════════════════════════════════════════════════════════════════
    # PART C — DEDUCTIONS AND TOTAL INCOME
    # (C2 / C3 are intentionally absent: this schema folds them into C1.)
    # ════════════════════════════════════════════════════════════════════════
 
    def ded_row(label: str, attr: str) -> str:
        val = g(ded, attr)
        if val is None or to_num(val) == 0:
            return ""
        return row(label, val, money=True)
 
    part_c_deduction_rows = (
        ded_row("C1 — 80C / 80CCC / 80CCD(1) (combined)", "sec_80c_80ccc_80ccd1_combined")
        + ded_row("C4 — 80CCD(1B) — NPS (extra ₹50,000)",  "sec_80ccd_1b")
        + ded_row("C5 — 80CCD(2) — Employer NPS",          "sec_80ccd_2")
        + ded_row("C6 — 80D — Health Insurance",           "sec_80d")
        + ded_row("C7 — 80DD — Dependent Disability",      "sec_80dd")
        + ded_row("C8 — 80DDB — Specified Disease",        "sec_80ddb")
        + ded_row("C9 — 80E — Education Loan",             "sec_80e")
        + ded_row("C10 — 80EE — Home Loan (old)",          "sec_80ee")
        + ded_row("C11 — 80EEA — Affordable Housing",      "sec_80eea")
        + ded_row("C12 — 80EEB — Electric Vehicle",        "sec_80eeb")
        + ded_row("C13 — 80G — Donations",                 "sec_80g")
        + ded_row("C14 — 80GG — House Rent (no HRA)",      "sec_80gg")
        + ded_row("C15 — 80GGC — Political Party",         "sec_80ggc")
        + ded_row("C16 — 80TTA — Savings Interest",        "sec_80tta")
        + ded_row("C17 — 80TTB — Senior Citizen Interest", "sec_80ttb")
        + ded_row("C18 — 80U — Self Disability",           "sec_80u")
        + ded_row("C18a — 80CCH — Agnipath",               "sec_80cch")
    )
 
    for entry in (g(ded, "unmapped_entries") or []):
        sec = unwrap(g(entry, "section")) or "Unknown"
        amt = g(entry, "deductible_amount")
        part_c_deduction_rows += row(
            f"⚠ Unmapped — {sec}",
            f"{inr(amt)} (not auto-mapped to ITR-1 field — verify manually)",
        )
 
    # Fallback names guard against label/schema drift (C19/C20 vs C1/C2).
    total_deductions = g_any(pc, "total_deductions_C19", "total_deductions_C1", "total_deductions")
    total_income     = g_any(pc, "total_income_C20", "total_income_C2", "total_income")
 
    part_c_summary_rows = (
        row("C19 — Total Deductions", total_deductions, money=True)
        + row("C20 — Total Income",   total_income,     money=True)
    )
 
    # ════════════════════════════════════════════════════════════════════════
    # PART D — TAX COMPUTATION
    # ════════════════════════════════════════════════════════════════════════
 
    part_d_rows = (
        row("D1 — Tax on Total Income",                 g(part_d, "tax_payable_on_total_income_D1"), money=True)
        + row("D2 — Rebate u/s 87A",                    g(part_d, "rebate_87a_D2"),                  money=True)
        + row("D3 — Tax after Rebate",                  g(part_d, "tax_after_rebate_D3"),            money=True)
        + row("D4 — Health & Education Cess @ 4%",      g(part_d, "health_education_cess_D4"),       money=True)
        + row("D5 — Total Tax and Cess",                g(part_d, "total_tax_and_cess_D5"),          money=True)
        + row("D6 — Relief u/s 89 (requires Form 10E)", g(part_d, "relief_89_D6"),                   money=True)
        + row("D7 — Interest u/s 234A (late filing)",   g(part_d, "interest_234a_D7"),               money=True)
        + row("D8 — Interest u/s 234B (advance tax)",   g(part_d, "interest_234b_D8"),               money=True)
        + row("D9 — Interest u/s 234C (installments)",  g(part_d, "interest_234c_D9"),               money=True)
        + row("D10 — Fee u/s 234F (belated filing)",    g(part_d, "fee_234f_D10"),                   money=True)
        + row("D11 — Total Tax, Fee and Interest",      g(part_d, "total_tax_fee_interest_D11"),     money=True)
        + row("D12 — Total Taxes Paid",                 g(part_d, "total_taxes_paid_D12"),           money=True)
        + row("D13 — Amount Payable",                   g(part_d, "amount_payable_D13"),             money=True)
        + row("D14 — Refund Due",                       g(part_d, "refund_D14"),                     money=True)
    )
 
    # ════════════════════════════════════════════════════════════════════════
    # PART E — BANK ACCOUNTS
    # ════════════════════════════════════════════════════════════════════════
 
    bank_body = ""
    for acc in banks:
        bank_body += (
            "<tr>"
            f"<td>{esc(g(acc, 'ifsc_code'))}</td>"
            f"<td>{esc(g(acc, 'bank_name'))}</td>"
            f"<td>{esc(mask_account(g(acc, 'account_number', default='')))}</td>"
            f"<td>{esc(g(acc, 'account_type'))}</td>"
            f"<td>{'✓' if g(acc, 'selected_for_refund') else ''}</td>"
            "</tr>"
        )
    part_e_html = (
        data_section(
            "Part E — Bank Accounts",
            th_row("IFSC Code", "Bank Name", "Account Number", "Type", "For Refund"),
            bank_body,
        )
        if banks else ""
    )
 
    # ════════════════════════════════════════════════════════════════════════
    # SCHEDULE IT — ADVANCE / SELF-ASSESSMENT TAX
    # ════════════════════════════════════════════════════════════════════════
 
    sit_body = ""
    sit_total = 0.0
    for entry in sits:
        amt = to_num(g(entry, "tax_paid"))
        sit_total += amt
        sit_body += (
            "<tr>"
            f"<td>{esc(g(entry, 'bsr_code'))}</td>"
            f"<td>{esc(fmt_date(g(entry, 'date_of_deposit')) if g(entry, 'date_of_deposit') else '')}</td>"
            f"<td>{esc(g(entry, 'challan_serial_no'))}</td>"
            f"<td class='money'>{esc(inr(amt))}</td>"
            "</tr>"
        )
    if sits:
        sit_body += (
            f"<tr class='total'><td colspan='3'><b>Total</b></td>"
            f"<td class='money'><b>{esc(inr(sit_total))}</b></td></tr>"
        )
    schedule_it_html = (
        data_section(
            "Schedule IT — Advance Tax / Self-Assessment Tax",
            th_row("BSR Code", "Date of Deposit", "Challan No.", "Amount (₹)"),
            sit_body,
        )
        if sits else ""
    )
 
    # ════════════════════════════════════════════════════════════════════════
    # SCHEDULE TDS — TDS / TCS CREDITS
    # ════════════════════════════════════════════════════════════════════════
 
    std_body = ""
    std_total_claimed = 0.0
    for entry in stds:
        claimed = to_num(g(entry, "tds_claimed_this_year"))
        std_total_claimed += claimed
        std_body += (
            "<tr>"
            f"<td>{esc(g(entry, 'tan_or_pan'))}</td>"
            f"<td>{esc(g(entry, 'deductor_name'))}</td>"
            f"<td>{esc(g(entry, 'section'))}</td>"
            f"<td class='money'>{esc(inr(g(entry, 'gross_payment')))}</td>"
            f"<td class='money'>{esc(inr(g(entry, 'tax_deducted')))}</td>"
            f"<td class='money'>{esc(inr(claimed))}</td>"
            "</tr>"
        )
    if stds:
        std_body += (
            f"<tr class='total'><td colspan='5'><b>Total TDS Claimed</b></td>"
            f"<td class='money'><b>{esc(inr(std_total_claimed))}</b></td></tr>"
        )
    schedule_tds_html = (
        data_section(
            "Schedule TDS — TDS / TCS Credits",
            th_row("TAN / PAN", "Deductor Name", "Section",
                   "Gross Payment (₹)", "TDS Deducted (₹)", "TDS Claimed (₹)"),
            std_body,
        )
        if stds else ""
    )
 
    # ════════════════════════════════════════════════════════════════════════
    # VALIDATION FLAGS
    # ════════════════════════════════════════════════════════════════════════
 
    def severity_value(f) -> str:
        sev = unwrap(getattr(f, "severity", None))
        return str(sev).upper() if sev is not None else "INFO"
 
    def severity_class(sev: str) -> str:
        return {"ERROR": "flag-error", "WARNING": "flag-warn", "INFO": "flag-info"}.get(sev, "flag-info")
 
    flags_html = ""
    if flags:
        flag_body = ""
        for f in flags:
            sev = severity_value(f)
            flag_body += (
                f"<tr class='{severity_class(sev)}'>"
                f"<td><b>{esc(sev)}</b></td>"
                f"<td>{esc(getattr(f, 'stage', ''))}</td>"
                f"<td>{esc(getattr(f, 'field', ''))}</td>"
                f"<td>{esc(getattr(f, 'issue', str(f)))}</td>"
                "</tr>"
            )
        flags_html = data_section(
            "Items to Verify Before Filing",
            th_row("Severity", "Stage", "Field", "Issue"),
            flag_body,
            warn=True,
        )
 
    # ════════════════════════════════════════════════════════════════════════
    # REFUND / PAYABLE BANNER
    # ════════════════════════════════════════════════════════════════════════
 
    refund_amt  = to_num(g(part_d, "refund_D14"))
    payable_amt = to_num(g(part_d, "amount_payable_D13"))
 
    if refund_amt > 0:
        summary_banner = (
            f"<div class='summary refund'>REFUND DUE: {esc(inr(refund_amt))}"
            f" — Credit to selected bank account after processing</div>"
        )
    elif payable_amt > 0:
        summary_banner = (
            f"<div class='summary payable'>TAX PAYABLE: {esc(inr(payable_amt))}"
            f" — Pay via Challan 280 (Self-Assessment) before filing</div>"
        )
    else:
        summary_banner = (
            "<div class='summary nil'>NIL BALANCE — Tax fully paid. No refund or payment due.</div>"
        )
 
    # ════════════════════════════════════════════════════════════════════════
    # ASSEMBLE HTML
    # ════════════════════════════════════════════════════════════════════════
 
    generated_at = datetime.now().strftime("%d %b %Y, %I:%M %p")
 
    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: A4;
    margin: 15mm 12mm 18mm 12mm;
    @bottom-left {{
      content: "TaxSathi DRAFT — NOT FILED — AI-assisted preparation";
      font-size: 7.5pt; color: #888; font-family: Arial, sans-serif;
    }}
    @bottom-right {{
      content: "Page " counter(page) " of " counter(pages);
      font-size: 7.5pt; color: #888; font-family: Arial, sans-serif;
    }}
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "DejaVu Sans", Arial, sans-serif;
    font-size: 9pt;
    color: #111;
    line-height: 1.4;
  }}
 
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 8px;
    border-bottom: 2px solid #1f3a5f;
    padding-bottom: 6px;
  }}
  .header h1 {{ font-size: 13pt; color: #1f3a5f; font-weight: bold; }}
  .header .meta {{ font-size: 7.5pt; color: #666; text-align: right; }}
 
  .draft-banner {{
    background: #fff4e5;
    border: 1.5px solid #f0a500;
    padding: 5px 10px;
    font-size: 8pt;
    margin-bottom: 8px;
    border-radius: 2px;
  }}
 
  .summary {{
    padding: 6px 12px;
    font-size: 10pt;
    font-weight: bold;
    margin-bottom: 10px;
    border-radius: 2px;
  }}
  .summary.refund  {{ background: #e6f4ea; border: 1.5px solid #34a853; color: #1a7035; }}
  .summary.payable {{ background: #fce8e6; border: 1.5px solid #d93025; color: #a31c12; }}
  .summary.nil     {{ background: #e8f0fe; border: 1.5px solid #4285f4; color: #1a56c4; }}
 
  .section {{ margin-bottom: 10px; }}
  .section.keep {{ page-break-inside: avoid; }}
  .sec-title {{
    background: #1f3a5f;
    color: #fff;
    font-size: 9.5pt;
    font-weight: bold;
    padding: 4px 8px;
    page-break-after: avoid;
  }}
  .section.warn .sec-title {{ background: #c0392b; }}
 
  table {{ width: 100%; border-collapse: collapse; font-size: 8.5pt; }}
  thead {{ display: table-header-group; }}
  tr {{ page-break-inside: avoid; }}
  th {{
    background: #dde4ee;
    border: 1px solid #b0bbc8;
    padding: 3px 6px;
    text-align: left;
    font-weight: bold;
  }}
  td {{ border: 1px solid #c9c9c9; padding: 3px 6px; vertical-align: top; }}
  td.lbl {{ width: 55%; color: #333; }}
  td.money {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tr.total td {{ background: #eef2f7; font-weight: bold; }}
 
  tr.flag-error td {{ background: #fce8e6; }}
  tr.flag-warn  td {{ background: #fef7e0; }}
  tr.flag-info  td {{ background: #e8f0fe; }}
</style>
</head>
<body>
 
<div class="header">
  <div>
    <h1>ITR-1 (Sahaj) — Draft Summary</h1>
    <div style="font-size:8pt; color:#555;">
      Assessment Year: 2026-27 &nbsp;|&nbsp; Financial Year: 2025-26
    </div>
  </div>
  <div class="meta">
    Generated by TaxSathi<br>
    {esc(generated_at)}<br>
    Powered by AI — Not filed
  </div>
</div>
 
<div class="draft-banner">
  <b>⚠ DRAFT — NOT FILED.</b> This is an AI-assisted preparation for review purposes only.
  Every figure must be verified against original Form 16 and Form 26AS.
  Consult a Chartered Accountant before submitting to the Income Tax portal.
</div>
 
{summary_banner}
 
{section("Part A — General Information", part_a_rows)}
{section("Part B — Gross Total Income", part_b_rows)}
{section("Part C — Deductions (Chapter VI-A)", part_c_deduction_rows, keep=False)}
{section("Part C — Total Income Summary", part_c_summary_rows)}
{section("Part D — Tax Computation", part_d_rows)}
{part_e_html}
{schedule_it_html}
{schedule_tds_html}
{flags_html}
 
</body>
</html>"""
 
    # ════════════════════════════════════════════════════════════════════════
    # GENERATE PDF
    # ════════════════════════════════════════════════════════════════════════
 
    try:
        pdf_bytes = HTML(string=html_doc).write_pdf()
    except Exception as e:
        return {
            "errors":            [f"pdf_generation: WeasyPrint rendering failed — {type(e).__name__}: {e}"],
            "pipeline_complete": False,
        }
 
    # ── Optional: save to disk (development / testing) ────────────────────────
    out_dir = os.getenv("PDF_OUTPUT_DIR")
    if out_dir:
        try:
            stamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = Path(out_dir) / f"itr1_draft_{stamp}.pdf"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(pdf_bytes)
            print(f"[pdf_generation] Saved draft PDF to {out_path}")
        except Exception as e:
            # Non-fatal — the PDF bytes are still returned.
            print(f"[pdf_generation] Warning: could not save to disk — {e}")
 
    return {
        "pdf_bytes":         pdf_bytes,
        "pipeline_complete": True,
    }
# ================================================================================
# GRAPH COMPILATION
# ================================================================================

def build_graph():
    """
    Builds and compiles the single unified TaxSathi StateGraph.

    Matches the exact architecture from the project design document:
      START → intent_router → chatbot path OR itr generation path

    Requires MemorySaver (or persistent checkpointer) for interrupt()
    nodes to work (cross_validation PAN mismatch and show_errors loop).
    """
    g = StateGraph(TaxSathiState)

    # ── Register all nodes ────────────────────────────────────────────────────

    # Chatbot path
    g.add_node("rewrite_query",    rewrite_query_node)
    g.add_node("retrieve",         retrieve_node)
    g.add_node("build_prompt",     build_prompt_node)
    g.add_node("gemini_call",      gemini_call_node)
    g.add_node("format_response",  format_response_node)

    # ITR generation path
    g.add_node("collect_user_input",  collect_user_input_node)
    g.add_node("receive_ocr_output",  receive_ocr_output_node)
    g.add_node("cross_validation",    cross_validation_node)
    g.add_node("tax_computation",     tax_computation_node)
    g.add_node("itr_field_mapper",    itr_field_mapper_node)
    g.add_node("cbdt_validation",     cbdt_validation_node)
    g.add_node("show_errors",         show_errors_node)
    g.add_node("pdf_generation",      pdf_generation_node)

    # ── Edges from START ──────────────────────────────────────────────────────
    g.add_conditional_edges(
        START,
        intent_router,
        {
            "rewrite_query":      "rewrite_query",
            "collect_user_input": "collect_user_input",
        },
    )

    # ── Chatbot path edges ────────────────────────────────────────────────────
    g.add_edge("rewrite_query",   "retrieve")
    g.add_edge("retrieve",        "build_prompt")
    g.add_edge("build_prompt",    "gemini_call")
    g.add_edge("gemini_call",     "format_response")
    g.add_edge("format_response", END)

    # ── ITR generation path edges ─────────────────────────────────────────────
    g.add_conditional_edges("collect_user_input",  route_after_user_input)
    g.add_conditional_edges("receive_ocr_output",  route_after_ocr)
    g.add_conditional_edges("cross_validation",    route_after_cross_validation)
    g.add_conditional_edges("tax_computation",     route_after_tax_computation)
    g.add_conditional_edges("itr_field_mapper",    route_after_itr_field_mapper)
    g.add_conditional_edges("cbdt_validation",     route_after_cbdt_validation,
        {
            "show_errors":    "show_errors",     # NO path
            "pdf_generation": "pdf_generation",  # YES path
            END:              END,
        }
    )

    # ── Loop back edge: show_errors → collect_user_input ─────────────────────
    g.add_conditional_edges(
        "show_errors",
        route_after_show_errors,
        {
            "collect_user_input": "collect_user_input",
            END:                  END,
        },
    )

    g.add_edge("pdf_generation", END)

    # ── Compile with checkpointer (required for interrupt nodes) ──────────────
    from langgraph.checkpoint.memory import MemorySaver
    return g.compile(checkpointer=MemorySaver())


# Single compiled app — import this everywhere
app = build_graph()
