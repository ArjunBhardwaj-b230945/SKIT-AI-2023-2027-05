/**
 * TaxSathi – AI Chat Interface
 * -----------------------------
 * 20% Milestone: chatbot layout and reusable message components.
 * 40% Milestone: character counter, message timestamps, typing indicator.
 * 60% Milestone (frontend scope): in-memory conversation history,
 *   in-flight loading state, decoupled typing indicator, system/error
 *   message utility. Real AI API integration deferred — endpoint and
 *   request/response contract are not yet confirmed by the backend team.
 * 80% Milestone: conversation flow improvements — UI does not lock when no
 *   API request is dispatched; system messages rendered with distinct styling;
 *   assistant response display prepared and ready for API integration.
 * 100% Milestone: full API integration with confirmed backend contract.
 *   - POST http://localhost:8000/chat with JWT Bearer auth.
 *   - Session ID persistence across turns.
 *   - Conversation history context sent with each request.
 *   - Markdown rendering for assistant replies (safe inline renderer).
 *   - Citations display below assistant bubble.
 *   - Suggestion chips for follow-up questions.
 *   - Full HTTP error mapping (400 / 401 / 422 / 500) + network errors.
 *   - Loading / typing indicator wired to real API lifecycle.
 *
 * Responsibilities:
 *   - Auth guard: redirect to login if no JWT is stored.
 *   - Populate nav user badge from JWT (same pattern as dashboard).
 *   - Sign-out handler.
 *   - Message submission: validate, record history, render bubble, reset input.
 *   - In-memory conversationHistory (role/content pairs) — no persistence.
 *   - In-flight guard: disable Send + input while an operation is active.
 *   - Typing indicator: shown while API call is in-flight.
 *   - displayAssistantReply(text): renders an assistant bubble (Markdown-aware)
 *       and records history.
 *   - System/error message display utility (plain text, no HTML injection,
 *       distinct visual role from assistant replies).
 *   - Disable Send when input is empty/whitespace or over char limit.
 *   - Auto-resize textarea.
 *   - Scroll conversation to latest message.
 *   - Hide "empty hint" after first user message.
 *   - Character counter with warning/limit states.
 *
 * PENDING — not yet available from backend:
 *   - PDF download: backend has not provided PDF response field or delivery
 *     mechanism. Leave pending until confirmed.
 *   - Streaming response handling.
 */

'use strict';

import { getToken, isLoggedIn, signOut } from './auth.js';
import { chatPost, CHAT_ENDPOINTS } from './api.js';

// ══ Auth guard ═══════════════════════════════════════════════════
// Must run before anything else.  Mirrors dashboard.html behaviour.
if (!isLoggedIn()) {
  window.location.replace('login.html');
}

// ══ Constants ════════════════════════════════════════════════════
/** Maximum characters allowed in a single message. */
const MAX_CHARS = 500;

/** Characters remaining at which the counter enters "warning" state. */
const WARN_THRESHOLD = 450;

/**
 * Safety-net timeout (ms) — forces the typing indicator to hide if
 * hideTypingIndicator() is never called (e.g. an uncaught error in a future
 * API handler).
 */
const TYPING_SAFETY_TIMEOUT_MS = 30000;

/** Default financial year sent with every request. */
const DEFAULT_FINANCIAL_YEAR = '2024-25';

/** Default regime preference sent with every request. */
const DEFAULT_REGIME = 'auto';

// ══ Session state ═════════════════════════════════════════════════
/**
 * Backend-generated session ID.  null before the first successful response.
 * Reused on every subsequent request so the backend can correlate turns.
 * @type {string|null}
 */
let currentSessionId = null;

// ══ DOM references ═══════════════════════════════════════════════
const emailEl      = document.getElementById('chatUserEmail');
const signOutBtn   = document.getElementById('chatSignOutBtn');
const conversation = document.getElementById('chatConversation');
const chatInput    = document.getElementById('chatInput');
const sendBtn      = document.getElementById('chatSendBtn');
const emptyHint    = document.getElementById('chatEmptyHint');
const charCount    = document.getElementById('chatCharCount');
const charAnnounce = document.getElementById('chatCharAnnounce');
const typingEl     = document.getElementById('chatTypingIndicator');

