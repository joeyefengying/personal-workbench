"""采集器框架 — 各数据源采集器基类 + 三个实现。

采集器约定:
  - collect() 返回事件 dict 列表, 每项含 add() 所需字段
  - 幂等: 依赖 db.add 的 dedup_key 去重, 可反复运行
  - 只读优先: 不修改源系统数据

数据源:
  - FileCollector    : 扫描指定目录的最近文件变化 (mtime 快照比对)
  - BrowserCollector : Chrome History / Safari History.db 访问记录
  - QingtuiCollector : 轻推消息 (只拉今天的 highlights, 防止网络请求过多)
  - GitCollector     : 各项目 git 提交 (复用 apps.json)
"""
import json
import os
import re
import sqlite3
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

HOME = Path.home()

# ---------------------------------------------------------------
# 采集器基类
# ---------------------------------------------------------------
class Collector:
    source = "base"
    name = "基础采集器"

    def collect(self, since_ms: int | None = None) -> list[dict]:
        raise NotImplementedError


# ---------------------------------------------------------------
# 文件变化采集器
# ---------------------------------------------------------------
# 监控的目录 (用户工作/项目目录, 排除 node_modules/.git 等)
WATCH_DIRS = [
    str(HOME / "Downloads" / "project"),
    str(HOME / "Downloads" / "笔记"),
    str(HOME / "Downloads" / "cisdi-work"),
    str(HOME / "Desktop"),
    str(HOME / "Documents"),
]

# 排除的子目录名
EXCLUDE_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", ".cache", ".DS_Store", ".obsidian",
    "__tests__", "__mocks__", "__snapshots__",  # 测试文件, 非人工产出
    "coverage", ".nyc_output",                  # 覆盖率产物
}

# 排除的子路径 (包含这些段的文件跳过)
EXCLUDE_PATH_SEGMENTS = [
    "version-monitor/snapshots",  # 低码快照目录 (自动生成, 非人工操作)
    "src_highcode",               # 低码 highcode 生成物 (自动构建产物)
    "low-code/apps/",             # 低码应用实例数据 (自动生成, 非人工操作)
]

# 关注的扩展名 (为空 = 全部)
INTERESTING_EXTS = {
    ".md", ".py", ".js", ".ts", ".vue", ".jsx", ".tsx", ".json",
    ".yaml", ".yml", ".html", ".css", ".sql", ".sh", ".go", ".rs",
    ".java", ".txt", ".pdf", ".png", ".jpg", ".jpeg", ".svg",
    ".drawio", ".excalidraw", ".canvas", ".base",
}

# 排除的文件后缀 (测试/快照文件)
EXCLUDE_EXTS = {
    ".spec.ts", ".spec.tsx", ".test.ts", ".test.tsx",
    ".spec.js", ".spec.jsx", ".test.js", ".test.jsx",
    ".snap",
}


