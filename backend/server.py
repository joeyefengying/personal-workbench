#!/usr/bin/env python3
"""Personal Workbench backend - 个人项目工作台后端
聚合个人自研项目的清单 / git 状态 / 一键启动停止
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "apps.json"
FRONTEND_DIST = ROOT.parent / "frontend" / "dist"
PYTHON = shutil.which("python3") or sys.executable

app = FastAPI(title="Personal Workbench")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 记录本会话启动的子进程: proj_id -> Popen
_procs = {}
_lock = threading.Lock()

def _resolve(p: str) -> Path:
    return Path(p).expanduser()

def _is_active(port: int) -> bool:
    if not port:
        return False
    try:
        s = subprocess.run(
            ["lsof", "-iTCP:%d" % port, "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, timeout=5)
        return bool(s.stdout.strip())
    except Exception:
        return False

def _git_info(path: Path) -> dict:
    git_dir = path / ".git"
    if not git_dir.exists():
        return {"isGit": False, "branch": "", "dirty": 0, "remote": "", "lastCommit": ""}
    try:
        def run(*a):
            r = subprocess.run(["git", "-C", str(path), *a],
                               capture_output=True, text=True, timeout=5)
            return r.stdout.strip()
        branch = run("branch", "--show-current")
        dirty = int(run("status", "--porcelain") and len(run("status", "--porcelain").splitlines()) or 0)
        remote = run("remote", "get-url", "origin").replace("https://github.com/", "").rstrip(".git")
        last = run("log", "-1", "--format=%h %s", "--date=short")
        return {"isGit": True, "branch": branch, "dirty": dirty,
                "remote": remote, "lastCommit": last}
    except Exception as e:
        return {"isGit": True, "error": str(e)}

def _expand_cmd(cmd: str, run_dir: Path, path: Path) -> str:
    return cmd.replace("{python}", PYTHON).replace("{path}", str(path))

def _build_project(proj: dict) -> dict:
    path = _resolve(proj.get("path", ""))
    run_dir = _resolve(proj.get("runDir", proj.get("path", "")))
    p = {
        "id": proj["id"],
        "name": proj["name"],
        "path": str(path),
        "desc": proj.get("desc", ""),
        "type": proj.get("type", "web"),
        "git": _git_info(path),
    }
    port = proj.get("port", 0)
    cmd = proj.get("cmd", "")
    if cmd:
        p["cmd"] = cmd
        p["runDir"] = str(run_dir)
        p["port"] = port
        p["url"] = proj.get("url", "http://127.0.0.1:%d" % port) if port else ""
        p["active"] = _is_active(port) if port else False
    if "children" in proj:
        p["children"] = [_build_project(c) for c in proj["children"]]
    return p

def _load_config() -> dict:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    cats = []
    for cat in cfg["categories"]:
        cats.append({
            "key": cat["key"], "name": cat["name"], "icon": cat.get("icon", "tool"),
            "projects": [_build_project(pr) for pr in cat["projects"]],
        })
    return {"categories": cats}

# ---------------------------------------------------------------
# Skill 能力墙 — 扫描本机两套 skill 库 (Hermes + Claude skills)
# ---------------------------------------------------------------
SKILL_ROOTS = {
    "hermes": [Path.home() / ".hermes" / "skills"],
    "claude": [Path.home() / "Downloads" / "笔记" / "笔记" / ".claude" / "skills"],
}

def _parse_skill_meta(skill_dir: Path) -> dict:
    """从 SKILL.md frontmatter 提取 name/description/version/category"""
    md = skill_dir / "SKILL.md"
    if not md.exists():
        return None
    try:
        text = md.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    meta = {"name": skill_dir.name, "description": "", "version": ""}
    if m:
        front = m.group(1)
        def grab(key):
            # 管道块:  description: |\n   行
            blk = re.search(rf"^{key}:\s*\|[ \t]*\n((?:[ \t]+.*\n?)+)", front, re.M)
            if blk:
                return " ".join(l.strip() for l in blk.group(1).splitlines() if l.strip())
            # 单行: description: value
            mm = re.search(rf"^{key}:\s*(.+)$", front, re.M)
            if mm:
                return mm.group(1).strip().strip("\"'")
            # 引号多行: description: ">... "
            mm = re.search(rf"^{key}:\s*(\"?[>|]?)\s*\n((?:[ \t]+\S.*\n?)+)", front, re.M)
            if mm:
                return " ".join(l.strip() for l in mm.group(2).splitlines() if l.strip())
            return ""
        meta["name"] = grab("name") or skill_dir.name
        meta["description"] = grab("description")
        meta["version"] = grab("version")
    return meta

def _scan_skills() -> list:
    out = []
    for source, roots in SKILL_ROOTS.items():
        for root in roots:
            if not root.exists():
                continue
            for skill_dir in sorted(root.iterdir()):
                if not skill_dir.is_dir() or skill_dir.name in (".archive", ".git", "node_modules"):
                    continue
                meta = _parse_skill_meta(skill_dir)
                if not meta:
                    continue
                out.append({
                    "name": meta["name"],
                    "slug": skill_dir.name,
                    "description": meta["description"][:300],
                    "version": meta["version"],
                    "source": source,
                    "path": str(skill_dir),
                })
    return out

@app.get("/api/skills")
def get_skills():
    return {"skills": _scan_skills()}


def _find_skill(slug: str) -> dict | None:
    for s in _scan_skills():
        if s["slug"] == slug:
            return s
    return None


# ---------------------------------------------------------------
# Skill 启动器 — 点卡片在原生终端/Terminal.app 打开 hermes chat --skills
# 多轮/记忆/流式/工具全由 Hermes 原生完成，工作台只负责"打开对话"。
# 优先用 open -a Terminal 触发 macOS 原生终端；失败则 osascript。
# ---------------------------------------------------------------
def _shell_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


@app.post("/api/skill/open")
def open_skill(payload: dict):
    """打开一个 skill 的交互式对话。payload: {slug, query?, project_dir?}
    - 在 macOS Terminal.app 新窗口跑 hermes chat --skills <skill> [可带初句]
    """
    slug = (payload or {}).get("slug", "")
    if not slug:
        return {"ok": False, "error": "缺少 slug"}
    skill = _find_skill(slug)
    if not skill:
        return {"ok": False, "error": "未找到 skill %s" % slug}

    # hermes chat 交互模式（带 skill 加载）
    cmd = "hermes chat --skills %s" % _shell_escape(skill["slug"])
    initial = (payload or {}).get("query", "").strip()
    if initial:
        cmd += " '%s'" % _shell_escape(initial)

    # 尝试用 Terminal.app 打开（AppleScript 弹新窗口）
    apple_script = (
        'tell application "Terminal"\n'
        '  activate\n'
        '  do script "clear; %s; echo; echo \\"[done: EXIT $?]\\", read -p \\"回车关闭窗口...\\""\n'
        'end tell' % cmd.replace('\\', '\\\\').replace('"', '\\"'))
    try:
        p = subprocess.run(
            ["osascript", "-e", apple_script],
            capture_output=True, text=True, timeout=15)
        if p.returncode == 0:
            return {"ok": True, "msg": "已在 Terminal 打开 %s 对话" % skill["name"],
                    "skill": skill["slug"], "source": skill["source"]}
        return {"ok": False, "error": "osascript 打开失败: %s" % (p.stderr.strip() or "未知"), "skill": slug}
    except Exception as e:
        return {"ok": False, "error": str(e), "skill": slug}


@app.get("/api/config")
def get_config():
    return _load_config()

@app.post("/api/start/{proj_id}")
def start(proj_id: str):
    with _lock:
        if proj_id in _procs and _procs[proj_id].poll() is None:
            return {"ok": True, "msg": "已在运行"}
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        proj = _find_proj(cfg, proj_id)
        if not proj:
            return {"ok": False, "error": "未找到项目 %s" % proj_id}
        cmd = proj.get("cmd", "")
        if not cmd:
            return {"ok": False, "error": "该项目无启动命令"}
        run_dir = _resolve(proj.get("runDir", proj.get("path")))
        cmd = _expand_cmd(cmd, run_dir, _resolve(proj.get("path", "")))
        try:
            proc = subprocess.Popen(
                cmd, shell=True, cwd=str(run_dir),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True)
            _procs[proj_id] = proc
            # 后台收集输出到日志文件
            log = ROOT / "logs" / f"{proj_id}.log"
            log.parent.mkdir(exist_ok=True)
            threading.Thread(target=_drain, args=(proc, log), daemon=True).start()
            return {"ok": True, "msg": f"已启动 {proj['name']} (pid {proc.pid})"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

@app.post("/api/stop/{proj_id}")
def stop(proj_id: str):
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    proj = _find_proj(cfg, proj_id) or {}
    port = proj.get("port", 0)
    killed = False
    with _lock:
        proc = _procs.pop(proj_id, None)
        if proc and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                killed = True
            except Exception:
                try: proc.terminate()
                except Exception: pass
    # 也杀端口进程(兜底, 用 pkill 管端口)
    if port:
        subprocess.run(["pkill", "-f", ":%d" % port], capture_output=True)
    return {"ok": True, "msg": "已停止" if killed else "未发现运行进程", "port": port}

@app.get("/api/status/{proj_id}")
def status(proj_id: str):
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    proj = _find_proj(cfg, proj_id) or {}
    port = proj.get("port", 0)
    log = ROOT / "logs" / f"{proj_id}.log"
    tail = ""
    if log.exists():
        lines = log.read_text(encoding="utf-8", errors="ignore").splitlines()
        tail = "\n".join(lines[-30:])
    return {"id": proj_id, "active": _is_active(port) if port else False,
            "port": port, "log": tail}

def _find_proj(cfg: dict, proj_id: str):
    for cat in cfg["categories"]:
        for pr in cat["projects"]:
            if pr.get("id") == proj_id:
                return pr
            for c in pr.get("children", []):
                if c.get("id") == proj_id:
                    return c
    return None

def _drain(proc, log: Path):
    """持续把子进程输出写进日志文件"""
    with open(log, "wb") as f:
        try:
            for line in proc.stdout:
                f.write(line)
                f.flush()
        except Exception:
            pass

@app.post("/api/open/{proj_id}")
def open_proj(proj_id: str):
    """用 Finder 打开项目目录"""
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    proj = _find_proj(cfg, proj_id)
    if not proj:
        return {"ok": False, "error": "未找到项目"}
    path = _resolve(proj.get("path", ""))
    if not path.is_dir():
        return {"ok": False, "error": "目录不存在: %s" % path}
    subprocess.Popen(["open", str(path)])
    return {"ok": True, "msg": "已打开 %s" % proj["name"]}

@app.get("/api/health")
def health():
    return {"ok": True, "time": time.strftime("%H:%M:%S")}

# 若前端已 build, 由后端 serve 静态产物(单端口访问)
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("WB_PORT", "8899"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")