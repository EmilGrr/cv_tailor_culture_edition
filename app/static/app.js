"use strict";

const $ = (sel, root = document) => root.querySelector(sel);

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "value") el.value = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(kid));
  }
  return el;
}

async function api(path, opts = {}) {
  const res = await fetch("/api" + path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch { /* keep status text */ }
    throw new Error(msg);
  }
  if (res.status === 204) return null;
  if ((res.headers.get("content-type") || "").includes("application/pdf")) {
    const blob = await res.blob();
    blob.pages = Number(res.headers.get("x-page-count")) || 0;
    return blob;
  }
  return res.json();
}
const sendJson = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

function banner(message, kind = "error", action = null) {
  const el = $("#banner");
  el.className = "banner" + (kind === "ok" ? " ok" : "");
  el.replaceChildren(
    h("span", {}, message, action ? " " : null, action ? h("button", { class: "banner-action", type: "button", onclick: action.fn }, action.label) : null),
    h("button", { class: "close", type: "button", "aria-label": "Dismiss", onclick: () => (el.hidden = true) }, "×")
  );
  el.hidden = false;
  if (kind === "ok") setTimeout(() => (el.hidden = true), 4000);
}

async function busy(btn, fn) {
  btn.classList.add("loading");
  btn.disabled = true;
  try {
    return await fn();
  } finally {
    btn.classList.remove("loading");
    btn.disabled = false;
  }
}

/* ---------- Navigation ---------- */
const VIEWS = ["new", "edit", "pdf", "about"];
let A = null;               // the open application
let lastAppView = "new";

function go(view) {
  const isApp = view !== "about";
  if (isApp) lastAppView = view;
  VIEWS.forEach((v) => $("#view-" + v).classList.toggle("is-active", v === view));
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("is-active", (t.dataset.tab === "about") === !isApp));
  if (isApp) $("#qa-panel").hidden = true;
  $("#stepper").hidden = !isApp;
  document.querySelectorAll(".step").forEach((s) => {
    s.classList.toggle("is-active", s.dataset.view === view);
    s.disabled = s.dataset.view !== "new" && !A;
  });
  const hash = view === "about" ? "#about" : view === "new" ? "" : `#app/${A.id}` + (view === "pdf" ? "/pdf" : "");
  history.replaceState(null, "", location.pathname + hash);
  window.scrollTo({ top: 0 });
}

document.querySelectorAll(".tab").forEach((t) =>
  t.addEventListener("click", () => go(t.dataset.tab === "about" ? "about" : lastAppView))
);
document.querySelectorAll(".step").forEach((s) =>
  s.addEventListener("click", () => {
    go(s.dataset.view);
    if (s.dataset.view === "pdf") generatePdf();
  })
);

/* ---------- Status ---------- */
let templates = [];
async function loadStatus() {
  const s = await api("/status");
  templates = s.templates;
  $("#status").replaceChildren(
    s.demo_data ? h("div", { class: "pill demo", title: "Fictional persona Maja Lindqvist, stored in demo-data. Your own data is not touched." }, "DEMO data: Maja Lindqvist") : null,
    s.demo_model
      ? h("div", { class: "pill demo", title: "Canned output, no call to AWS. Only makes sense with the sample persona." }, "DEMO model, no AWS")
      : h("div", { class: "pill" + (s.aws_credentials ? "" : " bad") }, s.aws_credentials ? "AWS key found" : "No AWS key in .env"),
    h("div", { class: "pill" + (s.tectonic ? "" : " bad") }, s.tectonic ? "LaTeX ready" : "Tectonic missing"),
    h("div", { class: "pill" }, s.model_id)
  );
}

/* ---------- About me (sources) ---------- */
let sourceCount = 0;
async function loadSources() {
  const sources = await api("/sources");
  sourceCount = sources.length;
  $("#source-count").textContent = sources.length ? `(${sources.length})` : "";
  const list = $("#source-list");
  if (!sources.length) {
    list.replaceChildren(h("li", { class: "empty-state" }, "Nothing here yet. Upload a document or write a note."));
    return;
  }
  list.replaceChildren(...sources.map(sourceItem));
}

