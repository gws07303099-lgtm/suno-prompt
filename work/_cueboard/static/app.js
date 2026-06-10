"use strict";

// 큐 색 팔레트(인덱스 순환) — 본문 띠 배경 + 카드 좌측 보더 공용.
const PALETTE = [
  "#ffd9a0", "#a0d8ff", "#c7f0c0", "#f3c0d8",
  "#d6c7f5", "#ffe9a0", "#b8ece4", "#ffc0bd",
];
const color = (i) => PALETTE[i % PALETTE.length];

let CUR = { project: null, n: null, data: null };

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls) => { const e = document.createElement(tag); if (cls) e.className = cls; return e; };

async function api(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error((await r.json()).error || r.statusText);
  return r.json();
}

// ---------------------------------------------------------------- 초기 로드
async function init() {
  const { projects } = await api("/api/projects");
  const sel = $("#project");
  projects.forEach((p) => {
    const o = el("option"); o.value = p; o.textContent = p; sel.appendChild(o);
  });
  sel.onchange = () => loadEpisodes(sel.value);
  if (projects.length) await loadEpisodes(projects[0]);
}

async function loadEpisodes(project) {
  CUR.project = project;
  const { episodes } = await api(`/api/episodes?p=${encodeURIComponent(project)}`);
  CUR.episodes = episodes;
  const ul = $("#episodes"); ul.innerHTML = "";
  let done = 0;
  episodes.forEach((e) => {
    const li = el("li"); li.dataset.n = e.n;
    const dot = el("span", "dot");
    if (e.has_cue && e.has_prompt) { dot.classList.add("done"); done++; }
    else if (e.has_script) dot.classList.add("script");
    const name = el("span", "epn"); name.textContent = `${e.n}화`;
    li.append(dot, name);
    li.onclick = () => loadEpisode(e.n);
    ul.appendChild(li);
  });
  $("#meta").textContent = `${project} · ${episodes.length}화 · 큐완료 ${done}화`;
}

async function loadEpisode(n) {
  CUR.n = n;
  document.querySelectorAll("#episodes li").forEach((li) =>
    li.classList.toggle("active", Number(li.dataset.n) === n));
  const data = await api(`/api/episode?p=${encodeURIComponent(CUR.project)}&n=${n}`);
  CUR.data = data;
  CUR.activeVar = {};                    // 화 전환 시 활성 변형 상태 초기화
  $("#scripthead").textContent = `대본 — ${data.dir}`;
  renderScript(data);
  renderCards(data);
}

// ---------------------------------------------------------------- 본문 + 색 띠
function renderScript(data) {
  const box = $("#script");
  box.innerHTML = "";
  const text = data.script;
  const cues = [...data.cues].sort((a, b) => a.char_start - b.char_start);
  // 인덱스(색) 매핑 — 카드 순서와 동일하게 유지
  const idxOf = {};
  data.cues.forEach((c, i) => (idxOf[c.id] = i));

  let prev = 0;
  cues.forEach((c) => {
    if (c.char_start > prev) box.appendChild(document.createTextNode(text.slice(prev, c.char_start)));
    const i = idxOf[c.id];
    const span = el("span", "band");
    span.style.background = color(i);
    span.dataset.cue = c.id;
    const label = el("span", "band-label");
    label.textContent = c.id.replace(/^EP\d+_/, "");   // Q1, Q2…
    span.appendChild(label);
    span.appendChild(document.createTextNode(text.slice(c.char_start, c.char_end)));
    span.onclick = () => selectCue(c.id, "band");
    box.appendChild(span);
    prev = c.char_end;
  });
  if (prev < text.length) box.appendChild(document.createTextNode(text.slice(prev)));
}

// ---------------------------------------------------------------- 큐 카드
function renderCards(data) {
  const wrap = $("#cards");
  wrap.innerHTML = "";
  if (!data.cues.length) {
    const ep = (CUR.episodes || []).find((e) => e.n === CUR.n);
    if (ep && ep.has_script) {
      const d = el("div", "empty");
      d.textContent = "이 화는 아직 큐시트가 없습니다.";
      const btn = el("button", "spotbtn");
      btn.textContent = "🎬 자동 스팟팅 실행";
      btn.onclick = () => startSpot(CUR.n, btn);
      const note = el("div", "spotnote");
      note.textContent = "헤들리스 claude가 분석→큐시트(앵커 포함)→프롬프트→QA를 생성합니다. 수 분 소요.";
      const log = el("pre", "joblog"); log.id = "joblog"; log.style.display = "none";
      wrap.append(d, btn, note, log);
    } else {
      const d = el("div", "empty");
      d.textContent = "대본(00_대본raw.txt)이 없어 스팟팅할 수 없습니다.";
      wrap.appendChild(d);
    }
    return;
  }
  data.cues.forEach((c, i) => wrap.appendChild(buildCard(c, i)));
}

