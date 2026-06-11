# -*- coding: utf-8 -*-
"""
Cue Board 로컬 서버 — 표준 라이브러리만(의존성 0).

실행:  python server.py            (기본 127.0.0.1:8765, work/ 자동 탐지)
        python server.py 8800       (포트 지정)
브라우저: http://127.0.0.1:8765/

API:
  GET  /api/projects            → 작품 목록
  GET  /api/episodes?p=<작품>   → 화 목록 + 진행상태
  GET  /api/episode?p=<작품>&n=<번호>
                                → 대본 원문 + 큐 카드(색 띠 char offset 포함)
  POST /api/spot                → 파이프라인 실행 (mode: full|prompts|single_cue,
                                   cue_filter: CUE_ID, note: 감독코멘트)
  POST /api/select              → selection.json selected/kept 저장
  POST /api/cue-meta            → selection.json range_override/comment 저장
정적: /  → static/index.html, 그 외 → static/<path>
"""
import json
import sys
import shutil
import threading
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cueparse
from spotjob import spot_prompt

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
WORK_ROOT = HERE.parent                 # work/
PROJ_ROOT = WORK_ROOT.parent            # suno prompt/ (.claude·스킬·에이전트 위치)
DEFAULT_PROJECT = "며느리가친정을숨김"

CLAUDE_BIN = shutil.which("claude")     # 헤들리스 두뇌(구독 인증 재사용·무과금 API키 아님)
PERMISSION_MODE = "acceptEdits"         # 편집만 자동수락(Bash 등 위험 도구는 막힘)
SPOT_MODEL = "sonnet"                   # full·prompts 모드
SPOT_MODEL_FAST = "haiku"              # single_cue 전용(속도 우선)

# ---- 자동 스팟팅 잡 레지스트리(인메모리) ----
JOBS = {}                               # job_id -> {project,n,status,started,ended,returncode,log}
JOBS_LOCK = threading.Lock()

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


# ---------------------------------------------------------------- 자동 스팟팅 잡
def _running_for(project, n, mode=None, cue_filter=None):
    """해당 화에 대해 이미 진행 중인 잡이 있으면 job_id 반환.
    single_cue는 같은 cue_filter에 대해서만 중복 차단(full/prompts 실행 중에도 시작 가능)."""
    with JOBS_LOCK:
        for jid, j in JOBS.items():
            if j["project"] != project or j["n"] != n:
                continue
            if j["status"] not in ("queued", "running"):
                continue
            if mode == "single_cue":
                if j["mode"] == "single_cue" and j["cue_filter"] == cue_filter:
                    return jid
            else:
                return jid
    return None


def start_spot_job(project, n, mode="full", cue_filter=None, note=None):
    """잡 등록 + 워커 스레드 기동. (job_id, error) 반환."""
    if CLAUDE_BIN is None:
        return None, "claude 실행파일을 찾을 수 없음(PATH 확인)"
    if mode not in ("full", "prompts", "single_cue"):
        return None, f"알 수 없는 mode: {mode}"
    ep = cueparse._ep_dir(WORK_ROOT, project, n)
    if ep is None:
        return None, f"{project} {n}화 폴더 없음"
    if not (ep / "00_대본raw.txt").exists():
        return None, f"{n}화 대본(00_대본raw.txt) 없음 — 스팟팅 불가"
    if mode in ("prompts", "single_cue") and not (ep / "02_큐시트.md").exists():
        return None, f"{n}화 큐시트(02_큐시트.md) 없음 — full 모드로 실행하세요"
    if mode == "single_cue" and not cue_filter:
        return None, "single_cue 모드는 cue_filter(CUE_ID) 필요"
    dup = _running_for(project, n, mode=mode, cue_filter=cue_filter)
    if dup:
        return dup, None                      # 중복 시작 방지: 기존 잡 반환

    jid = uuid.uuid4().hex[:8]
    log_path = ep / "_spot_log.txt"
    with JOBS_LOCK:
        JOBS[jid] = {
            "id": jid, "project": project, "n": n, "mode": mode,
            "cue_filter": cue_filter, "status": "queued",
            "started": time.time(), "ended": None, "returncode": None,
            "log": str(log_path), "tail": "",
        }
    t = threading.Thread(
        target=_run_spot,
        args=(jid, project, n, ep, log_path, mode, cue_filter, note),
        daemon=True,
    )
    t.start()
    return jid, None


def _run_spot(jid, project, n, ep, log_path, mode="full", cue_filter=None, note=None):
    prompt = spot_prompt(project, n, ep, WORK_ROOT, PROJ_ROOT,
                         mode=mode, cue_filter=cue_filter, note=note)
    model = SPOT_MODEL_FAST if mode == "single_cue" else SPOT_MODEL
    cmd = [
        CLAUDE_BIN, "-p",
        "--permission-mode", PERMISSION_MODE,
        "--model", model,
        "--add-dir", str(PROJ_ROOT),       # cwd(화 폴더) 밖의 바이블·스킬 읽기 허용
    ]
    with JOBS_LOCK:
        JOBS[jid]["status"] = "running"
    try:
        with open(log_path, "w", encoding="utf-8") as lf:
            proc = subprocess.Popen(
                cmd, cwd=str(ep),
                stdin=subprocess.PIPE, stdout=lf, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8",
            )
            proc.communicate(prompt)
            rc = proc.returncode
        tail = ""
        try:
            tail = "\n".join(log_path.read_text(encoding="utf-8").splitlines()[-12:])
        except Exception:
            pass
        # done 판정: prompts 모드는 03만, full은 02+03 존재 확인
        ok = (rc == 0) and (ep / "03_프롬프트.md").exists()
        if mode == "full":
            ok = ok and (ep / "02_큐시트.md").exists()
        with JOBS_LOCK:
            JOBS[jid].update(
                status="done" if ok else "error",
                ended=time.time(), returncode=rc, tail=tail,
            )
    except Exception as e:
        with JOBS_LOCK:
            JOBS[jid].update(status="error", ended=time.time(), tail=f"{type(e).__name__}: {e}")


