# -*- coding: utf-8 -*-
"""
자동 스팟팅 잡의 오케스트레이션 프롬프트 빌더.

server.py가 헤들리스 `claude -p`(구독 인증·acceptEdits)에 이 프롬프트를 stdin으로 넣어
한 화의 파이프라인(분석→스팟팅→프롬프트→QA)을 1회 실행, 4개 산출 파일을 생성한다.

설계 메모:
- 4개 서브에이전트 체이닝 대신 '경로 명시 단일 프롬프트'를 쓴다(에이전트 기본 경로가
  구안 `work/01_script_analysis.md`라 NN화 컨벤션과 어긋나기 때문).
- CUE_ID는 파서(parse_prompts: r"EP\\w+?_Q\\d+")와 큐시트(parse_anchors)에 맞춰 EP{n}_Q{k}.
- 큐시트에 '큐 앵커(기계 판독용)' 표를 반드시 포함 → 색 띠 결정적 매핑.
"""
import re
from pathlib import Path


def _renumber_cues(ep_dir: Path, ep_n: int, from_k: int, direction: str = "down") -> None:
    """from_k 이상인 EP{n}_Qk를 1씩 당김(down) 또는 밀기(up).
    down: 삭제 후 뒤 번호 당김 — ascending 순으로 처리.
    up: 추가 전 뒤 번호 밀기 — descending 순으로 처리(충돌 방지).
    02·03·04 파일 + selection.json 갱신."""
    import json as _json

    md_names = ("02_큐시트.md", "03_프롬프트.md", "04_QA.md")
    md_files = [ep_dir / n for n in md_names if (ep_dir / n).exists()]
    sel_path = ep_dir / "selection.json"

    pat = re.compile(rf"EP{ep_n}_Q(\d+)")
    ks_set: set[int] = set()
    for f in md_files:
        for m in pat.finditer(f.read_text(encoding="utf-8")):
            k = int(m.group(1))
            if k >= from_k:
                ks_set.add(k)

    if not ks_set:
        return

    delta = -1 if direction == "down" else 1
    # down=ascending(Q3→Q2, Q4→Q3), up=descending(Q4→Q5, Q3→Q4) — 충돌 방지
    ks = sorted(ks_set, reverse=(direction == "up"))

    for f in md_files:
        text = f.read_text(encoding="utf-8")
        for k in ks:
            text = text.replace(f"EP{ep_n}_Q{k}", f"EP{ep_n}_Q{k + delta}")
        f.write_text(text, encoding="utf-8")

    if sel_path.exists():
        try:
            data = _json.loads(sel_path.read_text(encoding="utf-8"))
            new_data: dict = {}
            moved: set[str] = set()
            for k in ks:
                old_key = f"EP{ep_n}_Q{k}"
                if old_key in data:
                    new_data[f"EP{ep_n}_Q{k + delta}"] = data[old_key]
                    moved.add(old_key)
            for key, val in data.items():
                if key not in moved:
                    new_data[key] = val
            sel_path.write_text(_json.dumps(new_data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


def _splice_cue_block(prompts_path: Path, cue_id: str, block_path: Path) -> None:
    """03_프롬프트.md에서 cue_id 섹션을 block_path 내용으로 교체 후 block_path 삭제."""
    raw = block_path.read_text(encoding="utf-8")
    # Claude가 _block.md에 프리앰블을 추가할 수 있으므로 ### CUE_ID 부터만 추출
    m = re.search(rf"### {re.escape(cue_id)}[\s\S]*", raw)
    if not m:
        raise ValueError(f"splice: '{cue_id}' 헤더를 _block.md에서 찾지 못함")
    new_block = m.group(0).strip()
    text = prompts_path.read_text(encoding="utf-8")
    pattern = rf"### {re.escape(cue_id)}[^\n]*\n[\s\S]*?(?=\n### |\Z)"
    result, count = re.subn(pattern, lambda m: new_block + "\n", text, count=1)
    if count == 0:
        raise ValueError(f"splice: '{cue_id}' 섹션을 {prompts_path.name}에서 찾지 못함")
    prompts_path.write_text(result, encoding="utf-8")
    block_path.unlink(missing_ok=True)


def _variant_format(n: int, cue_id: str | None = None) -> str:
    """큐당 3변형(A/B/C) 출력 포맷.
    cue_id 지정 시(single_cue 전용) 해당 CUE_ID로 예시 헤더를 채운다."""
    q = cue_id or f"EP{n}_Q1"
    return f"""큐마다 **3개의 음악적으로 구별되는 변형(A/B/C)**을 만든다. 단순 표현 바꾸기(rewording) 금지 — 서로 다른 음악적 해석이어야 한다:
- **변형 A** = 바이블 정공법(메인 팔레트·라이트모티프 정합, 가장 안전한 본).
- **변형 B** = 같은 기능·다른 색(대안 악기/질감·서브장르 변주).
- **변형 C** = 과감/실험적(템포·장르·구조를 더 밀어붙인 대안).
세 변형 모두 **인스트루멘탈·작품 톤 유지·해당 큐 기능 충족**. 큐당 형식(가이드 §6 A안):
```
### {q}
- 기능 / 길이: ... / 약 N초
- Lyrics 탭: Write

#### 변형 A — <한 줄 컨셉>
- Write(구조 태그):
  [Intro] ...
  [Build] ...
  [Climax] ...
  [Outro] ...
- Title: {q}_A_<짧은키워드>
- Styles: <BPM·키·장르·악기2개+·무드 + 끝에 instrumental, no vocals>
- 메모: ...

#### 변형 B — <한 줄 컨셉>
- Write(구조 태그):
  ...
- Title: {q}_B_<짧은키워드>
- Styles: <...>
- 메모: ...

#### 변형 C — <한 줄 컨셉>
- Write(구조 태그):
  ...
- Title: {q}_C_<짧은키워드>
- Styles: <...>
- 메모: ...
```
규칙(전 변형 공통): Write 블록엔 **가사 단어 0**(구조/연출 태그만), Styles 끝에 `instrumental, no vocals` 필수, 아티스트 실명 금지(질감 묘사로 대체), 모순/언어혼입/오타 금지, CUE_ID는 큐시트와 1:1 일치, 각 변형 Title에 `_A`/`_B`/`_C`."""


def spot_prompt(project: str, n: int, ep_dir: Path, work_root: Path,
                proj_root: Path, mode: str = "full",
                cue_filter: str | None = None, note: str | None = None,
                inject_info: dict | None = None) -> str:
    """
    mode="full"       : 신규 화 — 분석→큐시트(앵커)→프롬프트(3변형)→QA, 4파일 생성.
    mode="prompts"    : 기존 화 — 02_큐시트 그대로 두고 03_프롬프트만 3변형 재생성.
    mode="single_cue" : cue_filter로 지정한 큐 하나만 프롬프트 재생성. note(감독 코멘트) 주입.
    mode="add_cue"    : inject_info로 지정한 위치에 새 큐 생성. _block.md + _cue_row.md 출력.
    """
    script = ep_dir / "00_대본raw.txt"
    bible = ep_dir.parent / "_작품공통" / "00_음악바이블.md"   # 정규화-안전: 화 폴더의 부모
    skill = proj_root / ".claude" / "skills" / "suno-prompt-guide" / "SKILL.md"

    out_01 = ep_dir / "01_분석.md"
    out_02 = ep_dir / "02_큐시트.md"
    out_03 = ep_dir / "03_프롬프트.md"
    out_04 = ep_dir / "04_QA.md"

    def p(path: Path) -> str:
        return str(path).replace("\\", "/")

    header = f"""너는 숏폼드라마 「{project}」 **{n}화**의 음악감독 작업을 수행하는 실행자다.
대사 한 줄도 추측하지 말고, 아래 입력 파일을 **반드시 먼저 읽고** 근거 위에서만 작업한다.

## 입력(읽기)
1. 대본 원문:    {p(script)}
2. 음악 바이블:  {p(bible)}   ← 베이스톤·라이트모티프·악기 팔레트·금기. 최우선 준수.
3. SUNO 가이드:  {p(skill)}   ← 프롬프트 표준(A안: Write 탭 구조태그 + Style 텍스트).
"""

    if mode == "add_cue":
        inj = inject_info or {}
        new_cue_id = inj.get("cue_id", f"EP{n}_Q?")
        note_block = f"\n\n**감독 코멘트(반드시 반영):** {note}" if note else ""
        return header + f"""4. 기존 큐시트: {p(out_02)}   ← 기존 큐 컨텍스트 참고용. **수정 금지.**
5. 기존 프롬프트: {p(out_03)}   ← 인접 큐 사운드 참고용. **수정 금지.**

## 신규 큐 위치 정보
- 새 큐 ID: **{new_cue_id}** (이 번호로 고정 — 변경 금지)
- 앞 큐: {inj.get('prev_cue_id', '없음')}
- 뒤 큐: {inj.get('next_cue_id', '없음')}

### 앞 큐 큐시트 행
{inj.get('prev_row', '(없음)')}

### 뒤 큐 큐시트 행
{inj.get('next_row', '(없음)')}

### 새 큐가 커버할 대본 발췌
```
{inj.get('script_excerpt', '(없음)')}
```

## 작업 — {new_cue_id} 신규 큐 생성{note_block}
**02_큐시트.md·03_프롬프트.md는 절대 수정하지 말 것.**
위 대본 발췌와 인접 큐 컨텍스트를 바탕으로 새 큐를 설계하고 두 파일을 저장한다.

### 파일 1: `_block.md` (03_프롬프트.md 삽입용 — Write 도구)
{_variant_format(n, cue_id=new_cue_id)}

### 파일 2: `_cue_row.md` (02_큐시트.md 삽입용 — Write 도구)
아래 구분자 헤딩을 정확히 지킨다(서버가 파싱):

## MAIN_ROW
| {new_cue_id} | #<씬번호> | IN: "<인-아웃 설명>" | <유형> | <기능> | <장르> | <무드> | <BPM> | <핵심 악기> | <에너지 곡선> | <라이트모티프> | <메모> |

## CONCEPT
**{new_cue_id}** — <2~3줄 컨셉 설명>

## ANCHOR_ROW
| {new_cue_id} | <IN앵커(대본 원문 5~20자)> | <OUT앵커 또는 —> |

## 종료
두 파일 저장 후 마지막 줄에 정확히 `SPOT_DONE EP{n} cues=1` 한 줄만 출력하고 끝낸다.
"""

    if mode == "single_cue":
        note_block = f"\n\n**감독 코멘트(반드시 반영):** {note}" if note else ""

        range_block = ""
        sel_path = ep_dir / "selection.json"
        if sel_path.exists() and cue_filter:
            try:
                import json as _json
                sel_data = _json.loads(sel_path.read_text(encoding="utf-8"))
                ro = (sel_data.get(cue_filter) or {}).get("range_override")
                if ro:
                    raw = script.read_text(encoding="utf-8")
                    excerpt = raw[int(ro["start"]):int(ro["end"])]
                    range_block = (
                        f"\n\n**드래그 구간 오버라이드(큐시트 앵커보다 이 발췌 우선):**"
                        f" 사용자가 이 큐의 커버 구간을 아래 대본 구간으로 조정했다."
                        f" 큐시트 IN/OUT 앵커 대신 이 발췌를 기준으로 프롬프트를 작성한다:\n```\n{excerpt}\n```"
                    )
            except Exception:
                pass

        return header + f"""4. 기존 큐시트: {p(out_02)}   ← CUE_ID·기능·씬을 따른다. 아래 오버라이드가 있으면 앵커보다 우선.
5. 기존 프롬프트: {p(out_03)}   ← 인접 큐 사운드 참고용. **이 파일에는 쓰지 않는다(읽기 전용).**

## 작업 — {cue_filter} 단일 큐 프롬프트 재생성{range_block}{note_block}
**01_분석.md·02_큐시트.md·03_프롬프트.md는 절대 수정하지 말 것.**
`{cue_filter}` 큐의 새 블록(변형 A·B·C 전체)을 아래 포맷으로 작성하고 **`_block.md`에만 Write 도구로 저장**한다.
변형 A 하나만 바꾸거나 부분 수정 금지 — 세 변형 모두 새로 작성한다.

{_variant_format(n, cue_id=cue_filter)}

`_block.md` 저장 후 04_QA.md에서 `{cue_filter}` 행만 갱신한다(다른 행 유지).

## 종료
저장 후 마지막 줄에 정확히 `SPOT_DONE EP{n} cues=1` 한 줄만 출력하고 끝낸다.
"""

    if mode == "prompts":
        return header + f"""4. 기존 큐시트: {p(out_02)}   ← CUE_ID·기능·앵커·씬을 **그대로** 따른다.

## 작업 — 03_프롬프트만 3변형 재생성 (UTF-8, Write 도구로 저장)
**01_분석.md·02_큐시트.md는 절대 수정하지 말 것.** 02_큐시트의 큐 목록(CUE_ID·기능)을 그대로 받아 각 큐의 프롬프트만 새로 만든다.

### {p(out_03)}
{_variant_format(n)}

### {p(out_04)} (QA 갱신)
가이드 §7로 03_프롬프트만 자가검수(글자수·instrumental 표기·가사 혼입·CUE_ID 정합·톤 일관성, 변형 3개 존재). 문제 시 03만 수정 후 재검.

## 종료
03_프롬프트.md(필요시 04_QA.md) 저장 후 마지막 줄에 정확히 `SPOT_DONE EP{n} cues=<큐개수>` 한 줄만 출력하고 끝낸다.
"""

    return header + f"""
## 수행 단계 (4파일 생성, 모두 UTF-8)
순서대로 사고하되, 각 단계 산출을 해당 절대경로에 **Write 도구로 저장**한다.

### 1) 분석 → {p(out_01)}
씬 단위 분해(장소/시간/등장인물/갈등/감정선/전환점/페이싱). 대본의 `#N` 씬 번호를 그대로 쓴다(회차 넘어 연속번호).

### 2) 큐시트 → {p(out_02)}
음악이 들어갈 자리를 큐로 정의(score/underscore/source/stinger/transition). 침묵이 더 강한 곳은 비운다.
- CUE_ID는 **반드시 `EP{n}_Q1`, `EP{n}_Q2` …** 형식(EP{n}_Q+숫자). 다른 형식 금지.
- 큐 테이블 컬럼: `| CUE_ID | Scene | 인-아웃 (대본 근거) | 유형 | 기능 | 장르 | 무드 | BPM | 핵심 악기 | 에너지 곡선 | 라이트모티프 | 메모 |`
- 표 아래 큐별 1~2줄 컨셉 설명.
- **그리고 반드시** 아래 '큐 앵커' 표를 별도로 포함한다(색 띠 매핑 엔진용):

```
## 큐 앵커 (기계 판독용 — 대본 원문 정확 복붙, 수정 금지)
| CUE_ID | IN앵커 | OUT앵커 |
|---|---|---|
```
앵커 규칙(엄수):
- IN앵커 = 그 큐가 **시작**되는 지점의 대본 원문 **부분문자열을 그대로 복사**(5~20자). 대사 위 시작이면 그 대사 일부, 지문 위 시작이면 그 지문 일부.
- OUT앵커 = 큐가 **끝**나는 지점 원문 부분문자열. **다음 큐가 곧바로 이어지면 `—`**(다음 IN앵커가 끝점). 큐 뒤 의도적 침묵이 있을 때만 OUT앵커로 닫는다.
- 의역·요약·재구성 금지. 대본에서 그대로 찾아지는 문자열(조사·문장부호 포함). 같은 문자열이 여러 번이면 유일하게 식별되는 더 긴 조각을 쓴다.
- 큐 등장 순서 = 대본 등장 순서(앵커가 문서상 단조 증가).

### 3) 프롬프트 → {p(out_03)}
{_variant_format(n)}

### 4) QA → {p(out_04)}
가이드 §7 체크리스트로 자가검수. 각 큐 PASS/수정. 글자수·instrumental 표기·가사 혼입·CUE_ID 정합·톤 일관성·변형 3개 존재 점검. 문제 발견 시 2)·3) 파일을 직접 수정 후 재검.

## 종료
4개 파일을 모두 저장했으면 마지막 줄에 정확히 `SPOT_DONE EP{n} cues=<큐개수>` 한 줄만 출력하고 끝낸다.
"""