function sourceItem(src) {
  const slot = h("div");
  const toggle = async () => {
    if (slot.childElementCount) return slot.replaceChildren();
    const full = await api("/sources/" + src.id);
    const name = h("input", { value: full.name });
    const text = h("textarea", { rows: 12 });
    text.value = full.text;
    slot.replaceChildren(
      h("div", { class: "source-edit" },
        h("label", { class: "field" }, h("span", {}, "Title"), name),
        h("label", { class: "field" }, h("span", {}, "Extracted text"), text),
        h("button", { class: "btn small", type: "button", onclick: async () => {
          try {
            await api("/sources/" + src.id, sendJson("PUT", { name: name.value, text: text.value }));
            await loadSources();
          } catch (e) { banner(e.message); }
        } }, "Save changes"))
    );
  };
  return h("li", { class: "source-item" },
    h("div", { class: "source-row" },
      h("span", { class: "name" }, src.name),
      h("span", { class: "tag" }, src.kind === "note" ? "note" : "file"),
      h("span", { class: "hint" }, src.chars.toLocaleString("en") + " chars"),
      h("button", { class: "btn small ghost", type: "button", onclick: () => toggle().catch((e) => banner(e.message)) }, "View / edit"),
      h("button", { class: "icon-btn", type: "button", "aria-label": "Delete " + src.name, onclick: async () => {
        if (!confirm(`Delete "${src.name}"?`)) return;
        await api("/sources/" + src.id, { method: "DELETE" });
        loadSources();
      } }, "✕")),
    slot);
}

async function uploadFiles(files) {
  if (!files.length) return;
  const form = new FormData();
  for (const f of files) form.append("files", f);
  const out = $("#upload-result");
  out.textContent = "Reading…";
  try {
    const res = await api("/sources/upload", { method: "POST", body: form });
    out.replaceChildren(
      res.added.length ? h("div", {}, `Added ${res.added.length} file(s).`) : null,
      ...res.errors.map((e) => h("div", { class: "err" }, `${e.name}: ${e.error}`))
    );
    loadSources();
  } catch (e) {
    out.replaceChildren(h("div", { class: "err" }, e.message));
  }
}
$("#file-input").addEventListener("change", (e) => { uploadFiles([...e.target.files]); e.target.value = ""; });
const drop = $("#drop");
["dragenter", "dragover"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => uploadFiles([...e.dataTransfer.files]));

$("#note-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/sources/note", sendJson("POST", { name: $("#note-name").value, text: $("#note-text").value }));
    e.target.reset();
    banner("Note saved.", "ok");
    loadSources();
  } catch (err) { banner(err.message); }
});

/* ---------- Job posting ---------- */
$("#fetch-btn").addEventListener("click", (e) =>
  busy(e.currentTarget, async () => {
    try {
      const { text } = await api("/job/fetch", sendJson("POST", { url: $("#job-url").value }));
      $("#job-text").value = text;
    } catch (err) { banner(err.message); }
  })
);

$("#draft-btn").addEventListener("click", (e) =>
  busy(e.currentTarget, async () => {
    $("#banner").hidden = true;
    if (!sourceCount) {
      return banner("Tell the tool about yourself first: add a CV or a note.", "error", { label: "Go to About me", fn: () => go("about") });
    }
    try {
      const app = await api("/draft", sendJson("POST", { job_text: $("#job-text").value, job_url: $("#job-url").value }));
      $("#job-text").value = "";
      $("#job-url").value = "";
      await loadSaved();
      openApp(app, "edit");
    } catch (err) { banner(err.message); }
  })
);

/* ---------- Earlier applications ---------- */
async function loadSaved() {
  const items = await api("/applications");
  const list = $("#saved-list");
  if (!items.length) return list.replaceChildren(h("li", { class: "empty-state" }, "None yet."));
  list.replaceChildren(...items.map((a) =>
    h("li", {},
      h("button", { class: "open", type: "button", title: a.title, onclick: async () => {
        try { openApp(await api("/applications/" + a.id), "edit"); } catch (e) { banner(e.message); }
      } }, a.title || "Untitled"),
      h("button", { class: "icon-btn", type: "button", "aria-label": "Delete " + a.title, onclick: async () => {
        if (!confirm(`Delete "${a.title}"?`)) return;
        await api("/applications/" + a.id, { method: "DELETE" });
        if (A && A.id === a.id) A = null;
        loadSaved();
        go("new");
      } }, "✕"))
  ));
}

