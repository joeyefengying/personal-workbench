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
HOME = Path.home()
CONFIG = ROOT / "apps.json"
FRONTEND_DIST = ROOT.parent / "frontend" / "dist"
# 选一个真正装了 fastapi/uvicorn 的 python3, 避免 shutil.which 解析到无依赖的 /usr/bin/python3
PY_CANDIDATES = [
    "/usr/local/bin/python3",
    "/Users/zhanghao/.hermes/hermes-agent/venv/bin/python3",
    "/usr/bin/python3",
]


def _pick_python() -> str:
    """探测能 import fastapi+uvicorn 的 python3, 找不到时退回 sys.executable"""
    probe = "import fastapi, uvicorn"
    for cand in PY_CANDIDATES:
        if not os.path.exists(cand):
            continue
        try:
            r = subprocess.run([cand, "-c", probe], capture_output=True,
                               text=True, timeout=10)
            if r.returncode == 0:
                return cand
        except Exception:
            continue
    return sys.executable or "python3"


PYTHON = _pick_python()

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
    sessions = _load_proj_sessions()
    p = {
        "id": proj["id"],
        "name": proj["name"],
        "path": str(path),
        "desc": proj.get("desc", ""),
        "type": proj.get("type", "web"),
        "git": _git_info(path),
        "hasSession": proj["id"] in sessions,
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


@app.post("/api/project/open-chat")
def open_project_chat(payload: dict):
    """项目对话启动器: 在项目目录打开 hermes chat, 已有会话则续接不重复新建.
    - 已有会话: 立即弹 Terminal --resume <id> (快路径)
    - 首次: 后台线程建会话(拿 session_id 存档), 建好后弹 Terminal --resume
    payload: {proj_id}
    """
    proj_id = (payload or {}).get("proj_id", "")
    if not proj_id:
        return {"ok": False, "error": "缺少 proj_id"}
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    proj = _find_proj(cfg, proj_id)
    if not proj:
        return {"ok": False, "error": "未找到项目 %s" % proj_id}
    path = _resolve(proj.get("path", ""))
    if not path.is_dir():
        return {"ok": False, "error": "目录不存在: %s" % path}
    run_dir = _resolve(proj.get("runDir", proj.get("path", ""))) or path

    # 并发保护: 同一项目同时只建一个会话
    with _lock:
        if proj_id in _sess_building:
            return {"ok": True, "msg": "正在为该项目的对话会话… 建好后会自动打开", "building": True, "proj": proj_id}

    sessions = _load_proj_sessions()
    rec = sessions.get(proj_id) or {}
    sid = rec.get("session_id", "")

    if sid:
        # 快路径: 已有会话, 立即续接
        cmd = "hermes chat --resume %s" % _shell_escape(sid)
        ok, err = _spawn_terminal_run(run_dir, cmd)
        if not ok:
            return {"ok": False, "error": err, "proj": proj_id}
        return {"ok": True, "msg": "已续接 %s 项目对话" % proj["name"],
                "resumed": True, "session_id": sid, "proj": proj_id}

    # 首次: 后台建会话
    with _lock:
        _sess_building.add(proj_id)
    def _build_later():
        try:
            _create_project_session(proj, run_dir)
        finally:
            with _lock:
                _sess_building.discard(proj_id)
    threading.Thread(target=_build_later, daemon=True).start()
    return {"ok": True, "msg": "正在为 %s 创建专属对话会话… 建好后自动打开（约 30-60 秒）" % proj["name"],
            "building": True, "proj": proj_id}


_sess_building = set()


def _create_project_session(proj: dict, run_dir: Path) -> None:
    """后台建会话: hermes chat -q -Q 建一条, 拿 session_id 存档, 再弹 Terminal --resume"""
    proj_id = proj["id"]
    try:
        probe = subprocess.run(
            ["hermes", "chat", "-q", "你好，这是「%s」项目的工作对话，后续我会在这里和你讨论这个项目的开发、调试和迭代。" % proj["name"], "-Q"],
            cwd=str(run_dir), capture_output=True, text=True, timeout=240)
    except Exception:
        return
    sid = _extract_session(probe.stdout + "\n" + probe.stderr)
    if not sid:
        # 建会话失败, 至少打开一个普通对话
        _spawn_terminal_run(run_dir, "hermes chat")
        return
    sessions = _load_proj_sessions()
    sessions[proj_id] = {"session_id": sid, "name": proj["name"],
                         "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    _save_proj_sessions(sessions)
    cmd = "hermes chat --resume %s" % _shell_escape(sid)
    _spawn_terminal_run(run_dir, cmd)


def _spawn_terminal_run(run_dir: Path, cmd: str):
    """在 Terminal.app 新窗口: cd 到 run_dir 后运行 cmd"""
    cd = _shell_escape(str(run_dir))
    if not cd.startswith("/"):
        cd = "/" + cd
    apple_script = (
        'tell application "Terminal"\n'
        '  activate\n'
        '  do script "cd %s && %s; echo; read -p \\"回车关闭窗口...\\""\n'
        'end tell' % (cd, cmd.replace("\\", "\\\\").replace('"', '\\"')))
    try:
        p = subprocess.run(["osascript", "-e", apple_script],
                           capture_output=True, text=True, timeout=15)
        if p.returncode != 0:
            return False, "osascript 打开失败: %s" % (p.stderr.strip() or "未知")
        return True, None
    except Exception as e:
        return False, str(e)


def _extract_session(text: str) -> str:
    """从 hermes chat 输出中提取 session_id (格式 20260904_160314_abc31e, 打在 stderr/含 session_id:)"""
    # 直接匹配时间戳格式 id, 不依赖前面的 session/session_id 关键词(其前后缀多变)
    m = re.search(r"([0-9]{8}_[0-9]{6}_[a-f0-9]{6})", text)
    return m.group(1) if m else ""


def _load_proj_sessions() -> dict:
    f = ROOT / "project_sessions.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_proj_sessions(d: dict) -> None:
    (ROOT / "project_sessions.json").write_text(
        json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


@app.get("/api/skill/favorites")
def skill_favorites():
    """返回收藏的 skill key 列表 (key = slug+source), 有序"""
    return {"favorites": _load_skill_favs()}


@app.post("/api/skill/favorite")
def skill_favorite(payload: dict):
    """收藏/取消收藏 skill。payload: {key, favorite: bool}"""
    key = (payload or {}).get("key", "")
    favorite = bool((payload or {}).get("favorite", True))
    if not key:
        return {"ok": False, "error": "缺少 key"}
    favs = _load_skill_favs()
    if favorite and key not in favs:
        favs.append(key)
    if not favorite and key in favs:
        favs.remove(key)
    _save_skill_favs(favs)
    return {"ok": True, "favorites": favs}


def _load_skill_favs() -> list:
    f = ROOT / "skill_favorites.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_skill_favs(d: list) -> None:
    (ROOT / "skill_favorites.json").write_text(
        json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


@app.get("/api/project/sessions")
def project_sessions():
    """列出各项目的已建会话 (proj_id -> {session_id, name, created})"""
    return {"sessions": _load_proj_sessions()}


# ---------------------------------------------------------------
# 自动化任务 — 读取 Hermes cron jobs.json + 启停
# ---------------------------------------------------------------
CRON_JOBS = Path.home() / ".hermes" / "cron" / "jobs.json"
CRON_OUT = Path.home() / ".hermes" / "cron" / "output"


def _cron_status_tags(j: dict):
    """根据 last_status/last_error/state 推导状态标签"""
    if str(j.get("enabled")) != "True":
        return {"tag": "paused", "color": "default", "text": "已暂停"}
    st = j.get("last_status")
    if j.get("last_error") and st != "ok":
        return {"tag": "error", "color": "red", "text": "运行失败"}
    if st == "error":
        return {"tag": "error", "color": "red", "text": "上次失败"}
    if st == "ok":
        return {"tag": "ok", "color": "green", "text": "正常"}
    if j.get("last_run_at") is None:
        return {"tag": "pending", "color": "orange", "text": "未运行"}
    return {"tag": "ok", "color": "green", "text": "正常"}


@app.get("/api/system/cron")
def system_cron():
    """列出所有 Hermes cron 任务 + 状态 + 最近日志"""
    jobs = []
    if CRON_JOBS.exists():
        try:
            data = json.loads(CRON_JOBS.read_text(encoding="utf-8"))
            raw = data.get("jobs", [])
            if isinstance(raw, dict):
                raw = list(raw.values())
            for j in raw:
                status = _cron_status_tags(j)
                # 读最近一次日志 (output/<id>-<ts>.json 或 <id>.json)
                log = None
                if CRON_OUT.is_dir():
                    cand = sorted(CRON_OUT.glob(f"{j.get('id')}*"))
                    if cand:
                        try:
                            log = cand[-1].read_text(encoding="utf-8")[:600]
                        except Exception:
                            pass
                jobs.append({
                    "id": j.get("id"),
                    "name": j.get("name"),
                    "schedule": j.get("schedule_display") or (j.get("schedule") or {}).get("display"),
                    "enabled": str(j.get("enabled")) == "True",
                    "state": j.get("state"),
                    "last_run": j.get("last_run_at"),
                    "next_run": j.get("next_run_at"),
                    "last_status": j.get("last_status"),
                    "last_error": (j.get("last_error") or "")[:200],
                    "completed": (j.get("repeat") or {}).get("completed"),
                    "deliver": j.get("deliver"),
                    "script": j.get("script"),
                    "tag": status["tag"], "color": status["color"], "status_text": status["text"],
                    "recent_log": log,
                })
        except Exception as e:
            return {"ok": False, "error": str(e), "jobs": []}
    return {"ok": True, "jobs": jobs, "scheduler": _cron_scheduler_status()}


def _cron_scheduler_status():
    """检查 cron scheduler 是否在运行"""
    try:
        r = subprocess.run(["hermes", "cron", "status"], capture_output=True, text=True, timeout=20)
        return r.stdout.strip() or r.stderr.strip()
    except Exception as e:
        return str(e)


@app.post("/api/system/cron/toggle")
def cron_toggle(payload: dict):
    """启用/暂停 cron 任务。payload: {id, enabled: bool}"""
    cid = (payload or {}).get("id", "")
    enable = bool((payload or {}).get("enabled", True))
    if not cid:
        return {"ok": False, "error": "缺少 task id"}
    cmd = ["hermes", "cron", "resume" if enable else "pause", cid]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return {"ok": True, "msg": f"{'已启用' if enable else '已暂停'} {cid}", "out": r.stdout.strip()}
        return {"ok": False, "error": r.stderr.strip() or r.stdout.strip()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/system/cron/run")
def cron_run(payload: dict):
    """立即运行一次 cron 任务。payload: {id}"""
    cid = (payload or {}).get("id", "")
    if not cid:
        return {"ok": False, "error": "缺少 task id"}
    try:
        r = subprocess.run(["hermes", "cron", "run", cid], capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return {"ok": True, "msg": f"已触发运行 {cid}", "out": r.stdout.strip()}
        return {"ok": False, "error": r.stderr.strip() or r.stdout.strip()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------
# 活动时间线 — 统计各项目 git 最近提交
# ---------------------------------------------------------------
@app.get("/api/activity")
def activity():
    """扫描各项目最近的 git 提交, 拼出活动时间线"""
    events = []
    cfg = _load_config()
    for cat in cfg["categories"]:
        for p in cat["projects"]:
            if not p.get("git", {}).get("isGit"):
                continue
            try:
                r = subprocess.run(
                    ["git", "-C", p["path"], "log", "-5", "--pretty=%h|%ad|%s", "--date=format:%m-%d %H:%M"],
                    capture_output=True, text=True, timeout=8)
                for line in r.stdout.strip().splitlines():
                    if "|" not in line:
                        continue
                    h, when, subj = line.split("|", 2)
                    events.append({
                        "proj_id": p["id"], "proj_name": p["name"], "cat": cat["name"],
                        "hash": h, "when": when, "subject": subj[:80], "path": p["path"],
                    })
            except Exception:
                continue
    events.sort(key=lambda e: (e["when"] is None, e["when"]), reverse=True)
    return {"events": events[:80], "total": len(events)}


# ---------------------------------------------------------------
# 系统设置 — 本机环境自检
# ---------------------------------------------------------------
@app.get("/api/system/env")
def system_env():
    """检测本机 agent 环境: skill/项目/服务/版本"""
    import platform
    skills = len(_scan_skills())
    cats = _load_config()
    proj_count = sum(len(c["projects"]) for c in cats["categories"])
    running = [p["name"] for c in cats["categories"] for p in c["projects"] if p.get("active")]
    env_info = {
        "os": f"{platform.system()} {platform.machine()}",
        "python": sys.version.split()[0],
        "hermes": _hermes_version(),
        "skills": skills,
        "projects": proj_count,
        "running": running,
        "sessions": len(_load_proj_sessions()),
        "favorites": len(_load_skill_favs()),
    }
    return env_info


def _hermes_version():
    try:
        r = subprocess.run(["hermes", "--version"], capture_output=True, text=True, timeout=15)
        return (r.stdout.strip() or r.stderr.strip()).splitlines()[0][:40]
    except Exception:
        return "unknown"


# ---------------------------------------------------------------
# 知识库 — llm-wiki 统计 + 搜索
# ---------------------------------------------------------------
LLM_WIKI_SCRIPTS = Path.home() / "Downloads" / "笔记" / "笔记" / ".claude" / "skills" / "llm-wiki" / "scripts"
WIKI_ROOT = Path.home() / "Downloads" / "笔记" / "笔记" / "wiki"


@app.get("/api/wiki/stats")
def wiki_stats():
    """llm-wiki 内容统计 (entities/topics/sources/synthesis 计数)"""
    def count(sub):
        d = WIKI_ROOT / sub
        return len([f for f in d.glob("*.md")]) if d.is_dir() else 0
    return {
        "entities": count("entities"), "topics": count("topics"),
        "sources": count("sources"), "synthesis": count("synthesis"),
        "root": str(WIKI_ROOT),
    }


@app.get("/api/wiki/search")
def wiki_search(q: str = ""):
    """调用 llm-wiki search.sh 搜索"""
    if not q:
        return {"ok": False, "error": "缺少搜索词 q"}
    script = LLM_WIKI_SCRIPTS / "search.sh"
    if not script.exists():
        return {"ok": False, "error": "llm-wiki search.sh 不存在"}
    try:
        r = subprocess.run(["bash", str(script), "search", str(WIKI_ROOT), q, "--max-results", "10"],
                           capture_output=True, text=True, timeout=60)
        # search.sh 输出可能是结构化文本, 直接返回原文让前端展示
        text = (r.stdout or r.stderr)[:4000]
        return {"ok": r.returncode == 0, "output": text, "query": q}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "搜索超时(60s)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# 轻推集成 — 数据目录 (会话/任务/每日总结)
QINGTUI_DATA = ROOT / "qingtui_data"
QINGTUI_DATA.mkdir(exist_ok=True)
QINGTUI_WATCH = QINGTUI_DATA / "watch.json"   # 监控的会话清单 (用户选定)


# ---------------------------------------------------------------
# 轻推 (Qingtui) — 会话发现 / 每日总结 / 任务提取
# SQLite 直读方案, 不依赖调试端口 9222
# ---------------------------------------------------------------
def _load_watch():
    """读取监控会话清单: [{cid, type, name}, ...]"""
    if QINGTUI_WATCH.exists():
        try:
            return json.loads(QINGTUI_WATCH.read_text(encoding="utf-8")).get("sessions", [])
        except Exception:
            pass
    return []


def _save_watch(sessions):
    QINGTUI_WATCH.write_text(json.dumps({"sessions": sessions}, ensure_ascii=False, indent=1), encoding="utf-8")


@app.get("/api/qingtui/sessions")
def qt_sessions():
    """列出全部最近会话 (从 SQLite 直读)."""
    try:
        from timeline.qingtui_sqlite import list_sessions_sqlite, db_exists
    except ImportError:
        return {"ok": False, "error": "qingtui_sqlite 模块未就绪", "sessions": []}
    if not db_exists():
        return {"ok": False, "error": "轻推数据库不存在 (csp4.db)", "sessions": []}
    return {"ok": True, "sessions": list_sessions_sqlite(recent_days=7)}


@app.get("/api/qingtui/watch")
def qt_watch_list():
    """获取已选定的监控会话清单."""
    return {"ok": True, "sessions": _load_watch()}


@app.post("/api/qingtui/watch")
def qt_watch_set(payload: dict):
    """设置监控会话清单. payload: {sessions:[{cid,type,name}, ...]}"""
    sessions = (payload or {}).get("sessions", [])
    if not isinstance(sessions, list):
        return {"ok": False, "error": "sessions 必须是列表"}
    _save_watch(sessions)
    return {"ok": True, "count": len(sessions)}


@app.get("/api/qingtui/daily-summary")
def qt_daily_summary_api(date: str = "", sessions: str = ""):
    """某天的每日总结 (从 SQLite 直读). date=YYYY-MM-DD (默认今天)."""
    try:
        from timeline.qingtui_sqlite import daily_summary_sqlite, db_exists
    except ImportError:
        return {"ok": False, "error": "qingtui_sqlite 模块未就绪"}
    if not db_exists():
        return {"ok": False, "error": "轻推数据库不存在 (csp4.db)"}
    return daily_summary_sqlite(date or None)


@app.get("/api/qingtui/tasks")
def qt_tasks_api(date: str = "", sessions: str = ""):
    """从某天的消息提取待办任务 (SQLite 直读版, 基础关键词识别)."""
    try:
        from timeline.qingtui_sqlite import daily_summary_sqlite, db_exists
    except ImportError:
        return {"ok": False, "error": "qingtui_sqlite 模块未就绪", "tasks": []}
    if not db_exists():
        return {"ok": False, "error": "轻推数据库不存在", "tasks": []}

    # 待办关键词 (承诺/指派/截止/跟进)
    TASK_KEYWORDS = ["待办", "要跟进", "记得", "帮我", "明天", "下周", "尽快", "需要你",
                     "todo", "TODO", "还没", "别忘了", "处理下", "安排", "落实", "会后"]
    d = daily_summary_sqlite(date or None)
    highlights = d.get("achievement", {}).get("highlights", [])
    tasks = []
    for h in highlights:
        text = h.get("text", "")
        kind = h.get("kind", "mine")
        is_mention = kind in ("mention", "at_all")
        matched = [kw for kw in TASK_KEYWORDS if kw in text]
        # @提及 的全部纳入待办关注; 自己发的只纳入含关键词的
        if is_mention or matched:
            tasks.append({
                "id": f"{h.get('session','')}:{h.get('time','')}",
                "text": text,
                "session": h.get("session", ""),
                "time": h.get("time", ""),
                "status": "pending",
                "is_mention": is_mention,
                "kind": kind,
                "keywords": matched,
            })
    return {"ok": True, "tasks": tasks, "total": len(tasks)}


@app.post("/api/qingtui/task/verify")
def qt_task_verify(payload: dict):
    """人工核实任务 (SQLite 直读方案暂不支持)."""
    return {"ok": True, "task_id": (payload or {}).get("task_id", ""),
            "status": (payload or {}).get("status", ""),
            "hint": "SQLite 直读方案暂不支持任务核实, 数据已记录"}


@app.get("/api/qingtui/image-proxy")
def qt_image_proxy(url: str = ""):
    """代理轻推图片/文件 (轻推图片需鉴权, 浏览器无法直接加载).
    当前 qtfile CDN 需要 Electron session cookie, 从外部代理无法获取.
    失败时返回占位 SVG 提示用户在轻推 App 中查看.
    """
    from fastapi.responses import Response
    PLACEHOLDER_SVG = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="120">'
        '<rect fill="#f5f5f5" width="200" height="120" rx="8"/>'
        '<rect x="1" y="1" width="198" height="118" rx="7" fill="none" stroke="#ddd" stroke-width="1" stroke-dasharray="4"/>'
        '<text fill="#999" font-size="32" font-family="sans-serif" text-anchor="middle" x="100" y="52">🖼️</text>'
        '<text fill="#999" font-size="11" font-family="sans-serif" text-anchor="middle" x="100" y="74">图片</text>'
        '<text fill="#bbb" font-size="10" font-family="sans-serif" text-anchor="middle" x="100" y="92">(请在轻推中查看)</text>'
        '</svg>'
    ).encode()
    return Response(content=PLACEHOLDER_SVG, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/qingtui/context")
def qt_context(chat_id: str = "", ts: int = 0, direction: str = "", cursor_ts: int = 0,
               before: int = 20, after: int = 20):
    """消息上下文 (SQLite 直读): 初始按 chat_id+ts 取前后文; direction+cursor_ts 翻页."""
    if not chat_id:
        return {"ok": False, "error": "缺少 chat_id", "messages": []}
    try:
        from timeline.qingtui_sqlite import message_context_sqlite, message_context_page_sqlite
    except ImportError:
        return {"ok": False, "error": "模块未就绪", "messages": []}
    if direction and cursor_ts:
        return message_context_page_sqlite(chat_id, cursor_ts, direction, limit=30)
    if not ts:
        return {"ok": False, "error": "缺少 ts 或翻页游标", "messages": []}
    return message_context_sqlite(chat_id, ts, before, after)


@app.get("/api/qingtui/status")
def qt_status():
    """轻推连接状态自检 (SQLite 直读方案, 不再依赖调试端口)."""
    try:
        from timeline.qingtui_sqlite import db_exists
    except ImportError:
        return {"ok": False, "connected": False, "state": "not_running", "hint": "模块未就绪"}
    if not db_exists():
        return {"ok": False, "connected": False, "state": "not_running",
                "hint": "轻推数据库不存在, 请确认轻推已安装并使用过"}
    return {"ok": True, "connected": True, "state": "ok", "hint": "SQLite 直读正常",
            "watch_count": 0}


@app.post("/api/qingtui/launch")
def qt_launch():
    """一键启动轻推 (SQLite 直读方案: 仅确保轻推运行以更新 csp4.db)."""
    try:
        subprocess.run(["open", "-n", "/Applications/Qingtui.app"],
                       capture_output=True, timeout=10)
        return {"ok": True, "msg": "轻推已启动 (SQLite 直读无需调试端口)"}
    except Exception as e:
        return {"ok": False, "msg": f"启动失败: {e}"}


# ── 轻推群文档 ──

@app.get("/api/qingtui/docs")
def qt_docs(days: int = 7, date: str = "", type: str = "", chat_id: str = "",
            exclude_types: str = "article"):
    """提取轻推消息中的在线文档/文件/链接, 按权重排序, URL去重聚合."""
    try:
        from qingtui_docs import extract_docs
    except ImportError:
        return {"ok": False, "error": "qingtui_docs 模块未就绪"}
    return extract_docs(days=days, date=date, doc_type=type, chat_id=chat_id,
                        exclude_types=exclude_types)


# ── 轻推文档直开 (从 localStorage LevelDB 提取 webofficeUrl) ──

@app.get("/api/qingtui/cached-docs")
def qt_cached_docs():
    """列出轻推 app 缓存的所有文档 webofficeUrl (可在 Chrome 直开)."""
    try:
        from qt_doc_opener import list_cached_docs
    except ImportError:
        return {"ok": False, "error": "qt_doc_opener 模块未就绪"}
    return list_cached_docs()


@app.post("/api/qingtui/open-doc")
def qt_open_doc(payload: dict):
    """用 Chrome 打开指定文档 (从 localStorage 缓存提取 URL)."""
    try:
        from qt_doc_opener import open_doc_in_chrome
    except ImportError:
        return {"ok": False, "error": "qt_doc_opener 模块未就绪"}
    file_id = (payload or {}).get("file_id", "")
    if not file_id:
        return {"ok": False, "error": "缺少 file_id"}
    return open_doc_in_chrome(file_id)


@app.post("/api/qingtui/open-or-generate")
def qt_open_or_generate(payload: dict):
    """打开文档 (刷新 token + 构造 WPS 页面 URL + Chrome 打开)。

    需要配合 Tampermonkey 脚本使用 (拦截 iframe XHR 注入 Authorization 头)。
    脚本: backend/qingtui-wps-auth.user.js
    """
    try:
        from qt_doc_opener import open_doc_with_token
    except ImportError:
        return {"ok": False, "error": "qt_doc_opener 模块未就绪"}
    p = payload or {}
    file_id = p.get("file_id", "")
    if not file_id:
        return {"ok": False, "error": "缺少 file_id"}
    return open_doc_with_token(file_id)


@app.get("/api/qingtui/wps-auth-script")
def qt_wps_auth_script():
    """返回 Tampermonkey 脚本内容 (供前端安装提示)。"""
    import os
    script_path = os.path.join(os.path.dirname(__file__), "qingtui-wps-auth.user.js")
    try:
        with open(script_path, "r") as f:
            content = f.read()
        return {"ok": True, "script": content}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------- 智能待办 ----------
@app.get("/api/qingtui/todos")
def qt_todos(status: str = "pending", limit: int = 50):
    """获取待办列表 (pending/confirmed/ignored/all)."""
    try:
        from smart_todo import list_todos
    except ImportError:
        return {"ok": False, "error": "smart_todo 模块未就绪"}
    return list_todos(status=status, limit=limit)


@app.post("/api/qingtui/todos/analyze")
def qt_todos_analyze(payload: dict):
    """触发 AI 分析: 扫描消息 → 评分 → 聚类 → 存储."""
    try:
        from smart_todo import analyze_todos
    except ImportError:
        return {"ok": False, "error": "smart_todo 模块未就绪"}
    days = (payload or {}).get("days", 3)
    min_score = (payload or {}).get("min_score", 20)
    return analyze_todos(days=days, min_score=min_score)


@app.post("/api/qingtui/todos/operate")
def qt_todos_operate(payload: dict):
    """操作待办: confirm/ignore/reopen/delete."""
    try:
        from smart_todo import operate_todo
    except ImportError:
        return {"ok": False, "error": "smart_todo 模块未就绪"}
    todo_id = (payload or {}).get("todo_id")
    action = (payload or {}).get("action")
    if not todo_id or not action:
        return {"ok": False, "error": "缺少 todo_id 或 action"}
    return operate_todo(int(todo_id), action)


@app.post("/api/qingtui/todos/add")
def qt_todos_add(payload: dict):
    """手动添加待办."""
    try:
        from smart_todo import add_manual_todo
    except ImportError:
        return {"ok": False, "error": "smart_todo 模块未就绪"}
    p = payload or {}
    title = p.get("title", "").strip()
    if not title:
        return {"ok": False, "error": "标题不能为空"}
    return add_manual_todo(title, p.get("chat_name", ""), p.get("body", ""))


@app.get("/api/qingtui/todos/learning")
def qt_todos_learning():
    """获取学习模式 (关键词权重 + 群权重)."""
    try:
        from smart_todo import get_learning
    except ImportError:
        return {"ok": False, "error": "smart_todo 模块未就绪"}
    return get_learning()


@app.post("/api/analyze/run")
def analyze_run():
    """(已废弃) — 请使用报告中心的 AI 周报/月报功能代替"""
    return {"ok": False, "error": "已废弃, 请使用报告中心的周报/月报功能"}


@app.get("/api/analyze/latest")
def analyze_latest():
    """(已废弃)"""
    return {"ok": False, "error": "已废弃, 请使用报告中心的周报/月报功能"}


@app.get("/api/analyze/history")
def analyze_history():
    """(已废弃)"""
    return {"ok": False, "error": "已废弃, 请使用报告中心的周报/月报功能"}


# ---------------------------------------------------------------
# 每日日结 — 读取 second-brain-daily 生成的日报
# ---------------------------------------------------------------
DAILY_VAULT = Path.home() / "Downloads" / "笔记" / "笔记" / "PARA 管理" / "0. 周期笔记"
SECOND_BRAIN_CRON_ID = "823dc9de965a"


def _find_daily_files(limit: int = 30) -> list:
    """扫描周期笔记目录, 返回最近 N 个日报文件信息"""
    base = DAILY_VAULT
    if not base.is_dir():
        return []
    files = sorted(base.rglob("*.md"), reverse=True)
    result = []
    for f in files:
        # 文件名格式 YYYY-MM-DD.md
        name = f.stem
        if not re.match(r"\d{4}-\d{2}-\d{2}", name):
            continue
        try:
            stat = f.stat()
        except Exception:
            continue
        # 快速判断是否有 AI 回顾段
        has_ai = False
        try:
            head = f.read_text(encoding="utf-8", errors="ignore")
            has_ai = "🧠 AI 今日回顾" in head
        except Exception:
            pass
        result.append({
            "date": name,
            "path": str(f),
            "size": stat.st_size,
            "mtime": int(stat.st_mtime),
            "has_ai": has_ai,
        })
        if len(result) >= limit:
            break
    return result


def _extract_ai_section(filepath: str) -> str:
    """从日报文件中提取 '## 🧠 AI 今日回顾' 段落"""
    try:
        text = Path(filepath).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    marker = "## 🧠 AI 今日回顾"
    idx = text.find(marker)
    if idx < 0:
        return ""
    rest = text[idx + len(marker):]
    # 截到下一个 ## 标题或文件末尾
    next_h2 = rest.find("\n## ")
    if next_h2 >= 0:
        rest = rest[:next_h2]
    return rest.strip()


@app.get("/api/daily-report/list")
def daily_report_list(limit: int = 20):
    """列出最近的日结报告"""
    files = _find_daily_files(limit)
    return {"reports": files, "total": len(files), "vault": str(DAILY_VAULT)}


@app.get("/api/daily-report/get")
def daily_report_get(date: str = ""):
    """获取指定日期的日结报告内容 (AI 回顾段)"""
    if not date:
        return {"ok": False, "error": "缺少 date 参数"}
    # 在 vault 里找 date.md
    matches = list(DAILY_VAULT.rglob(f"{date}.md"))
    if not matches:
        return {"ok": False, "error": f"未找到 {date} 的日报"}
    fpath = matches[0]
    ai_section = _extract_ai_section(str(fpath))
    try:
        full_text = fpath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        full_text = ""
    return {
        "ok": True,
        "date": date,
        "path": str(fpath),
        "has_ai": bool(ai_section),
        "ai_section": ai_section,
        "full_length": len(full_text),
    }


@app.post("/api/daily-report/run")
def daily_report_run():
    """手动触发 second-brain-daily 日结"""
    try:
        r = subprocess.run(
            ["hermes", "cron", "run", SECOND_BRAIN_CRON_ID],
            capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return {"ok": True, "msg": "已触发日结, 约 1-2 分钟后生成",
                    "out": r.stdout.strip()[:200]}
        return {"ok": False, "error": r.stderr.strip() or r.stdout.strip()[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/config")
def get_config():
    return _load_config()

def _wait_port(port: int, timeout: float = 12.0) -> bool:
    """轮询端口是否已监听(服务真正就绪), 返回是否就绪"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            s = subprocess.run(["lsof", "-iTCP:%d" % port, "-sTCP:LISTEN", "-t"],
                               capture_output=True, text=True)
            if s.stdout.strip():
                return True
        except Exception:
            pass
        time.sleep(0.6)
    return False


@app.post("/api/start/{proj_id}")
def start(proj_id: str):
    with _lock:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        proj = _find_proj(cfg, proj_id)
        if not proj:
            return {"ok": False, "error": "未找到项目 %s" % proj_id}
        if proj_id in _procs and _procs[proj_id].poll() is None:
            if _is_active(proj.get("port", 0)):
                return {"ok": True, "msg": "已在运行"}
        cmd = proj.get("cmd", "")
        if not cmd:
            return {"ok": False, "error": "该项目无启动命令"}
        run_dir = _resolve(proj.get("runDir", proj.get("path")))
        cmd = _expand_cmd(cmd, run_dir, _resolve(proj.get("path", "")))
        log = ROOT / "logs" / f"{proj_id}.log"
        log.parent.mkdir(exist_ok=True)
        try:
            proc = subprocess.Popen(
                cmd, shell=True, cwd=str(run_dir),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True)
            _procs[proj_id] = proc
            # 后台收集输出到日志文件
            threading.Thread(target=_drain, args=(proc, log), daemon=True).start()
        except Exception as e:
            return {"ok": False, "error": "拉起进程失败: %s" % e}

        # ★ 就绪验证: 有端口才等端口就绪, 否则检查进程存活几秒
        port = proj.get("port", 0)
        started = time.time()
        if port:
            ok = _wait_port(port, timeout=12)
            if not ok:
                # 读日志尾部找真实报错, 反馈给前端
                err_tail = ""
                if log.exists():
                    err_tail = "\n".join(log.read_text(encoding="utf-8", errors="ignore")
                                         .splitlines()[-15:])
                # 清理失败进程
                for pid_proc in list(_procs.values()):
                    if pid_proc.poll() is None:
                        try: os.killpg(os.getpgid(pid_proc.pid), signal.SIGKILL)
                        except Exception: pass
                _procs.pop(proj_id, None)
                return {"ok": False, "error": "启动失败: 端口 %d %d 秒内未就绪.\n%s"
                        % (port, int(time.time() - started), err_tail)}
            return {"ok": True, "msg": f"已启动 {proj['name']} (pid {proc.pid}, {int(time.time()-started)}s 就绪)"}
        # 无端口: 等它运行几秒确认没立刻崩
        time.sleep(3)
        if proc.poll() is not None:
            err_tail = ""
            if log.exists():
                err_tail = "\n".join(log.read_text(encoding="utf-8", errors="ignore")
                                     .splitlines()[-10:])
            return {"ok": False, "error": "启动失败: 进程很快退出.\n%s" % err_tail}
        return {"ok": True, "msg": f"已启动 {proj['name']} (pid {proc.pid})"}

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


# ---------------------------------------------------------------
# 统一时间线 (Timeline) — 文件/浏览器/轻推/Git 多源事件汇聚
# ---------------------------------------------------------------
sys.path.insert(0, str(ROOT))
from timeline import (  # noqa: E402
    get_db, run_all_collectors,
)
from timeline.reporter import ensure_project, ensure_projects_from_events  # noqa: E402
from timeline.db import EventDB  # noqa: E402


@app.get("/api/timeline/events")
def timeline_events(date: str = "", source: str = "", category: str = "",
                    limit: int = 100, offset: int = 0, search: str = ""):
    """查询事件时间线."""
    db = get_db()
    events, total = db.query(date=date, source=source, category=category,
                             limit=limit, offset=offset, search=search)
    return {"ok": True, "events": events, "total": total,
            "limit": limit, "offset": offset}


@app.get("/api/timeline/stats")
def timeline_stats(date: str = ""):
    """事件统计聚合."""
    db = get_db()
    return {"ok": True, "stats": db.stats(date=date)}


@app.get("/api/timeline/dates")
def timeline_dates(limit: int = 60):
    """有事件的日期列表."""
    db = get_db()
    return {"ok": True, "dates": db.distinct_dates(limit=limit)}


@app.get("/api/timeline/daily")
def timeline_daily(date: str = ""):
    """某天结构化总结."""
    if not date:
        date = time.strftime("%Y-%m-%d")
    db = get_db()
    return {"ok": True, "summary": db.daily_summary(date)}


@app.get("/api/timeline/channels")
def timeline_channels():
    """各采集渠道的实时状态 + 覆盖情况 + 遗漏说明."""
    import urllib.request
    from timeline.collector import (
        FileCollector, BrowserCollector, GitCollector, QingtuiCollector,
        WATCH_DIRS, CHROME_HISTORY, CHROME_PROFILES, SAFARI_HISTORY,
    )
    from timeline.reporter import APPS_NAME_MAP

    db = get_db()
    channels = []

    # ---- Git 渠道 ----
    gc = GitCollector()
    projs = gc._projects()
    git_projects = [(p, n, (Path(p) / ".git").exists()) for p, n in projs]
    git_with_repo = [x for x in git_projects if x[2]]
    git_count = db._conn().execute("SELECT COUNT(*) FROM events WHERE source='git'").fetchone()[0]
    channels.append({
        "key": "git", "name": "代码提交", "icon": "🔧", "active": True,
        "count": git_count,
        "status": "ok" if git_count else "empty",
        "status_text": f"已采集 {git_count} 条",
        "detail": f"监控 {len(git_with_repo)}/{len(git_projects)} 个 git 仓库",
        "missed": [
            f"「{n}」非 git 目录，未纳入" for p, n, has in git_projects if not has
        ],
    })

    # ---- 浏览器渠道 ----
    chrome_ok = CHROME_HISTORY.exists()
    safari_ok = SAFARI_HISTORY.exists()
    browser_count = db._conn().execute("SELECT COUNT(*) FROM events WHERE source='browser'").fetchone()[0]
    # Safari 数据量极少时, 在说明里标注
    safari_count = 0
    if safari_ok:
        try:
            import sqlite3, tempfile, shutil as _shutil
            _tmp = Path(tempfile.gettempdir()) / f"safari_probe_{os.getpid()}.db"
            _shutil.copy2(str(SAFARI_HISTORY), str(_tmp))
            _c = sqlite3.connect(str(_tmp))
            safari_count = _c.execute("SELECT COUNT(*) FROM history_items").fetchone()[0]
            _c.close()
            _tmp.unlink(missing_ok=True)
        except Exception:
            pass
    browsers = []
    if chrome_ok:
        browsers.append("Chrome")
    if safari_ok and safari_count > 5:
        browsers.append(f"Safari({safari_count})")
    missed = []
    if safari_ok and safari_count <= 5:
        missed.append("Safari 历史极少（几乎不用），主要靠 Chrome")
    if not browsers:
        missed.append("未覆盖 Edge/Firefox/Arc（如使用会遗漏）")
    channels.append({
        "key": "browser", "name": "浏览器访问", "icon": "🌐", "active": bool(browsers),
        "count": browser_count,
        "status": "ok" if browser_count else "empty",
        "status_text": f"已采集 {browser_count} 条",
        "detail": f"覆盖: {', '.join(browsers) or '无'}",
        "missed": missed,
    })

    # ---- 文件渠道 ----
    fc = FileCollector()
    snap = fc._load_snapshot()
    file_count = db._conn().execute("SELECT COUNT(*) FROM events WHERE source='files'").fetchone()[0]
    first_run = not bool(snap)
    channels.append({
        "key": "files", "name": "文件变化", "icon": "📁", "active": True,
        "count": file_count,
        "status": "ok" if not first_run else "init",
        "status_text": f"快照 {len(snap)} 个文件" + ("（首次建快照）" if first_run else ""),
        "detail": f"监控 {len(WATCH_DIRS)} 个目录",
        "missed": [
            "首次运行只建快照，从第二次起才有变更事件",
        ] if first_run else [],
    })

    # ---- 轻推渠道 ----
    # 检查 csp4.db 是否存在 (SQLite 直读方案, 不需要调试端口)
    qingtui_db = HOME / "Library/Application Support/Qingtui/sqlite/344548d972f44d799aeea39ae3e231ba/csp4.db"
    qingtui_db_ok = qingtui_db.exists()
    qingtui_count = db._conn().execute("SELECT COUNT(*) FROM events WHERE source='qingtui'").fetchone()[0]
    if not qingtui_db_ok:
        missed = ["轻推数据库不存在 (csp4.db), 请确认轻推已安装"]
        detail = "数据库未找到"
    elif qingtui_count == 0:
        missed = []
        detail = "数据库在线，待采集"
    else:
        missed = []
        detail = "数据库在线"
    channels.append({
        "key": "qingtui", "name": "轻推消息", "icon": "💬", "active": qingtui_db_ok,
        "count": qingtui_count,
        "status": "ok" if qingtui_count else ("empty" if qingtui_db_ok else "down"),
        "status_text": f"已采集 {qingtui_count} 条" if qingtui_count else ("待采集" if qingtui_db_ok else "未连接"),
        "detail": detail,
        "missed": missed,
    })

    # ---- 未覆盖渠道 (预告) ----
    channels.append({
        "key": "wechat", "name": "微信消息", "icon": "💭", "active": False,
        "count": 0, "status": "planned", "status_text": "未接入",
        "detail": "计划第二期接入",
        "missed": ["微信聊天记录未采集（需确认本机 WeChat 数据格式）"],
    })
    channels.append({
        "key": "others", "name": "其他来源", "icon": "📌", "active": False,
        "count": 0, "status": "planned", "status_text": "可扩展",
        "detail": "邮件/日历/番茄钟/健康数据等",
        "missed": ["邮件、日历、番茄钟、健康等未接入"],
    })

    return {"ok": True, "channels": channels,
            "total": sum(c["count"] for c in channels if c.get("count"))}


@app.post("/api/timeline/collect")
def timeline_collect():
    """手动触发全量采集 (后台执行, 立即返回)."""
    def _run():
        try:
            run_all_collectors()
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "msg": "已触发采集, 后台执行中"}


@app.post("/api/timeline/collect/sync")
def timeline_collect_sync():
    """同步采集 (快渠道立即返回, 轻推后台进行)."""
    result = run_all_collectors()
    # 轻推是否在后台采集
    qt_state = result.get("sources", {}).get("qingtui", {})
    background = qt_state.get("status") == "background"
    return {"ok": True, "result": result, "qingtui_background": background}


@app.post("/api/timeline/lifecycle")
def timeline_lifecycle(ttl_days: int = 30):
    """执行数据生命周期: 聚合到 summary → 清理过期事件 → VACUUM."""
    db = get_db()
    try:
        result = db.lifecycle(ttl_days)
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/timeline/summary")
def timeline_summary(date: str = "", source: str = ""):
    """查询汇总层统计数据."""
    db = get_db()
    conn = db._conn()
    where = []
    params = []
    if date:
        where.append("date = ?")
        params.append(date)
    if source:
        where.append("source = ?")
        params.append(source)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        f"""SELECT date, source, dimension, dim_key, count, meta
            FROM summary_events {where_sql}
            ORDER BY date DESC, count DESC LIMIT 200""",
        params).fetchall()
    items = [{"date": r[0], "source": r[1], "dimension": r[2],
              "dim_key": r[3], "count": r[4], "meta": json.loads(r[5] or "{}")}
             for r in rows]
    total = conn.execute(
        f"SELECT COUNT(*) FROM summary_events {where_sql}", params).fetchone()[0]
    return {"ok": True, "items": items, "total": total}


@app.post("/api/timeline/daily/preview")
def timeline_daily_preview(payload: dict | None = None):
    """预览日报: AI 总结 + 项目归类 (不落盘)."""
    payload = payload or {}
    date = payload.get("date", "") or time.strftime("%Y-%m-%d")
    try:
        from timeline.daily_report import preview_daily_report
        result = preview_daily_report(date)
        result["ok"] = True
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/timeline/daily/commit")
def timeline_daily_commit(payload: dict | None = None):
    """提交日报: 写入各项目 README + 独立日报文件.

    payload: {date, project_summaries?: {项目名: summary_md}}
    """
    payload = payload or {}
    date = payload.get("date", "") or time.strftime("%Y-%m-%d")
    project_summaries = payload.get("project_summaries", None)
    try:
        from timeline.daily_report import commit_daily_report
        result = commit_daily_report(date, project_summaries)
        result["ok"] = True
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/timeline/today-overview")
def timeline_today_overview(date: str = ""):
    """今日概览 — 聚合今天的事件、@提及、采集状态."""
    if not date:
        date = time.strftime("%Y-%m-%d")
    try:
        from timeline.today_overview import today_overview
        result = today_overview(date)
        result["ok"] = True
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/timeline/obsidian/projects")
def timeline_obsidian_projects():
    """根据事件库里的项目名, 自动创建缺失的 LifeOS 项目."""
    try:
        db = get_db()
        # 全局扫描 git 事件里的项目名
        events, _ = db.query(source="git", limit=100000)
        created = []
        seen = set()
        for e in events:
            proj = e.get("target", "") or (e.get("meta", {}) or {}).get("project", "")
            if proj and proj not in seen:
                p = ensure_project(proj, display_name=proj)
                if p:
                    seen.add(proj)
                    created.append(p)
        return {"ok": True, "created": [str(p) for p in created],
                "count": len(created)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────
# 周报 / 月报 API
# ─────────────────────────────────────────────────────────────

@app.get("/api/weekly/list")
def weekly_list():
    try:
        from weekly_api import list_weekly_reports
        return {"ok": True, "weeks": list_weekly_reports()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/weekly/report")
def weekly_report(week: str = ""):
    if not week:
        return {"ok": False, "error": "缺少 week 参数 (如 2026-W37)"}
    try:
        from weekly_api import get_weekly_report
        r = get_weekly_report(week)
        if r is None:
            return {"ok": False, "error": f"周报 {week} 不存在"}
        return {"ok": True, "report": r}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/weekly/export-md")
def weekly_export_md(week: str = ""):
    if not week:
        return {"ok": False, "error": "缺少 week 参数"}
    try:
        from weekly_api import export_weekly_markdown
        md = export_weekly_markdown(week)
        if md is None:
            return {"ok": False, "error": f"周报 {week} 不存在"}
        return {"ok": True, "markdown": md}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/monthly/list")
def monthly_list():
    try:
        from weekly_api import list_monthly_reports
        return {"ok": True, "months": list_monthly_reports()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/monthly/report")
def monthly_report(month: str = ""):
    if not month:
        return {"ok": False, "error": "缺少 month 参数 (如 2026-08)"}
    try:
        from weekly_api import get_monthly_report
        r = get_monthly_report(month)
        if r is None:
            return {"ok": False, "error": f"月报 {month} 不存在"}
        return {"ok": True, "report": r}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/monthly/export-md")
def monthly_export_md(month: str = ""):
    if not month:
        return {"ok": False, "error": "缺少 month 参数"}
    try:
        from weekly_api import export_monthly_markdown
        md = export_monthly_markdown(month)
        if md is None:
            return {"ok": False, "error": f"月报 {month} 不存在"}
        return {"ok": True, "markdown": md}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/weekly/summarize")
def weekly_summarize(week: str = "", force: bool = False):
    """AI 生成周报总结. 默认优先返回缓存(JSON→LifeOS回读), force=true 强制重新生成."""
    if not week:
        return {"ok": False, "error": "缺少 week 参数"}
    try:
        from weekly_api import summarize_weekly, get_cached_ai_summary
        s = summarize_weekly(week, force=force)
        if s is None:
            return {"ok": False, "error": f"周报 {week} 不存在或 AI 总结失败"}
        # 区分是否命中缓存(生成后已持久化, 二次读回判断)
        cached = get_cached_ai_summary("weekly", week)
        was_cached = (not force) and cached is not None and cached["summary"] == s
        at = (cached or {}).get("at", "")
        return {"ok": True, "summary": s, "cached": was_cached, "at": at}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/monthly/summarize")
def monthly_summarize(month: str = "", force: bool = False):
    """AI 生成月报总结. 默认优先返回缓存(JSON→LifeOS回读), force=true 强制重新生成."""
    if not month:
        return {"ok": False, "error": "缺少 month 参数"}
    try:
        from weekly_api import summarize_monthly, get_cached_ai_summary
        s = summarize_monthly(month, force=force)
        if s is None:
            return {"ok": False, "error": f"月报 {month} 不存在或 AI 总结失败"}
        cached = get_cached_ai_summary("monthly", month)
        was_cached = (not force) and cached is not None and cached["summary"] == s
        at = (cached or {}).get("at", "")
        return {"ok": True, "summary": s, "cached": was_cached, "at": at}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/weekly/write-lifeos")
def weekly_write_lifeos(payload: dict | None = None):
    """把周报 AI 总结写入 LifeOS 周期笔记."""
    payload = payload or {}
    week = payload.get("week", "")
    if not week:
        return {"ok": False, "error": "缺少 week 参数"}
    try:
        from weekly_api import write_summary_to_lifeos
        return write_summary_to_lifeos("weekly", week)
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/monthly/write-lifeos")
def monthly_write_lifeos(payload: dict | None = None):
    """把月报 AI 总结写入 LifeOS 周期笔记."""
    payload = payload or {}
    month = payload.get("month", "")
    if not month:
        return {"ok": False, "error": "缺少 month 参数"}
    try:
        from weekly_api import write_summary_to_lifeos
        return write_summary_to_lifeos("monthly", month)
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── 季报 / 年报 API ──


@app.get("/api/quarterly/list")
def quarterly_list():
    """列出所有可聚合的季度."""
    try:
        from weekly_api import list_quarterly_reports
        return {"ok": True, "quarters": list_quarterly_reports()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/quarterly/report")
def quarterly_report(quarter: str = ""):
    """获取某季度聚合报告."""
    if not quarter:
        return {"ok": False, "error": "缺少 quarter 参数 (如 2026-Q3)"}
    try:
        from weekly_api import get_quarterly_report
        r = get_quarterly_report(quarter)
        if r is None:
            return {"ok": False, "error": f"季报 {quarter} 不存在（需有对应月份数据）"}
        return {"ok": True, "report": r}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/quarterly/summarize")
def quarterly_summarize(quarter: str = "", force: bool = False):
    """AI 生成季报总结. 默认优先返回缓存(JSON→LifeOS回读), force=true 强制重新生成."""
    if not quarter:
        return {"ok": False, "error": "缺少 quarter 参数"}
    try:
        from weekly_api import summarize_quarterly, get_cached_ai_summary
        s = summarize_quarterly(quarter, force=force)
        if s is None:
            return {"ok": False, "error": f"季报 {quarter} 不存在或 AI 总结失败"}
        cached = get_cached_ai_summary("quarterly", quarter)
        was_cached = (not force) and cached is not None and cached["summary"] == s
        at = (cached or {}).get("at", "")
        return {"ok": True, "summary": s, "cached": was_cached, "at": at}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/quarterly/write-lifeos")
def quarterly_write_lifeos(payload: dict | None = None):
    """把季报 AI 总结写入 LifeOS 周期笔记."""
    payload = payload or {}
    quarter = payload.get("quarter", "")
    if not quarter:
        return {"ok": False, "error": "缺少 quarter 参数"}
    try:
        from weekly_api import write_summary_to_lifeos
        return write_summary_to_lifeos("quarterly", quarter)
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/yearly/list")
def yearly_list():
    """列出所有可聚合的年度."""
    try:
        from weekly_api import list_yearly_reports
        return {"ok": True, "years": list_yearly_reports()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/yearly/report")
def yearly_report(year: str = ""):
    """获取某年度聚合报告."""
    if not year:
        return {"ok": False, "error": "缺少 year 参数 (如 2026)"}
    try:
        from weekly_api import get_yearly_report
        r = get_yearly_report(year)
        if r is None:
            return {"ok": False, "error": f"年报 {year} 不存在（需有对应月份数据）"}
        return {"ok": True, "report": r}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/yearly/summarize")
def yearly_summarize(year: str = "", force: bool = False):
    """AI 生成年报总结. 默认优先返回缓存(JSON→LifeOS回读), force=true 强制重新生成."""
    if not year:
        return {"ok": False, "error": "缺少 year 参数"}
    try:
        from weekly_api import summarize_yearly, get_cached_ai_summary
        s = summarize_yearly(year, force=force)
        if s is None:
            return {"ok": False, "error": f"年报 {year} 不存在或 AI 总结失败"}
        cached = get_cached_ai_summary("yearly", year)
        was_cached = (not force) and cached is not None and cached["summary"] == s
        at = (cached or {}).get("at", "")
        return {"ok": True, "summary": s, "cached": was_cached, "at": at}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/yearly/write-lifeos")
def yearly_write_lifeos(payload: dict | None = None):
    """把年报 AI 总结写入 LifeOS 周期笔记."""
    payload = payload or {}
    year = payload.get("year", "")
    if not year:
        return {"ok": False, "error": "缺少 year 参数"}
    try:
        from weekly_api import write_summary_to_lifeos
        return write_summary_to_lifeos("yearly", year)
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── 工作周报 DOC 生成 ──

@app.get("/api/weekly/doc/weeks")
def weekly_doc_weeks():
    """列出可生成工作周报的周列表."""
    try:
        from weekly_report_doc import list_available_weeks
        weeks = list_available_weeks()
        return {"ok": True, "weeks": weeks}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/weekly/doc/generate")
def weekly_doc_generate(payload: dict | None = None):
    """生成工作周报 .doc 文件. payload: {week_start: 'YYYY-MM-DD'}"""
    import datetime as _dt
    payload = payload or {}
    week_start_str = payload.get("week_start", "")
    try:
        from weekly_report_doc import generate_doc, _check_existing
        if week_start_str:
            try:
                week_start = _dt.datetime.strptime(week_start_str, "%Y-%m-%d").date()
            except Exception:
                return {"ok": False, "error": "week_start 格式应为 YYYY-MM-DD"}
        else:
            week_start = None  # 默认上周
        # 检查是否已有
        existing = _check_existing(week_start) if week_start else []
        result = generate_doc(week_start)
        if result.get("ok"):
            result["existing"] = existing
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/weekly/doc/preview")
def weekly_doc_preview(payload: dict | None = None):
    """预览工作周报数据 (不生成文件). payload: {week_start: 'YYYY-MM-DD'}"""
    import datetime as _dt
    from weekly_report_doc import _get_week_range, _analyze_week
    payload = payload or {}
    week_start_str = payload.get("week_start", "")
    try:
        if week_start_str:
            try:
                week_start = _dt.datetime.strptime(week_start_str, "%Y-%m-%d").date()
            except Exception:
                return {"ok": False, "error": "week_start 格式应为 YYYY-MM-DD"}
        else:
            week_start, week_end = _get_week_range()
        data = _analyze_week(week_start, week_start + _dt.timedelta(days=6))
        # 汇总每天分组计数
        summary = {}
        for day, msgs in data['daily'].items():
            group_counts = {}
            for m in msgs:
                for g in m['groups']:
                    group_counts[g] = group_counts.get(g, 0) + 1
            summary[day] = {
                'total': len(msgs),
                'groups': group_counts,
            }
        return {
            "ok": True,
            "week_start": week_start.strftime('%Y-%m-%d'),
            "week_end": (week_start + _dt.timedelta(days=6)).strftime('%Y-%m-%d'),
            "total_my_msgs": data['total_my'],
            "daily_summary": summary,
            "group_spans": {k: [v[0], v[1]] for k, v in data['group_spans'].items()},
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── 日报 ──

@app.get("/api/daily/dates")
def daily_dates():
    """返回有日报数据的日期列表, 供日历打点."""
    try:
        from weekly_api import list_daily_dates
        dates = list_daily_dates()
        return {"ok": True, "dates": dates}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/daily/report")
def daily_report(date: str = ""):
    """返回某天日报 -- LifeOS 文件优先, 事件聚合兜底."""
    if not date:
        import time
        date = time.strftime("%Y-%m-%d")
    try:
        from weekly_api import get_daily_report
        report = get_daily_report(date)
        report["ok"] = True
        return report
    except Exception as e:
        return {"ok": False, "error": str(e)}


# 若前端已 build, 由后端 serve 静态产物(单端口访问)
if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

    # SPA fallback: 深层路由(如 /projects /skills) 回退到 index.html
    from starlette.responses import FileResponse
    index_file = FRONTEND_DIST / "index.html"

    @app.exception_handler(404)
    async def spa_fallback(request, exc):
        # 仅对非 API 路径回退, API 404 保持原样
        if request.url.path.startswith("/api/"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        if request.url.path.startswith(("/assets/", "/favicon.ico")):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        if index_file.exists():
            return FileResponse(str(index_file))
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not Found"}, status_code=404)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("WB_PORT", "8899"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")