---
name: suno-prompt-guide
description: SUNO v5.5 인스트루멘탈 음악 생성용 프롬프트 작성 레퍼런스. 가사 없는 스코어/언더스코어/소스뮤직 기준. v5.5 Style of Music 필드(~1000자), 구조·연출 메타태그([Intro]/[Build]/[Climax]/[Outro] 등), 인라인 네거티브 프롬프팅(no vocals), 글자수 제약, 장르/무드/악기/BPM/키 표기법을 다룰 때 사용. SUNO 프롬프트를 쓰거나 검수할 때 항상 참고.
---

# SUNO v5.5 인스트루멘탈 프롬프트 작성 가이드

숏폼드라마 후반 작업에서 **SUNO v5.5**로 스코어/언더스코어/소스뮤직(전부 **가사 없는 인스트루멘탈**)을 뽑기 위한 프롬프트 표준. 모든 프롬프트 작성·검수 에이전트가 이 문서를 기준으로 한다.

> 기준 버전: **Suno v5.5 / Advanced 모드** (2026-03-26 릴리스). 인스트루멘탈 작업이므로 보이스 기능은 사용하지 않는다.

## 1. SUNO v5.5 Advanced 입력 구조 (인스트루멘탈) — 실제 UI 기준

상단 모드 토글은 **Advanced** 선택. Lyrics 영역에 탭 3개가 있다:

- **`Write` ← 우리가 쓰는 탭.** 가사/구조 `[tag]`를 직접 넣는 칸. **우리는 가사 단어는 한 글자도 안 넣고 `[Intro]`/`[Build]`/`[Climax]`/`[Outro]` 같은 구조 태그만** 넣어 곡 진행을 통제한다(§3).
- `Prompt`: 주제를 주면 Suno가 **가사를 생성(=보컬)**. → 인스트루멘탈 작업과 정반대이므로 **사용 금지.**
- `Instrumental`: 무보컬 100% 보장이나 **입력칸이 사라져 구조 태그를 못 넣는다.** → 구조 통제를 위해 우리는 Write 탭을 쓴다(트레이드오프, §4).

입력 필드 정리:
- **Lyrics(Write 탭)** — **구조 태그만**(가사 단어 0). 흐름 지시가 불필요한 단발 스팅어는 비우거나 `[Intro]/[Outro]`만.
- **Styles (스타일)** — 음악 사운드 결정 핵심 필드. 장르·BPM·키·악기·무드 + 끝에 인라인 네거티브 `instrumental, no vocals`. ~1000자(밀도 ≤950 권장).
- **Title (제목)** — 관리용. 큐 ID와 연결.
- **more options (Exclude Styles / Weirdness / Style Influence)** — **건드리지 않는다(기본값 유지).** 산출물에도 적지 않는다. (사용자 확정)

> 역할 분담: **구조=Write 탭 태그**, **사운드=Styles 텍스트.** 둘을 분리해 Styles가 산문 구조 묘사로 비대해지지 않게 한다. (단 태그는 "힌트"이므로 핵심 흐름은 Styles에도 형용사로 가볍게 중복 강조.)

## 2. 스타일 필드 작성 규칙 (v5.5)

권장 구성 순서:
1. **BPM + 키 + 장르 디스크립터 1개** (예: `70 BPM, A minor, cinematic underscore`)
2. **구체 악기 2개 이상 + 형용사** (예: `pulsing low synth bass, staccato muted strings`)
3. **무드/감정 + 프로덕션 질감** (예: `tense, claustrophobic, wide stereo, film score`)
4. **인라인 네거티브 2~3개** — 끝에 `no` 접두로 (예: `no vocals, no lyrics, no choir`)

- v5.5는 **별도 Exclude 필드 없이** 스타일 안에서 `no X` 인라인 네거티브로 배제한다.
- 콤마 키워드 나열. 모순 키워드 금지(`minimal` + `wall of sound` 동시 지양).
- 아티스트 실명 금지 → 질감 묘사로 우회(예: "Hans Zimmer" → `epic cinematic brass, deep ostinato strings`).
- ~1000자까지 허용되지만 숏폼 큐는 짧고 명확한 게 일관성에 유리. 무리해서 채우지 말 것.

### 스타일 예시 (v5.5)
```
70 BPM, A minor, cinematic underscore, tense and suspenseful, pulsing low synth bass, staccato muted strings, distant prepared piano, sparse sub percussion, building dread, wide cinematic stereo, film score, instrumental only, no vocals, no lyrics
```

## 3. 구조·연출 메타태그 (Write 탭, 가사 단어 없이 태그만)

Write 탭에 **가사 단어는 넣지 않고 구조 태그만** 넣어 곡 진행을 지시한다. 태그 안/옆에 간단한 사운드 지시를 붙여도 된다.

**구조 태그**: `[Intro]` `[Build]` `[Climax]` `[Breakdown]` `[Interlude]` `[Outro]` `[Solo]`(예: `[Piano Solo]`)
**연출 지시(태그 옆 대괄호)**: `[soft]` `[building intensity]` `[fade out]` `[silence]` `[strings swell]` `[percussion enters]` `[full orchestra hit]` `[cut to silence]`

> 태그는 "강한 힌트"이지 보장이 아니다. 핵심 흐름(시작·절정·끝의 다이내믹)은 Styles 형용사로도 가볍게 중복 강조한다. 단발 스팅어처럼 진행이 거의 없는 큐는 `[Intro] [full orchestra hit] [cut to silence]` 정도로 짧게.

