"""工作周报 DOC 生成器 — 从轻推 SQLite 提取上周数据, 按模板生成 .doc 文件.

模板: 五矿财务管控产研_工作周报_（组别） 模板.doc
输出: 五矿财务管控产研_工作周报_张浩（共享运营）_{上周周一}.doc
"""
import datetime
import os
import re
from pathlib import Path

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

TEMPLATE_NAME = "五矿财务管控产研_工作周报_（组别） 模板.doc"
TEMPLATE_PATHS = [
    Path(__file__).parent / "templates" / "weekly_report_template.doc",
    Path.home() / "Downloads" / "我的项目" / "2026 年 1 月 7 日集团统建项目"
    / "财务系统" / "04. 应付" / "周报" / TEMPLATE_NAME,
    Path.home() / "Downloads" / "我的项目" / "2026 年 1 月 7 日集团统建项目"
    / "财务系统" / "04. 应付" / "周报" / "五矿财务管控产研_工作周报_（组别） 模板.doc",
    Path.home() / "Downloads" / "我的项目" / "2026 年 1 月 7 日集团统建项目"
    / "财务系统" / "04. 应付" / "周报" / "五矿财务管控产研_工作周报_张浩（共享运营）_模板.doc",
]
OUTPUT_DIRS = [
    Path.home() / "Downloads" / "我的项目" / "2026 年 1 月 7 日集团统建项目"
    / "财务系统" / "04. 应付" / "周报",
    Path.home() / "Downloads" / "我的项目" / "2026 年 1 月 7 日集团统建项目"
    / "财务系统" / "10. 共享运营" / "周报",
]

# ---------------------------------------------------------------
# 工作识别关键词 (与 qingtui_sqlite 保持一致)
# ---------------------------------------------------------------
WORK_GROUPS = [
    ("环境部署/发版", ["发版", "分支", "hotfix", "部署", "压测", "stg", "准生产",
                      "命名空间", "k8s", "打包", "发布", "重启", "release"]),
    ("主数据/一致性", ["主数据", "一致性", "数据同步", "卡死", "分流", "数据对账",
                      "重新推送", "重复数据", "离线", "期初"]),
    ("代码安全扫描", ["安全扫描", "安恒", "奇安信", "SCA", "SAST", "堡垒机",
                     "lodash", "axios", "漏洞", "代码审计", "扫描"]),
    ("UX 改造", ["UX", "用户名", "间距", "样式", "改造", "设计页面", "915", "收口"]),
    ("应付/报账支撑", ["应付", "报账", "联查凭证", "isShow", "显影", "bug", "缺陷",
                      "支付申请池", "ONES", "联调"]),
    ("权限/账号", ["账号", "权限", "4A", "密码", "申请", "实施定制", "堡垒机", "登录",
                  "网络权限", "中冶"]),
]

SKIP_BODY = {'好的', '收到', '了解', '嗯', 'ok', 'okk', 'OK', '👌', '图片', '[图片]',
             '1', '对', '是的', '可以', '行', '在', '没', '有', '无', '？', '?',
             '👌👌', '好', '嗯嗯', '。', '..', '...'}


def _find_template():
    for p in TEMPLATE_PATHS:
        if p.exists():
            return p
    return None


def _ensure_dirs():
    for d in OUTPUT_DIRS:
        os.makedirs(d, exist_ok=True)


def _get_week_range(ref_date: datetime.date = None) -> tuple:
    """返回上周一和上周日的日期对象."""
    if ref_date is None:
        ref_date = datetime.date.today()
    # this Monday = ref_date - ref_date.weekday()
    this_monday = ref_date - datetime.timedelta(days=ref_date.weekday())
    last_monday = this_monday - datetime.timedelta(days=7)
    last_sunday = last_monday + datetime.timedelta(days=6)
    return last_monday, last_sunday


def _classify_body(body: str) -> list:
    """返回匹配的工作分组名列表."""
    hits = []
    for name, kws in WORK_GROUPS:
        if any(kw in body for kw in kws):
            hits.append(name)
    return hits


def _extract_my_messages(start_ms: int, end_ms: int) -> list:
    """从 SQLite 提取指定时间范围内我发的实质消息."""
    from timeline.qingtui_sqlite import iter_messages, get_channels, ME
    channels = get_channels()
    msgs = iter_messages(start_ms, end_ms, mine_only=True)
    out = []
    for m in msgs:
        body = m['body']
        if not body or body in SKIP_BODY or len(body) < 6:
            continue
        if '@所有人' in body:
            continue
        cname = channels.get(m['chat_id'], {}).get('name', m['chat_id'][:8])
        ts = datetime.datetime.fromtimestamp(m['ts'] / 1000)
        out.append({
            'time': ts.strftime('%H:%M'),
            'date': ts.strftime('%m-%d'),
            'ts': m['ts'],
            'channel': cname,
            'body': body[:200],
            'groups': _classify_body(body),
        })
    return out


