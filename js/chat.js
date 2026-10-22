/**
 * TaxSathi – AI Chat Interface
 * -----------------------------
 * 20% Milestone: chatbot layout and reusable message components.
 * 40% Milestone: character counter, message timestamps, typing indicator.
 *
 * Responsibilities:
 *   - Auth guard: redirect to login if no JWT is stored.
 *   - Populate nav user badge from JWT (same pattern as dashboard).
 *   - Sign-out handler.
 *   - Message submission: validate, render user bubble, clear input.
 *   - Disable Send when input is empty/whitespace or over char limit.
 *   - Auto-resize textarea.
 *   - Scroll conversation to latest message.
 *   - Hide "empty hint" after first user message.
 *   - Character counter with warning/limit states (40%).
 *   - Typing indicator shown briefly after each user message (40%).
 *   - Timestamp on each user message bubble (40%).
 *
 * NOT implemented (future milestones):
 *   - Real AI response generation or API calls.
 *   - Conversation persistence / history.
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
 * Duration (ms) to show the typing indicator after a user message.
 * Structural only at this milestone — no real AI response is generated.
 */
const TYPING_DISPLAY_MS = 1800;

// ══ DOM references ═══════════════════════════════════════════════
const emailEl       = document.getElementById('chatUserEmail');
const signOutBtn    = document.getElementById('chatSignOutBtn');
const conversation  = document.getElementById('chatConversation');
const chatInput     = document.getElementById('chatInput');
const sendBtn       = document.getElementById('chatSendBtn');
const emptyHint     = document.getElementById('chatEmptyHint');
const charCount     = document.getElementById('chatCharCount');
const charAnnounce  = document.getElementById('chatCharAnnounce');
const typingEl      = document.getElementById('chatTypingIndicator');

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
    signOutBtn.disabled   = true;
    signOutBtn.textContent = 'Signing out…';
    signOut(); // clears token and redirects to login.html
  });
}

// ══ formatTime ═══════════════════════════════════════════════════
/**
 * Returns the current time as a short human-readable string, e.g. "2:34 PM".
 * Used to stamp each outgoing user message.
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
 * @param {'user'|'assistant'} role  - Who sent the message.
 * @param {string}             text  - The message content (plain text, not HTML).
 * @returns {HTMLElement}            - A fully constructed .chat-message element.
 *
 * Structure produced (40% adds .chat-message-time):
 *   <div class="chat-message chat-message--{role}" role="article" aria-label="{role} message">
 *     <span class="chat-message-meta" aria-hidden="true">{label}</span>
 *     <div class="chat-message-bubble">{text}</div>
 *     <span class="chat-message-time" aria-hidden="true">{time}</span>  <!-- user only -->
 *   </div>
 */
function createMessageElement(role, text) {
  const isUser  = role === 'user';
  const label   = isUser ? 'You' : 'TaxSathi AI';

  const wrapper = document.createElement('div');
  wrapper.className   = `chat-message chat-message--${role}`;
  wrapper.setAttribute('role', 'article');
  wrapper.setAttribute('aria-label', `${isUser ? 'Your' : 'Assistant'} message`);

  const meta   = document.createElement('span');
  meta.className      = 'chat-message-meta';
  meta.setAttribute('aria-hidden', 'true');
  meta.textContent    = label;

  const bubble = document.createElement('div');
  bubble.className    = 'chat-message-bubble';
  // Use textContent (not innerHTML) to prevent XSS
  bubble.textContent  = text;

  wrapper.appendChild(meta);
  wrapper.appendChild(bubble);

  // 40%: Add timestamp below each user message bubble
  if (isUser) {
    const timeEl = document.createElement('span');
    timeEl.className        = 'chat-message-time';
    timeEl.setAttribute('aria-hidden', 'true');
    timeEl.textContent      = formatTime();
    wrapper.appendChild(timeEl);
  }

  return wrapper;
}

// ══ appendMessage ════════════════════════════════════════════════
/**
 * Appends a new message to the conversation area and scrolls to it.
 * Hides the empty-state hint on the first user submission.
 *
 * @param {'user'|'assistant'} role
 * @param {string}             text
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

  // Scroll conversation to show the new message.
  // Use 'instant' behavior so the scroll completes synchronously within the
  // same paint cycle as the DOM update — reliably detectable and avoids
  // CSS smooth-scroll animation competing with programmatic scroll.
  requestAnimationFrame(() => {
    conversation.scrollTo({ top: conversation.scrollHeight, behavior: 'instant' });
  });
}

// ══ showTypingIndicator / hideTypingIndicator ═════════════════════
/**
 * Shows the animated typing indicator for TYPING_DISPLAY_MS milliseconds,
 * then hides it automatically.
 *
 * Structural only at this milestone — no real AI response is sent.
 */
