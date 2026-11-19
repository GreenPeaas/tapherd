// Interactive concept of the planned TapHerd Pro dashboard.
// Everything here is a local simulation: no phones, accounts, or network calls.
(() => {
  const root = document.querySelector("#pro-app");
  if (!root) return;

  const GROUPS = ["Creators", "Creators", "Creators", "Creators", "Creators", "Creators", "QA", "QA", "QA", "QA", "Cloud", "Cloud"];
  const phones = GROUPS.map((group, i) => ({
    id: i,
    name: `Phone ${String(i + 1).padStart(2, "0")}`,
    group,
    status: i === 9 ? "needs" : [1, 4, 7].includes(i) ? "posting" : "ready",
    screen: ["home", "upload", "gallery", "settings"][i % 4],
  }));
  const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const TIMES = ["9 AM", "12 PM", "3 PM", "6 PM"];
  let posts = [
    { id: 1, day: 0, time: 1, platform: "TikTok", phones: 4 },
    { id: 2, day: 0, time: 3, platform: "Reels", phones: 4 },
    { id: 3, day: 1, time: 0, platform: "Shorts", phones: 2 },
    { id: 4, day: 2, time: 1, platform: "Reels", phones: 3 },
    { id: 5, day: 2, time: 2, platform: "TikTok", phones: 6 },
    { id: 6, day: 3, time: 2, platform: "Shorts", phones: 5 },
    { id: 7, day: 5, time: 1, platform: "TikTok", phones: 4 },
    { id: 8, day: 6, time: 3, platform: "Reels", phones: 6 },
  ];
  let nextId = 9;
  const state = { view: "fleet", filter: "All", phone: 0, mirror: false, log: [], chat: [] };

  const h = (tag, attrs = {}, ...children) => {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") el.className = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (v === true) el.setAttribute(k, "");
      else if (v !== false && v != null) el.setAttribute(k, v);
    }
    for (const child of children.flat()) if (child != null && child !== false) el.append(child);
    return el;
  };
  const STATUS = { ready: "Ready", posting: "Posting", needs: "Needs you" };

  // ---------- Faux Android screens
  const SCREENS = {
    home: { title: null },
    settings: { title: "Settings", rows: [["Network & internet", "Mobile, Wi-Fi, hotspot", "network"], ["Connected devices", "Bluetooth, pairing"], ["Apps", "Recent apps, default apps"], ["Notifications", "Notification history"], ["Battery", "100%"], ["Storage", "43% used"]] },
    network: { title: "Network & internet", back: "settings", rows: [["Internet", "Connected", "internet"], ["Calls & SMS", ""], ["SIMs", ""], ["Airplane mode", "Off"], ["Hotspot & tethering", "Off"]] },
    internet: { title: "Internet", back: "network", rows: [["Wi-Fi", "On"], ["Studio Wi-Fi", "Connected"], ["Network preferences", ""]] },
    gallery: { title: "Gallery", back: "home", grid: true },
    upload: { title: "New post", back: "home", rows: [["Select video", "launch-video.mp4", "gallery"], ["Caption", "Drafted by your assistant"], ["Visibility", "Private"], ["Post", "Tap to publish (concept)"]] },
  };
  const APPS = [["Settings", "settings", "#6b7f99"], ["Gallery", "gallery", "#c4703d"], ["Video app", "upload", "#b5463a"], ["Camera", null, "#4f7d5c"], ["Files", null, "#7a6aa8"], ["Chrome", null, "#3f78c8"]];

  const logAction = (kind, text) => {
    state.log.unshift({ kind, text });
    state.log = state.log.slice(0, 7);
  };

  const navigatePhone = (to, label) => {
    const phone = phones[state.phone];
    phone.screen = to;
    logAction("tap", label);
    logAction("screen", `${SCREENS[to].title || "Home"} opened on ${phone.name}`);
    if (state.mirror) {
      const group = phones.filter((p) => p.group === phone.group && p !== phone);
      for (const p of group) p.screen = to;
      logAction("mirror", `Same step sent to ${group.length} ${phone.group} phones`);
    }
    render();
  };

  const screen = (phone, interactive) => {
    const s = SCREENS[phone.screen];
    const body = h("div", { class: "pa-screen" + (interactive ? "" : " mini") });
    body.append(h("div", { class: "pa-status" }, h("span", {}, "10:48"), h("span", {}, "▾ ▴ ▮")));
    if (!s.title) {
      body.append(h("div", { class: "pa-clock" }, "10:48"));
      const grid = h("div", { class: "pa-apps" });
      for (const [name, to, color] of APPS) {
        grid.append(interactive && to
          ? h("button", { type: "button", class: "pa-app", onclick: () => navigatePhone(to, name) }, h("i", { style: `background:${color}` }), name)
          : h("div", { class: "pa-app" }, h("i", { style: `background:${color}` }), name));
      }
      body.append(grid);
      return body;
    }
    body.append(h("div", { class: "pa-title" },
      interactive && s.back ? h("button", { type: "button", class: "pa-back", "aria-label": "Back", onclick: () => navigatePhone(s.back, "Back") }, "←") : null,
      s.title));
    if (s.grid) {
      const g = h("div", { class: "pa-gallery" });
      for (let i = 0; i < 9; i++) g.append(h("i", { style: `--h:${(i * 47) % 360}` }));
      body.append(g);
    } else {
      for (const [title, sub, to] of s.rows) {
        const content = [h("b", {}, title), sub ? h("small", {}, sub) : null];
        body.append(interactive && to
          ? h("button", { type: "button", class: "pa-row is-link", onclick: () => navigatePhone(to, title) }, content)
          : h("div", { class: "pa-row" }, content));
      }
    }
    return body;
  };

  // ---------- Views
  const fleetView = () => {
    const filters = ["All", "Creators", "QA", "Cloud"];
    const shown = phones.filter((p) => state.filter === "All" || p.group === state.filter);
    const counts = { online: phones.length, posting: phones.filter((p) => p.status === "posting").length, needs: phones.filter((p) => p.status === "needs").length };
    return h("div", { class: "pa-view" },
      h("div", { class: "pa-head" },
        h("div", {}, h("h4", {}, "Fleet"), h("p", {}, "Click any phone to control it.")),
        h("div", { class: "pa-chips", role: "group", "aria-label": "Filter phones" },
          filters.map((f) => h("button", { type: "button", class: "pa-chip", "aria-pressed": String(state.filter === f), onclick: () => { state.filter = f; render(); } },
            f === "All" ? `All ${phones.length}` : `${f} ${phones.filter((p) => p.group === f).length}`)))),
      h("div", { class: "pa-stats" },
        h("div", {}, h("small", {}, "Online"), h("b", { class: "ok" }, String(counts.online))),
        h("div", {}, h("small", {}, "Posting now"), h("b", { class: "warm" }, String(counts.posting))),
        h("div", {}, h("small", {}, "Scheduled"), h("b", {}, String(posts.length))),
        h("div", {}, h("small", {}, "Need you"), h("b", { class: "bad" }, String(counts.needs)))),
      h("div", { class: "pa-fleet" },
        shown.map((p) => h("button", { type: "button", class: "pa-tile", onclick: () => { state.phone = p.id; state.view = "remote"; logAction("open", `${p.name} (${p.group})`); render(); } },
          h("span", { class: `pa-dot ${p.status}` }), h("b", {}, p.name),
          h("div", { class: "pa-tile-screen" }, screen(p, false)),
          h("small", {}, `${STATUS[p.status]} · ${p.group}`)))));
  };

  const remoteView = () => {
    const phone = phones[state.phone];
    const group = phones.filter((p) => p.group === phone.group && p !== phone);
    return h("div", { class: "pa-view pa-remote" },
      h("div", { class: "pa-device" }, screen(phone, true),
        h("div", { class: "pa-nav" },
          h("button", { type: "button", "aria-label": "Back", onclick: () => { const b = SCREENS[phone.screen].back; if (b) navigatePhone(b, "Back"); } }, "‹"),
          h("button", { type: "button", "aria-label": "Home", onclick: () => navigatePhone("home", "Home") }, "●"),
          h("button", { type: "button", "aria-label": "Recents", onclick: () => { logAction("key", "Recents"); render(); } }, "■"))),
      h("div", { class: "pa-side" },
        h("div", { class: "pa-head" },
          h("div", {}, h("h4", {}, phone.name, " ", h("span", { class: "pa-live" }, "Live")), h("p", {}, "Click the screen to tap. Try Settings → Network & internet."))),
        h("label", { class: "pa-switch" },
          h("input", { type: "checkbox", checked: state.mirror, onchange: (e) => { state.mirror = e.target.checked; logAction("mirror", state.mirror ? `Mirroring to ${phone.group} (${group.length + 1} phones)` : "Mirroring off"); render(); } }),
          h("span", {}), `Mirror to the ${phone.group} group`),
        h("div", { class: "pa-minis", "aria-hidden": "true" }, group.slice(0, 5).map((p) => h("div", { class: "pa-mini" }, screen(p, false)))),
        h("div", { class: "pa-log" }, h("small", {}, "Action log"),
          state.log.length ? state.log.map((l) => h("div", {}, h("code", { "data-kind": l.kind }, l.kind), l.text)) : h("div", { class: "muted" }, "Nothing yet.")),
        h("div", { class: "pa-actions" },
          h("button", { type: "button", class: "pa-chip", onclick: () => { state.view = "fleet"; render(); } }, "← All phones"),
          h("button", { type: "button", class: "pa-chip", onclick: () => { logAction("handoff", `${phone.name} handed to your AI client`); render(); } }, "Hand to my AI"))));
  };

  // Drag posts between cells with pointer events; arrow keys move a focused post.
  let drag = null;
  const scheduleView = () => {
    const grid = h("div", { class: "pa-cal", role: "grid", "aria-label": "Week schedule" });
    grid.append(h("div", { class: "pa-corner" }));
    for (const d of DAYS) grid.append(h("div", { class: "pa-day", role: "columnheader" }, d));
    TIMES.forEach((t, ti) => {
      grid.append(h("div", { class: "pa-time", role: "rowheader" }, t));
      DAYS.forEach((_, di) => {
        const cell = h("div", { class: "pa-cell", role: "gridcell", "data-day": di, "data-time": ti });
        for (const post of posts.filter((p) => p.day === di && p.time === ti)) {
          cell.append(h("button", {
            type: "button", class: `pa-post ${post.platform.toLowerCase()}${post.fresh ? " fresh" : ""}`, "data-id": post.id,
            "aria-label": `${post.platform}, ${post.phones} phones, ${DAYS[post.day]} ${TIMES[post.time]}. Drag or use arrow keys to move.`,
            onpointerdown: (e) => startDrag(e, post),
            onkeydown: (e) => {
              const moves = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
              const m = moves[e.key];
              if (!m) return;
              e.preventDefault();
              post.day = Math.max(0, Math.min(6, post.day + m[0]));
              post.time = Math.max(0, Math.min(3, post.time + m[1]));
              render();
              root.querySelector(`[data-id="${post.id}"]`)?.focus();
            },
          }, h("b", {}, post.platform), h("small", {}, `${post.phones} phones`)));
        }
        grid.append(cell);
      });
    });
    return h("div", { class: "pa-view" },
      h("div", { class: "pa-head" },
        h("div", {}, h("h4", {}, "Schedule"), h("p", {}, "Drag a post to another time. Each phone posts on its own."))),
      grid);
  };
  const startDrag = (event, post) => {
    if (event.button !== 0) return;
    const el = event.currentTarget;
    const rect = el.getBoundingClientRect();
    drag = { post, el, dx: event.clientX - rect.left, dy: event.clientY - rect.top, moved: false };
    el.setPointerCapture(event.pointerId);
    el.addEventListener("pointermove", onDrag);
    el.addEventListener("pointerup", endDrag, { once: true });
    el.addEventListener("pointercancel", endDrag, { once: true });
  };
  const onDrag = (event) => {
    if (!drag) return;
    drag.moved = true;
    const { el } = drag;
    el.classList.add("is-dragging");
    el.style.position = "fixed";
    el.style.width = `${el.offsetWidth}px`;
    el.style.left = `${event.clientX - drag.dx}px`;
    el.style.top = `${event.clientY - drag.dy}px`;
    for (const c of root.querySelectorAll(".pa-cell.is-over")) c.classList.remove("is-over");
    el.style.pointerEvents = "none";
    const cell = document.elementFromPoint(event.clientX, event.clientY)?.closest(".pa-cell");
    el.style.pointerEvents = "";
    if (cell) cell.classList.add("is-over");
  };
  const endDrag = (event) => {
    if (!drag) return;
    const { el, post } = drag;
    el.removeEventListener("pointermove", onDrag);
    el.style.pointerEvents = "none";
    const cell = document.elementFromPoint(event.clientX, event.clientY)?.closest(".pa-cell");
    if (cell && drag.moved) {
      post.day = Number(cell.dataset.day);
      post.time = Number(cell.dataset.time);
    }
    drag = null;
    render();
  };

  const SUGGESTIONS = [
    "Post Friday's launch video to all Creators phones at 6 PM. Keep Shorts private.",
    "Which phones need me?",
    "Move Wednesday's posts to Thursday.",
  ];
  const reply = (text) => {
    if (text === SUGGESTIONS[0]) {
      for (const platform of ["TikTok", "Reels", "Shorts"]) posts.push({ id: nextId++, day: 4, time: 3, platform, phones: 6, fresh: true });
      return { text: "Done. I added 3 posts for Friday at 6 PM across 6 Creators phones: TikTok, Reels, and Shorts (Private). Captions are drafted for each.", action: ["Open the schedule", "schedule"] };
    }
    if (text === SUGGESTIONS[1]) {
      const needs = phones.filter((p) => p.status === "needs");
      return { text: `${needs.map((p) => p.name).join(", ")} needs you: the upload screen changed, so the run stopped instead of guessing.`, action: [`Open ${needs[0].name}`, "remote", needs[0].id] };
    }
    if (text === SUGGESTIONS[2]) {
      const moved = posts.filter((p) => p.day === 2);
      for (const p of moved) { p.day = 3; p.fresh = true; }
      return { text: moved.length ? `Moved ${moved.length} post${moved.length > 1 ? "s" : ""} from Wednesday to Thursday, same times.` : "There's nothing on Wednesday right now.", action: ["Open the schedule", "schedule"] };
    }
    return { text: "This is a concept preview, so I only know the suggestions below. In Pro, you'll be able to ask about any phone, post, or run." };
  };
  const send = (text) => {
    if (!text.trim() || state.typing) return;
    for (const p of posts) p.fresh = false;
    state.chat.push({ from: "you", text });
    state.typing = true;
    render();
    setTimeout(() => {
      state.typing = false;
      state.chat.push({ from: "bot", ...reply(text) });
      render();
    }, 900);
  };
  const assistantView = () => {
    const input = h("input", { type: "text", placeholder: "Ask about your phones, posts, or runs…", "aria-label": "Message the assistant" });
    const log = h("div", { class: "pa-chat", "aria-live": "polite" },
      state.chat.length ? null : h("div", { class: "pa-bubble bot" }, "Hi. I can see your 12 phones and this week's schedule. Try a suggestion below."),
      state.chat.map((m) => h("div", { class: `pa-bubble ${m.from}` }, m.text,
        m.action ? h("button", { type: "button", class: "pa-chip", onclick: () => { if (m.action[2] != null) state.phone = m.action[2]; state.view = m.action[1]; render(); } }, `${m.action[0]} →`) : null)),
      state.typing ? h("div", { class: "pa-bubble bot pa-typing", "aria-label": "Assistant is typing" }, h("i"), h("i"), h("i")) : null);
    queueMicrotask(() => { log.scrollTop = log.scrollHeight; });
    return h("div", { class: "pa-view pa-assistant" },
      h("div", { class: "pa-head" }, h("div", {}, h("h4", {}, "Assistant"), h("p", {}, "It knows your phones and schedule. Suggestions change the demo."))),
      log,
      h("div", { class: "pa-suggest" }, SUGGESTIONS.map((s) => h("button", { type: "button", class: "pa-chip", disabled: state.typing, onclick: () => send(s) }, s))),
      h("form", { class: "pa-input", onsubmit: (e) => { e.preventDefault(); send(input.value); } }, input, h("button", { type: "submit", class: "pa-chip" }, "Send")));
  };

  const VIEWS = { fleet: ["Fleet", fleetView], remote: ["Remote", remoteView], schedule: ["Schedule", scheduleView], assistant: ["Assistant", assistantView] };

  const render = () => {
    const focusedId = document.activeElement && root.contains(document.activeElement) ? document.activeElement.id : null;
    const nav = h("nav", { class: "pa-nav-side", "aria-label": "Concept dashboard" },
      Object.entries(VIEWS).map(([key, [label]]) => h("button", {
        type: "button", id: `pa-tab-${key}`, "aria-current": state.view === key ? "page" : false,
        onclick: () => { state.view = key; render(); },
      }, label)),
      h("div", { class: "pa-quota" }, h("small", {}, "12 of 50 devices"), h("i", { style: "--w:24%" })));
    const top = h("div", { class: "pa-top" },
      h("span", { class: "pa-dots" }, h("i"), h("i"), h("i")),
      h("b", {}, "TapHerd ", h("span", { class: "pa-pro" }, "Pro")),
      h("span", { class: "pa-concept" }, "Interactive concept · simulated data"),
      h("span", { class: "pa-ws" }, "Your studio ▾"));
    const main = h("div", { class: "pa-main" }, VIEWS[state.view][1]());
    root.replaceChildren(top, h("div", { class: "pa-body" }, nav, main));
    if (focusedId) document.getElementById(focusedId)?.focus();
  };
  render();
})();
