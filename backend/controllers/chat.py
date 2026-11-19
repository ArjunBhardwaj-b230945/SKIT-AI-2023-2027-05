from datetime import datetime, timezone
import json
import os
import re
from typing import Any
import uuid

import httpx
from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from models.chat import ChatMessageModel
from schemas.chat import (
    ChatCitation,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatSessionHistoryResponse,
    ChatSessionSummary,
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# ==============================================================================
# TAX KNOWLEDGE BASE & EXPERT LOGIC (OFFLINE / FALLBACK & ENRICHMENT)
# ==============================================================================

TAX_KNOWLEDGE_BASE = [
    {
        "keywords": ["regime", "old vs new", "new vs old", "difference", "compare", "slab"],
        "title": "Tax Regimes Comparison (FY 2024-25 / AY 2025-26)",
        "section": "Section 115BAC vs Old Regime",
        "citation": "Finance Act 2024 & Section 115BAC of Income Tax Act, 1961",
        "reply": (
            "### Comparison: New vs Old Tax Regime (FY 2024-25 / AY 2025-26)\n\n"
            "**1. New Tax Regime (Default):**\n"
            "- **Standard Deduction:** Increased to **₹75,000** for salaried individuals.\n"
            "- **Tax Slabs:**\n"
            "  - Up to ₹3,00,000: **Nil**\n"
            "  - ₹3,00,001 to ₹7,00,000: **5%**\n"
            "  - ₹7,00,001 to ₹10,00,000: **10%**\n"
            "  - ₹10,00,001 to ₹12,00,000: **15%**\n"
            "  - ₹12,00,001 to ₹15,00,000: **20%**\n"
            "  - Above ₹15,00,000: **30%**\n"
            "- **Section 87A Rebate:** Taxable income up to **₹7,00,000** pays **ZERO tax** (effectively up to ₹7,75,000 with standard deduction).\n"
            "- *Note:* Most exemptions/deductions (80C, 80D, HRA) are not allowed under New Regime.\n\n"
            "**2. Old Tax Regime:**\n"
            "- Standard deduction: **₹50,000**.\n"
            "- Allows full deductions: Section 80C (up to ₹1.5L), 80D (Health Insurance up to ₹25k/₹50k), HRA under Sec 10(13A), Home loan interest under Sec 24(b) (up to ₹2L).\n"
            "- Zero tax rebate up to **₹5,00,000** taxable income.\n\n"
            "**Recommendation:** If your total deductions (80C + 80D + HRA + Home Loan) exceed ~₹3.75 Lakhs to ₹4 Lakhs, the Old Regime may be beneficial; otherwise, the New Regime provides lower tax."
        ),
        "suggestions": [
            "Which regime is better for my salary?",
            "What deductions are allowed under New Tax Regime?",
            "How to calculate HRA exemption?",
        ],
    },
    {
        "keywords": ["80c", "deduction", "investment", "ppf", "elss", "epf", "lic"],
        "title": "Deductions under Section 80C",
        "section": "Section 80C",
        "citation": "Income Tax Act, 1961 - Section 80C Deductions",
        "reply": (
            "### Section 80C Deductions Overview\n\n"
            "- **Maximum Limit:** **₹1,50,000** per financial year (available only in **Old Tax Regime**).\n"
            "- **Eligible Investments & Expenses:**\n"
            "  1. **EPF / VPF:** Employee Provident Fund contributions deducted by employer.\n"
            "  2. **PPF (Public Provident Fund):** 15-year government-backed tax-free scheme.\n"
            "  3. **ELSS (Equity Linked Savings Scheme):** Tax-saving mutual funds with a 3-year lock-in period.\n"
            "  4. **Life Insurance Premium:** Term insurance or traditional LIC policies.\n"
            "  5. **National Savings Certificate (NSC) & Sukanya Samriddhi Yojana (SSY).**\n"
            "  6. **Home Loan Principal Repayment.**\n"
            "  7. **Children's Tuition Fees:** Paid for full-time education in Indian schools/colleges.\n\n"
            "*Note: Section 80C is NOT deductible under the New Tax Regime (Section 115BAC).*"
        ),
        "suggestions": [
            "Can I claim Section 80D in addition to 80C?",
            "How to get tax benefit for NPS under 80CCD(1B)?",
            "What is the lock-in period for ELSS mutual funds?",
        ],
    },
    {
        "keywords": ["80d", "health", "medical", "insurance", "mediclaim"],
        "title": "Deductions under Section 80D",
        "section": "Section 80D",
        "citation": "Income Tax Act, 1961 - Section 80D Deduction for Medical Insurance",
        "reply": (
            "### Medical Insurance Deductions (Section 80D)\n\n"
            "Available under the **Old Tax Regime**:\n"
            "1. **Self, Spouse & Dependent Children:** Up to **₹25,000** per year (or **₹50,000** if self/spouse is a senior citizen age 60+).\n"
            "2. **Parents (below 60 years):** Additional deduction up to **₹25,000**.\n"
            "3. **Senior Citizen Parents (60+ years):** Additional deduction up to **₹50,000**.\n"
            "4. **Preventive Health Checkup:** Up to **₹5,000** included within the overall limit.\n\n"
            "- **Maximum Possible Deduction:** **₹1,00,000** (if both taxpayer and parents are senior citizens 60+).\n"
            "- Payment must be made through non-cash modes (net banking, UPI, cards); preventive health checkup can be in cash."
        ),
        "suggestions": [
            "Can I claim medical bills without insurance under 80D?",
            "Is 80D available in the New Tax Regime?",
            "What is Section 80CCD(1B) for NPS?",
        ],
    },
    {
        "keywords": ["hra", "rent", "house rent", "allowance", "landlord", "10(13a)"],
        "title": "House Rent Allowance (HRA) Exemption",
        "section": "Section 10(13A) read with Rule 2A",
        "citation": "Income Tax Act, 1961 - Rule 2A of Income Tax Rules",
        "reply": (
            "### House Rent Allowance (HRA) Exemption Rules\n\n"
            "HRA exemption is claimed under the **Old Tax Regime**. The exempt amount is the **minimum of the following three**:\n"
            "1. **Actual HRA received** from employer.\n"
            "2. **50% of Basic Salary + DA** (if living in Delhi, Mumbai, Kolkata, Chennai) OR **40% of Basic Salary** (for non-metro cities).\n"
            "3. **Actual rent paid minus 10% of Basic Salary + DA**.\n\n"
            "- **Mandatory Requirements:** Rent receipts, rent agreement, and Landlord's PAN if annual rent exceeds **₹1,00,000**.\n"
            "- *Note:* HRA cannot be claimed if you opt for the New Tax Regime."
        ),
        "suggestions": [
            "How to claim HRA if living with parents?",
            "What if my landlord does not have a PAN card?",
            "Can I claim both HRA and Home Loan Interest?",
        ],
    },
    {
        "keywords": ["form 16", "26as", "ais", "tis", "tds", "mismatch"],
        "title": "Reconciliation of Form 16, 26AS, and AIS",
        "section": "Section 203 & 206AA",
        "citation": "Income Tax Department AIS/26AS Validation Standards",
        "reply": (
            "### Form 16 vs 26AS vs AIS Reconciliation\n\n"
            "1. **Form 16:** Certificate issued by your employer stating total salary paid and TDS deducted under Section 192.\n"
            "2. **Form 26AS:** Tax credit statement showing all TDS/TCS deposited against your PAN with the government.\n"
            "3. **AIS (Annual Information Statement):** Comprehensive report including salary, bank interest, dividends, mutual fund sales, and property transactions.\n\n"
            "**Key Checklist before filing ITR:**\n"
            "- Ensure the TDS reported in Form 16 Part A matches Part A of Form 26AS.\n"
            "- Check savings account interest and FD interest from AIS/TIS and report them under 'Income from Other Sources'.\n"
            "- If there is a mismatch in TDS, contact your employer or deductor to file a revised TDS return."
        ),
        "suggestions": [
            "What to do if TDS is deducted but not showing in 26AS?",
            "Which ITR form should I file for salary income?",
            "How to download Form 26AS from Income Tax portal?",
        ],
    },
    {
        "keywords": ["itr-1", "itr-2", "sahaj", "which itr", "form should i file", "eligibility"],
        "title": "ITR Form Selection Guide",
        "section": "CBDT ITR Filing Guidelines",
        "citation": "Rule 12 of Income Tax Rules, 1962",
        "reply": (
            "### Which ITR Form Should You File?\n\n"
            "- **ITR-1 (Sahaj):** For resident individuals having total income up to **₹50 Lakhs** from:\n"
            "  - Salary or Pension\n"
            "  - One house property\n"
            "  - Other sources (interest, family pension)\n"
            "  - Agricultural income up to ₹5,000.\n"
            "  *(Cannot be filed if you have capital gains, business income, or foreign assets).*\n\n"
            "- **ITR-2:** For individuals/HUFs with salary, more than one house property, or **Capital Gains** (shares, mutual funds, property sale), but NO business/profession income.\n\n"
            "- **ITR-3:** For individuals having income from business or profession.\n\n"
            "- **ITR-4 (Sugam):** For presumptive taxation income under Section 44AD, 44ADA, 44AE with total income up to ₹50 Lakhs."
        ),
        "suggestions": [
            "Can I file ITR-1 if I sold mutual funds or shares?",
            "What is the penalty for filing ITR after the due date?",
            "How to file ITR online through TaxSathi?",
        ],
    },
    {
        "keywords": ["standard deduction", "75000", "50000"],
        "title": "Standard Deduction Rules",
        "section": "Section 16(ia)",
        "citation": "Finance (No. 2) Act 2024 Amendment to Section 16",
        "reply": (
            "### Standard Deduction for Salaried Employees\n\n"
            "- **New Tax Regime (FY 2024-25 / AY 2025-26):** **₹75,000** (increased from ₹50,000 in Budget 2024).\n"
            "- **Old Tax Regime:** **₹50,000**.\n"
            "- **Pensioners:** Family pensioners get standard deduction of **₹25,000** under New Regime (previously ₹15,000).\n"
            "- **Proof Required:** No bills, rent receipts, or investment documents are required. It is an automatic statutory deduction directly applied against gross salary."
        ),
        "suggestions": [
            "Is standard deduction available for freelancers?",
            "What is the 87A rebate limit with standard deduction?",
            "How does standard deduction reduce taxable income?",
        ],
    },
]


def _match_knowledge_base(query: str) -> dict[str, Any] | None:
    """Scan the internal tax knowledge base for relevant domain content."""
    clean_query = query.lower()
    best_match = None
    max_matches = 0

    for entry in TAX_KNOWLEDGE_BASE:
        matches = sum(1 for kw in entry["keywords"] if kw in clean_query)
        if matches > max_matches:
            max_matches = matches
            best_match = entry

    return best_match if max_matches > 0 else None


def _calculate_sample_tax(salary: float, regime: str = "new") -> str:
    """Calculate sample tax for quick conversational figures."""
    if regime == "new":
        std_ded = 75000.0
        taxable = max(0.0, salary - std_ded)
        if taxable <= 700000:
            return f"Under the **New Tax Regime**, with gross salary ₹{salary:,.0f}:\n- Standard Deduction: ₹{std_ded:,.0f}\n- Taxable Income: ₹{taxable:,.0f}\n- **Net Tax Payable:** **₹0** (Zero tax due to Section 87A rebate up to ₹7 Lakhs)."
        
        # Slabs calculation
        tax = 0.0
        if taxable > 300000:
            tax += min(taxable - 300000, 400000) * 0.05
        if taxable > 700000:
            tax += min(taxable - 700000, 300000) * 0.10
        if taxable > 1000000:
            tax += min(taxable - 1000000, 200000) * 0.15
        if taxable > 1200000:
            tax += min(taxable - 1200000, 300000) * 0.20
        if taxable > 1500000:
            tax += (taxable - 1500000) * 0.30

        cess = tax * 0.04
        total = tax + cess
        return (
            f"Under the **New Tax Regime** for salary ₹{salary:,.0f}:\n"
            f"- Standard Deduction: ₹{std_ded:,.0f}\n"
            f"- Net Taxable Income: ₹{taxable:,.0f}\n"
            f"- Base Tax: ₹{tax:,.0f}\n"
            f"- Health & Education Cess (4%): ₹{cess:,.0f}\n"
            f"- **Total Tax Payable:** **₹{total:,.0f}**"
        )
    return ""


# ==============================================================================
# GEMINI API CALLER
# ==============================================================================

def _generate_with_gemini(
    user_prompt: str,
    history: list[ChatMessage],
    system_instruction: str,
) -> str | None:
    """
    Call Google Gemini REST API directly if GEMINI_API_KEY is configured.
    Returns response text or None if API key is absent or request fails.
    """
    if not GEMINI_API_KEY:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

    contents = []
    # Add system context
    contents.append({
        "role": "user",
        "parts": [{"text": f"SYSTEM INSTRUCTION: {system_instruction}"}],
    })
    contents.append({
        "role": "model",
        "parts": [{"text": "Understood. I will act as TaxSathi's expert Indian Income Tax filing advisor."}],
    })

    # Add conversation history
    for msg in history[-6:]:  # last 6 turns for context
        role = "user" if msg.role == "user" else "model"
        contents.append({
            "role": role,
            "parts": [{"text": msg.content}],
        })

    # Current user message
    contents.append({
        "role": "user",
        "parts": [{"text": user_prompt}],
    })

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                url,
                json={"contents": contents},
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        # Fall back gracefully to internal domain knowledge engine
        pass

    return None


# ==============================================================================
# CORE CONTROLLER FUNCTIONS
# ==============================================================================

def process_chat_message(
    db: Session,
    user_id: int,
    request: ChatRequest,
) -> ChatResponse:
    """
    Main controller to handle incoming AI chat queries:
    1. Validates and generates session ID if needed.
    2. Persists the user's incoming message to PostgreSQL.
    3. Queries Gemini API or TaxSathi expert knowledge engine.
    4. Formats response, citations, and follow-up suggestions.
    5. Persists the assistant's response to PostgreSQL.
    """
    session_id = request.session_id or str(uuid.uuid4())
    user_query = request.message.strip()

    if not user_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty",
        )

    # 1. Save user message to database
    user_msg_record = ChatMessageModel(
        user_id=user_id,
        session_id=session_id,
        role="user",
        content=user_query,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_msg_record)
    try:
        db.commit()
    except Exception:
        db.rollback()

    # 2. Extract potential numerical salary inquiry (e.g. "tax on 12 lakh" or "1500000")
    salary_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lac|l|k)?", user_query.lower())
    quick_calc = ""
    if salary_match and any(w in user_query.lower() for w in ["tax on", "calculate", "salary"]):
        try:
            num = float(salary_match.group(1))
            if "lakh" in user_query.lower() or "lac" in user_query.lower() or num < 100:
                salary = num * 100000
            else:
                salary = num
            if salary >= 100000:
                quick_calc = _calculate_sample_tax(salary, regime="new")
        except Exception:
            quick_calc = ""

    # 3. Check Tax Knowledge Base for domain matches
    kb_match = _match_knowledge_base(user_query)

    # 4. Attempt Gemini API Generation
    system_instruction = (
        "You are TaxSathi AI, an expert conversational assistant for Indian Income Tax filing, "
        "ITR-1/2, CBDT tax guidelines, Section 115BAC (New Regime), Section 80C, 80D, HRA, "
        "and Form 16 / 26AS reconciliation for FY 2024-25 (AY 2025-26). "
        "Provide structured, clear, friendly markdown answers with bullet points and practical advice."
    )
    gemini_reply = _generate_with_gemini(user_query, request.conversation_history, system_instruction)

    # 5. Assemble final response text and citations
    citations: list[ChatCitation] = []
    suggestions: list[str] = [
        "What is the standard deduction in New Tax Regime?",
        "Compare Old vs New Tax Regime for my income",
        "How can I save tax legally under Section 80C & 80D?",
    ]
    model_name = "Gemini-1.5-Flash (TaxSathi)" if gemini_reply else "TaxSathi-RuleEngine-v1"

    if gemini_reply:
        reply_text = gemini_reply
        if kb_match:
            citations.append(ChatCitation(
                title=kb_match["title"],
                section=kb_match["section"],
                snippet=kb_match["citation"],
            ))
            suggestions = kb_match["suggestions"]
    elif quick_calc:
        reply_text = f"### Tax Computation Result\n\n{quick_calc}\n\n*Note: This calculation uses New Tax Regime slabs for FY 2024-25 including the ₹75,000 standard deduction and 4% Health & Education Cess.*"
        citations.append(ChatCitation(
            title="Finance Act 2024 Tax Slabs",
            section="Section 115BAC",
            snippet="Tax slab rates and Section 87A rebate thresholds for FY 2024-25",
        ))
        suggestions = [
            "How much would I pay under the Old Regime?",
            "What if I have home loan interest?",
            "Which ITR form should I file?",
        ]
    elif kb_match:
        reply_text = kb_match["reply"]
        citations.append(ChatCitation(
            title=kb_match["title"],
            section=kb_match["section"],
            snippet=kb_match["citation"],
        ))
        suggestions = kb_match["suggestions"]
    else:
        reply_text = (
            f"Hello! I am **TaxSathi AI**, your personal Indian Income Tax assistant.\n\n"
            f"I can help you with:\n"
            f"- **New vs Old Tax Regime** comparison and slab rates for FY 2024-25 / 2023-24\n"
            f"- **Standard Deduction** (₹75,000 in New Regime / ₹50,000 in Old Regime)\n"
            f"- **Tax Saving Deductions:** Section 80C, 80D, 80CCD (NPS), and HRA exemption\n"
            f"- **Document Reconciliation:** Form 16, Form 26AS, AIS/TIS, and TDS verification\n"
            f"- **ITR Selection:** Choosing between ITR-1 (Sahaj), ITR-2, and ITR-4\n\n"
            f"Could you please share your specific question or income details so I can assist you?"
        )
        citations.append(ChatCitation(
            title="Income Tax Act, 1961",
            section="General Provisions",
            snippet="Statutory tax assessment and filing regulations administered by CBDT",
        ))

    # 6. Save assistant response to database
    assistant_msg_record = ChatMessageModel(
        user_id=user_id,
        session_id=session_id,
        role="assistant",
        content=reply_text,
        created_at=datetime.now(timezone.utc),
    )
    db.add(assistant_msg_record)
    try:
        db.commit()
    except Exception:
        db.rollback()

    return ChatResponse(
        success=True,
        session_id=session_id,
        reply=reply_text,
        citations=citations,
        suggestions=suggestions,
        model_used=model_name,
        created_at=datetime.now(timezone.utc),
    )


