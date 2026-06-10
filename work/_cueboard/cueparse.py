# -*- coding: utf-8 -*-
"""
큐보드 파서 — 화별 대본/큐시트/프롬프트를 읽어 UI용 데이터로 변환.

산출 구조(작품 폴더 컨벤션):
  work/<작품>/NN화/00_대본raw.txt   대본 원문
  work/<작품>/NN화/02_큐시트.md      큐 테이블(인-아웃 = 인용 대사)
  work/<작품>/NN화/03_프롬프트.md    Write 탭 + Styles (A안)
  work/<작품>/NN화/status.json       카드 상태(선택)

핵심: 큐시트 인-아웃 셀의 인용 대사를 대본 원문에서 찾아
각 큐가 커버하는 char offset(IN→OUT 구간)을 계산한다.
"""
import re
import json
import unicodedata
from pathlib import Path

EP_DIR_RE = re.compile(r"^(\d+)\s*화$")
SCENE_RE = re.compile(r"^\s*#\s*(\d+)\b", re.M)
# 곧은/굽은 따옴표 모두 매칭
QUOTE_RE = re.compile(r"[\"“]([^\"”]+?)[\"”]")


# ---------------------------------------------------------------- 작품/화 스캔
def list_projects(work_root: Path):
    out = []
    for p in sorted(work_root.iterdir()):
        if not p.is_dir() or p.name.startswith("_"):
            continue
        if any(EP_DIR_RE.match(c.name) for c in p.iterdir() if c.is_dir()):
            out.append(p.name)
    return out


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def resolve_project(work_root: Path, project: str):
    """
    프로젝트 폴더 Path 해석 — 유니코드 정규화(NFC/NFD) 무관 매칭.
    한글 폴더명이 디스크는 NFC인데 HTTP/브라우저 경유로 NFD가 오는 문제 방어.
    """
    direct = work_root / project
    if direct.is_dir():
        return direct
    target = _nfc(project)
    for c in work_root.iterdir():
        if c.is_dir() and _nfc(c.name) == target:
            return c
    return direct          # 못 찾으면 원경로(상위에서 FileNotFound 처리)


def list_episodes(work_root: Path, project: str):
    proj = resolve_project(work_root, project)
    eps = []
    for c in proj.iterdir():
        if not c.is_dir():
            continue
        m = EP_DIR_RE.match(c.name)
        if not m:
            continue
        n = int(m.group(1))
        has_script = (c / "00_대본raw.txt").exists()
        has_cue = (c / "02_큐시트.md").exists()
        has_prompt = (c / "03_프롬프트.md").exists()
        eps.append({
            "n": n,
            "dir": c.name,
            "has_script": has_script,
            "has_cue": has_cue,
            "has_prompt": has_prompt,
        })
    eps.sort(key=lambda e: e["n"])
    return eps


def _ep_dir(work_root: Path, project: str, n: int):
    proj = resolve_project(work_root, project)
    if not proj.is_dir():
        return None
    for c in proj.iterdir():
        if c.is_dir():
            m = EP_DIR_RE.match(c.name)
            if m and int(m.group(1)) == n:
                return c
    return None


# ---------------------------------------------------------------- 씬 블록
def scene_spans(text: str):
    """{scene_num: (start, end)} — 본문 내 #N 씬 블록의 char 범위."""
    marks = [(int(m.group(1)), m.start()) for m in SCENE_RE.finditer(text)]
    spans = {}
    for i, (num, start) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        spans[num] = (start, end)
    return spans


def _scene_nums(scene_cell: str):
    """'S60', 'S60→S61', 'S60-61' 등에서 씬 번호 추출."""
    return [int(x) for x in re.findall(r"\d+", scene_cell)]