// ══ Populate nav badge from JWT ══════════════════════════════════
const token = getToken();
if (token) {
  try {
    const payload     = JSON.parse(atob(token.split('.')[1]));
    const email       = payload.email || null;

    if (email) {
      const firstName   = email.split('@')[0];
      const displayName = firstName.charAt(0).toUpperCase() + firstName.slice(1);

      if (emailEl) emailEl.textContent = email;

      // Update browser tab title to greet the user
      document.title = 'AI Assistant — ' + displayName + ' | TaxSathi';
    }
  } catch (_) {
    // JWT may not carry expected claims — keep default placeholder text.
  }
}

// ══ Sign-out handler ═════════════════════════════════════════════
if (signOutBtn) {
  signOutBtn.addEventListener('click', () => {
    signOutBtn.disabled    = true;
    signOutBtn.textContent = 'Signing out…';
    signOut(); // clears token and redirects to login.html
  });
}

// ══ In-memory conversation history ═══════════════════════════════
/**
 * Ordered record of the conversation.  Each entry is a plain object:
 *   { role: 'user' | 'assistant', content: string }
 *
 * Sent as `conversation_history` in the request body.
 * Not persisted — cleared on page reload.
 */
const conversationHistory = [];

/**
 * Records a message in the in-memory history.
 *
 * @param {'user'|'assistant'} role
 * @param {string}             content  Plain text content of the message.
 */
function addToHistory(role, content) {
  conversationHistory.push({ role, content });
}

/**
 * Returns a shallow copy of the conversation history EXCLUDING the last entry
 * (which is the current user message being submitted — it goes in `message`,
 * not in `conversation_history`, per the confirmed API contract).
 *
 * @returns {{ role: string, content: string }[]}
 */
function getHistoryForRequest() {
  // The last entry in conversationHistory is the user message just added.
  // The API contract puts the current message in the `message` field and
  // prior turns in `conversation_history`.  Exclude the last entry.
  return conversationHistory.slice(0, -1);
}

// ══ In-flight loading state ═══════════════════════════════════════
/**
 * True while a submission is being processed.
 * Prevents duplicate sends before an API response (or error) is received.
 */
let isBusy = false;

/** Handle for the typing-indicator safety-net timeout. */
let _typingSafetyHandle = null;

/**
 * Locks or unlocks the composer UI.
 *
 * @param {boolean} loading  true = lock (disable Send + input), false = unlock.
 */
function setLoadingState(loading) {
  isBusy = loading;

  // Disable/enable the textarea
  chatInput.disabled = loading;

  if (loading) {
    // Disable Send unconditionally while busy
    sendBtn.disabled = true;
    sendBtn.setAttribute('aria-disabled', 'true');
  } else {
    // Re-evaluate Send state based on current input content
    updateSendButtonState();
    // Restore focus so the user can continue typing immediately
    chatInput.focus();
  }
}

// ══ formatTime ═══════════════════════════════════════════════════
/**
 * Returns the current time as a short human-readable string, e.g. "2:34 PM".
 * Used to stamp outgoing user messages.
 *
 * @returns {string}
 */
function formatTime() {
  return new Date().toLocaleTimeString(undefined, {
    hour:   'numeric',
    minute: '2-digit',
  });
}

// ══ Safe inline Markdown renderer ════════════════════════════════
/**
 * Converts a small, safe subset of Markdown to sanitised HTML.
 *
 * Supported syntax (sufficient for AI tax guidance responses):
 *   **bold**, *italic*, `inline code`,
 *   # / ## / ### headings, --- horizontal rule,
 *   - / * / + unordered list items, 1. ordered list items,
 *   > blockquote lines, blank lines between paragraphs.
 *
 * Security: all raw text segments are HTML-escaped before insertion.
 * No external library required — no CDN dependency, no install step.
 *
 * @param {string} md  Raw Markdown string from the API reply field.
 * @returns {string}   Safe HTML string, ready for innerHTML assignment.
 */