class FileCollector(Collector):
    source = "files"
    name = "文件变化"

    def __init__(self, watch_dirs: list[str] | None = None, snapshot_file: Path | None = None):
        self.watch_dirs = watch_dirs or WATCH_DIRS
        self.snapshot_file = snapshot_file or (Path(__file__).resolve().parent / "file_snapshot.json")

    def _load_snapshot(self) -> dict:
        if self.snapshot_file.exists():
            try:
                return json.loads(self.snapshot_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_snapshot(self, snap: dict):
        self.snapshot_file.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")

    def _scan_dir(self, dirpath: str) -> dict[str, int]:
        """扫描目录, 返回 {路径: mtime}"""
        result = {}
        base = Path(dirpath)
        if not base.exists():
            return result
        for root, dirs, files in os.walk(base):
            # 剪枝排除目录
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
            for f in files:
                if f.startswith("."):
                    continue
                fp = Path(root) / f
                fp_str = str(fp)
                # 排除指定路径片段
                if any(seg in fp_str for seg in EXCLUDE_PATH_SEGMENTS):
                    continue
                if INTERESTING_EXTS and fp.suffix.lower() not in INTERESTING_EXTS:
                    continue
                # 排除测试/快照文件 (按完整后缀匹配, 如 button.spec.ts)
                lower_name = f.lower()
                if any(lower_name.endswith(ext) for ext in EXCLUDE_EXTS):
                    continue
                try:
                    result[fp_str] = int(fp.stat().st_mtime * 1000)
                except OSError:
                    continue
        return result

    def collect(self, since_ms: int | None = None) -> list[dict]:
        """比对快照, 产出新增/修改/删除事件."""
        old = self._load_snapshot()
        new = {}
        events = []

        # 全量扫描当前状态
        for d in self.watch_dirs:
            new.update(self._scan_dir(d))

        # 首次运行: 只建快照, 不产出事件 (避免历史全量灌入)
        if not old:
            self._save_snapshot(new)
            return events

        # 新增 & 修改
        for path, mtime in new.items():
            if path not in old:
                events.append(self._make_event("add", path, mtime))
            elif old[path] != mtime:
                events.append(self._make_event("mod", path, mtime))

        # 删除
        for path, mtime in old.items():
            if path not in new:
                events.append(self._make_event("del", path, mtime))

        self._save_snapshot(new)
        return events

    def _make_event(self, action: str, path: str, ts: int) -> dict:
        p = Path(path)
        rel = self._short_path(path)
        action_map = {"add": "新增", "mod": "修改", "del": "删除"}
        # 标题优先显示文件名, 太长则截断
        fname = p.name
        if len(fname) > 60:
            fname = fname[:57] + "..."
        return {
            "ts": ts,
            "source": self.source,
            "category": action,
            "action": action_map[action],
            "target": path,
            "title": f"{action_map[action]} {fname}",
            "detail": f"文件: {rel}",
            "meta": {"path": path, "ext": p.suffix.lower(), "size": self._file_size(p)},
        }

    @staticmethod
    def _short_path(path: str) -> str:
        h = str(HOME)
        if path.startswith(h):
            return "~" + path[len(h):]
        return path

    @staticmethod
    def _file_size(p: Path) -> int:
        try:
            return p.stat().st_size
        except OSError:
            return 0


# ---------------------------------------------------------------
# 浏览器历史采集器
# ---------------------------------------------------------------
CHROME_HISTORY = HOME / "Library/Application Support/Google/Chrome/Default/History"
CHROME_PROFILES = HOME / "Library/Application Support/Google/Chrome"
SAFARI_HISTORY = HOME / "Library/Safari/History.db"


class BrowserCollector(Collector):
    source = "browser"
    name = "浏览器访问"

    def _collect_chrome(self, since_ms: int) -> list[dict]:
        """采集 Chrome 历史, 按 date+domain 去重.
        
        去重策略: 同一天访问同一域名只产生 1 条事件 (title=该域名最频繁的页面),
        而不是每条 URL 一行。这样日均从 ~180 条降到 ~35 条。
        """
        # Chrome 可能多 profile
        history_files = []
        if CHROME_HISTORY.exists():
            history_files.append(CHROME_HISTORY)
        if CHROME_PROFILES.exists():
            for p in CHROME_PROFILES.iterdir():
                if p.is_dir() and (p / "History").exists() and p.name != "Default":
                    history_files.append(p / "History")

        # 收集中间列表: (date, domain, ts, title)
        raw = []
        chrome_epoch_offset = 11644473600000000

        for hf in history_files:
            try:
                import tempfile, shutil
                tmp = Path(tempfile.gettempdir()) / f"chrome_history_{os.getpid()}_{int(time.time()*1000)}.db"
                shutil.copy2(str(hf), str(tmp))
                conn = sqlite3.connect(str(tmp))
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """SELECT url, title, visit_count, last_visit_time
                       FROM urls ORDER BY last_visit_time DESC LIMIT 5000""",
                ).fetchall()
                for r in rows:
                    ts = (r["last_visit_time"] - chrome_epoch_offset) // 1000
                    if ts < since_ms:
                        continue
                    date = time.strftime("%Y-%m-%d", time.localtime(ts / 1000))
                    domain = self._domain(r["url"] or "")
                    title = (r["title"] or domain)[:120]
                    # 记录 (date, domain, ts, title, visit_count)
                    raw.append((date, domain, ts, title, r["visit_count"] or 1))
                conn.close()
                tmp.unlink(missing_ok=True)
            except Exception:
                continue

        # 去重: 按 (date, domain) 聚合, 累加 visit_count, 取最晚 ts + 最佳 title
        dedup = {}
        for date, domain, ts, title, vc in raw:
            key = (date, domain)
            if key not in dedup:
                dedup[key] = [ts, title, 0]
            if ts > dedup[key][0]:
                dedup[key][0] = ts
                if title and "http" not in title[:8]:
                    dedup[key][1] = title
            dedup[key][2] += vc  # 累加访问次数

        events = []
        for (date, domain), (ts, title, visits) in dedup.items():
            events.append({
                "ts": ts,
                "source": self.source,
                "category": "visit",
                "action": "浏览",
                "target": domain,
                "title": title or domain,
                "detail": domain,
                "meta": {"browser": "chrome", "domain": domain, "visits": visits},
                "dedup_key": f"browser|visit|{date}|{domain}",  # 单日每域名去重
            })
        return events

    def _collect_safari(self, since_ms: int) -> list[dict]:
        """Safari 采集, 同样 date+domain 去重."""
        events = []
        if not SAFARI_HISTORY.exists():
            return events
        try:
            import tempfile, shutil
            tmp = Path(tempfile.gettempdir()) / f"safari_history_{os.getpid()}_{int(time.time()*1000)}.db"
            shutil.copy2(str(SAFARI_HISTORY), str(tmp))
            conn = sqlite3.connect(str(tmp))
            conn.row_factory = sqlite3.Row
            APPLE_EPOCH = 978307200
            rows = conn.execute(
                """SELECT hi.url, hi.visit_count, hv.visit_time
                   FROM history_items hi
                   JOIN history_visits hv ON hi.id = hv.history_item
                   ORDER BY hv.visit_time DESC LIMIT 2000""",
            ).fetchall()
            raw = []
            for r in rows:
                visit_time = r["visit_time"]
                if visit_time < 1:
                    continue
                ts = int((visit_time + APPLE_EPOCH) * 1000)
                if ts < since_ms:
                    continue
                date = time.strftime("%Y-%m-%d", time.localtime(ts / 1000))
                domain = self._domain(r["url"] or "")
                raw.append((date, domain, ts))
            # 去重
            dedup = set()
            for date, domain, ts in raw:
                key = (date, domain)
                if key not in dedup:
                    dedup.add(key)
                    events.append({
                        "ts": ts, "source": self.source, "category": "visit",
                        "action": "浏览", "target": domain, "title": domain[:120],
                        "detail": domain,
                        "meta": {"browser": "safari", "domain": domain},
                        "dedup_key": f"browser|visit|{date}|{domain}",
                    })
            conn.close()
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        return events

    def collect(self, since_ms: int | None = None) -> list[dict]:
        since_ms = since_ms or (int(time.time() * 1000) - 24 * 3600 * 1000)
        events = self._collect_chrome(since_ms)
        # Safari 和 Chrome 去重合并 (同 domain 同日期只保留一条, 优先 Chrome)
        chrome_domains = {(e["meta"]["domain"], time.strftime("%Y-%m-%d", time.localtime(e["ts"]/1000)))
                          for e in events if e.get("meta", {}).get("domain")}
        safari_events = self._collect_safari(since_ms)
        for e in safari_events:
            key = (e["meta"]["domain"], time.strftime("%Y-%m-%d", time.localtime(e["ts"]/1000)))
            if key not in chrome_domains:
                events.append(e)
        return events

    @staticmethod
    def _domain(url: str) -> str:
        m = re.match(r"https?://([^/]+)", url or "")
        return m.group(1) if m else (url or "")[:60]


