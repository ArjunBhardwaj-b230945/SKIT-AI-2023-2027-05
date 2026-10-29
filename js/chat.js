/**
 * TaxSathi – AI Chat Interface
 * -----------------------------
 * 20% Milestone: chatbot layout and reusable message components.
 * 40% Milestone: character counter, message timestamps, typing indicator.
 * 60% Milestone (frontend scope): in-memory conversation history,
 *   in-flight loading state, decoupled typing indicator, system/error
 *   message utility. Real AI API integration deferred — endpoint and
 *   request/response contract are not yet confirmed by the backend team.
 *
 * Responsibilities:
 *   - Auth guard: redirect to login if no JWT is stored.
 *   - Populate nav user badge from JWT (same pattern as dashboard).
 *   - Sign-out handler.
 *   - Message submission: validate, record history, render bubble, reset input.
 *   - In-memory conversationHistory (role/content pairs) — no persistence.
 *   - In-flight guard: disable Send + input while an operation is active.
 *   - Typing indicator: show on submit, hide explicitly (not on a timer).
 *   - System/error message display utility (plain text, no HTML injection).
 *   - Disable Send when input is empty/whitespace or over char limit.
 *   - Auto-resize textarea.
 *   - Scroll conversation to latest message.
 *   - Hide "empty hint" after first user message.
 *   - Character counter with warning/limit states.
 *
 * DEFERRED — requires confirmed backend contract (Apoorv):
 *   - Real AI Assistant API request (POST to undisclosed endpoint).
 *   - Exact request-body field names and conversation-context schema.
 *   - Response JSON parsing and assistant-reply display.
 *   - Mapping of HTTP status codes (401/403/422/500/503) to verified responses.
 *   - Streaming response handling.
 */

'use strict';

import { getToken, isLoggedIn, signOut } from './auth.js';

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
 * API handler).  Does NOT simulate an AI response delay.
 */
