#!/usr/bin/env python3
"""独立日报生成入口 — launchd 定时调用, 无需依赖 HTTP 服务。

用法:
  python3 backend/daily_cli.py              # 生成今天日报 (AI 总结 + 写项目 README + 写 LifeOS 日报)
  python3 backend/daily_cli.py --date 2026-09-11  # 补生成指定日

日志:
  /tmp/workbench-daily.log
"""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from timeline.daily_report import commit_daily_report


def main():
    ap = argparse.ArgumentParser(description="个人工作台 — 定时日报生成器")
    ap.add_argument("--date", default="", help="日报日期 (YYYY-MM-DD), 默认今天")
    args = ap.parse_args()

    today = args.date or time.strftime("%Y-%m-%d")

    started = time.time()
    log_lines = []
    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 日报生成开始 ({today})")

    try:
        result = commit_daily_report(today)
        log_lines.append(f"  更新项目 README: {result.get('projects_updated', 0)} 个")
        log_lines.append(f"  事件总数: {result.get('events_total', 0)} 条")
        dpath = result.get("daily_path", "")
        if dpath:
            log_lines.append(f"  日报文件: {dpath}")
        else:
            log_lines.append("  日报文件: 写入失败 (可能无事件数据)")
        for r in result.get("results", []):
            if r.get("error"):
                log_lines.append(f"  项目 {r.get('project')} 失败: {r['error']}")
    except Exception as e:
        log_lines.append(f"  日报生成失败: {e}")

    elapsed = time.time() - started
    log_lines.append(f"  耗时: {elapsed:.1f}s")
    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 日报生成完成")
    log_lines.append("")

    full_log = "\n".join(log_lines)
    print(full_log, flush=True)

    log_file = Path("/tmp/workbench-daily.log")
    try:
        with open(log_file, "a") as f:
            f.write(full_log)
    except Exception:
        pass


if __name__ == "__main__":
    main()