def _analyze_week(start_day: datetime.date, end_day: datetime.date) -> dict:
    """分析一周工作数据."""
    import collections
    daily_msgs = {}
    all_msgs = []
    group_days = collections.defaultdict(set)

    for i in range(7):
        d = start_day + datetime.timedelta(days=i)
        day = d.strftime('%Y-%m-%d')
        day_dt = datetime.datetime(d.year, d.month, d.day)
        start_ms = int(day_dt.timestamp() * 1000)
        end_ms = start_ms + 24 * 3600 * 1000
        msgs = _extract_my_messages(start_ms, end_ms)
        daily_msgs[day] = msgs
        all_msgs.extend(msgs)
        for m in msgs:
            for g in m['groups']:
                group_days[g].add(d.strftime('%m-%d'))

    # 汇总每个工作分组的起止日期
    group_date_range = {}
    for g, days_set in group_days.items():
        sorted_days = sorted(days_set)
        group_date_range[g] = (sorted_days[0], sorted_days[-1])

    return {
        'daily': daily_msgs,
        'all': all_msgs,
        'total_my': len(all_msgs),
        'group_spans': group_date_range,
    }


# ---------------------------------------------------------------
# DOC 生成
# ---------------------------------------------------------------
def _set_cell(cell, text, bold=False, align='left', size=10.5):
    cell.text = ''
    p = cell.paragraphs[0]
    if align == 'center':
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(str(text))
    run.font.name = '宋体'
    run.font.size = Pt(size)
    run.font.bold = bold
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    tcPr = cell._tc.get_or_add_tcPr()
    vAlign = OxmlElement('w:vAlign')
    vAlign.set(qn('w:val'), 'center')
    tcPr.append(vAlign)


def _fetch_weekly_report_data(week_start: datetime.date) -> dict:
    """从 weekly_api 获取周报数据, 供工作周报 doc 生成使用."""
    try:
        from weekly_api import get_weekly_report
        # week_label 格式: 2026-W37
        iso_year, iso_week, _ = week_start.isocalendar()
        week_label = f"{iso_year}-W{iso_week:02d}"
        report = get_weekly_report(week_label)
        return report or {}
    except Exception:
        return {}


def _build_work_items_from_data(week_start: datetime.date, data: dict, group_spans: dict) -> list:
    """从周报数据动态生成工作内容条目.

    优先用 git.by_project 的项目分组 + commit 主题汇总,
    结合 qingtui 的 group_spans 填充日期范围.
    """
    ws_fmt = week_start.strftime('%m月%d日')
    we_fmt = (week_start + datetime.timedelta(days=6)).strftime('%m月%d日')

    git_by_project = (data.get('git') or {}).get('by_project', {})
    ai_summary = data.get('ai_summary', '')

    work_items = []
    idx = 1

    # 按项目分组生成工作项
    for proj_name, proj_data in git_by_project.items():
        commits = proj_data.get('commits', [])
        if not commits:
            continue

        # 汇总 commit 主题, 去重前缀
        subjects = []
        seen_prefix = set()
        for c in commits:
            s = c.get('subject', '')
            # 取前 8 字做去重前缀
            prefix = s[:8]
            if prefix not in seen_prefix:
                seen_prefix.add(prefix)
                # 清理 subject 中的特殊字符
                clean = s.replace('\n', ' ').strip()
                if len(clean) > 80:
                    clean = clean[:77] + '...'
                subjects.append(clean)

        # 组装描述: 项目名 + N 条 commit 概要
        desc_parts = [f"{proj_name}（{proj_data.get('count', len(commits))} 次提交）："]
        for s in subjects[:5]:
            desc_parts.append(f"  · {s}")
        if len(subjects) > 5:
            desc_parts.append(f"  · ...等 {len(subjects)} 项")
        desc = '\n'.join(desc_parts)

        # 日期范围: 从 commits 的 date 字段提取
        dates = sorted(set(c.get('date', '') for c in commits if c.get('date')))
        start_date = dates[0][5:].replace('-', '/') if dates else ws_fmt.replace('月', '/').replace('日', '')
        end_date = dates[-1][5:].replace('-', '/') if dates else we_fmt.replace('月', '/').replace('日', '')

        work_items.append((
            str(idx), desc, '张浩', '已完成' if len(commits) > 2 else '进行中',
            start_date, '', end_date
        ))
        idx += 1

    # 如果没有 git 数据, 用 AI 总结生成兜底条目
    if not work_items and ai_summary:
        work_items.append((
            '1', ai_summary[:200], '张浩', '进行中',
            ws_fmt.replace('月', '/').replace('日', ''), '', we_fmt.replace('月', '/').replace('日', '')
        ))

    # 确保至少有 1 条
    if not work_items:
        work_items.append((
            '1', '本周工作内容待补充。', '张浩', '进行中',
            ws_fmt.replace('月', '/').replace('日', ''), '', we_fmt.replace('月', '/').replace('日', '')
        ))

    return work_items


