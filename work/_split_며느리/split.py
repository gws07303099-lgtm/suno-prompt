# -*- coding: utf-8 -*-
"""
「며느리가 친정을 숨김」 대본 분할 스크립트.
clean docx (OCR 불필요) → word/document.xml 파싱 → <N화> 헤딩으로 50화 분할.
- 각 화 본문(#씬 블록 포함)을 work/며느리가친정을숨김/NN화/00_대본raw.txt 로 저장
- 헤딩 앞 도입부(로그라인/시놉/캐릭터) → _작품공통/00_기획안raw.txt
- 각 NN화/브금/ 빈 폴더 생성
"""
import zipfile, re, os, sys, html

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # work/
DOCX = os.path.join(BASE, "며느리가 친정을 숨김_260223.docx")
OUT = os.path.join(BASE, "며느리가친정을숨김")


def extract_lines(path):
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8", "ignore")
    paras = re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)
    lines = []
    for pp in paras:
        t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", pp, re.S))
        t = re.sub(r"<[^>]+>", "", t)
        t = html.unescape(t).strip()
        lines.append(t)  # keep empties to preserve paragraph spacing
    return lines


def is_episode_head(line):
    # <1화>, < 37 화 > 등
    m = re.match(r"^<\s*(\d+)\s*화\s*>$", line.strip())
    return int(m.group(1)) if m else None


def main():
    lines = extract_lines(DOCX)
    # 회차 헤딩 인덱스 수집
    heads = []  # (idx, ep_num)
    for i, l in enumerate(lines):
        ep = is_episode_head(l)
        if ep is not None:
            heads.append((i, ep))

    print(f"감지된 회차 헤딩 수: {len(heads)}")
    eps = [e for _, e in heads]
    print(f"회차 범위: {min(eps)}~{max(eps)}, 연속성: {eps == list(range(1, len(eps)+1))}")

    os.makedirs(os.path.join(OUT, "_작품공통"), exist_ok=True)

    # 도입부 = 첫 헤딩 전
    intro = "\n".join(lines[: heads[0][0]]).strip() + "\n"
    with open(os.path.join(OUT, "_작품공통", "00_기획안raw.txt"), "w", encoding="utf-8") as f:
        f.write(intro)
    print(f"_작품공통/00_기획안raw.txt 저장 ({len(intro)}자)")

    # 각 화 분할
    for k, (idx, ep) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        body = "\n".join(lines[idx:end]).strip() + "\n"
        epdir = os.path.join(OUT, f"{ep:02d}화")
        os.makedirs(os.path.join(epdir, "브금"), exist_ok=True)
        with open(os.path.join(epdir, "00_대본raw.txt"), "w", encoding="utf-8") as f:
            f.write(body)
    print(f"{len(heads)}개 화 폴더 + 00_대본raw.txt + 브금/ 생성 완료 → {OUT}")


if __name__ == "__main__":
    main()
