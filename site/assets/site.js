// TapHerd site behaviour shared by every page: smooth scrolling, reveals,
// copy buttons, tabs, the header, looping media, and cookieless analytics.
document.documentElement.classList.add("js");
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---- Smooth wheel scrolling (mouse and trackpad on desktop only).
// Keyboard, scrollbar, and touch scrolling stay native.
const smooth = (() => {
  if (reduceMotion || !matchMedia("(pointer: fine)").matches) return null;
  let target = scrollY;
  let current = scrollY;
  let frame = 0;
  const max = () => document.documentElement.scrollHeight - innerHeight;
  const tick = () => {
    current += (target - current) * 0.11;
    if (Math.abs(target - current) < 0.5) current = target;
    scrollTo(0, current);
    frame = current === target ? 0 : requestAnimationFrame(tick);
  };
  const to = (y) => {
    target = Math.max(0, Math.min(max(), y));
    if (!frame) { current = scrollY; frame = requestAnimationFrame(tick); }
  };
  addEventListener("wheel", (event) => {
    if (event.ctrlKey || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
    // Let inner scroll areas (code blocks, chat) scroll on their own.
    for (let el = event.target; el && el !== document.body; el = el.parentElement) {
      if (el.scrollHeight > el.clientHeight + 1 && /auto|scroll/.test(getComputedStyle(el).overflowY)) return;
    }
    event.preventDefault();
    const unit = event.deltaMode === 1 ? 40 : event.deltaMode === 2 ? innerHeight : 1;
    if (!frame) target = scrollY;
    to(target + event.deltaY * unit);
  }, { passive: false });
  // Keep in sync when something else scrolls the page.
  addEventListener("scroll", () => { if (!frame) target = current = scrollY; }, { passive: true });
  return { to };
})();

// In-page links glide to their section.
document.addEventListener("click", (event) => {
  const link = event.target.closest('a[href^="#"], a[href^="./#"]');
  if (!link) return;
  const id = link.getAttribute("href").split("#")[1];
  const section = id && document.getElementById(id);
  if (!section) return;
  event.preventDefault();
  const y = section.getBoundingClientRect().top + scrollY - 72;
  if (smooth) smooth.to(y); else scrollTo({ top: y, behavior: reduceMotion ? "auto" : "smooth" });
  history.pushState(null, "", `#${id}`);
  section.dispatchEvent(new CustomEvent("navigated"));
});

// ---- Header: hairline once scrolled, hides on the way down, returns on the way up.
const header = document.querySelector(".site-header");
if (header) {
  let last = scrollY;
  addEventListener("scroll", () => {
    const y = scrollY;
    header.classList.toggle("is-scrolled", y > 8);
    header.classList.toggle("is-hidden", y > 400 && y > last + 4);
    if (y < last - 4 || y < 400) header.classList.remove("is-hidden");
    last = y;
  }, { passive: true });
}

// ---- Headlines: split into words so they rise line by line.
for (const heading of document.querySelectorAll("[data-split]")) {
  let i = 0;
  const wrapWords = (node) => {
    for (const child of [...node.childNodes]) {
      if (child.nodeType === Node.TEXT_NODE) {
        const parts = child.textContent.split(/(\s+)/);
        const frag = document.createDocumentFragment();
        for (const part of parts) {
          if (!part) continue;
          if (/^\s+$/.test(part)) { frag.append(part); continue; }
          const w = document.createElement("span");
          w.className = "w";
          const inner = document.createElement("span");
          inner.style.setProperty("--i", String(i++));
          inner.textContent = part;
          w.append(inner);
          frag.append(w);
        }
        child.replaceWith(frag);
      } else if (child.nodeType === Node.ELEMENT_NODE) {
        wrapWords(child);
      }
    }
  };
  wrapWords(heading);
  heading.classList.add("split");
}

// ---- Reveal on scroll.
const revealables = document.querySelectorAll(".reveal, .split");
if ("IntersectionObserver" in window && !reduceMotion) {
  const io = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) { entry.target.classList.add("is-in"); io.unobserve(entry.target); }
    }
  }, { rootMargin: "0px 0px -8% 0px" });
  for (const el of revealables) io.observe(el);
} else {
  for (const el of revealables) el.classList.add("is-in");
}

