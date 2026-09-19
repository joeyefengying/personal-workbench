#!/usr/bin/env python3
"""数据生命周期清理 — 定时调用, 不会启动 HTTP 服务。

清理项:
  1. events.db: 聚合 → 删除过期事件 → VACUUM (TTL 默认 30 天)
  2. performance/reports/: 删除超过 6 个月的周报/月报 JSON
  3. file_snapshot.json: 保留 (全量覆盖, 不单独清理)

用法:
  python3 backend/cleanup_cli.py              # 默认 TTL=30天
  python3 backend/cleanup_cli.py --ttl 14     # 保留 14 天

日志: /tmp/workbench-cleanup.log
"""

import argparse
import sys
import time
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def cleanup_events_db(ttl_days: int) -> dict:
    """清理 events.db: 聚合 → 删除 → VACUUM."""
    from timeline import get_db
    db = get_db()
    result = db.lifecycle(ttl_days)
    return result


def cleanup_performance_reports(max_months: int = 6) -> dict:
    """清理 performance/reports/ 下超过 max_months 个月的 JSON 文件."""
    import datetime
    reports_dir = ROOT / "performance" / "reports"
    if not reports_dir.exists():
        return {"deleted": 0, "scanned": 0}

    cutoff = datetime.date.today() - datetime.timedelta(days=max_months * 30)
    deleted = []
    scanned = 0

    for pattern in ["weekly/*.json", "monthly/*.json"]:
        for fp in (reports_dir).glob(pattern):
            if fp.name == "latest.json":
                continue
            scanned += 1
            # 从文件名提取日期: 2026-W38.json / 2026-08.json
            stem = fp.stem  # 2026-W38 or 2026-08
            try:
                if "-W" in stem:
                    # 周报: 2026-W38 → 取该周一日期
                    year, week = stem.split("-W")
                    iso_date = datetime.date.fromisocalendar(int(year), int(week), 1)
                elif "-" in stem:
                    # 月报: 2026-08
                    year, month = stem.split("-")
                    iso_date = datetime.date(int(year), int(month), 1)
                else:
                    continue
                if iso_date < cutoff:
                    fp.unlink()
                    deleted.append(fp.name)
            except Exception:
                continue

    return {"deleted": len(deleted), "deleted_files": deleted, "scanned": scanned, "cutoff": str(cutoff)}


def main():
    ap = argparse.ArgumentParser(description="个人工作台 — 数据清理")
    ap.add_argument("--ttl", type=int, default=30, help="events.db 事件保留天数 (默认30)")
    ap.add_argument("--report-months", type=int, default=6, help="performance/reports 保留月数 (默认6)")
    args = ap.parse_args()

    started = time.time()
    log_lines = []
    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 数据清理开始")

    # 1. events.db
    try:
        ev_result = cleanup_events_db(args.ttl)
        log_lines.append(f"  [events.db] 聚合 {ev_result.get('aggregated', 0)} 条, "
                         f"清理 {ev_result.get('deleted', 0)} 条, "
                         f"剩余 {ev_result.get('remaining_events', 0)} 条事件, "
                         f"摘要 {ev_result.get('summary_total', 0)} 条")
    except Exception as e:
        log_lines.append(f"  [events.db] 失败: {e}")

    # 2. performance/reports
    try:
        perf_result = cleanup_performance_reports(args.report_months)
        log_lines.append(f"  [reports] 扫描 {perf_result['scanned']} 文件, "
                         f"删除 {perf_result['deleted']} 个过期报告 "
                         f"(cutoff={perf_result['cutoff']})")
        if perf_result.get("deleted_files"):
            log_lines.append(f"    已删: {', '.join(perf_result['deleted_files'])}")
    except Exception as e:
        log_lines.append(f"  [reports] 失败: {e}")

    elapsed = time.time() - started
    log_lines.append(f"  耗时: {elapsed:.1f}s")
    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 清理完成")
    log_lines.append("")

    full_log = "\n".join(log_lines)
    print(full_log, flush=True)

    # 写日志
    log_file = Path("/tmp/workbench-cleanup.log")
    try:
        with open(log_file, "a") as f:
            f.write(full_log)
    except Exception:
        pass


if __name__ == "__main__":
    main()
