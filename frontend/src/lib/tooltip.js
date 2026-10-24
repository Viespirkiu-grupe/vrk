// Viešpirkiai tooltips (issue #200): the main site's RiskSignalChip pattern
// -- a role="tooltip" bubble, `is-open` when pinned by a tap or click,
// with a close button -- as one small component for any trigger, so a native
// `title` (no touch, no keyboard, one plain line) can be replaced anywhere.
//
// - Mouse: shows after HOVER_DELAY ms, so sweeping across a line does not
//   flicker, and hides when the pointer leaves.
// - Keyboard: the trigger is focusable and described by the bubble
//   (aria-describedby); focus shows it, Esc closes it.
// - Touch and click: toggles it pinned; a press outside closes it.
// - One bubble at a time, placed above the trigger (below when there is no
//   room under the sticky header) and clamped to the viewport, so it never
//   widens the page.
//
// Bubbles live in <body> with position: fixed, out of the trigger's text and
// out of any clipping container; one whose trigger has left the document is
// removed the next time any bubble opens.

import "../styles/tooltip.css";

const HOVER_DELAY = 150;
const GAP = 8;
const MARGIN = 8;

const tips = new Map(); // trigger -> {bubble, toggle}
let current = null; // {trigger, bubble, pinned, byPointer, toggle}
let hoverTimer = 0;
let pointerPress = false;
let seq = 0;
let listening = false;

function place(trigger, bubble) {
  const rect = trigger.getBoundingClientRect();
  const width = bubble.offsetWidth;
  const height = bubble.offsetHeight;
  const vw = document.documentElement.clientWidth;
  const vh = window.innerHeight;
  // The sticky site header is the ceiling, not the viewport edge: a bubble
  // drawn over the navigation hides it and reads as part of it.
  const header = document.querySelector(".site-header-shell");
  const ceiling = Math.max(MARGIN, header ? header.getBoundingClientRect().bottom + MARGIN / 2 : 0);
  const above = rect.top - GAP - height;
  const below = rect.bottom + GAP;
  const flip = above < ceiling && below + height <= vh - MARGIN;
  const top = flip ? below : Math.max(ceiling, above);
  const left = Math.min(Math.max(MARGIN, rect.left), Math.max(MARGIN, vw - MARGIN - width));
  bubble.style.top = `${Math.round(top)}px`;
  bubble.style.left = `${Math.round(left)}px`;
  bubble.dataset.side = flip ? "below" : "above";
}

function sweep() {
  for (const [trigger, tip] of tips) {
    if (!trigger.isConnected) {
      tip.bubble.remove();
      tips.delete(trigger);
    }
  }
}

function hide() {
  clearTimeout(hoverTimer);
  if (!current) return;
  current.bubble.classList.remove("is-visible", "is-open");
  current.trigger.classList.remove("tip-active");
  if (current.toggle) current.trigger.setAttribute("aria-expanded", "false");
  current = null;
}

function show(trigger, pinned = false, byPointer = false) {
  clearTimeout(hoverTimer);
  const tip = tips.get(trigger);
  if (!tip) return;
  if (current && current.trigger !== trigger) hide();
  sweep();
  current = { trigger, bubble: tip.bubble, pinned, byPointer, toggle: tip.toggle };
  tip.bubble.classList.add("is-visible");
  tip.bubble.classList.toggle("is-open", pinned);
  trigger.classList.add("tip-active");
  if (tip.toggle) trigger.setAttribute("aria-expanded", String(pinned));
  place(trigger, tip.bubble);
}

function listen() {
  if (listening) return;
  listening = true;
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && current) {
      hide();
      event.stopPropagation();
    }
  }, true);
  document.addEventListener("pointerdown", event => {
    if (!current) return;
    if (current.trigger.contains(event.target) || current.bubble.contains(event.target)) return;
    hide();
  }, true);
  const replace = () => { if (current) place(current.trigger, current.bubble); };
  window.addEventListener("scroll", replace, { passive: true, capture: true });
  window.addEventListener("resize", replace, { passive: true });
}

// Give `trigger` a tooltip holding `content` (a string or a node). A trigger
// that does its own thing on click -- a button -- passes `{toggle: false}`, so
// a click keeps its meaning and the bubble answers only hover and focus.
function attachTooltip(trigger, content, { toggle = true } = {}) {
  listen();
  const bubble = document.createElement("div");
  bubble.className = "vp-tip";
  bubble.id = `vp-tip-${++seq}`;
  bubble.setAttribute("role", "tooltip");
  const body = document.createElement("div");
  body.className = "vp-tip-body";
  body.append(content);
  bubble.append(body);
  if (toggle) {
    const close = document.createElement("button");
    close.type = "button";
    close.className = "vp-tip-close";
    // For mouse and touch only: Esc closes it by keyboard, and the bubble's
    // description must not end in "Uždaryti".
    close.tabIndex = -1;
    close.setAttribute("aria-hidden", "true");
    close.setAttribute("aria-label", "Uždaryti");
    close.textContent = "×";
    close.addEventListener("click", () => {
      const trigger = current && current.trigger;
      hide();
      if (trigger) trigger.focus({ preventScroll: true });
    });
    bubble.append(close);
  }
  document.body.append(bubble);
  tips.set(trigger, { bubble, toggle });

  trigger.removeAttribute("title");
  trigger.classList.add("has-tip");
  if (trigger.tabIndex < 0) trigger.tabIndex = 0;
  const described = (trigger.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
  trigger.setAttribute("aria-describedby", [...described, bubble.id].join(" "));

  trigger.addEventListener("pointerenter", event => {
    if (event.pointerType !== "mouse" || (current && current.pinned)) return;
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => show(trigger), HOVER_DELAY);
  });
  trigger.addEventListener("pointerleave", event => {
    if (event.pointerType !== "mouse") return;
    clearTimeout(hoverTimer);
    if (current && current.trigger === trigger && !current.pinned) hide();
  });
  // A press focuses the trigger too; the click, not the focus, decides then.
  trigger.addEventListener("pointerdown", () => { pointerPress = true; });
  trigger.addEventListener("focus", () => {
    if (pointerPress) return;
    if (!current || current.trigger !== trigger) show(trigger);
  });
  // Leaving by keyboard closes it; a bubble pinned by a press stays until a
  // press elsewhere, which may well have taken the focus.
  trigger.addEventListener("blur", event => {
    pointerPress = false;
    if (!current || current.trigger !== trigger) return;
    if (event.relatedTarget && current.bubble.contains(event.relatedTarget)) return;
    if (!(current.pinned && current.byPointer)) hide();
  });
  if (toggle) {
    if (!(trigger instanceof HTMLButtonElement)) trigger.setAttribute("role", "button");
    trigger.setAttribute("aria-expanded", "false");
    trigger.addEventListener("click", () => {
      const byPointer = pointerPress;
      pointerPress = false;
      if (current && current.trigger === trigger && current.pinned) hide();
      else show(trigger, true, byPointer);
    });
    trigger.addEventListener("keydown", event => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      if (current && current.trigger === trigger && current.pinned) hide();
      else show(trigger, true);
    });
  } else {
    trigger.addEventListener("click", () => { pointerPress = false; });
  }
  return bubble;
}

// Close whatever bubble is open, e.g. before its trigger is hidden.
function closeTooltip() {
  hide();
}

export { HOVER_DELAY, attachTooltip, closeTooltip };