### Write 탭 예시 (가사 없음, 구조 태그만)
```
[Intro] soft prepared piano, from silence, sparse
[Build] thin strings swell, tension rising
[Climax] low strings peak
[Outro] cut to silence
```

## 4. 인스트루멘탈 보장 (v5.5 Advanced, Write 탭)

- **Write 탭에 가사 단어를 한 글자도 넣지 않는다**(구조 태그만). + **Styles 끝에 `instrumental, no vocals`** 명시 → 이 둘로 보컬을 억제한다.
- 스코어/언더스코어처럼 보컬 유도 요소가 없는 프롬프트에선 사실상 인스트루멘탈로 나오지만, **무보컬 100% 기계적 보장은 Instrumental 탭뿐**이다(그 경우 구조 태그 불가). 본 워크플로우는 구조 통제를 우선해 Write 탭을 택했다.
- 보이스 클론/보컬 톤 지정·Voice 기능은 사용하지 않는다.

## 5. 숏폼드라마 큐 유형별 템플릿 (전부 instrumental, v5.5)

- **긴장/서스펜스**: `65 BPM, D minor, tense cinematic underscore, low drone, ticking percussion, dissonant muted strings, claustrophobic, instrumental only, no vocals, no lyrics`
- **감정 절정/눈물**: `60 BPM, C minor, emotional piano underscore, warm legato strings, intimate, rubato, swelling dynamics, instrumental only, no vocals, no lyrics`
- **로맨스**: `80 BPM, G major, warm romantic score, soft felt piano, light pizzicato strings, gentle, hopeful, instrumental only, no vocals, no lyrics`
- **액션/추격**: `150 BPM, E minor, driving action score, aggressive taiko percussion, distorted bass, brass stabs, urgent relentless, instrumental only, no vocals, no lyrics`
- **코믹/가벼움**: `110 BPM, C major, quirky playful score, pizzicato strings, light woodwinds, bouncy, comedic, instrumental only, no vocals, no lyrics`
- **반전/충격(stinger)**: `sudden orchestral hit, sharp brass stab, sub boom, short dramatic accent, cinematic, instrumental only, no vocals, no lyrics`
- **회상/몽환**: `60 BPM, dreamy ambient underscore, airy synth pads, soft bells, reverb-drenched, slow nostalgic, instrumental only, no vocals, no lyrics`

## 6. 출력 포맷 (큐 1건당)

```
### CUE_ID: (예: EP30_Q1)
- 기능 / 길이: (긴장 빌드 / 감정 절정 / 스팅어 등) / (대략 sec)
- Lyrics 탭: Write  ← 구조 태그만(가사 단어 없음)
- Write(구조 태그):
  [Intro] ...
  [Build] ...
  [Climax] ...
  [Outro] ...        ← 진행 없는 단발 큐는 짧게 또는 비움
- Title: (관리용)
- Styles: <~1000자 이내. 장르·BPM·키·악기·무드 + 끝에 instrumental, no vocals>
- 메모: (연출 의도 / SFX 충돌·덜킹 / 대안 버전)
```

> more options(Exclude Styles / Weirdness / Style Influence)는 적지 않는다 — 기본값 유지.

### 6-1. 큐당 3변형(A/B/C) 옵션 — Cue Board 자동 스팟팅
Cue Board v0.3 자동 스팟팅은 큐당 **음악적으로 구별되는 3변형**을 뽑아 사용자가 카드에서 비교·선택한다. 이때 큐 헤딩 아래에 변형 소헤딩을 둔다(파서가 `#### 변형 X`로 분할):
```
### EP{n}_Q1
- 기능 / 길이: ... / 약 N초
- Lyrics 탭: Write

#### 변형 A — <한 줄 컨셉>
- Write(구조 태그): ...
- Title: EP{n}_Q1_A_<키워드>
- Styles: <... instrumental, no vocals>
- 메모: ...
#### 변형 B — ...
#### 변형 C — ...
```
- A=바이블 정공법(메인 팔레트 정합) / B=같은 기능·다른 색(대안 악기·서브장르) / C=과감·실험적(템포·장르·구조 변주). 셋 다 인스트루멘탈·톤 유지·기능 충족.
- 단순 표현 바꾸기 금지 — 서로 다른 해석이어야 한다. 각 변형 Title에 `_A`/`_B`/`_C`.
- 단발(1건) 산출이 필요한 일반 작업은 위 6번 단일 포맷을 그대로 쓴다.

## 7. 검수 체크리스트 (QA용, v5.5)

- [ ] Styles 글자수 ≤1000자(밀도 권장 ≤950)
- [ ] `Lyrics 탭: Write` 명시 + **Write 블록에 구조 태그만(가사 단어 0)**, Styles 끝에 `instrumental, no vocals` 유지
- [ ] Write 블록에 실제 가사(부를 단어)가 섞이지 않았는지 — `[태그]`와 사운드 지시만 허용
- [ ] BPM·키·장르·악기 2개+ 포함(Styles)
- [ ] 모순 키워드 없음 / 언어 혼입·오타 없음(키릴문자 등)
- [ ] 아티스트 실명 미사용(질감 묘사로 대체)
- [ ] CUE_ID가 큐시트와 일치
- [ ] 같은 작품 내 톤/악기 팔레트 일관성 유지
- [ ] more options(Exclude Styles / Weirdness / Style Influence) 미기재 — 기본값 유지
