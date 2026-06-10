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
from pathlib import Path


def spot_prompt(project: str, n: int, ep_dir: Path, work_root: Path, proj_root: Path) -> str:
    script = ep_dir / "00_대본raw.txt"
    bible = ep_dir.parent / "_작품공통" / "00_음악바이블.md"   # 정규화-안전: 화 폴더의 부모
    skill = proj_root / ".claude" / "skills" / "suno-prompt-guide" / "SKILL.md"

    out_01 = ep_dir / "01_분석.md"
    out_02 = ep_dir / "02_큐시트.md"
    out_03 = ep_dir / "03_프롬프트.md"
    out_04 = ep_dir / "04_QA.md"

    def p(path: Path) -> str:
        return str(path).replace("\\", "/")

    return f"""너는 숏폼드라마 「{project}」 **{n}화**의 음악감독 파이프라인을 한 번에 수행하는 실행자다.
대사 한 줄도 추측하지 말고, 아래 입력 파일을 **반드시 먼저 읽고** 근거 위에서만 작업한다.

## 입력(읽기)
1. 대본 원문:    {p(script)}
2. 음악 바이블:  {p(bible)}   ← 베이스톤·라이트모티프·악기 팔레트·금기. 최우선 준수.
3. SUNO 가이드:  {p(skill)}   ← 프롬프트 표준(A안: Write 탭 구조태그 + Style 텍스트).

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
큐마다 SUNO v5.5 Advanced **A안** 1건. 가이드 §6 포맷 그대로. 전 큐 인스트루멘탈.
```
### EP{n}_Q1
- 기능 / 길이: ... / 약 N초
- Lyrics 탭: Write
- Write(구조 태그):
  [Intro] ...
  [Build] ...
  [Climax] ...
  [Outro] ...
- Title: ...
- Styles: <BPM·키·장르·악기2개+·무드 + 끝에 instrumental, no vocals>
- 메모: ...
```
- Write 블록엔 **가사 단어 0**, 구조/연출 태그만. Styles 끝에 `instrumental, no vocals` 필수.
- 아티스트 실명 금지(질감 묘사로 대체). 모순 키워드·언어 혼입·오타(키릴문자 등) 금지.
- CUE_ID는 큐시트와 1:1 일치.

### 4) QA → {p(out_04)}
가이드 §7 체크리스트로 자가검수. 각 큐 PASS/수정. 글자수·instrumental 표기·가사 혼입·CUE_ID 정합·톤 일관성 점검. 문제 발견 시 2)·3) 파일을 직접 수정 후 재검.

## 종료
4개 파일을 모두 저장했으면 마지막 줄에 정확히 `SPOT_DONE EP{n} cues=<큐개수>` 한 줄만 출력하고 끝낸다.
"""