// ---- Scroll-linked values: elements with data-parallax get --p from 0 to 1 as they cross the viewport.
const parallax = [...document.querySelectorAll("[data-parallax]")];
if (parallax.length && !reduceMotion) {
  let queued = false;
  const update = () => {
    queued = false;
    for (const el of parallax) {
      const r = el.getBoundingClientRect();
      const p = Math.max(0, Math.min(1, (innerHeight - r.top) / (innerHeight + r.height * 0.5)));
      el.style.setProperty("--p", p.toFixed(3));
    }
  };
  addEventListener("scroll", () => { if (!queued) { queued = true; requestAnimationFrame(update); } }, { passive: true });
  update();
}

// ---- Copy buttons on every .code block (except output-only blocks).
for (const block of document.querySelectorAll(".code:not([data-no-copy])")) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "copy";
  button.textContent = "Copy";
  button.setAttribute("aria-label", "Copy to clipboard");
  button.addEventListener("click", async () => {
    const text = [...block.querySelectorAll("pre code")]
      .map((code) => [...code.childNodes].filter((n) => !(n.classList && (n.classList.contains("prompt-mark") || n.classList.contains("out")))).map((n) => n.textContent).join(""))
      .join("\n").trim();
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = "Copied ✓";
      button.classList.add("is-copied");
    } catch {
      const range = document.createRange();
      range.selectNodeContents(block.querySelector("pre"));
      getSelection().removeAllRanges();
      getSelection().addRange(range);
      button.textContent = "Press ⌘C";
    }
    setTimeout(() => { button.textContent = "Copy"; button.classList.remove("is-copied"); }, 1800);
  });
  block.append(button);
}

// ---- Tabs: [role=tablist] with buttons whose aria-controls name their panels.
// A tablist with data-sync="os" also switches every [data-os] element on the page.
const OS_KEY = "tapherd-os";
const setOs = (os) => {
  for (const el of document.querySelectorAll("[data-os]")) el.hidden = el.dataset.os !== os;
  for (const tab of document.querySelectorAll("[data-os-tab]")) tab.setAttribute("aria-selected", String(tab.dataset.osTab === os));
  try { localStorage.setItem(OS_KEY, os); } catch {}
};
for (const list of document.querySelectorAll("[role=tablist]")) {
  const tabs = [...list.querySelectorAll("[role=tab]")];
  const select = (tab) => {
    if (tab.dataset.osTab) { setOs(tab.dataset.osTab); return; }
    for (const other of tabs) {
      const on = other === tab;
      other.setAttribute("aria-selected", String(on));
      other.tabIndex = on ? 0 : -1;
      const panel = document.getElementById(other.getAttribute("aria-controls"));
      if (panel) panel.hidden = !on;
    }
  };
  for (const tab of tabs) {
    tab.addEventListener("click", () => select(tab));
    tab.addEventListener("keydown", (event) => {
      const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
      if (!step) return;
      const next = tabs[(tabs.indexOf(tab) + step + tabs.length) % tabs.length];
      next.focus();
      select(next);
    });
  }
}
if (document.querySelector("[data-os]")) {
  let saved = null;
  try { saved = localStorage.getItem(OS_KEY); } catch {}
  const ua = navigator.userAgent;
  const guess = /Windows/i.test(ua) ? "windows" : /Linux|X11/i.test(ua) && !/Android/i.test(ua) ? "linux" : "mac";
  const valid = [...document.querySelectorAll("[data-os-tab]")].map((t) => t.dataset.osTab);
  setOs(valid.includes(saved) ? saved : valid.includes(guess) ? guess : valid[0]);
}

// ---- Looping media: swap the still for the animated loop once it is near the screen.
// With reduced motion, the still stays.
for (const img of document.querySelectorAll("img[data-loop]")) {
  if (reduceMotion) continue;
  const load = () => {
    const loop = new Image();
    loop.decoding = "async";
    loop.onload = () => { img.src = loop.src; img.classList.add("is-playing"); };
    loop.src = img.dataset.loop;
  };
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) { io.disconnect(); load(); }
    }, { rootMargin: "300px" });
    io.observe(img);
  } else {
    load();
  }
}

// ---- Cookieless analytics, only on the live site and only if a token is set.
const tokenMeta = document.querySelector('meta[name="tapherd-analytics-token"]');
const analyticsToken = tokenMeta ? tokenMeta.content.trim() : "";
if (/^[0-9a-f]{32}$/.test(analyticsToken) && location.protocol === "https:") {
  const beacon = document.createElement("script");
  beacon.defer = true;
  beacon.src = "https://static.cloudflareinsights.com/beacon.min.js";
  beacon.dataset.cfBeacon = JSON.stringify({ token: analyticsToken });
  document.head.append(beacon);
}