# ---------------------------------------------------------------- 큐시트 파싱
def parse_cuesheet(md: str):
    """큐 테이블 → [{id, scene, inout, function, type, memo}]"""
    lines = md.splitlines()
    header_idx = None
    for i, ln in enumerate(lines):
        if "CUE_ID" in ln and "인-아웃" in ln and ln.strip().startswith("|"):
            header_idx = i
            break
    if header_idx is None:
        return []

    headers = [h.strip() for h in lines[header_idx].strip().strip("|").split("|")]
    col = {h: j for j, h in enumerate(headers)}

    def find_col(*names):
        for nm in names:
            for h, j in col.items():
                if nm in h:
                    return j
        return None

    c_id = find_col("CUE_ID")
    c_scene = find_col("Scene")
    c_inout = find_col("인-아웃")
    c_type = find_col("유형")
    c_func = find_col("기능")
    c_memo = find_col("메모")

    rows = []
    for ln in lines[header_idx + 1:]:
        s = ln.strip()
        if not s.startswith("|"):
            break
        if set(s) <= set("|-: "):  # 구분선
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if c_id is None or c_id >= len(cells) or not cells[c_id]:
            continue
        rows.append({
            "id": cells[c_id],
            "scene": cells[c_scene] if c_scene is not None and c_scene < len(cells) else "",
            "inout": cells[c_inout] if c_inout is not None and c_inout < len(cells) else "",
            "type": cells[c_type] if c_type is not None and c_type < len(cells) else "",
            "function": cells[c_func] if c_func is not None and c_func < len(cells) else "",
            "memo": cells[c_memo] if c_memo is not None and c_memo < len(cells) else "",
        })
    return rows


def split_inout(cell: str):
    """인-아웃 셀 → (in_text, out_text)."""
    in_text, out_text = "", ""
    m_in = re.search(r"IN\s*[:：]\s*(.*?)(?=/\s*OUT\s*[:：]|$)", cell, re.S | re.I)
    m_out = re.search(r"OUT\s*[:：]\s*(.*?)(?=/\s*(?:약|길이|duration)|$)", cell, re.S | re.I)
    if m_in:
        in_text = m_in.group(1).strip()
    if m_out:
        out_text = m_out.group(1).strip()
    return in_text, out_text


def first_quote(s: str):
    m = QUOTE_RE.search(s)
    return m.group(1).strip() if m else None


def parse_anchors(md: str):
    """
    '큐 앵커'(기계 판독용) 테이블 → {CUE_ID: {"in": str, "out": str}}.
    헤더에 CUE_ID·IN앵커가 든 표를 찾는다. 없으면 {} (레거시 = 휴리스틱).
    앵커 값은 대본 원문 정확 부분문자열이어야 하며, 빈칸/대시는 없음으로 처리.
    """
    lines = md.splitlines()
    hidx = None
    for i, ln in enumerate(lines):
        if "CUE_ID" in ln and "IN앵커" in ln and ln.strip().startswith("|"):
            hidx = i
            break
    if hidx is None:
        return {}
    headers = [h.strip() for h in lines[hidx].strip().strip("|").split("|")]
    col = {h: j for j, h in enumerate(headers)}

    def fc(*names):
        for nm in names:
            for h, j in col.items():
                if nm in h:
                    return j
        return None

    c_id, c_in, c_out = fc("CUE_ID"), fc("IN앵커"), fc("OUT앵커")
    out = {}
    for ln in lines[hidx + 1:]:
        s = ln.strip()
        if not s.startswith("|"):
            break
        if set(s) <= set("|-: "):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if c_id is None or c_id >= len(cells) or not cells[c_id]:
            continue

        def g(j):
            v = cells[j] if j is not None and j < len(cells) else ""
            return "" if v in ("—", "-", "–", "") else v

        out[cells[c_id]] = {"in": g(c_in), "out": g(c_out)}
    return out