function renderMarkdown(md) {
  if (!md || typeof md !== 'string') return '';

  // ── 1. Escape HTML in the entire input first ──────────────────
  // This prevents any raw HTML in the AI response from executing.
  function escHtml(str) {
    return str
      .replace(/&/g,  '&amp;')
      .replace(/</g,  '&lt;')
      .replace(/>/g,  '&gt;')
      .replace(/"/g,  '&quot;')
      .replace(/'/g,  '&#39;');
  }

  // ── 2. Process line-by-line for block elements ────────────────
  const lines = md.split('\n');
  const outputParts = [];
  let inUl = false;
  let inOl = false;
  let inBlockquote = false;
  let paragraphLines = [];

  function flushParagraph() {
    if (paragraphLines.length > 0) {
      const inner = applyInline(paragraphLines.join(' '));
      outputParts.push(`<p>${inner}</p>`);
      paragraphLines = [];
    }
  }

  function flushList() {
    if (inUl) { outputParts.push('</ul>'); inUl = false; }
    if (inOl) { outputParts.push('</ol>'); inOl = false; }
  }

  function flushBlockquote() {
    if (inBlockquote) { outputParts.push('</blockquote>'); inBlockquote = false; }
  }

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const line = raw; // keep original for regex; escaping happens per-segment

    // Blank line — close open containers, flush paragraph
    if (/^\s*$/.test(line)) {
      flushParagraph();
      flushList();
      flushBlockquote();
      continue;
    }

    // Horizontal rule
    if (/^(\-{3,}|\*{3,}|_{3,})\s*$/.test(line.trim())) {
      flushParagraph();
      flushList();
      flushBlockquote();
      outputParts.push('<hr>');
      continue;
    }

    // ATX Headings: # ## ###
    const headingMatch = line.match(/^(#{1,3})\s+(.+)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      flushBlockquote();
      const level = headingMatch[1].length;
      const text  = applyInline(escHtml(headingMatch[2].trim()));
      outputParts.push(`<h${level} class="chat-md-h">${text}</h${level}>`);
      continue;
    }

    // Blockquote
    const bqMatch = line.match(/^>\s?(.*)$/);
    if (bqMatch) {
      flushParagraph();
      flushList();
      if (!inBlockquote) { outputParts.push('<blockquote class="chat-md-bq">'); inBlockquote = true; }
      outputParts.push(`<p>${applyInline(escHtml(bqMatch[1]))}</p>`);
      continue;
    }
    flushBlockquote();

    // Unordered list item: - / * / +
    const ulMatch = line.match(/^[\s]*[-*+]\s+(.+)$/);
    if (ulMatch) {
      flushParagraph();
      if (inOl) { outputParts.push('</ol>'); inOl = false; }
      if (!inUl) { outputParts.push('<ul class="chat-md-list">'); inUl = true; }
      outputParts.push(`<li>${applyInline(escHtml(ulMatch[1]))}</li>`);
      continue;
    }

    // Ordered list item: 1. 2. etc.
    const olMatch = line.match(/^[\s]*\d+\.\s+(.+)$/);
    if (olMatch) {
      flushParagraph();
      if (inUl) { outputParts.push('</ul>'); inUl = false; }
      if (!inOl) { outputParts.push('<ol class="chat-md-list">'); inOl = true; }
      outputParts.push(`<li>${applyInline(escHtml(olMatch[1]))}</li>`);
      continue;
    }

    // Regular paragraph line
    flushList();
    paragraphLines.push(escHtml(line));
  }

  // Flush any remaining open containers
  flushParagraph();
  flushList();
  flushBlockquote();

  return outputParts.join('\n');
}

/**
 * Applies inline Markdown spans to an already-HTML-escaped string segment.
 * Input must already be HTML-escaped (angle brackets as &lt;, etc.).
 *
 * Order matters: code first to prevent double-processing its content.
 *
 * @param {string} str  HTML-escaped text.
 * @returns {string}    HTML with inline formatting applied.
 */
function applyInline(str) {
  // Inline code: `code` — must come BEFORE bold/italic
  str = str.replace(/`([^`]+)`/g, '<code class="chat-md-code">$1</code>');
  // Bold: **text** or __text__
  str = str.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  str = str.replace(/__(.+?)__/g, '<strong>$1</strong>');
  // Italic: *text* or _text_
  str = str.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  str = str.replace(/_([^_]+)_/g, '<em>$1</em>');
  return str;
}

// ══ createMessageElement ═════════════════════════════════════════
/**
 * Reusable message component factory.
 *
 * For 'assistant' role, the bubble's innerHTML is set from the sanitised
 * Markdown renderer.  For 'user' and 'system' roles, textContent is used
 * (XSS-safe, no HTML interpretation).
 *
 * @param {'user'|'assistant'|'system'} role  Who sent the message.
 * @param {string}                      text  Content of the message.
 * @returns {HTMLElement}
 */
function createMessageElement(role, text) {
  const isUser      = role === 'user';
  const isSystem    = role === 'system';
  const label       = isUser ? 'You' : 'TaxSathi AI';

  const wrapper = document.createElement('div');
  wrapper.className = `chat-message chat-message--${role}`;
  wrapper.setAttribute('role', 'article');
  wrapper.setAttribute(
    'aria-label',
    isUser ? 'Your message' : isSystem ? 'System notice' : 'Assistant message'
  );

  // Meta label — not shown for system notices (they use minimal styling)
  if (!isSystem) {
    const meta = document.createElement('span');
    meta.className = 'chat-message-meta';
    meta.setAttribute('aria-hidden', 'true');
    meta.textContent = label;
    wrapper.appendChild(meta);
  }

  const bubble = document.createElement('div');
  bubble.className = 'chat-message-bubble';

  if (role === 'assistant') {
    // Safe HTML from our controlled Markdown renderer
    bubble.innerHTML = renderMarkdown(text);
  } else {
    // User and system messages: plain text only, no HTML interpretation
    bubble.textContent = text;
  }

  wrapper.appendChild(bubble);

  // Timestamp shown below user bubbles only
  if (isUser) {
    const timeEl = document.createElement('span');
    timeEl.className = 'chat-message-time';
    timeEl.setAttribute('aria-hidden', 'true');
    timeEl.textContent = formatTime();
    wrapper.appendChild(timeEl);
  }

  return wrapper;
}

// ══ appendMessage ════════════════════════════════════════════════
/**
 * Renders a message bubble in the conversation area and scrolls to it.
 * Hides the empty-state hint on the first user submission.
 * Does NOT update conversationHistory — callers manage history themselves.
 *
 * @param {'user'|'assistant'|'system'} role
 * @param {string}                      text
 * @returns {HTMLElement}  The inserted element (useful for citation/suggestion injection).
 */
function appendMessage(role, text) {
  // Hide the "type below" hint once any message is submitted
  if (role === 'user' && emptyHint && !emptyHint.hidden) {
    emptyHint.hidden = true;
    emptyHint.setAttribute('aria-hidden', 'true');
  }

  const el = createMessageElement(role, text);
  // Insert before the typing indicator so it always stays at the bottom
  if (typingEl && typingEl.parentNode === conversation) {
    conversation.insertBefore(el, typingEl);
  } else {
    conversation.appendChild(el);
  }

  requestAnimationFrame(() => {
    conversation.scrollTo({ top: conversation.scrollHeight, behavior: 'instant' });
  });

  return el;
}

// ══ showSystemMessage ════════════════════════════════════════════
/**
 * Displays a plain-text status or error notice in the conversation.
 * Uses the 'system' role so it renders with distinct styling and is NOT
 * confused with a real AI reply.
 *
 * Safe: uses textContent, never innerHTML.
 * Does NOT add to conversationHistory — system notices are not conversation
 * turns and must NOT be sent as context to the AI.
 *
 * @param {string} text  A short, human-readable plain-text message.
 */
function showSystemMessage(text) {
  appendMessage('system', text);
}

// ══ appendCitations ══════════════════════════════════════════════
/**
 * Renders a citations block below the assistant bubble element.
 * Only called when the API response contains a non-empty `citations` array.
 *
 * Each citation is a plain object: { title, section, snippet }
 * All text is escaped via textContent — no innerHTML from API data.
 *
 * @param {HTMLElement} messageEl   The wrapper element returned by appendMessage().
 * @param {Array<{title:string, section:string, snippet:string}>} citations
 */
function appendCitations(messageEl, citations) {
  if (!citations || citations.length === 0) return;

  const citationsEl = document.createElement('div');
  citationsEl.className = 'chat-citations';
  citationsEl.setAttribute('aria-label', 'Sources');

  const heading = document.createElement('p');
  heading.className = 'chat-citations-heading';
  heading.textContent = 'Sources';
  citationsEl.appendChild(heading);

  const list = document.createElement('ul');
  list.className = 'chat-citations-list';

  citations.forEach((cite, index) => {
    const item = document.createElement('li');
    item.className = 'chat-citation-item';

    const title = document.createElement('span');
    title.className = 'chat-citation-title';
    title.textContent = cite.title || `Source ${index + 1}`;

    item.appendChild(title);

    if (cite.section) {
      const section = document.createElement('span');
      section.className = 'chat-citation-section';
      section.textContent = ` — ${cite.section}`;
      item.appendChild(section);
    }

    if (cite.snippet) {
      const snippet = document.createElement('p');
      snippet.className = 'chat-citation-snippet';
      snippet.textContent = cite.snippet;
      item.appendChild(snippet);
    }

    list.appendChild(item);
  });

  citationsEl.appendChild(list);

  // Insert after the message wrapper element
  if (messageEl.nextSibling) {
    messageEl.parentNode.insertBefore(citationsEl, messageEl.nextSibling);
  } else {
    messageEl.parentNode.appendChild(citationsEl);
  }

  // Insert before typing indicator if it's the last child
  if (typingEl && typingEl.parentNode === conversation) {
    conversation.insertBefore(citationsEl, typingEl);
  }

  requestAnimationFrame(() => {
    conversation.scrollTo({ top: conversation.scrollHeight, behavior: 'instant' });
  });
}

// ══ appendSuggestions ════════════════════════════════════════════
/**
 * Renders clickable suggestion chips below the assistant reply.
 * Clicking a suggestion submits it through the existing handleSubmit() flow.
 *
 * Only called when the API response contains a non-empty `suggestions` array.
 * The chips are removed once any one of them is clicked (or the user sends a
 * manual message), so they don't accumulate per turn.
 *
 * @param {string[]} suggestions  Array of follow-up question strings.
 */
function appendSuggestions(suggestions) {
  if (!suggestions || suggestions.length === 0) return;

  const suggestionsEl = document.createElement('div');
  suggestionsEl.className = 'chat-suggestions';
  suggestionsEl.setAttribute('aria-label', 'Suggested follow-up questions');
  suggestionsEl.id = 'chatSuggestions'; // ID so handleSubmit can clear it

  const heading = document.createElement('p');
  heading.className = 'chat-suggestions-heading';
  heading.textContent = 'You might also ask:';
  suggestionsEl.appendChild(heading);

  const chipsRow = document.createElement('div');
  chipsRow.className = 'chat-suggestions-chips';

  suggestions.forEach((suggestion) => {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'chat-suggestion-chip';
    chip.textContent = suggestion;
    chip.setAttribute('aria-label', `Ask: ${suggestion}`);

    chip.addEventListener('click', () => {
      // Remove all suggestion chips immediately on click
      clearSuggestions();
      // Populate the input and trigger submit
      chatInput.value = suggestion;
      autoResizeTextarea();
      updateCharCounter();
      updateSendButtonState();
      handleSubmit();
    });

    chipsRow.appendChild(chip);
  });

  suggestionsEl.appendChild(chipsRow);

  // Insert before typing indicator
  if (typingEl && typingEl.parentNode === conversation) {
    conversation.insertBefore(suggestionsEl, typingEl);
  } else {
    conversation.appendChild(suggestionsEl);
  }

  requestAnimationFrame(() => {
    conversation.scrollTo({ top: conversation.scrollHeight, behavior: 'instant' });
  });
}

/**
 * Removes the current suggestions block (if present).
 * Called at the start of every new user submission so stale chips disappear.
 */
function clearSuggestions() {
  const existing = document.getElementById('chatSuggestions');
  if (existing) existing.remove();
}

// ══ displayAssistantReply ═════════════════════════════════════════
/**
 * Renders an assistant reply bubble (Markdown-rendered) and records it
 * in conversationHistory.  Optionally renders citations and suggestions.
 *
 * This is the single integration point called from the fetch() handler.
 *
 * @param {string}   text         Plain-text / Markdown reply from API `reply` field.
 * @param {Array}    [citations]  Optional citations array from API response.
 * @param {string[]} [suggestions] Optional suggestions array from API response.
 */
function displayAssistantReply(text, citations, suggestions) {
  addToHistory('assistant', text);
  const msgEl = appendMessage('assistant', text);

  if (citations && citations.length > 0) {
    appendCitations(msgEl, citations);
  }

  if (suggestions && suggestions.length > 0) {
    appendSuggestions(suggestions);
  }
}

// ══ showTypingIndicator / hideTypingIndicator ═════════════════════
/**
 * Shows the animated typing indicator.
 * Stays visible until hideTypingIndicator() is called (e.g. from .finally()).
 * A 30-second safety-net timeout prevents permanent lock if an error occurs.
 */
function showTypingIndicator() {
  if (!typingEl) return;

  typingEl.classList.add('is-visible');
  typingEl.setAttribute('aria-hidden', 'false');

  requestAnimationFrame(() => {
    conversation.scrollTo({ top: conversation.scrollHeight, behavior: 'instant' });
  });

  if (_typingSafetyHandle !== null) {
    clearTimeout(_typingSafetyHandle);
  }
  _typingSafetyHandle = setTimeout(() => {
    hideTypingIndicator();
    if (isBusy) setLoadingState(false);
  }, TYPING_SAFETY_TIMEOUT_MS);
}

/**
 * Hides the typing indicator and clears the safety-net timeout.
 * Always called from the fetch .finally() block.
 */
function hideTypingIndicator() {
  if (!typingEl) return;

  typingEl.classList.remove('is-visible');
  typingEl.setAttribute('aria-hidden', 'true');

  if (_typingSafetyHandle !== null) {
    clearTimeout(_typingSafetyHandle);
    _typingSafetyHandle = null;
  }
}

// ══ updateSendButtonState ════════════════════════════════════════
/**
 * Enable or disable the Send button based on whether the textarea
 * contains non-whitespace text AND is within the character limit.
 * Has no effect while isBusy is true (loading state takes precedence).
 */
function updateSendButtonState() {
  if (isBusy) return;

  const len        = chatInput.value.length;
  const hasContent = chatInput.value.trim().length > 0;
  const atLimit    = len >= MAX_CHARS;

  const shouldEnable = hasContent && !atLimit;
  sendBtn.disabled   = !shouldEnable;
  sendBtn.setAttribute('aria-disabled', String(!shouldEnable));
}

// ══ updateCharCounter ════════════════════════════════════════════
/**
 * Updates the character counter display and applies visual state classes.
 * Announces the character limit to screen readers when reached.
 */
function updateCharCounter() {
  if (!charCount) return;

  const len = chatInput.value.length;

  if (len > 0) {
    charCount.classList.add('is-visible');
  } else {
    charCount.classList.remove('is-visible');
  }

  charCount.textContent = `${len} / ${MAX_CHARS}`;

  charCount.classList.remove('is-warning', 'is-limit');
  chatInput.classList.remove('is-at-limit');

  if (len >= MAX_CHARS) {
    charCount.classList.add('is-limit');
    chatInput.classList.add('is-at-limit');
    if (charAnnounce && charAnnounce.textContent !== 'Character limit reached.') {
      charAnnounce.textContent = 'Character limit reached.';
    }
  } else if (len >= WARN_THRESHOLD) {
    charCount.classList.add('is-warning');
    if (charAnnounce) charAnnounce.textContent = '';
  } else {
    if (charAnnounce) charAnnounce.textContent = '';
  }
}

// ══ autoResizeTextarea ═══════════════════════════════════════════
/**
 * Adjusts textarea height to fit its content, up to the CSS max-height.
 */
function autoResizeTextarea() {
  chatInput.style.height = 'auto';
  chatInput.style.height = chatInput.scrollHeight + 'px';
}

// ══ resolveErrorMessage ══════════════════════════════════════════
/**
 * Maps an HTTP status code (or a NetworkError) to a user-facing string.
 *
 * Checks `data.detail` before `data.message` to match Apoorv's confirmed
 * backend error shape: { "detail": "…" }.  Falls back to `data.message`
 * for compatibility, then to a generic string.
 *
 * @param {number|'network'} status
 * @param {object} [data]  Parsed response body (may contain `detail` or `message`).
 * @returns {string}
 */
function resolveErrorMessage(status, data) {
  if (status === 'network') {
    return 'Unable to reach the AI server. Please check your connection and try again.';
  }
  switch (status) {
    case 400:
      return 'Your message could not be processed (empty or invalid). Please try again.';
    case 401:
      return 'Your session has expired or is invalid. Please sign out and sign in again.';
    case 422:
      return 'The request was not accepted by the server. Please rephrase your question.';
    case 500:
      return 'The AI server encountered an error. Please try again in a moment.';
    default:
      return (data && (data.detail || data.message))
        ? (data.detail || data.message)
        : 'An unexpected error occurred. Please try again.';
  }
}

// ══ handleSubmit ═════════════════════════════════════════════════
/**
 * Validates the current input, records the message in conversationHistory,
 * renders the user bubble, resets the composer, then:
 *   1. Locks the UI and shows the typing indicator.
 *   2. POSTs to http://localhost:8000/chat with JWT Bearer auth.
 *   3. On success: persists session_id, renders Markdown reply, citations,
 *      and suggestion chips.
 *   4. On HTTP error: shows a mapped error message via showSystemMessage().
 *   5. On network failure: shows a network error message.
 *   6. Always (finally): hides typing indicator and unlocks the UI.
 */
function handleSubmit() {
  // Guard: do not allow a second submission while one is in progress
  if (isBusy) return;

  const text = chatInput.value.trim();

  // Guard: reject empty / whitespace-only input
  if (!text) return;

  // Guard: reject input at or over the character limit
  if (chatInput.value.length >= MAX_CHARS) return;

  // Clear any stale suggestion chips from the previous turn
  clearSuggestions();

  // ── Record in history ─────────────────────────────────────────
  // addToHistory BEFORE getHistoryForRequest() so the slice excludes this turn
  addToHistory('user', text);

  // ── Render the user bubble ────────────────────────────────────
  appendMessage('user', text);

  // ── Reset the composer ────────────────────────────────────────
  chatInput.value = '';
  autoResizeTextarea();
  updateCharCounter();
  updateSendButtonState();

  // ── Lock UI and show typing indicator ─────────────────────────
  setLoadingState(true);
  showTypingIndicator();

  // ── Build request body ─────────────────────────────────────────
  // conversation_history = all prior turns (excludes the message just added)
  const historySnapshot = getHistoryForRequest();
  const requestBody = {
    message:              text,
    session_id:           currentSessionId,          // null on first turn
    conversation_history: historySnapshot,
    financial_year:       DEFAULT_FINANCIAL_YEAR,
    regime_preference:    DEFAULT_REGIME,
  };

  // ── Dispatch API call ─────────────────────────────────────────
  const jwtToken = getToken();

  chatPost(CHAT_ENDPOINTS.CHAT, requestBody, jwtToken)
    .then(({ ok, status, data }) => {
      if (!ok) {
        // HTTP error — map to user-friendly message
        showSystemMessage(resolveErrorMessage(status, data));
        return;
      }

      // ── Success path ────────────────────────────────────────
      // Persist session ID for subsequent turns
      if (data.session_id) {
        currentSessionId = data.session_id;
      }

      const reply       = data.reply        || '';
      const citations   = data.citations    || [];
      const suggestions = data.suggestions  || [];

      if (reply) {
        displayAssistantReply(reply, citations, suggestions);
      } else {
        // Unlikely but guard: empty reply field
        showSystemMessage('The assistant returned an empty response. Please try again.');
      }
    })
    .catch((err) => {
      // Network-level failure (no server, DNS failure, CORS hard-block)
      showSystemMessage(resolveErrorMessage('network', null));
    })
    .finally(() => {
      hideTypingIndicator();
      setLoadingState(false);
    });
}

// ══ Event listeners ══════════════════════════════════════════════

// Input validation on every keystroke
chatInput.addEventListener('input', () => {
  updateSendButtonState();
  updateCharCounter();
  autoResizeTextarea();
});

// Send on button click
sendBtn.addEventListener('click', handleSubmit);

// Send on Enter (without Shift).
// Shift+Enter inserts a newline, keeping multi-line input practical.
chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled && !isBusy) {
      handleSubmit();
    }
  }
});

// ══ Initial state ════════════════════════════════════════════════
updateSendButtonState();
updateCharCounter();
