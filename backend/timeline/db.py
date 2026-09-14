"""SQLite 事件库 — 统一时间线的存储层。

表结构:
  events: (id, ts, date, source, category, action, target, title, detail, meta, created_at)
    - ts       : 事件发生时间戳 (Unix ms, 可索引)
    - date     : 事件所属日期 YYYY-MM-DD (便于按天聚合)
    - source   : 数据源 files|browser|qingtui|git|...
    - category : 业务分类 (如 qingtui:task|msg, files:add|mod|del)
    - action   : 动作描述
    - target   : 目标对象 (文件路径/URL/会话名/项目名)
    - title    : 标题/摘要 (短文本, 用于时间线直接展示)
    - detail   : 详情 (长文本)
    - meta     : JSON 元数据 (源系统补充字段, 前端可选展示)

设计原则:
  - 只读优先, 采集器幂等 (重复采集不重复入库, 用 source+target+ts 去重)
  - 高可用: 写入用 WAL 模式 + 连接池, 查询走索引
"""
import json
import os
import sqlite3
import threading
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "events.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        INTEGER NOT NULL,             -- Unix ms
    date      TEXT    NOT NULL,             -- YYYY-MM-DD
    source    TEXT    NOT NULL,             -- files|browser|qingtui|git|...
    category  TEXT    DEFAULT '',           -- 业务分类
    action    TEXT    DEFAULT '',           -- 动作
    target    TEXT    DEFAULT '',           -- 目标对象
    title     TEXT    DEFAULT '',           -- 标题/摘要
    detail    TEXT    DEFAULT '',           -- 详情
    meta      TEXT    DEFAULT '{}',         -- JSON 元数据
    dedup_key TEXT    DEFAULT '',           -- 去重键 (source|category|target|ts)
    created_at INTEGER NOT NULL             -- 入库时间 Unix ms
);

CREATE INDEX IF NOT EXISTS idx_events_ts       ON events(ts DESC);
CREATE INDEX IF NOT EXISTS idx_events_date     ON events(date);
CREATE INDEX IF NOT EXISTS idx_events_source   ON events(source);
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);
CREATE INDEX IF NOT EXISTS idx_events_dedup    ON events(dedup_key);
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_dedup_unique ON events(dedup_key)
    WHERE dedup_key != '';