const vlabel = (k) => String.fromCharCode(65 + k);          // 0→A,1→B,2→C

// 카드 1장 빌드(변형 탭 + 선택/킵). 상태 변경 시 노드만 교체해 재호출.
function buildCard(c, i) {
  const card = el("div", "card");
  card.dataset.cue = c.id;
  card.style.borderLeftColor = color(i);

  const vars = c.variants || [];
  const sel = (c.selected != null) ? c.selected : null;
  const kept = c.kept || [];

  // 헤더
  const head = el("div", "card-head");
  const cid = el("span", "cid"); cid.textContent = c.id;
  head.appendChild(cid);
  if (c.scene) { const b = el("span", "badge scene"); b.textContent = c.scene; head.appendChild(b); }
  if (c.type) { const b = el("span", "badge"); b.textContent = c.type; head.appendChild(b); }
  if (c.approx) { const b = el("span", "badge approx"); b.textContent = "근사"; head.appendChild(b); }
  const sb = el("span", "badge sel-badge");
  sb.textContent = sel != null ? `★선택 ${(vars[sel] && vars[sel].label) || vlabel(sel)}` : "미선택";
  if (sel == null) sb.classList.add("none");
  head.appendChild(sb);
  card.appendChild(head);

  if (c.function) { const fn = el("div", "fn"); fn.textContent = c.function; card.appendChild(fn); }
  const io = el("div", "inout");
  io.textContent = `IN ${c.in_quote ? `“${c.in_quote}”` : "—"}  ▸  OUT ${c.out_quote ? `“${c.out_quote}”` : "—"}`;
  card.appendChild(io);

  if (!vars.length) {
    const e = el("div", "empty"); e.textContent = "이 큐는 아직 프롬프트가 없습니다.";
    card.appendChild(e);
    card.onclick = (ev) => { if (!ev.target.closest("button")) selectCue(c.id, "card"); };
    return card;
  }

  // 활성 변형(로컬 상태 우선, 없으면 선택본, 그것도 없으면 A)
  CUR.activeVar = CUR.activeVar || {};
  let active = (CUR.activeVar[c.id] != null) ? CUR.activeVar[c.id] : (sel != null ? sel : 0);
  if (active >= vars.length) active = 0;
  CUR.activeVar[c.id] = active;

  // 변형 탭
  const tabs = el("div", "vtabs");
  vars.forEach((v, k) => {
    const tab = el("button", "vtab");
    const lab = v.label || vlabel(k);
    tab.textContent = lab + (k === sel ? " ●" : "") + (kept.includes(k) ? " ★" : "");
    if (k === active) tab.classList.add("active");
    if (k === sel) tab.classList.add("selected");
    if (kept.includes(k)) tab.classList.add("kept");
    tab.onclick = (e) => { e.stopPropagation(); CUR.activeVar[c.id] = k; replaceCardById(c.id); };
    tabs.appendChild(tab);
  });
  card.appendChild(tabs);

  // 활성 변형 내용
  const v = vars[active];
  card.appendChild(block("Write 탭", v.write));
  card.appendChild(block("Style 탭", v.style));
  if (v.memo) { const m = el("div", "vmemo"); m.textContent = "📝 " + v.memo; card.appendChild(m); }

  // 액션
  const act = el("div", "vactions");
  const isSel = active === sel;
  const selBtn = el("button", "vselect" + (isSel ? " on" : ""));
  selBtn.textContent = isSel ? "✓ 선택됨" : "이 변형 선택";
  selBtn.onclick = (e) => { e.stopPropagation(); postSelect(c.id, { selected: isSel ? null : active }); };
  const isKept = kept.includes(active);
  const keepBtn = el("button", "vkeep" + (isKept ? " on" : ""));
  keepBtn.textContent = isKept ? "★ 킵됨" : "☆ 킵";
  keepBtn.onclick = (e) => {
    e.stopPropagation();
    const s = new Set(kept);
    s.has(active) ? s.delete(active) : s.add(active);
    postSelect(c.id, { kept: [...s].sort((a, b) => a - b) });
  };
  act.append(selBtn, keepBtn);
  card.appendChild(act);

  card.onclick = (e) => { if (!e.target.closest("button")) selectCue(c.id, "card"); };
  return card;
}

