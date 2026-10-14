/**
 * TaxSathi – AI Chat Interface
 * -----------------------------
 * 20% Milestone: chatbot layout and reusable message components.
 *
 * Responsibilities:
 *   - Auth guard: redirect to login if no JWT is stored.
 *   - Populate nav user badge from JWT (same pattern as dashboard).
 *   - Sign-out handler.
 *   - Message submission: validate, render user bubble, clear input.
 *   - Disable Send when input is empty/whitespace.
 *   - Auto-resize textarea.
 *   - Scroll conversation to latest message.
 *   - Hide "empty hint" after first user message.
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

// ══ DOM references ═══════════════════════════════════════════════
const emailEl       = document.getElementById('chatUserEmail');
const signOutBtn    = document.getElementById('chatSignOutBtn');
const conversation  = document.getElementById('chatConversation');
const chatInput     = document.getElementById('chatInput');
const sendBtn       = document.getElementById('chatSendBtn');
const emptyHint     = document.getElementById('chatEmptyHint');

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

// ══ createMessageElement ═════════════════════════════════════════
/**
 * Reusable message component factory.
 *
 * @param {'user'|'assistant'} role  - Who sent the message.
 * @param {string}             text  - The message content (plain text, not HTML).
 * @returns {HTMLElement}            - A fully constructed .chat-message element.
 *
 * Structure produced:
 *   <div class="chat-message chat-message--{role}" role="article" aria-label="{role} message">
 *     <span class="chat-message-meta" aria-hidden="true">{label}</span>
 *     <div class="chat-message-bubble">{text}</div>
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
  conversation.appendChild(el);

  // Scroll conversation to show the new message.
  // requestAnimationFrame ensures the DOM has painted before we measure height.
  requestAnimationFrame(() => {
    conversation.scrollTop = conversation.scrollHeight;
  });
}

// ══ updateSendButtonState ════════════════════════════════════════
/**
 * Enable or disable the Send button based on whether the textarea
 * contains non-whitespace text.
 */
function updateSendButtonState() {
  const hasContent = chatInput.value.trim().length > 0;
  sendBtn.disabled          = !hasContent;
  sendBtn.setAttribute('aria-disabled', String(!hasContent));
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
 * Does NOT generate or simulate an AI response.
 */
function handleSubmit() {
  const text = chatInput.value.trim();

  // Guard: prevent empty or whitespace-only submission
  if (!text) return;

  // Render the user message
  appendMessage('user', text);

  // Clear and reset the input
  chatInput.value    = '';
  autoResizeTextarea();
  updateSendButtonState();

  // Return focus to input so the user can type the next message
  chatInput.focus();
}

// ══ Event listeners ══════════════════════════════════════════════

// Input validation on every keystroke
chatInput.addEventListener('input', () => {
  updateSendButtonState();
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