-- 汇总层: 永久保留的聚合统计 (体积最小, 供周报/月报/趋势)
CREATE TABLE IF NOT EXISTS summary_events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    date     TEXT    NOT NULL,          -- YYYY-MM-DD
    source   TEXT    NOT NULL,          -- files|browser|qingtui|git
    dimension TEXT   NOT NULL,          -- 聚合维度 (domain|project|session|path 等)
    dim_key  TEXT    NOT NULL,          -- 维度值 (如域名/项目名/会话名)
    count    INTEGER NOT NULL DEFAULT 0, -- 当日计数
    meta     TEXT    DEFAULT '{}',       -- 附加 (主题分布等)
    UNIQUE(date, source, dimension, dim_key)
);
CREATE INDEX IF NOT EXISTS idx_summary_date ON summary_events(date);
CREATE INDEX IF NOT EXISTS idx_summary_source ON summary_events(source);
"""


class EventDB:
    """线程安全的事件库封装 (WAL + 每线程连接)."""

    def __init__(self, path: Path = DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._lock = threading.Lock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._connect()
            self._local.conn = conn
        return conn

    def _init(self):
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(SCHEMA)
                conn.commit()
            finally:
                conn.close()

    # ---------------------------------------------------------------
    # 写入
    # ---------------------------------------------------------------
    def add(self, ts: int, source: str, category: str = "", action: str = "",
            target: str = "", title: str = "", detail: str = "",
            meta: dict | None = None, dedup_key: str | None = None) -> bool:
        """插入一条事件. 返回是否真的插入 (False = 重复跳过).

        dedup_key: 为空则自动生成 source|category|target|ts.
        幂等: 相同 dedup_key 只保留首条.
        """
        ts = int(ts)
        date = time.strftime("%Y-%m-%d", time.localtime(ts / 1000))
        if dedup_key is None:
            dedup_key = f"{source}|{category}|{target}|{ts}"
        if meta is None:
            meta = {}
        conn = self._conn()
        try:
            conn.execute(
                """INSERT OR IGNORE INTO events
                   (ts, date, source, category, action, target, title, detail, meta, dedup_key, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (ts, date, source, category, action, target, title, detail,
                 json.dumps(meta, ensure_ascii=False), dedup_key, int(time.time() * 1000)),
            )
            conn.commit()
            return conn.total_changes > 0
        except sqlite3.OperationalError:
            # 并发写冲突时重试一次
            try:
                conn.rollback()
                conn.execute(
                    """INSERT OR IGNORE INTO events
                       (ts, date, source, category, action, target, title, detail, meta, dedup_key, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (ts, date, source, category, action, target, title, detail,
                     json.dumps(meta, ensure_ascii=False), dedup_key, int(time.time() * 1000)),
                )
                conn.commit()
                return conn.total_changes > 0
            except Exception:
                return False

    def add_many(self, events: list[dict]) -> int:
        """批量插入. 返回实际插入条数."""
        inserted = 0
        for e in events:
            if self.add(**e):
                inserted += 1
        return inserted

    # ---------------------------------------------------------------
    # 查询
    # ---------------------------------------------------------------
    def _row_to_dict(self, row) -> dict:
        return {
            "id": row[0], "ts": row[1], "date": row[2], "source": row[3],
            "category": row[4], "action": row[5], "target": row[6],
            "title": row[7], "detail": row[8],
            "meta": json.loads(row[9] or "{}"),
        }

    def query(self, date: str = "", source: str = "", category: str = "",
              limit: int = 100, offset: int = 0, search: str = "") -> tuple[list[dict], int]:
        """查询事件 + 总数. 返回 (events, total)."""
        where = []
        params = []
        if date:
            where.append("date = ?")
            params.append(date)
        if source:
            where.append("source = ?")
            params.append(source)
        if category:
            where.append("category = ?")
            params.append(category)
        if search:
            where.append("(title LIKE ? OR detail LIKE ? OR target LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like])

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        conn = self._conn()
        total = conn.execute(
            f"SELECT COUNT(*) FROM events {where_sql}", params).fetchone()[0]
        rows = conn.execute(
            f"""SELECT id, ts, date, source, category, action, target, title, detail, meta
                FROM events {where_sql}
                ORDER BY ts DESC LIMIT ? OFFSET ?""",
            params + [limit, offset]).fetchall()
        return [self._row_to_dict(r) for r in rows], total

    def stats(self, date: str = "") -> dict:
        """按天/源/分类聚合统计."""
        conn = self._conn()
        where = "WHERE date = ?" if date else ""
        params = [date] if date else []

        total = conn.execute(f"SELECT COUNT(*) FROM events {where}", params).fetchone()[0]

        by_source = {}
        for row in conn.execute(
                f"SELECT source, COUNT(*) FROM events {where} GROUP BY source", params):
            by_source[row[0]] = row[1]

        by_category = {}
        for row in conn.execute(
                f"SELECT source, category, COUNT(*) FROM events {where} GROUP BY source, category", params):
            by_category.setdefault(row[0], {})[row[1] or "other"] = row[2]

        # 活跃日期范围
        date_range = conn.execute(
            "SELECT MIN(date), MAX(date) FROM events").fetchone()
        return {
            "total": total,
            "by_source": by_source,
            "by_category": by_category,
            "date_range": {"min": date_range[0], "max": date_range[1]},
        }

    def distinct_dates(self, limit: int = 60) -> list[str]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT DISTINCT date FROM events ORDER BY date DESC LIMIT ?", (limit,)).fetchall()
        return [r[0] for r in rows]

    def daily_summary(self, date: str) -> dict:
        """某天的结构化总结 (给前端 + Obsidian 日报用)."""
        events, total = self.query(date=date, limit=100000)
        summary = {
            "date": date,
            "total": total,
            "by_source": {},
            "files": [],
            "browser": [],
            "qingtui": [],
            "git": [],
            "other": [],
        }
        for e in events:
            src = e["source"]
            summary["by_source"][src] = summary["by_source"].get(src, 0) + 1
            bucket = summary.get(src, summary["other"])
            bucket.append(e)
        return summary

    def close(self):
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None

    # ---------------------------------------------------------------
    # 数据生命周期 — 聚合 + 清理
    # ---------------------------------------------------------------
    def aggregate_to_summary(self, date: str | None = None) -> int:
        """把 events 聚合到 summary_events 表 (幂等, 用 UNIQUE 约束).
        
        聚合维度:
          browser: 按 domain 每日计数
          qingtui: 按 session 每日计数 (附主题分布)
          git:     按 project 每日计数
          files:   按 parent_dir 每日计数
        返回新写入 summary 的行数.
        """
        date_clause = "date = ?" if date else "1=1"
        params = [date] if date else []
        conn = self._conn()
        inserted = 0

        # browser: domain 聚合 (用 meta.visits 累加而非 COUNT)
        for row in conn.execute(f"""
            SELECT date, json_extract(meta, '$.domain') as dim,
                   json_extract(meta, '$.visits') as vc
            FROM events WHERE source='browser' AND {date_clause}
        """, params):
            try:
                visits = int(row[2]) if row[2] else 1
                conn.execute(
                    """INSERT INTO summary_events (date, source, dimension, dim_key, count)
                       VALUES (?, 'browser', 'domain', ?, ?)
                       ON CONFLICT(date, source, dimension, dim_key)
                       DO UPDATE SET count = count + excluded.count""",
                    (row[0], row[1] or "unknown", visits))
                inserted += conn.total_changes
            except Exception:
                continue

        # qingtui: session 聚合
        for row in conn.execute(f"""
            SELECT date, meta->>'$."session"' as dim, COUNT(*) as cnt
            FROM events WHERE source='qingtui' AND {date_clause}
            GROUP BY date, dim
        """, params):
            try:
                conn.execute(
                    """INSERT INTO summary_events (date, source, dimension, dim_key, count)
                       VALUES (?, 'qingtui', 'session', ?, ?)
                       ON CONFLICT(date, source, dimension, dim_key)
                       DO UPDATE SET count = excluded.count""",
                    (row[0], row[1] or "unknown", row[2]))
                inserted += conn.total_changes
            except Exception:
                continue

        # git: project 聚合
        for row in conn.execute(f"""
            SELECT date, target, COUNT(*) as cnt
            FROM events WHERE source='git' AND {date_clause}
            GROUP BY date, target
        """, params):
            try:
                conn.execute(
                    """INSERT INTO summary_events (date, source, dimension, dim_key, count)
                       VALUES (?, 'git', 'project', ?, ?)
                       ON CONFLICT(date, source, dimension, dim_key)
                       DO UPDATE SET count = excluded.count""",
                    (row[0], row[1] or "unknown", row[2]))
                inserted += conn.total_changes
            except Exception:
                continue

        conn.commit()
        return inserted

    def cleanup_events(self, ttl_days: int = 30) -> int:
        """删除超过 TTL 的 events (数据已聚合进 summary).
        返回删除行数."""
        conn = self._conn()
        deleted = conn.execute(
            "DELETE FROM events WHERE date < date('now', ?)",
            (f'-{ttl_days} days',)).rowcount
        conn.commit()
        return deleted

    def vacuum(self):
        """压缩 SQLite WAL 回主文件, 回收空间."""
        conn = self._connect()
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("VACUUM")
        finally:
            conn.close()

    def lifecycle(self, ttl_days: int = 30) -> dict:
        """执行完整数据生命周期: 聚合 → 清理 → VACUUM.
        返回执行结果统计."""
        import datetime
        today = datetime.date.today().strftime("%Y-%m-%d")
        result = {}

        # 1. 聚合 (按天, 从最早到最新)
        days = self.distinct_dates()
        total_aggregated = 0
        for d in days:
            total_aggregated += self.aggregate_to_summary(d)
        result["aggregated"] = total_aggregated

        # 2. 清理过期事件
        deleted = self.cleanup_events(ttl_days)
        result["deleted"] = deleted

        # 3. 剩余事件数
        remaining = self._conn().execute("SELECT COUNT(*) FROM events").fetchone()[0]
        result["remaining_events"] = remaining

        # 4. 汇总层总量
        summary_total = self._conn().execute("SELECT COUNT(*) FROM summary_events").fetchone()[0]
        result["summary_total"] = summary_total

        # 5. VACUUM
        self.vacuum()
        result["vacuumed"] = True

        return result


_db_singleton = None
_db_lock = threading.Lock()


def get_db() -> EventDB:
    global _db_singleton
    with _db_lock:
        if _db_singleton is None:
            _db_singleton = EventDB()
        return _db_singleton


def migrate():
    """显式触发建表/迁移 (幂等)."""
    get_db()