/* ---------- Editor ---------- */
let saveTimer = null;
const openSections = new Set();   // empty sections the user has just added

const SECTIONS = [
  { key: "contact", title: "Contact" },
  { key: "summary", title: "Summary", regen: true },
  { key: "core_skills", title: "Key skills", regen: true },
  { key: "experience", title: "Experience", regen: true },
  { key: "projects", title: "Projects & assignments", regen: true },
  { key: "education", title: "Education", regen: true },
  { key: "languages", title: "Languages", regen: true },
  { key: "digital_skills", title: "Digital skills", regen: true },
  { key: "volunteer", title: "Volunteering", regen: true },
  { key: "references", title: "References" },
];

const isEmpty = (key) => {
  const v = A.cv[key];
  return Array.isArray(v) ? v.length === 0 : !(v && v.trim());
};
// References show the standard line when empty, so they count as filled unless removed.
const isShown = (key) =>
  key === "contact" ||
  (!A.cv.hidden_sections.includes(key) && (key === "references" || !isEmpty(key) || openSections.has(key)));

function scheduleSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveNow, 700);
}
async function saveNow() {
  clearTimeout(saveTimer);
  if (!A) return;
  try {
    await api("/applications/" + A.id, sendJson("PUT", { cv: A.cv, template: A.template, title: A.title }));
  } catch (e) { banner("Could not save: " + e.message); }
}
const markEdited = () => scheduleSave();

function openApp(app, view = "edit") {
  A = app;
  A.cv.hidden_sections = A.cv.hidden_sections || [];
  openSections.clear();
  $("#app-title").value = A.title || "";
  $("#job-pre").textContent = A.job_text || "";
  renderEditor();
  renderSide();
  renderTemplates();
  go(view);
  if (view === "pdf") generatePdf();
}

$("#app-title").addEventListener("input", (e) => { if (A) { A.title = e.target.value; scheduleSave(); } });
document.querySelectorAll(".to-pdf").forEach((b) => b.addEventListener("click", async () => {
  await saveNow();
  go("pdf");
  generatePdf();
}));

function autosize(ta) { ta.style.height = "auto"; ta.style.height = ta.scrollHeight + "px"; }

function textField(label, obj, prop, opts = {}) {
  const input = opts.area ? h("textarea", { rows: opts.rows || 3 }) : h("input", { type: "text" });
  input.value = obj[prop] ?? "";
  input.addEventListener("input", () => { obj[prop] = input.value; if (opts.area) autosize(input); markEdited(); });
  if (opts.area) requestAnimationFrame(() => autosize(input));
  return h("label", { class: "field" + (opts.span2 ? " span2" : "") }, h("span", {}, label), input);
}

function csvField(label, obj, prop, opts = {}) {
  const input = h("input", { type: "text" });
  input.value = (obj[prop] || []).join(", ");
  input.addEventListener("input", () => {
    obj[prop] = input.value.split(",").map((s) => s.trim()).filter(Boolean);
    markEdited();
  });
  return h("label", { class: "field" + (opts.span2 ? " span2" : "") }, h("span", {}, label), input);
}

function sourceChip(source) {
  return h("span", { class: "src" + (source ? "" : " none"), title: source ? "Source document: " + source : "No source recorded" }, source || "no source");
}

function listBlock(arr, blank, renderItem, addLabel) {
  const wrap = h("div");
  const draw = () => {
    const move = (i, d) => {
      const j = i + d;
      if (j < 0 || j >= arr.length) return;
      [arr[i], arr[j]] = [arr[j], arr[i]];
      markEdited(); draw();
    };
    wrap.replaceChildren(
      ...arr.map((item, i) =>
        h("div", { class: "item" },
          h("div", { class: "item-tools" },
            h("button", { class: "icon-btn", type: "button", title: "Move up", onclick: () => move(i, -1) }, "↑"),
            h("button", { class: "icon-btn", type: "button", title: "Move down", onclick: () => move(i, 1) }, "↓"),
            h("button", { class: "icon-btn", type: "button", title: "Remove", onclick: () => { arr.splice(i, 1); markEdited(); draw(); } }, "✕")),
          renderItem(item))),
      h("button", { class: "btn small ghost add", type: "button", onclick: () => { arr.push(blank()); markEdited(); draw(); } }, addLabel)
    );
  };
  draw();
  return wrap;
}