async function postSelect(cid, changes) {
  try {
    const r = await fetch("/api/select", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project: CUR.project, n: CUR.n, cue: cid, ...changes }),
    });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "저장 실패");
    const c = CUR.data.cues.find((x) => x.id === cid);
    if (c) {
      if ("selected" in changes) c.selected = j.selection.selected;
      if ("kept" in changes) c.kept = j.selection.kept || [];
    }
    replaceCardById(cid);
  } catch (e) { alert("선택 저장 오류: " + e.message); }
}

function replaceCardById(cid) {
  const i = CUR.data.cues.findIndex((x) => x.id === cid);
  if (i < 0) return;
  const old = document.querySelector(`.card[data-cue="${CSS.escape(cid)}"]`);
  const fresh = buildCard(CUR.data.cues[i], i);
  if (old) old.replaceWith(fresh);
}

function block(title, content) {
  const b = el("div", "block");
  const h = el("div", "block-head");
  const t = el("span"); t.textContent = title;
  const btn = el("button", "copy"); btn.textContent = "복사";
  btn.onclick = async () => {
    try {
      await navigator.clipboard.writeText(content || "");
      btn.textContent = "복사됨"; btn.classList.add("ok");
      setTimeout(() => { btn.textContent = "복사"; btn.classList.remove("ok"); }, 1200);
    } catch { btn.textContent = "실패"; }
  };
  h.append(t, btn);
  const pre = el("pre"); pre.textContent = content || "(비어 있음)";
  b.append(h, pre);
  return b;
}

// ---------------------------------------------------------------- 자동 스팟팅
async function startSpot(n, btn) {
  btn.disabled = true; btn.textContent = "시작 중…";
  const log = $("#joblog"); log.style.display = "block"; log.textContent = "잡 시작 요청…";
  try {
    const r = await fetch("/api/spot", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project: CUR.project, n }),
    });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "시작 실패");
    pollJob(j.job_id, n, btn, log);
  } catch (e) {
    log.textContent = "오류: " + e.message;
    btn.disabled = false; btn.textContent = "🎬 자동 스팟팅 실행";
  }
}

function pollJob(jobId, n, btn, log) {
  const tick = async () => {
    let v;
    try { v = await api(`/api/job?id=${jobId}`); }
    catch (e) { log.textContent = "상태 조회 오류: " + e.message; return; }
    const t = v.elapsed != null ? `${v.elapsed}s` : "";
    log.textContent = `[${v.status}] ${t}\n` + (v.tail || "");
    log.scrollTop = log.scrollHeight;
    if (v.status === "done") {
      btn.textContent = "✅ 완료 — 불러오는 중";
      await loadEpisodes(CUR.project);      // 좌측 점 색 갱신
      await loadEpisode(n);                 // 카드 + 색 띠 렌더(스팟팅 결과)
      return;
    }
    if (v.status === "error") {
      btn.disabled = false; btn.textContent = "⚠️ 실패 — 다시 시도";
      log.textContent = `[error] rc=${v.returncode ?? "?"}\n` + (v.tail || "(로그 없음)");
      return;
    }
    btn.textContent = `스팟팅 중… ${t}`;
    setTimeout(tick, 2500);
  };
  tick();
}

// ---------------------------------------------------------------- 양방향 선택
function selectCue(id, origin) {
  document.querySelectorAll(".band.sel").forEach((e) => e.classList.remove("sel"));
  document.querySelectorAll(".card.sel").forEach((e) => e.classList.remove("sel"));
  const band = document.querySelector(`.band[data-cue="${id}"]`);
  const card = document.querySelector(`.card[data-cue="${id}"]`);
  if (band) {
    band.classList.add("sel");
    if (origin === "card") band.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  if (card) {
    card.classList.add("sel");
    if (origin === "band") card.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

init().catch((e) => { $("#meta").textContent = "오류: " + e.message; });