def job_view(jid):
    with JOBS_LOCK:
        j = JOBS.get(jid)
        if not j:
            return None
        out = dict(j)
    # 진행 중이면 로그 꼬리 갱신
    if out["status"] in ("queued", "running"):
        try:
            out["tail"] = "\n".join(Path(out["log"]).read_text(encoding="utf-8").splitlines()[-12:])
        except Exception:
            pass
    out["elapsed"] = round((out["ended"] or time.time()) - out["started"], 1)
    return out


class Handler(BaseHTTPRequestHandler):
    # ---- 응답 헬퍼 ----
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _err(self, msg, code=400):
        self._json({"error": msg}, code)

    def _file(self, path: Path):
        if not path.is_file():
            self._err("not found", 404)
            return
        body = path.read_bytes()
        ct = CONTENT_TYPES.get(path.suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        # 정적 자원(JS/CSS/HTML) 캐시 무효화 — 코드 갱신 시 브라우저가 옛 파일 쓰는 문제 방지
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    # ---- 라우팅 ----
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        path = u.path

        if path.startswith("/api/"):
            try:
                self._api(path, q)
            except Exception as e:
                self._err(f"{type(e).__name__}: {e}", 500)
            return

        # 정적 파일
        if path == "/" or path == "":
            self._file(STATIC / "index.html")
            return
        rel = path.lstrip("/")
        target = (STATIC / rel).resolve()
        if STATIC.resolve() not in target.parents and target != STATIC.resolve():
            self._err("forbidden", 403)       # 디렉터리 탈출 방지
            return
        self._file(target)

    def _api(self, path, q):
        project = (q.get("p") or [DEFAULT_PROJECT])[0]

        if path == "/api/projects":
            self._json({"projects": cueparse.list_projects(WORK_ROOT)})
            return

        if path == "/api/episodes":
            self._json({
                "project": project,
                "episodes": cueparse.list_episodes(WORK_ROOT, project),
            })
            return

        if path == "/api/episode":
            n = q.get("n", [None])[0]
            if n is None or not n.isdigit():
                self._err("n(화 번호) 필요")
                return
            data = cueparse.build_episode(WORK_ROOT, project, int(n))
            if data is None:
                self._err(f"{project} {n}화 없음", 404)
                return
            self._json(data)
            return

        if path == "/api/job":
            jid = q.get("id", [None])[0]
            view = job_view(jid) if jid else None
            if view is None:
                self._err("job 없음", 404)
                return
            self._json(view)
            return

        self._err("unknown api", 404)

    # ---- POST: 자동 스팟팅 시작 / 선택·킵·코멘트 저장 ----
    def do_POST(self):
        u = urlparse(self.path)
        if u.path not in ("/api/spot", "/api/select", "/api/cue-meta"):
            self._err("unknown api", 404)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b"{}"
            payload = json.loads(body.decode("utf-8") or "{}")
        except Exception as e:
            self._err(f"bad request: {e}")
            return

        project = payload.get("project") or DEFAULT_PROJECT
        n = payload.get("n")
        if not isinstance(n, int):
            try:
                n = int(n)
            except Exception:
                self._err("n(화 번호) 필요")
                return

        if u.path == "/api/spot":
            mode = payload.get("mode") or "full"
            cue_filter = payload.get("cue_filter")   # single_cue 모드용
            note = payload.get("note")               # 감독 코멘트
            jid, err = start_spot_job(project, n, mode=mode,
                                      cue_filter=cue_filter, note=note)
            if err:
                self._err(err)
                return
            self._json({"job_id": jid, "project": project, "n": n,
                        "mode": mode, "cue_filter": cue_filter})
            return

        # /api/select — selection.json selected/kept 머지 저장
        if u.path == "/api/select":
            cid = payload.get("cue")
            if not cid:
                self._err("cue(CUE_ID) 필요")
                return
            ep = cueparse._ep_dir(WORK_ROOT, project, n)
            if ep is None:
                self._err(f"{project} {n}화 폴더 없음", 404)
                return
            SENT = "__keep__"
            selected = payload.get("selected", SENT)
            kept = payload.get("kept", SENT)
            data = cueparse.save_selection(ep, cid, selected=selected, kept=kept)
            self._json({"ok": True, "cue": cid, "selection": data.get(cid, {})})
            return

        # /api/cue-meta — range_override / comment 저장
        cid = payload.get("cue")
        if not cid:
            self._err("cue(CUE_ID) 필요")
            return
        ep = cueparse._ep_dir(WORK_ROOT, project, n)
        if ep is None:
            self._err(f"{project} {n}화 폴더 없음", 404)
            return
        SENT = "__keep__"
        range_override = payload.get("range_override", SENT)
        comment = payload.get("comment", SENT)
        data = cueparse.save_selection(ep, cid,
                                       range_override=range_override,
                                       comment=comment)
        self._json({"ok": True, "cue": cid, "selection": data.get(cid, {})})

    def log_message(self, fmt, *args):       # 조용한 로그(요청 1줄)
        sys.stderr.write(f"  {self.address_string()} {fmt % args}\n")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Cue Board  →  http://127.0.0.1:{port}/")
    print(f"  work root: {WORK_ROOT}")
    print(f"  작품 기본값: {DEFAULT_PROJECT}   (Ctrl+C 종료)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n종료.")
        httpd.shutdown()


if __name__ == "__main__":
    main()