# ---------------------------------------------------------------- 프롬프트 파싱
def parse_prompts(md: str):
    """
    A안 03_프롬프트.md → {CUE_ID: {function, variants: [{label,write,style,title,memo}, ...]}}
    큐 헤딩 '### EP30_Q1'(또는 '## EP1_Q1'). 큐 본문 안의 '#### 변형 A' 소헤딩으로 변형 분할.
    변형 소헤딩이 없으면(레거시) 본문 전체를 단일 변형으로 처리한다.
    """
    out = {}
    # 큐 헤딩: '### EP30_Q1' 또는 '## EP30_Q1 — "제목"'(꼬리표 허용). #### 변형(4해시)은 제외.
    blocks = re.split(r"^#{2,3}\s+(EP\w+?_Q\d+)\b.*$", md, flags=re.M)
    # blocks: [pre, id1, body1, id2, body2, ...]
    for i in range(1, len(blocks), 2):
        cid = blocks[i].strip()
        body = blocks[i + 1]
        # 큐 레벨 '기능 / 길이'는 첫 변형(####) 앞에서 추출
        head = re.split(r"^####\s+", body, maxsplit=1, flags=re.M)[0]
        function = _grab(head, r"기능\s*/\s*길이\s*[:：]\s*(.+)")
        # 변형 분할
        parts = re.split(r"^####\s+(.+?)\s*$", body, flags=re.M)
        variants = []
        if len(parts) >= 3:                       # [pre, label1, vbody1, label2, vbody2, ...]
            for j in range(1, len(parts), 2):
                variants.append(_parse_variant(parts[j].strip(), parts[j + 1]))
        else:                                     # 레거시 1변형(소헤딩 없음)
            variants.append(_parse_variant("", body))
        out[cid] = {"function": function, "variants": variants}
    return out


def _parse_variant(label: str, vbody: str):
    """변형 1개 본문 → {label, write, style, title, memo}. label은 '변형 A — ...'에서 A만 추려둠."""
    short = label
    m = re.search(r"변형\s*([A-Z가-힣\d]+)", label)
    if m:
        short = m.group(1)
    elif label:
        short = label.split("—")[0].split("-")[0].strip()[:8]
    return {
        "label": short or "",
        "write": _grab_write(vbody),
        "style": _grab_style(vbody),
        "title": _grab(vbody, r"Title\s*[:：]\s*(.+)"),
        "memo": _grab(vbody, r"메모\s*[:：]\s*(.+)"),
    }


def _grab(body: str, pat: str):
    m = re.search(pat, body)
    return m.group(1).strip() if m else ""


def _grab_style(body: str):
    # '- Styles:' (A안) 또는 'Style of Music' 코드블록(구안)
    m = re.search(r"Styles?\s*[:：]\s*(.+)", body)
    if m:
        return m.group(1).strip()
    m = re.search(r"\*\*Style of Music\*\*\s*```(.*?)```", body, re.S)
    return m.group(1).strip() if m else ""


def _grab_write(body: str):
    """Write(구조 태그) 블록 전체(태그 + 옆 사운드 지시 포함)를 줄 단위로 보존."""
    # A안: '- Write(구조 태그):' 다음 들여쓴 줄들 — '- Title'/'- Styles' 또는 끝까지
    m = re.search(r"Write\s*\(구조 태그\)\s*[:：]\s*\n(.*?)(?=\n\s*-\s*Title|\n\s*-\s*Styles|\Z)", body, re.S)
    if m:
        lines = [ln.strip() for ln in m.group(1).strip("\n").splitlines()]
        lines = [ln for ln in lines if ln]          # 빈 줄 제거, 들여쓰기 정리
        return "\n".join(lines)
    # 구안: '**구조 메타태그**' 코드블록
    m = re.search(r"\*\*구조 메타태그\*\*\s*```(.*?)```", body, re.S)
    if m:
        return m.group(1).strip()
    return ""


