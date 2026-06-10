# 숏폼드라마 SUNO 음악 프롬프트 워크플로우

대본 → 음악 스팟팅 → SUNO 인스트루멘탈 프롬프트 추출 파이프라인.
모든 음악은 **가사 없는 인스트루멘탈**(스코어/언더스코어/소스뮤직) 기준.
음악 제작 툴: **SUNO v5.5** (Style ~1000자, 인라인 네거티브 `no vocals`, 별도 Exclude 필드 없음).

## 에이전트 (단계별)
| 순서 | 에이전트 | 모델 | 역할 | 산출물 |
|---|---|---|---|---|
| 0 | `music-project-planner` | **Opus** | 총괄 기획·방향 제시·디벨롭 (필수) | `work/00_creative_brief.md` |
| 1 | `script-analyzer` | Sonnet | 대본 → 장면·감정선 분해 | `work/01_script_analysis.md` |
| 2 | `music-spotting-director` | Sonnet | 스팟팅 + 음악 컨셉 = 큐시트 | `work/02_cue_sheet.md` |
| 3 | `suno-prompt-writer` | Sonnet | 큐 → SUNO 스타일+메타태그 | `work/03_suno_prompts.md` |
| 4 | `suno-prompt-qa` | **Haiku** | 규칙 검수·취합 (단순 반복) | `work/04_qa_report.md`, `work/05_final_deliverable.md` |

## 스킬
- `suno-prompt-guide` — SUNO 인스트루멘탈 프롬프트 문법/메타태그/제약 레퍼런스. 작성·검수 에이전트가 항상 참고.

## 쓰는 법
1. 대본 파일을 `work/`에 넣는다.
2. **플래너부터** 시작 — 작품 톤/팔레트/방향을 함께 정한다.
3. 메인 세션(나)에게 "1단계 돌려줘"처럼 지시하면 순서대로 에이전트를 호출한다.
   - 각 에이전트는 직접 서로를 호출하지 않는다. 메인 세션이 오케스트레이션한다.
4. 단계마다 산출물을 플래너로 검토·디벨롭한 뒤 다음 단계로.
5. 최종 `work/05_final_deliverable.md`의 Style/Meta를 SUNO에 복붙.

## 모델 정책
- 머리 쓰는 단계(기획)는 Opus. 판단이 필요한 중간 단계는 Sonnet. 단순 검수/정리는 Haiku로 토큰 절약.