function bulletsBlock(bullets) {
  const wrap = h("div");
  const draw = () => {
    wrap.replaceChildren(
      ...bullets.map((b, i) => {
        const ta = h("textarea", { rows: 1 });
        ta.value = b.text;
        ta.addEventListener("input", () => { b.text = ta.value; autosize(ta); markEdited(); });
        requestAnimationFrame(() => autosize(ta));
        return h("div", { class: "bullet" }, ta, sourceChip(b.source),
          h("button", { class: "icon-btn", type: "button", title: "Remove bullet", onclick: () => { bullets.splice(i, 1); markEdited(); draw(); } }, "✕"));
      }),
      h("button", { class: "btn small ghost add", type: "button", onclick: () => { bullets.push({ text: "", source: "" }); markEdited(); draw(); } }, "Add bullet")
    );
  };
  draw();
  return wrap;
}

const BUILDERS = {
  contact: (cv) => h("div", { class: "cols contact" },
    ["name", "title", "email", "phone", "city"].map((p) => textField(p[0].toUpperCase() + p.slice(1), cv.contact, p)),
    csvField("Links (comma separated)", cv.contact, "links", { span2: true })),
  summary: (cv) => textField("Summary", cv, "summary", { area: true, rows: 4 }),
  core_skills: (cv) => csvField("Skills (comma separated)", cv, "core_skills"),
  experience: (cv) => listBlock(cv.experience,
    () => ({ role: "", employer: "", place: "", start: "", end: "", bullets: [] }),
    (e) => h("div", {},
      h("div", { class: "cols" },
        textField("Role", e, "role"), textField("Employer", e, "employer"),
        textField("Place", e, "place"), textField("From", e, "start"), textField("To (empty = present)", e, "end")),
      bulletsBlock(e.bullets)),
    "Add role"),
  projects: (cv) => listBlock(cv.projects,
    () => ({ year: "", title: "", role: "", partner: "", scope: "", source: "" }),
    (p) => h("div", {},
      h("div", { class: "cols" },
        textField("Year", p, "year"), textField("Title", p, "title"),
        textField("Role", p, "role"), textField("Partner", p, "partner"),
        textField("Scope", p, "scope", { area: true, span2: true })),
      sourceChip(p.source)),
    "Add project"),
  education: (cv) => listBlock(cv.education,
    () => ({ degree: "", institution: "", period: "", details: "" }),
    (e) => h("div", { class: "cols" },
      textField("Degree", e, "degree"), textField("Institution", e, "institution"),
      textField("Period", e, "period"), textField("Details", e, "details", { area: true, span2: true })),
    "Add education"),
  languages: (cv) => listBlock(cv.languages, () => ({ name: "", level: "" }),
    (l) => h("div", { class: "cols" }, textField("Language", l, "name"), textField("Level", l, "level")),
    "Add language"),
  digital_skills: (cv) => csvField("Digital skills (comma separated)", cv, "digital_skills"),
  volunteer: (cv) => listBlock(cv.volunteer,
    () => ({ role: "", organisation: "", period: "", details: "" }),
    (v) => h("div", { class: "cols" },
      textField("Role", v, "role"), textField("Organisation", v, "organisation"),
      textField("Period", v, "period"), textField("Details", v, "details", { area: true, span2: true })),
    "Add"),
  references: (cv) => textField("Reference line (empty = standard text)", cv, "references"),
};