# ---------------------------------------------------------------
# 轻推事件采集器 (SQLite 直读 csp4.db, 不需要调试端口)
# ---------------------------------------------------------------
QINGTUI_DB = HOME / "Library/Application Support/Qingtui/sqlite/344548d972f44d799aeea39ae3e231ba/csp4.db"
QINGTUI_ME = "344548d972f44d799aeea39ae3e231ba"

QINGTUI_WORK_KEYWORDS = [
    "共享运营", "会计引擎", "财务", "低开", "低码",
    "平台组", "平台支撑", "基础框架", "流程引擎", "消息中心",
    "文件中心", "任务中心", "统一密码", "UX", "PRD",
    "测试", "联调", "部署", "发版", "攻坚",
    "主数据", "合同台账", "应付", "报账", "资产",
    "票据", "影像", "安全合规", "性能测试",
    "日报", "实施", "配置", "环境",
    "前端", "开发", "统建", "五矿", "应用架构",
    "智慧政企", "平台业务部", "核心研发",
    "财务管控", "财务组", "ACoding", "数据建模",
    "需求", "评审", "值班",
]


class QingtuiCollector(Collector):
    source = "qingtui"
    name = "轻推消息"

    def _channel_names(self) -> dict:
        try:
            conn = sqlite3.connect(str(QINGTUI_DB))
            rows = conn.execute("SELECT id, name FROM channel_detail").fetchall()
            conn.close()
            return {r[0]: r[1] for r in rows}
        except Exception:
            return {}

    def _is_work_channel(self, name: str) -> bool:
        for kw in QINGTUI_WORK_KEYWORDS:
            if kw in name:
                return True
        return False

    def _extract_body(self, content: str, body: str) -> str:
        """从消息中提取纯文本.
        
        body 字段直接存了纯文本 (亿级消息量优化).
        如果 body 为空, 从 content JSON 里解析 body 字段.
        """
        body = (body or "").strip()
        if body:
            return body
        content = (content or "").strip()
        if not content:
            return ""
        # 尝试从 content JSON 中解析 body
        try:
            import json
            obj = json.loads(content)
            return str(obj.get("body", ""))
        except Exception:
            return ""

    def collect(self, since_ms: int | None = None) -> list[dict]:
        """从 csp4.db 直接读今天的消息 + 别人@我的, 不依赖调试端口."""
        events = []
        if not QINGTUI_DB.exists():
            return events

        since_ms = since_ms or (int(time.time() * 1000) - 24 * 3600 * 1000)
        today = time.strftime("%Y-%m-%d")
        channel_names = self._channel_names()

        try:
            conn = sqlite3.connect(str(QINGTUI_DB))
            conn.row_factory = sqlite3.Row
        except Exception:
            return events

        my_msgs = []
        mention_msgs = []

        for i in range(60):
            try:
                rows = conn.execute(
                    f'SELECT create_time, chat_id, content, body, "from" FROM message_{i} '
                    f'WHERE create_time>=? ORDER BY create_time DESC LIMIT 300',
                    (since_ms,)).fetchall()
                for r in rows:
                    body = self._extract_body(r["content"], r["body"])
                    if not body:
                        continue
                    body = re.sub(r'\[图片\]|\[文件\]|\[协作文档\]|\[语音\]|\[视频\]|\[位置\]', '', body).strip()
                    if not body:
                        continue
                    msg = {
                        "ts": int(r["create_time"]),
                        "chat_id": r["chat_id"],
                        "body": body,
                        "from": r["from"],
                    }
                    if r["from"] == QINGTUI_ME:
                        my_msgs.append(msg)
                    elif any(kw in body for kw in ("@张浩", "@我", "@所有人")):
                        mention_msgs.append(msg)
            except Exception:
                pass
        conn.close()

        # 合并: 我发的 + 别人@我的
        all_msgs = my_msgs + mention_msgs

        # 去重
        seen_content = set()
        for m in sorted(all_msgs, key=lambda x: x["ts"]):
            cname = channel_names.get(m["chat_id"], m["chat_id"])
            if not self._is_work_channel(cname):
                continue
            fingerprint = m["body"].strip()[:80]
            if fingerprint in seen_content:
                continue
            seen_content.add(fingerprint)

            # 区分事件类型
            is_mine = m["from"] == QINGTUI_ME
            action = "发言" if is_mine else ("@我" if "@张浩" in m["body"] or "@我" in m["body"] else "@所有人")
            category = "msg" if is_mine else "mention"

            import hashlib
            fp = hashlib.md5(m["body"].encode("utf-8", errors="ignore")).hexdigest()[:12]
            events.append({
                "ts": m["ts"],
                "source": self.source,
                "category": category,
                "action": action,
                "target": cname,
                "title": m["body"][:120],
                "detail": m["body"],
                "meta": {"session": cname, "kind": "mine" if is_mine else "mention"},
                "dedup_key": f"qingtui|{category}|{today}|{fp}",
            })

        return events