def get_chat_history(
    db: Session,
    session_id: str,
    user_id: int,
) -> ChatSessionHistoryResponse:
    """Retrieve all historical messages for a specific conversation session."""
    query = (
        select(ChatMessageModel)
        .where(
            ChatMessageModel.session_id == session_id,
            ChatMessageModel.user_id == user_id,
        )
        .order_by(ChatMessageModel.created_at.asc())
    )
    records = db.scalars(query).all()

    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No conversation history found for session '{session_id}'",
        )

    messages = [
        ChatMessage(
            role=rec.role,
            content=rec.content,
            timestamp=rec.created_at,
        )
        for rec in records
    ]

    return ChatSessionHistoryResponse(
        session_id=session_id,
        messages=messages,
        total_messages=len(messages),
    )


def list_user_chat_sessions(
    db: Session,
    user_id: int,
) -> list[ChatSessionSummary]:
    """List all conversation sessions for the authenticated user."""
    # Find distinct session IDs with last updated timestamp and count
    query = (
        select(
            ChatMessageModel.session_id,
            func.max(ChatMessageModel.created_at).label("latest_at"),
            func.count(ChatMessageModel.id).label("total"),
        )
        .where(ChatMessageModel.user_id == user_id)
        .group_by(ChatMessageModel.session_id)
        .order_by(desc("latest_at"))
    )
    rows = db.execute(query).all()

    summaries = []
    for row in rows:
        sid, latest_at, count = row
        # Fetch last message snippet
        last_msg = db.scalar(
            select(ChatMessageModel.content)
            .where(
                ChatMessageModel.session_id == sid,
                ChatMessageModel.user_id == user_id,
            )
            .order_by(ChatMessageModel.created_at.desc())
            .limit(1)
        ) or ""
        snippet = (last_msg[:80] + "...") if len(last_msg) > 80 else last_msg
        summaries.append(ChatSessionSummary(
            session_id=sid,
            last_message=snippet,
            message_count=count,
            updated_at=latest_at,
        ))

    return summaries


def clear_chat_history(
    db: Session,
    session_id: str,
    user_id: int,
) -> dict[str, Any]:
    """Delete all stored messages for a specific session."""
    existing = db.scalars(
        select(ChatMessageModel).where(
            ChatMessageModel.session_id == session_id,
            ChatMessageModel.user_id == user_id,
        )
    ).all()

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found or belongs to another user",
        )

    for item in existing:
        db.delete(item)
    db.commit()

    return {
        "success": True,
        "message": f"Chat history for session '{session_id}' cleared successfully",
    }
