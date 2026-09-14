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

    # 提取数据
    data = _analyze_week(week_start, week_end)
    group_spans = data['group_spans']

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

    # ────── 1 工作内容 ──────
    p = doc.add_paragraph()
    r = p.add_run('1     工作内容'); r.font.bold = True; r.font.size = Pt(12)
    doc.add_paragraph()

    ws_fmt = week_start.strftime('%m月%d日')
    we_fmt = week_end.strftime('%m月%d日')

    work_items = [
        ('1', '共享运营环境部署与发版管控：负责共享运营各环境（test/UAT/准生产/stg压测）版本发布与分支管理，每日新建 hotfix 分支，跟进准生产环境 k8s 命名空间（app-finance-pre）整改及服务重启，保障环境发版规范与稳定。',
         '张浩', '已完成',
         group_spans.get('环境部署/发版', (ws_fmt, ''))[0], '',
         group_spans.get('环境部署/发版', ('', we_fmt))[1]),
        ('2', '主数据一致性问题排查：定位并修复主数据同步 18 万条数据一次性请求导致服务器卡死的问题，改为分流策略并重新优化同步逻辑，测试环境已验证；建立数据一致性验证工具流程，纳入发版工作流。',
         '张浩', '已完成',
         group_spans.get('主数据/一致性', (ws_fmt, ''))[0], '',
         group_spans.get('主数据/一致性', ('', we_fmt))[1]),
        ('3', '代码安全扫描：申请云堡垒机账号，使用安恒 SAST 静态代码审计平台与奇安信 SCA 开源组件扫描工具，对共享运营前端/后端代码进行初测扫描，识别超危/高危开源组件漏洞（lodash-es、axios 等）并推动整改。',
         '张浩', '进行中',
         group_spans.get('代码安全扫描', (ws_fmt, ''))[0], '', ''),
        ('4', 'UX 改造推进：统筹共享运营组 UX 改造进度（9月15日收口），跟进各单据设计页面调整与冲突协调，跟踪 ONES 进度看板，推动平台问题挂起标注。',
         '张浩', '进行中',
         group_spans.get('UX 改造', (ws_fmt, ''))[0], '', ''),
        ('5', '应付报账合并支撑：协助应付组排查 bug，处理应付报账单"联查凭证"按钮不显示问题（全局 isShow 显影逻辑排查并修复），协助排查支付申请池支付状态更新问题，配合共享报账与应付报账合并上线前的联调与测试。',
         '张浩', '进行中',
         group_spans.get('应付/报账支撑', (ws_fmt, ''))[0], '', ''),
        ('6', '权限与账号管理：收集并配置实施定制环境测试人员账号权限（4A 账号、平台使用权限），跟进堡垒机账号申请流程与 mac 输入异常排查，协调中冶集团网络权限信息收集。',
         '张浩', '已完成',
         group_spans.get('权限/账号', (ws_fmt, ''))[0], '',
         group_spans.get('权限/账号', ('', we_fmt))[1]),
    ]

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
    for i, v in enumerate(['数量', '0', '0', '1', '1']):
        _set_cell(t2.rows[1].cells[i], v, align='center')
    doc.add_paragraph()
    p = doc.add_paragraph(); r = p.add_run('2.2 突出问题综述'); r.font.bold = True

    t3 = doc.add_table(rows=2, cols=2); t3.style = 'Table Grid'
    _set_cell(t3.rows[0].cells[0], '编号', bold=True, align='center')
    _set_cell(t3.rows[0].cells[1], '描述', bold=True, align='center')
    _set_cell(t3.rows[1].cells[0], '1', align='center')
    _set_cell(t3.rows[1].cells[1],
              '共享运营前端代码扫描发现 lodash-es、axios 等超危/高危开源组件漏洞，存在安全合规风险（930 上线前需整改），需升级组件版本或采取缓解措施后方可上线。',
              align='left')
    doc.add_paragraph()

    # ────── 3 下周计划 ──────
    p = doc.add_paragraph(); r = p.add_run('3   下周工作计划'); r.font.bold = True; r.font.size = Pt(12)
    doc.add_paragraph()

    plans = [
        '推进共享运营闭环问题收敛与解决，保障系统稳定运行。',
        '持续推进缺陷动态清零，跟踪并修复遗留缺陷，配合 930 上线冲刺。',
        '完成代码安全扫描整改，升级超危/高危开源组件版本，推动安全合规达标。',
        '完成 UX 改造收口，跟进各单据设计页面调整确认。',
        '配合应付报账模块实施，推进应付相关功能落地与联调测试。',
    ]
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
        "msg_count": data['total_my'],
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