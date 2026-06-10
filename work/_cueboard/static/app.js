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
  data.cues.forEach((c, i) => {
    const card = el("div", "card");
    card.dataset.cue = c.id;
    card.style.borderLeftColor = color(i);

    const head = el("div", "card-head");
    const cid = el("span", "cid"); cid.textContent = c.id; cid.style.color = "#1d2127";
    head.appendChild(cid);
    if (c.scene) { const b = el("span", "badge scene"); b.textContent = c.scene; head.appendChild(b); }
    if (c.type) { const b = el("span", "badge"); b.textContent = c.type; head.appendChild(b); }
    if (c.approx) { const b = el("span", "badge approx"); b.textContent = "근사"; head.appendChild(b); }
    card.appendChild(head);

    if (c.function) { const fn = el("div", "fn"); fn.textContent = c.function; card.appendChild(fn); }

    const io = el("div", "inout");
    io.textContent = `IN ${c.in_quote ? `“${c.in_quote}”` : "—"}  ▸  OUT ${c.out_quote ? `“${c.out_quote}”` : "—"}`;
    card.appendChild(io);

    card.appendChild(block("Write 탭", c.write));
    card.appendChild(block("Style 탭", c.style));

    card.onclick = (e) => { if (!e.target.classList.contains("copy")) selectCue(c.id, "card"); };
    wrap.appendChild(card);
  });
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
