#!/usr/bin/env python3
"""独立采集入口 — launchd 定时调用, 无需依赖 HTTP 服务。

用法:
  python3 backend/collect_cli.py              # 全量采集 (今天)
  python3 backend/collect_cli.py --date 2026-09-11  # 补采指定日
  python3 backend/collect_cli.py --lifecycle          # 采集 + 数据生命周期维护
  python3 backend/collect_cli.py --lifecycle --ttl 14 # 采集 + 清理14天前事件

日志:
  /tmp/workbench-collect.log  (launchd 运行时写这里)
  stderr 输出也打到同一个文件, 方便排查
"""

import argparse
import sys
import time
from pathlib import Path

# 确保能 import timeline 包
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from timeline import run_all_collectors, get_db


def main():
    ap = argparse.ArgumentParser(description="个人工作台 — 定时采集器")
    ap.add_argument("--date", default="", help="采集日期 (YYYY-MM-DD), 默认今天")
    ap.add_argument("--lifecycle", action="store_true", help="采集完后执行数据生命周期 (聚合+清理)")
    ap.add_argument("--ttl", type=int, default=30, help="事件保留天数 (默认30)")

    args = ap.parse_args()

    started = time.time()
    log_lines = []
    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 采集开始")
    if args.date:
        log_lines.append(f"  指定日期: {args.date}")

    # 1. 采集
    result = run_all_collectors()
    log_lines.append(f"  入库: {result['total_inserted']} 条")
    for src, info in sorted(result.get("sources", {}).items()):
        if info.get("status") == "background":
            log_lines.append(f"  {src}: 后台进行中")
        elif "error" in info:
            log_lines.append(f"  {src}: 失败 — {info['error']}")
        else:
            log_lines.append(f"  {src}: 扫描 {info.get('collected', 0)} 条, 入库 {info.get('inserted', 0)} 条")

    # 2. (可选) 生命周期
    lifecycle_result = None
    if args.lifecycle:
        db = get_db()
        try:
            lifecycle_result = db.lifecycle(args.ttl)
            log_lines.append(f"  生命周期: 聚合 {lifecycle_result.get('aggregated', 0)} 条, "
                           f"清理 {lifecycle_result.get('deleted', 0)} 条, "
                           f"剩余 {lifecycle_result.get('remaining_events', 0)} 条事件")
        except Exception as e:
            log_lines.append(f"  生命周期失败: {e}")

    elapsed = time.time() - started
    log_lines.append(f"  耗时: {elapsed:.1f}s")
    log_lines.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 采集完成")
    log_lines.append("")

    full_log = "\n".join(log_lines)
    print(full_log, flush=True)

    # 写日志文件
    log_file = Path("/tmp/workbench-collect.log")
    try:
        with open(log_file, "a") as f:
            f.write(full_log)
    except Exception:
        pass


if __name__ == "__main__":
    main()