function showTypingIndicator() {
  if (!typingEl) return;
  typingEl.classList.add('is-visible');
  typingEl.setAttribute('aria-hidden', 'false');
  // Ensure indicator is visible (scroll)
  requestAnimationFrame(() => {
    conversation.scrollTo({ top: conversation.scrollHeight, behavior: 'instant' });
  });
  setTimeout(hideTypingIndicator, TYPING_DISPLAY_MS);
}

function hideTypingIndicator() {
  if (!typingEl) return;
  typingEl.classList.remove('is-visible');
  typingEl.setAttribute('aria-hidden', 'true');
}

// ══ updateSendButtonState ════════════════════════════════════════
/**
 * Enable or disable the Send button based on whether the textarea
 * contains non-whitespace text AND is within the character limit.
 */
function updateSendButtonState() {
  const len        = chatInput.value.length;
  const hasContent = chatInput.value.trim().length > 0;
  const atLimit    = len >= MAX_CHARS;

  const shouldEnable = hasContent && !atLimit;
  sendBtn.disabled          = !shouldEnable;
  sendBtn.setAttribute('aria-disabled', String(!shouldEnable));
}

// ══ updateCharCounter ════════════════════════════════════════════
/**
 * Updates the character counter display and applies visual state classes.
 * Announces the limit to screen readers when reached.
 */
function updateCharCounter() {
  if (!charCount) return;

  const len       = chatInput.value.length;
  const remaining = MAX_CHARS - len;

  // Show counter only after the user starts typing
  if (len > 0) {
    charCount.classList.add('is-visible');
  } else {
    charCount.classList.remove('is-visible');
  }

  charCount.textContent = `${len} / ${MAX_CHARS}`;

  // Remove all state classes first
  charCount.classList.remove('is-warning', 'is-limit');
  chatInput.classList.remove('is-at-limit');

  if (len >= MAX_CHARS) {
    // At limit
    charCount.classList.add('is-limit');
    chatInput.classList.add('is-at-limit');
    // Screen reader announcement (throttled to avoid repeat spam)
    if (charAnnounce && charAnnounce.textContent !== 'Character limit reached.') {
      charAnnounce.textContent = 'Character limit reached.';
    }
  } else if (len >= WARN_THRESHOLD) {
    // Warning zone
    charCount.classList.add('is-warning');
    chatInput.classList.remove('is-at-limit');
    // Clear previous limit announcement
    if (charAnnounce) charAnnounce.textContent = '';
  } else {
    // Normal
    if (charAnnounce) charAnnounce.textContent = '';
  }
}

// ══ autoResizeTextarea ═══════════════════════════════════════════
/**
 * Adjusts textarea height to fit its content, up to the CSS max-height.
 */
function autoResizeTextarea() {
  chatInput.style.height = 'auto';       // reset to measure scroll height
  chatInput.style.height = chatInput.scrollHeight + 'px';
}

// ══ handleSubmit ═════════════════════════════════════════════════
/**
 * Validates the current input, adds the user message to the
 * conversation, and resets the composer.
 * Shows the typing indicator briefly (structural, no real AI response).
 */
function handleSubmit() {
  const text = chatInput.value.trim();

  // Guard: prevent empty or whitespace-only submission
  if (!text) return;

  // Guard: prevent submission if at or over character limit
  if (chatInput.value.length >= MAX_CHARS) return;

  // Render the user message
  appendMessage('user', text);

  // Show typing indicator (structural — no real AI response)
  showTypingIndicator();

  // Clear and reset the input
  chatInput.value    = '';
  autoResizeTextarea();
  updateSendButtonState();
  updateCharCounter();

  // Return focus to input so the user can type the next message
  chatInput.focus();
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
    if (!sendBtn.disabled) {
      handleSubmit();
    }
  }
});

// ══ Initial state ════════════════════════════════════════════════
// Ensure button is disabled on page load (input is empty)
updateSendButtonState();
// Counter starts hidden (no text yet)
updateCharCounter();