const TYPING_SAFETY_TIMEOUT_MS = 30000;

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
 * Field names are intentionally generic and independent of the backend
 * contract (Apoorv's exact request schema is still pending).  When the
 * API contract is confirmed the 60% integration step will map or rename
 * these fields as required.
 *
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
 * Returns a shallow copy of the conversation history.
 * Intended for use by the future API integration layer — the caller
 * receives a snapshot and cannot mutate the internal array.
 *
 * @returns {{ role: string, content: string }[]}
 */
function getHistory() {
  return conversationHistory.slice();
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

// ══ createMessageElement ═════════════════════════════════════════
/**
 * Reusable message component factory.
 *
 * @param {'user'|'assistant'|'system'} role  Who sent the message.
 * @param {string}                      text  Plain text content (never HTML).
 * @returns {HTMLElement}
 *
 * Produced structure:
 *   <div class="chat-message chat-message--{role}" role="article" aria-label="…">
 *     <span class="chat-message-meta" aria-hidden="true">{label}</span>
 *     <div class="chat-message-bubble">{text}</div>
 *     <span class="chat-message-time" aria-hidden="true">{time}</span>  <!-- user only -->
 *   </div>
 */
function createMessageElement(role, text) {
  const isUser = role === 'user';
  const label  = isUser ? 'You' : 'TaxSathi AI';

  const wrapper = document.createElement('div');
  wrapper.className = `chat-message chat-message--${role}`;
  wrapper.setAttribute('role', 'article');
  wrapper.setAttribute('aria-label', `${isUser ? 'Your' : 'Assistant'} message`);

  const meta = document.createElement('span');
  meta.className = 'chat-message-meta';
  meta.setAttribute('aria-hidden', 'true');
  meta.textContent = label;

  const bubble = document.createElement('div');
  bubble.className = 'chat-message-bubble';
  // textContent — never innerHTML — prevents XSS from message content
  bubble.textContent = text;

  wrapper.appendChild(meta);
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
 * @param {string}                      text  Plain text.
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
}

// ══ showSystemMessage ════════════════════════════════════════════
/**
 * Displays a plain-text status or error message in the conversation as an
 * assistant-style bubble.  Intended for frontend-generated notices (e.g.
 * "Unable to reach the server.") — NOT for forwarding raw backend error JSON.
 *
 * Safe: uses textContent, never innerHTML.
 * Does NOT add to conversationHistory (system notices are not conversation
 * turns and should not be sent as context to the AI).
 *
 * @param {string} text  A short, human-readable plain-text message.
 */
function showSystemMessage(text) {
  appendMessage('assistant', text);
}

// ══ showTypingIndicator / hideTypingIndicator ═════════════════════
/**
 * Shows the animated typing indicator.
 *
 * The indicator now stays visible until hideTypingIndicator() is called
 * explicitly (e.g. from a fetch .finally() block once the API is integrated).
 * A 30-second safety-net timeout prevents it from getting permanently stuck
 * if an uncaught error skips the explicit hide call.
 *
 * No artificial delay or fake response is generated here.
 */
function showTypingIndicator() {
  if (!typingEl) return;

  typingEl.classList.add('is-visible');
  typingEl.setAttribute('aria-hidden', 'false');

  requestAnimationFrame(() => {
    conversation.scrollTo({ top: conversation.scrollHeight, behavior: 'instant' });
  });

  // Safety net: force-hide after TYPING_SAFETY_TIMEOUT_MS if still visible.
  // Cleared by hideTypingIndicator() on the normal code path.
  if (_typingSafetyHandle !== null) {
    clearTimeout(_typingSafetyHandle);
  }
  _typingSafetyHandle = setTimeout(() => {
    hideTypingIndicator();
    // If a future API call is still in-flight at this point, also unlock the UI
    // so the user is not permanently blocked.
    if (isBusy) setLoadingState(false);
  }, TYPING_SAFETY_TIMEOUT_MS);
}

/**
 * Hides the typing indicator and clears the safety-net timeout.
 * Call this from a fetch .finally() block once API integration is added.
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
  if (isBusy) return; // loading state controls Send during an operation

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

  // Show counter only after the user starts typing
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

// ══ handleSubmit ═════════════════════════════════════════════════
/**
 * Validates the current input, records the message in conversationHistory,
 * renders the user bubble, locks the UI, and shows the typing indicator.
 *
 * Real API integration is deferred.  When the endpoint and JSON contract are
 * confirmed, replace the comment block below with a fetch() call that:
 *   1. POSTs to the confirmed endpoint with the JWT header and request body.
 *   2. Calls appendMessage('assistant', responseText) + addToHistory('assistant', responseText).
 *   3. Calls hideTypingIndicator() and setLoadingState(false) in .finally().
 *   4. Calls showSystemMessage(…) in .catch() with a plain-text error notice.
 *
 * NOTE: getHistory() returns a snapshot of conversationHistory for use as
 * context in the request body once field names are confirmed.
 */
function handleSubmit() {
  // Guard: do not allow a second submission while one is in progress
  if (isBusy) return;

  const text = chatInput.value.trim();

  // Guard: reject empty / whitespace-only input
  if (!text) return;

  // Guard: reject input at or over the character limit
  if (chatInput.value.length >= MAX_CHARS) return;

  // ── Record in history ─────────────────────────────────────────
  addToHistory('user', text);

  // ── Render the user bubble ────────────────────────────────────
  appendMessage('user', text);

  // ── Lock UI and show typing indicator ─────────────────────────
  setLoadingState(true);
  showTypingIndicator();

  // ── Reset the composer ────────────────────────────────────────
  chatInput.value = '';
  autoResizeTextarea();
  updateCharCounter();
  // Note: setLoadingState(true) already disabled Send; no need to call
  // updateSendButtonState() here — it will be called by setLoadingState(false).

  // ── API integration point (deferred) ─────────────────────────
  //
  // REPLACE THIS BLOCK when Apoorv's endpoint and JSON contract are ready:
  //
  //   const history = getHistory();  // snapshot for request context
  //
  //   fetch('<confirmed_endpoint>', {
  //     method: 'POST',
  //     headers: {
  //       'Content-Type': 'application/json',
  //       'Authorization': `Bearer ${getToken()}`,
  //     },
  //     body: JSON.stringify({
  //       /* field names TBD — use confirmed schema from Apoorv */
  //     }),
  //   })
  //   .then((res) => {
  //     if (!res.ok) {
  //       // Map confirmed status codes here
  //       throw new Error(`HTTP ${res.status}`);
  //     }
  //     return res.json();
  //   })
  //   .then((data) => {
  //     const reply = data.<confirmed_reply_field>;
  //     addToHistory('assistant', reply);
  //     appendMessage('assistant', reply);
  //   })
  //   .catch(() => {
  //     showSystemMessage('Unable to get a response. Please try again.');
  //   })
  //   .finally(() => {
  //     hideTypingIndicator();
  //     setLoadingState(false);
  //   });
  //
  // Until then, do nothing further — no fake response, no artificial delay.
  // The typing indicator will auto-hide after TYPING_SAFETY_TIMEOUT_MS (30 s)
  // and the UI will be unlocked by the safety-net timeout in showTypingIndicator().
  //
  // For local development/demo before the backend is ready, the developer may
  // call the following two lines manually in the browser console to reset:
  //   hideTypingIndicator();
  //   setLoadingState(false);
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
    e.preventDefault(); // prevent textarea from inserting newline
    if (!sendBtn.disabled && !isBusy) {
      handleSubmit();
    }
  }
});

// ══ Initial state ════════════════════════════════════════════════
updateSendButtonState();
updateCharCounter();