def _build_next_week_plans(ai_summary: str) -> list:
    """从 AI 总结提取下周计划, 或用默认计划."""
    # 尝试从 AI 总结中提取关键方向
    plans = []
    if ai_summary:
        # 按句号分割, 取关键句
        sentences = [s.strip() for s in ai_summary.replace('；', '。').split('。') if len(s.strip()) > 10]
        for s in sentences[:5]:
            # 去掉过多细节, 只取方向性描述
            if len(s) > 60:
                s = s[:57] + '...'
            plans.append(s)

    # 兜底默认计划
    defaults = [
        '推进共享运营闭环问题收敛与解决，保障系统稳定运行。',
        '持续推进缺陷动态清零，跟踪并修复遗留缺陷。',
        '跟进代码安全扫描整改，推动安全合规达标。',
        '完成 UX 改造收口，跟进各单据设计页面调整确认。',
        '配合应付报账模块实施，推进相关功能落地与联调测试。',
    ]
    while len(plans) < 3:
        idx = len(plans)
        if idx < len(defaults):
            plans.append(defaults[idx])
        else:
            break

    return plans[:5] if plans else defaults


def generate_doc(week_start: datetime.date = None) -> dict:
    """生成工作周报 doc. 返回 {ok, path, filename, week_label}."""
    if week_start is None:
        week_start, week_end = _get_week_range()
    else:
        week_end = week_start + datetime.timedelta(days=6)

    # 验证模板
    tpl = _find_template()
    if not tpl:
        return {"ok": False, "error": f"模板文件未找到。请确认 {TEMPLATE_NAME} 存在。"}

    # 提取轻推数据 (用于 group_spans)
    qt_data = _analyze_week(week_start, week_end)
    group_spans = qt_data['group_spans']

    # 获取周报 AI 总结 + git/qingtui 结构化数据
    weekly_data = _fetch_weekly_report_data(week_start)
    ai_summary = weekly_data.get('ai_summary', '')

    # 动态生成工作项 (替换硬编码)
    work_items = _build_work_items_from_data(week_start, weekly_data, group_spans)

    # 生成文档
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = '宋体'
    style.font.size = Pt(10.5)
    style._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')

    # ────── 标题 ──────
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('Project Weekly Status Report'); r.font.size = Pt(16); r.font.bold = True; r.font.name = 'Arial'
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('项目工作周报告'); r.font.size = Pt(15); r.font.bold = True
    doc.add_paragraph()

    # ────── 报告周期 ──────
    ws_str = week_start.strftime('%Y年%m月%d日')
    we_str = week_end.strftime('%Y年%m月%d日')
    today_str = datetime.date.today().strftime('%Y年%m月%d日')
    for label, v1, v2 in [
        ('报告周', f'始：{ws_str}', f'至：{we_str}'),
        ('报告人', '张浩', ''),
        ('报告日期', today_str, ''),
    ]:
        p = doc.add_paragraph()
        r = p.add_run(f'{label}  '); r.font.bold = True
        p.add_run(v1)
        if v2: p.add_run('    ' + v2)
    doc.add_paragraph()

    # ────── 1 工作内容 (动态生成) ──────
    p = doc.add_paragraph()
    r = p.add_run('1     工作内容'); r.font.bold = True; r.font.size = Pt(12)
    doc.add_paragraph()

    table = doc.add_table(rows=1, cols=7)
    table.style = 'Table Grid'
    for i, h in enumerate(['编号', '描述', '执行人', '完成状况', '原计划\n完成日期', '变更\n完成日期', '实际\n完成日期']):
        _set_cell(table.rows[0].cells[i], h, bold=True, align='center')

    for item in work_items:
        row = table.add_row().cells
        aligns = ['center', 'left', 'center', 'center', 'center', 'center', 'center']
        for i, val in enumerate(item):
            _set_cell(row[i], val, align=aligns[i])

    # 空行
    for _ in range(4):
        table.add_row()

    doc.add_paragraph()

    # ────── 2 问题汇报 ──────
    p = doc.add_paragraph(); r = p.add_run('2    问题汇报（含风险与潜在问题）'); r.font.bold = True; r.font.size = Pt(12)
    doc.add_paragraph()
    p = doc.add_paragraph(); r = p.add_run('2.1 问题统计'); r.font.bold = True

    t2 = doc.add_table(rows=2, cols=5); t2.style = 'Table Grid'
    for i, h in enumerate(['项目', '上周遗留的突出问题', '本周已结束的问题', '本周新增问题', '突出问题累计']):
        _set_cell(t2.rows[0].cells[i], h, bold=True, align='center')
    for i, v in enumerate(['数量', '0', '0', '0', '0']):
        _set_cell(t2.rows[1].cells[i], v, align='center')
    doc.add_paragraph()
    p = doc.add_paragraph(); r = p.add_run('2.2 突出问题综述'); r.font.bold = True

    t3 = doc.add_table(rows=2, cols=2); t3.style = 'Table Grid'
    _set_cell(t3.rows[0].cells[0], '编号', bold=True, align='center')
    _set_cell(t3.rows[0].cells[1], '描述', bold=True, align='center')
    _set_cell(t3.rows[1].cells[0], '1', align='center')
    _set_cell(t3.rows[1].cells[1], '本周无突出问题。' if not ai_summary else ai_summary[:150], align='left')
    doc.add_paragraph()

    # ────── 3 下周计划 (动态生成) ──────
    p = doc.add_paragraph(); r = p.add_run('3   下周工作计划'); r.font.bold = True; r.font.size = Pt(12)
    doc.add_paragraph()

    plans = _build_next_week_plans(ai_summary)
    t4 = doc.add_table(rows=1, cols=2); t4.style = 'Table Grid'
    _set_cell(t4.rows[0].cells[0], '编号', bold=True, align='center')
    _set_cell(t4.rows[0].cells[1], '工作内容', bold=True, align='center')
    for idx, plan in enumerate(plans, 1):
        row = t4.add_row().cells
        _set_cell(row[0], str(idx), align='center')
        _set_cell(row[1], plan, align='left')

    # ────── 保存 ──────
    _ensure_dirs()
    ws_short = week_start.strftime('%Y%m%d')
    ws_fmt = week_start.strftime('%m月%d日')
    basename = f'五矿财务管控产研_工作周报_张浩（共享运营）_{ws_short}'
    saved = []
    for out_dir in OUTPUT_DIRS:
        docx_path = out_dir / f'{basename}.docx'
        doc.save(str(docx_path))
        # 转 .doc (兼容 WPS)
        import subprocess
        doc_path = out_dir / f'{basename}.doc'
        subprocess.run(['textutil', '-convert', 'doc', str(docx_path),
                       '-output', str(doc_path)], check=False)
        saved.append(str(doc_path))

    return {
        "ok": True,
        "filename": f"{basename}.doc",
        "paths": saved,
        "week_label": f"{ws_str} ~ {we_str}",
        "week_start": ws_fmt.replace('月', '/').replace('日', ''),
        "msg_count": qt_data['total_my'],
        "work_items_count": len(work_items),
        "ai_summary": ai_summary[:200],
    }