function renderEditor() {
  const scrollY = window.scrollY;
  $("#sections").replaceChildren(...SECTIONS.filter((s) => isShown(s.key)).map(sectionCard));
  const addable = SECTIONS.filter((s) => !isShown(s.key));
  $("#add-bar").replaceChildren(...(addable.length
    ? [h("span", { class: "hint" }, "Add a section:"), ...addable.map((s) =>
        h("button", { class: "btn small ghost", type: "button", onclick: () => {
          A.cv.hidden_sections = A.cv.hidden_sections.filter((k) => k !== s.key);
          openSections.add(s.key);
          scheduleSave();
          renderEditor();
          $(`.sec[data-key=${s.key}]`)?.scrollIntoView({ behavior: "smooth", block: "center" });
        } }, "+ " + s.title))]
    : []));
  window.scrollTo({ top: scrollY });
}

function sectionCard(sec) {
  const card = h("section", { class: "sec", "data-key": sec.key });
  const head = h("div", { class: "sec-head" }, h("h2", {}, sec.title));
  const regenSlot = h("div");
  if (sec.regen) {
    head.append(h("button", { class: "btn small ghost", type: "button", onclick: () => {
      if (regenSlot.childElementCount) return regenSlot.replaceChildren();
      const instr = h("input", { type: "text", placeholder: 'Optional instruction, e.g. "shorter" or "emphasise project management"' });
      const run = h("button", { class: "btn small primary", type: "button" }, "Regenerate");
      run.addEventListener("click", () => busy(run, async () => {
        try {
          const res = await api(`/applications/${A.id}/regenerate`, sendJson("POST", { cv: A.cv, section: sec.key, instruction: instr.value }));
          A.cv[sec.key] = res.value;
          openSections.add(sec.key);
          scheduleSave();
          renderEditor();
        } catch (e) { banner(e.message); }
      }));
      regenSlot.replaceChildren(h("div", { class: "regen" }, instr, run));
      instr.focus();
    } }, "Regenerate with AI"));
  }
  if (sec.key !== "contact") {
    head.append(h("button", { class: "link-btn", type: "button", title: "Remove this section from the CV", onclick: () => {
      A.cv.hidden_sections.push(sec.key);
      openSections.delete(sec.key);
      scheduleSave();
      renderEditor();
    } }, "Remove section"));
  }
  card.append(head, regenSlot, h("div", { class: "sec-body" }, BUILDERS[sec.key](A.cv)));
  return card;
}

function renderSide() {
  const reqs = (A.analysis && A.analysis.requirements) || [];
  $("#req-panel").hidden = !reqs.length;
  $("#req-panel").replaceChildren(h("h2", {}, "Requirements"), h("ul", { class: "req" }, ...reqs.map((r) =>
    h("li", {}, h("span", { class: "mark" + (r.evidence ? "" : " miss") }, r.evidence ? "✓" : "○"),
      h("span", {}, r.text, h("small", {}, r.evidence ? `${r.evidence}${r.source ? " · " + r.source : ""}` : "No evidence found in your sources"))))));

  const gaps = A.cv.gaps_and_questions || [];
  $("#gaps-panel").hidden = !gaps.length;
  $("#gaps-panel").replaceChildren(h("h2", {}, "Missing details"),
    h("p", { class: "hint" }, "Add these to About me, or to the text, if they are true."),
    h("ul", { class: "q-list" }, ...gaps.map((g, i) =>
      h("li", {}, h("span", {}, g), h("button", { class: "icon-btn", type: "button", title: "Dismiss", onclick: () => {
        A.cv.gaps_and_questions.splice(i, 1); scheduleSave(); renderSide();
      } }, "✕")))),
    h("button", { class: "btn small", type: "button", onclick: showQuestions }, "Add details"));

  const left = A.cv.left_out || [];
  $("#left-panel").hidden = !left.length;
  $("#left-panel").replaceChildren(h("h2", {}, "Left out"),
    h("ul", { class: "q-list" }, ...left.map((l) => h("li", {}, h("span", {}, l)))));
}

