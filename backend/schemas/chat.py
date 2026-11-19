from datetime import datetime, timezone
from typing import Any, Literal
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    """Schema representing an individual message in a conversation thread."""
    role: Literal["user", "assistant", "system"] = Field(
        ...,
        description="Sender role: 'user', 'assistant', or 'system'",
        examples=["user"],
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Message content text",
        examples=["What is the basic exemption limit under the New Tax Regime for FY 2024-25?"],
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="ISO 8601 UTC timestamp of the message",
    )


class ChatRequest(BaseModel):
    """Schema for incoming AI Chat query requests."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="The user's question or tax prompt",
        examples=["Can I claim standard deduction of ₹75,000 under the New Tax Regime?"],
    )
    conversation_history: list[ChatMessage] = Field(
        default=[],
        description="List of prior messages in the conversation for multi-turn context",
    )
    session_id: str | None = Field(
        default=None,
        description="Unique session/conversation UUID. If omitted, a new session is created.",
        examples=["f47ac10b-58cc-4372-a567-0e02b2c3d479"],
    )
    financial_year: str = Field(
        default="2024-25",
        description="Target financial year context",
        examples=["2024-25"],
    )
    regime_preference: Literal["new", "old", "compare", "auto"] = Field(
        default="auto",
        description="Tax regime preference for contextual advice",
    )


class ChatCitation(BaseModel):
    """Reference citation backing up the AI answer."""
    title: str = Field(..., description="Document or section title")
    section: str | None = Field(default=None, description="Income Tax Act Section or Clause")
    snippet: str | None = Field(default=None, description="Relevant excerpt or guideline")


class ChatResponse(BaseModel):
    """Schema for successful AI Chat responses."""
    success: bool = Field(default=True, description="Indicates if the request succeeded")
    session_id: str = Field(..., description="Active session ID for continuing conversation")
    reply: str = Field(..., description="The AI assistant's formatted markdown reply")
    citations: list[ChatCitation] = Field(
        default=[],
        description="Official references and Income Tax Act section citations",
    )
    suggestions: list[str] = Field(
        default=[],
        description="Suggested follow-up questions to help the user",
    )
    model_used: str = Field(
        default="TaxSathi-AI-v1",
        description="Name of the underlying LLM/AI model used",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Response generation timestamp",
    )

    model_config = ConfigDict(from_attributes=True)


class ChatSessionSummary(BaseModel):
    """Summary of a past chat conversation."""
    session_id: str
    last_message: str
    message_count: int
    updated_at: datetime


class ChatSessionHistoryResponse(BaseModel):
    """Schema for retrieving past messages of a specific session."""
    session_id: str
    messages: list[ChatMessage]
    total_messages: int


class ChatErrorDetail(BaseModel):
    """Error response schema for failed chat requests."""
    success: bool = Field(default=False)
    error: str = Field(..., description="Error message description")
    code: int = Field(..., description="HTTP status code")
    detail: str | None = Field(default=None, description="Detailed diagnostic info")