# ---------------------------------------------------------------
# Git 提交采集器 (复用 apps.json)
# ---------------------------------------------------------------
class GitCollector(Collector):
    source = "git"
    name = "Git 提交"

    def __init__(self, apps_json: Path | None = None):
        self.apps_json = apps_json or (Path(__file__).resolve().parent.parent / "apps.json")

    def _projects(self) -> list[tuple[str, str]]:
        """返回 [(path, name)]"""
        if not self.apps_json.exists():
            return []
        try:
            cfg = json.loads(self.apps_json.read_text(encoding="utf-8"))
            result = []
            for cat in cfg.get("categories", []):
                for proj in cat.get("projects", []):
                    p = Path(proj.get("path", "")).expanduser()
                    if p.exists():
                        result.append((str(p), proj.get("name", p.name)))
            return result
        except Exception:
            return []

    def collect(self, since_ms: int | None = None) -> list[dict]:
        since_ms = since_ms or (int(time.time() * 1000) - 24 * 3600 * 1000)
        since_dt = datetime.fromtimestamp(since_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")
        events = []
        for path, name in self._projects():
            if not (Path(path) / ".git").exists():
                continue
            try:
                r = subprocess.run(
                    ["git", "-C", path, "log", "--since", since_dt,
                     "--pretty=format:%at|%an|%s"],
                    capture_output=True, text=True, timeout=10)
                for line in r.stdout.strip().splitlines():
                    if "|" not in line:
                        continue
                    ts_str, author, subject = line.split("|", 2)
                    ts = int(ts_str) * 1000
                    events.append({
                        "ts": ts,
                        "source": self.source,
                        "category": "commit",
                        "action": "提交",
                        "target": name,
                        "title": subject[:120],
                        "detail": f"{name}: {subject}",
                        "meta": {"project": name, "author": author},
                    })
            except Exception:
                continue
        return events


# ---------------------------------------------------------------
# 统一运行入口
# 按速度排序: 快渠道在前, 慢渠道 (轻推) 放最后并行
FAST_COLLECTORS = [FileCollector, BrowserCollector, GitCollector, QingtuiCollector]
SLOW_COLLECTORS = []  # 轻推已改为 SQLite 直读, 不再需要后台采集


def run_all_collectors(since_ms: int | None = None, db=None) -> dict:
    """运行所有采集器, 写入事件库.

    快渠道 (文件/浏览器/Git) 同步串行, 轻推后台并行 (不阻塞总耗时).
    轻推采集结果通过 /api/timeline/collect 轮询确认.
    """
    from .db import get_db
    db = db or get_db()
    result = {"sources": {}, "total_inserted": 0}

    # 快渠道: 同步
    for cls in FAST_COLLECTORS:
        try:
            collector = cls()
            events = collector.collect(since_ms=since_ms)
            inserted = db.add_many(events)
            result["sources"][collector.source] = {
                "collected": len(events), "inserted": inserted,
            }
            result["total_inserted"] += inserted
        except Exception as e:
            result["sources"][cls.source] = {"error": str(e)}

    # 慢渠道 (轻推): 后台并行 (不阻塞其他渠道的结果返回)
    def _bg_qingtui():
        try:
            collector = QingtuiCollector()
            events = collector.collect(since_ms=since_ms)
            inserted = db.add_many(events)
            result["sources"][collector.source] = {
                "collected": len(events), "inserted": inserted,
            }
            result["total_inserted"] += inserted
        except Exception as e:
            result["sources"]["qingtui"] = {"error": str(e)}
    import threading
    t = threading.Thread(target=_bg_qingtui, daemon=True)
    t.start()
    result["sources"]["qingtui"] = {"status": "background", "note": "轻推采集在后台进行 (~2-3分钟), 完成后数据自动入库"}

    return result