# ---------------------------------------------------------------- 통합: 화 데이터
def build_episode(work_root: Path, project: str, n: int):
    ep = _ep_dir(work_root, project, n)
    if ep is None:
        return None
    script = (ep / "00_대본raw.txt")
    text = script.read_text(encoding="utf-8") if script.exists() else ""
    spans = scene_spans(text)

    cue_rows = []
    anchors = {}
    cf = ep / "02_큐시트.md"
    if cf.exists():
        cue_md = cf.read_text(encoding="utf-8")
        cue_rows = parse_cuesheet(cue_md)
        anchors = parse_anchors(cue_md)          # 기계 판독용 앵커(있으면 결정적 매핑)

    prompts = {}
    pf = ep / "03_프롬프트.md"
    if pf.exists():
        prompts = parse_prompts(pf.read_text(encoding="utf-8"))

    status = {}
    sf = ep / "status.json"
    if sf.exists():
        try:
            status = json.loads(sf.read_text(encoding="utf-8"))
        except Exception:
            status = {}

    selection = load_selection(ep)               # {cid: {selected:int|null, kept:[int]}}

    # 큐를 대본 순서대로 색 띠 구간에 매핑(앵커 우선, 없으면 커서 전진+보간 휴리스틱).
    mapped = _map_cues(text, spans, cue_rows, anchors)

    cues = []
    for m in mapped:
        r = m["row"]
        cid = r["id"]
        p = prompts.get(cid, {})
        variants = p.get("variants", [])
        sel = selection.get(cid, {})
        cues.append({
            "id": cid,
            "scene": r["scene"],
            "type": r["type"],
            "function": p.get("function") or r["function"],
            "inout": r["inout"],
            "in_quote": m["in_q"],
            "out_quote": m["out_q"],
            "char_start": m["cstart"],
            "char_end": m["cend"],
            "approx": m["approx"],
            "variants": variants,
            "selected": sel.get("selected"),      # int 또는 None
            "kept": sel.get("kept", []),
            "memo": r["memo"],
            "status": status.get(cid, "생성됨" if cid in prompts else "미작업"),
        })

    return {
        "project": project,
        "n": n,
        "dir": ep.name,
        "script": text,
        "scenes": [{"num": k, "start": v[0], "end": v[1]} for k, v in sorted(spans.items())],
        "cues": cues,
    }