/* ---------- Answer the "Missing details" questions in About me ---------- */
function showQuestions() {
  const panel = $("#qa-panel");
  const questions = [...(A.cv.gaps_and_questions || [])];
  if (!questions.length) { panel.hidden = true; return; }
  const answers = questions.map(() => h("textarea", { rows: 3, placeholder: "Answer only if it is true. Leave blank to skip." }));
  const form = h("form", { class: "stack" },
    h("h2", {}, "Questions from your draft"),
    h("p", { class: "hint" }, "Your answers are saved as a note in About me, so the AI may use them in this and later drafts."),
    ...questions.map((q, i) => h("label", { class: "field" }, h("span", {}, q), answers[i])),
    h("div", { class: "qa-actions" },
      h("button", { class: "btn", type: "submit" }, "Save answers"),
      h("button", { class: "btn ghost", type: "button", onclick: () => { panel.hidden = true; go(lastAppView); } }, "Back to the CV")));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const answered = questions.map((q, i) => ({ q, a: answers[i].value.trim() })).filter((x) => x.a);
    if (!answered.length) return banner("Write at least one answer first.");
    try {
      const title = A.title || (A.analysis && A.analysis.title) || "";
      await api("/sources/note", sendJson("POST", {
        name: "Svar på frågor" + (title ? ": " + title : ""),
        text: answered.map((x) => `Fråga: ${x.q}\nSvar: ${x.a}`).join("\n\n"),
      }));
      const done = new Set(answered.map((x) => x.q));
      A.cv.gaps_and_questions = A.cv.gaps_and_questions.filter((g) => !done.has(g));
      await saveNow();
      renderSide();
      loadSources();
      banner("Saved to About me. Regenerate a section or the draft to use the new details.", "ok");
      showQuestions();
    } catch (err) { banner(err.message); }
  });
  panel.replaceChildren(form);
  panel.hidden = false;
  go("about");
  panel.scrollIntoView({ block: "start" });
}

/* ---------- PDF ---------- */
let pdfUrl = null;
let pdfSeq = 0;

function renderTemplates() {
  $("#template-picker").replaceChildren(...templates.map((t) => {
    const [name, desc] = t.label.split(" - ");
    return h("button", { type: "button", class: "tpl" + (A.template === t.id ? " sel" : ""), onclick: () => {
      if (A.template === t.id) return;
      A.template = t.id;
      renderTemplates();
      saveNow();
      generatePdf();
    } }, h("span", {}, h("b", {}, name), h("small", {}, desc || "")));
  }));
}

async function generatePdf() {
  const seq = ++pdfSeq;
  const status = $("#pdf-status");
  status.className = "pdf-status busy";
  status.textContent = "Typesetting… the first run can take a minute while LaTeX packages download.";
  $("#pdf-frame").hidden = true;
  $("#pdf-note").hidden = true;
  $("#download-btn").hidden = true;
  try {
    await saveNow();
    const blob = await api("/render", sendJson("POST", { cv: A.cv, template: A.template }));
    if (seq !== pdfSeq) return;
    if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    pdfUrl = URL.createObjectURL(blob);
    status.className = "pdf-status";
    status.textContent = "";
    const note = $("#pdf-note");
    note.hidden = blob.pages < 2;
    note.textContent = blob.pages > 1
      ? `The CV runs to ${blob.pages} pages. Two is fine, but for a single page try the Compact template or remove a section in Edit.`
      : "";
    const frame = $("#pdf-frame");
    frame.src = pdfUrl;
    frame.hidden = false;
    const dl = $("#download-btn");
    dl.href = pdfUrl;
    dl.download = `cv ${A.cv.contact.name || "cv"}.pdf`.trim();
    dl.hidden = false;
  } catch (err) {
    if (seq !== pdfSeq) return;
    status.className = "pdf-status err";
    status.textContent = err.message;
  }
}

$("#back-btn").addEventListener("click", () => go("edit"));

/* ---------- Boot ---------- */
async function boot() {
  await loadStatus();
  const m = location.hash.match(/^#app\/([0-9a-f]{8})(\/pdf)?$/);
  if (m) {
    try { return openApp(await api("/applications/" + m[1]), m[2] ? "pdf" : "edit"); } catch { /* fall through */ }
  }
  go(location.hash === "#about" ? "about" : "new");
}
boot().catch((e) => banner(e.message));
loadSources().catch((e) => banner(e.message));
loadSaved().catch((e) => banner(e.message));