def list_available_weeks() -> list:
    """列出所有可生成周报的周 (周一日期列表), 从消息表的最早时间到最晚时间."""
    from timeline.qingtui_sqlite import db_exists
    if not db_exists():
        return []

    import sqlite3
    from timeline.qingtui_sqlite import QT_DB
    conn = sqlite3.connect(str(QT_DB))
    min_ts = None
    max_ts = None
    try:
        for i in range(60):
            try:
                row = conn.execute(
                    f'SELECT MIN(create_time), MAX(create_time) FROM message_{i} WHERE create_time > 0'
                ).fetchone()
                if row and row[0]:
                    if min_ts is None or row[0] < min_ts:
                        min_ts = row[0]
                    if max_ts is None or row[1] > max_ts:
                        max_ts = row[1]
            except Exception:
                pass
    finally:
        conn.close()

    if not min_ts or not max_ts:
        return []

    min_date = datetime.date.fromtimestamp(min_ts / 1000)
    max_date = datetime.date.fromtimestamp(max_ts / 1000)

    # 从最早消息所在周一到最晚消息所在周一
    monday = min_date - datetime.timedelta(days=min_date.weekday())
    last_monday = max_date - datetime.timedelta(days=max_date.weekday())

    weeks = []
    while monday <= last_monday:
        weeks.append(monday.strftime('%Y-%m-%d'))
        monday += datetime.timedelta(days=7)

    return sorted(weeks, reverse=True)


def _check_existing(week_start: datetime.date) -> list:
    """检查是否已有该周的周报文件."""
    _ensure_dirs()
    ws_short = week_start.strftime('%Y%m%d')
    basename = f'五矿财务管控产研_工作周报_张浩（共享运营）_{ws_short}'
    existing = []
    for out_dir in OUTPUT_DIRS:
        for ext in ['.doc', '.docx']:
            p = out_dir / f'{basename}{ext}'
            if p.exists():
                existing.append(str(p))
    return existing