# ---------------------------------------------------------------- 선택/킵 영속화
def load_selection(ep: Path):
    """selection.json → {cid: {"selected": int|None, "kept": [int]}}. 없으면 {}."""
    sf = ep / "selection.json"
    if not sf.exists():
        return {}
    try:
        return json.loads(sf.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_selection(ep: Path, cid: str, selected="__keep__", kept="__keep__"):
    """
    selection.json의 한 큐 항목을 머지 저장. 제공된 필드만 갱신(센티넬로 미변경 구분).
    selected=int|None, kept=list[int]. 저장된 전체 dict 반환.
    """
    data = load_selection(ep)
    cur = data.get(cid, {"selected": None, "kept": []})
    if selected != "__keep__":
        cur["selected"] = selected
    if kept != "__keep__":
        cur["kept"] = sorted({int(x) for x in (kept or [])})
    data[cid] = cur
    (ep / "selection.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return data


def _scope(spans, scene_nums, text_len):
    """관련 씬 블록들의 합집합 char 범위. 못 찾으면 전체."""
    start = end = None
    for num in scene_nums:
        if num in spans:
            s, e = spans[num]
            start = s if start is None else min(start, s)
            end = e if end is None else max(end, e)
    if start is None:
        return 0, text_len
    return start, end


def _interp_starts(rows, n):
    """앵커(found)는 그대로, 못 찾은 큐의 시작점은 양옆 앵커 사이로 균등 보간."""
    m = len(rows)
    starts = [r["pos"] for r in rows]            # found면 char offset, 아니면 None
    if starts and starts[0] is None:             # 맨 앞이 비면 첫 큐 스코프 시작으로 고정
        starts[0] = rows[0]["sc_start"]
    i = 0
    while i < m:
        if starts[i] is not None:
            i += 1
            continue
        a = i - 1                                # 왼쪽 known 인덱스
        j = i
        while j < m and starts[j] is None:       # 오른쪽 known 찾기
            j += 1
        left = starts[a]
        right = starts[j] if j < m else n        # 뒤가 전부 None이면 본문 끝까지
        gap = j - a
        for k in range(i, j):
            starts[k] = int(round(left + (right - left) * (k - a) / gap))
        i = j
    for i in range(1, m):                        # 단조 증가 보정
        if starts[i] <= starts[i - 1]:
            starts[i] = min(starts[i - 1] + 1, n)
    return starts


def _map_cues(text, spans, cue_rows, anchors=None):
    """
    큐를 대본 순서대로 색 띠 구간(char offset)에 매핑.
      - 앵커(IN앵커/OUT앵커, 원문 정확 부분문자열)가 있으면 그것을 우선 사용 → 결정적.
        없으면 인-아웃 셀의 인용 대사를 폴백으로 쓴다(레거시 휴리스틱).
      - IN을 '커서 이후 + 씬 스코프 안'에서 찾아 시작점 앵커로(동일 문자열 중복 시 다음 출현).
      - IN을 못 찾은 큐는 양옆 앵커 사이로 균등 보간(approx=True 배지).
      - 띠 끝: OUT을 찾으면 그 끝까지(정밀 — 침묵 간격 자연 표현), 못 찾으면 다음 큐 시작까지
        연속, 마지막 큐는 씬 끝까지. 다음 큐 시작을 넘지 않도록 클램프(겹침 방지).
    """
    anchors = anchors or {}
    n = len(text)
    rows = []
    cursor = 0
    for r in cue_rows:
        a = anchors.get(r["id"], {})
        in_q = a.get("in") or first_quote(split_inout(r["inout"])[0])
        out_q = a.get("out") or first_quote(split_inout(r["inout"])[1])
        sc_start, sc_end = _scope(spans, _scene_nums(r["scene"]), n)
        lo = max(cursor, sc_start)
        pos = -1
        if in_q:
            pos = text.find(in_q, lo, sc_end)
            if pos < 0:
                pos = text.find(in_q, lo)        # 스코프 밖이라도 전진 위치 이후 허용
        found = pos >= 0
        rows.append({
            "row": r, "in_q": in_q, "out_q": out_q,
            "pos": pos if found else None, "found": found,
            "sc_start": sc_start, "sc_end": sc_end,
        })
        if found:
            cursor = pos + 1

    starts = _interp_starts(rows, n)

    out = []
    for i, r in enumerate(rows):
        cstart = starts[i]
        nxt = starts[i + 1] if i + 1 < len(rows) else None
        oq = r["out_q"]
        hi = nxt if nxt is not None else r["sc_end"]
        opos = text.find(oq, cstart, hi) if oq else -1
        if opos >= 0:
            cend = opos + len(oq)                 # OUT 앵커 끝 = 정밀 띠 끝
        elif nxt is not None:
            cend = nxt                            # 연속 띠: 다음 큐 시작까지
        else:
            cend = r["sc_end"]                    # 마지막 큐: 씬 끝
        if nxt is not None:
            cend = min(cend, nxt)                 # 겹침 방지
        if cend <= cstart:
            cend = min(cstart + 1, n)
        out.append({
            "row": r["row"], "in_q": r["in_q"], "out_q": r["out_q"],
            "cstart": cstart, "cend": cend, "approx": not r["found"],
        })
    return out


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # 윈도우 cp949 콘솔 대응
    except Exception:
        pass
    root = Path(__file__).resolve().parents[1]  # work/
    project = sys.argv[2] if len(sys.argv) > 2 else "며느리가친정을숨김"
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    data = build_episode(root, project, n)
    if not data:
        print(f"[!] {project} {n}화 폴더 없음")
        sys.exit(1)
    txt = data["script"]
    print(f"=== {project} {n}화 — 씬 {len(data['scenes'])}개 / 큐 {len(data['cues'])}개 / 대본 {len(txt)}자 ===")
    print("씬: " + ", ".join(f"#{s['num']}({s['start']}~{s['end']})" for s in data["scenes"]))
    print()
    for c in data["cues"]:
        seg = txt[c["char_start"]:c["char_end"]].replace("\n", " ").strip()
        if len(seg) > 70:
            seg = seg[:67] + "..."
        flag = "  ~근사" if c["approx"] else ""
        vs = c["variants"]
        sel = c["selected"]
        print(f"[{c['id']}] {c['scene']}  ({c['char_start']}~{c['char_end']}){flag}"
              f"  변형{len(vs)}개 선택={sel} 킵={c['kept']}")
        print(f"   IN={c['in_quote']!r}  OUT={c['out_quote']!r}")
        print(f"   띠 구간: {seg}")
        for k, v in enumerate(vs):
            mark = "●" if k == sel else ("★" if k in c["kept"] else " ")
            wr = (v.get("write") or "").replace("\n", " ")
            print(f"   {mark}{v.get('label') or chr(65 + k)}: Write={wr[:40]!r}  Style={(v.get('style') or '')[:34]!r}")
        print()
