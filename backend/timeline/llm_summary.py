"""LLM 总结模块 — 调用 DeepSeek API 对时间线事件做 AI 总结.

配置复用 DeepSeek Harness (DSH) 的 settings.yaml + .credentials.yaml:
  - baseURL / provider / model 读 DSH 的 settings.yaml
  - API key 读 DSH 的 .credentials.yaml 里的 DIANXIN_API_KEY
  - 兜底: 环境变量 DIANXIN_API_KEY

DSH 配置文件路径:
  ~/Library/Application Support/dsh-desktop/harness/settings.yaml
  ~/Library/Application Support/dsh-desktop/harness/.credentials.yaml
"""
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------
# 读取 DSH 配置 (settings.yaml + .credentials.yaml)
# ---------------------------------------------------------------
_HOME = Path.home()
_DSH_HARNESS = _HOME / "Library" / "Application Support" / "dsh-desktop" / "harness"
_SETTINGS_FILE = _DSH_HARNESS / "settings.yaml"
_CREDENTIALS_FILE = _DSH_HARNESS / ".credentials.yaml"

MODEL = "DeepSeek-V4-Pro"
BASE_URL = "https://ai.ctaigw.cn/v1"
PROVIDER = "dianxin"
API_KEY = ""


def _load_yaml(path: Path) -> dict:
    """极简 YAML 读取 (只解析我们需要的扁平 key: value / 嵌套一层)."""
    result = {}
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return result
    current_section = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if ":" not in stripped:
            continue
        key, _, val = stripped.partition(":")
        key = key.strip().strip('"\'')
        val = val.strip().strip('"\'')

        if indent == 0:
            # 顶层 key (可能是 section 或 标量)
            if val == "":
                current_section = key
                result.setdefault(key, {})
            else:
                result[key] = val
                current_section = None
        else:
            # 嵌套项
            if current_section is not None:
                section = result.setdefault(current_section, {})
                section[key] = val
    return result


def _load_dsh_config() -> None:
    """从 DSH 配置加载 model/baseURL/provider/API key."""
    global MODEL, BASE_URL, PROVIDER, API_KEY

    # 1. settings.yaml → provider/model/baseURL
    settings = _load_yaml(_SETTINGS_FILE)

    # 默认 provider (agent-default-model.provider)
    agent_model = settings.get("agent-default-model", {})
    if isinstance(agent_model, dict) and agent_model.get("provider"):
        PROVIDER = agent_model["provider"]
        if agent_model.get("model"):
            MODEL = agent_model["model"]

    # provider 详情 (llm-pi-ai.providers.<name>)
    llm_pi = settings.get("llm-pi-ai", {})
    providers = llm_pi.get("providers", {})
    if isinstance(providers, dict) and PROVIDER in providers:
        p = providers[PROVIDER]
        if isinstance(p, dict):
            if p.get("baseURL"):
                BASE_URL = p["baseURL"]
            # apiKeyEnv 字段告诉我们应该从哪个环境变量/credential 取 key
            key_env = p.get("apiKeyEnv", "")

    # 2. .credentials.yaml → API key
    creds = _load_yaml(_CREDENTIALS_FILE)
    refs = creds.get("refs", {})
    if isinstance(refs, dict):
        # 优先 DIANXIN_API_KEY, 其次 DEEPSEEK_API_KEY
        for key_name in ("DIANXIN_API_KEY", "DEEPSEEK_API_KEY"):
            if refs.get(key_name):
                API_KEY = refs[key_name]
                break

    # 3. 兜底: 环境变量
    if not API_KEY:
        API_KEY = os.environ.get("DIANXIN_API_KEY", "") or os.environ.get("DEEPSEEK_API_KEY", "")


_load_dsh_config()


def _api_request(messages: list[dict], max_tokens: int = 2048, temperature: float = 0.3) -> str:
    """调用 /chat/completions, 返回 assistant 文本."""
    if not API_KEY:
        return "[LLM 不可用: DIANXIN_API_KEY 未设置]"

    data = json.dumps({
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()

    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode())
            choices = body.get("choices", [])
            if not choices:
                return f"[LLM 返回为空: {body.get('error', {}).get('message', '')}]"
            return choices[0].get("message", {}).get("content", "")
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:200] if e.fp else str(e)
        return f"[LLM 调用失败: HTTP {e.code} {err}]"
    except Exception as e:
        return f"[LLM 调用失败: {e}]"


def summarize_daily(events_by_project: dict[str, list[dict]], date: str,
                    system: str | None = None, user: str | None = None,
                    max_tokens: int = 2048) -> str:
    """对某天的事件做 AI 总结.

    events_by_project: {项目名: [events, ...]}  按项目归类的全量事件
    system/user/max_tokens: 可选覆盖, 用于生成特殊格式总结 (如今日一句话)
    返回 Markdown 格式的日报正文.
    """
    if not API_KEY:
        return _fallback_summary(events_by_project)

    # 构建事件上下文 (固定格式, 供自定义 prompt 复用)
    project_summaries = []
    for proj, evts in sorted(events_by_project.items()):
        lines = [f"## {proj}"]
        for e in evts[:30]:  # 每个项目最多 30 条
            ts_str = time.strftime("%H:%M", time.localtime(e["ts"] / 1000))
            src = e.get("source", "?")
            action = e.get("action", "")
            title = e.get("title", "")
            target = e.get("target", "")
            lines.append(f"- [{ts_str}] [{src}/{action}] {title} (target: {target})")
        project_summaries.append("\n".join(lines))

    context = "\n\n".join(project_summaries)

    if user is None:
        prompt = f"""你是个人工作台的日报助手。下面是我在 {date} 当天的工作事件记录，请生成一份简洁的日报 (Markdown)。

要求:
1. 用中文，语气专业但亲切
2. 按项目分组，每个项目 1-3 句话总结当天进展
3. 不要逐条罗列事件，而是提炼成"做了什么"的总结
4. 如果有 @我的消息值得关注，单独列在「待关注」段落
5. 日报格式:
   ## 今日总结
   ### {{{{project_name}}}}
   总结内容...
   
   ## 待关注
   - 值得关注的 @提及 (如果有)

事件数据:
{context}

请只输出日报正文，不要加解释说明。"""
    else:
        prompt = f"{user}\n\n事件数据:\n{context}"

    sys_content = system if system is not None else "你是个人工作日报助手，擅长从工作事件记录中提炼简洁的日报总结。"

    messages = [
        {"role": "system", "content": sys_content},
        {"role": "user", "content": prompt},
    ]
    return _api_request(messages, max_tokens=max_tokens, temperature=0.3)


def _fallback_summary(events_by_project: dict[str, list[dict]]) -> str:
    """无 LLM 时的退化总结 (纯规则聚合)."""
    lines = ["## 今日总结", ""]
    for proj, evts in sorted(events_by_project.items(), key=lambda x: -len(x[1])):
        # 统计
        src_count = {}
        actions = {}
        for e in evts:
            src = e.get("source", "?")
            act = e.get("action", "?")
            src_count[src] = src_count.get(src, 0) + 1
            actions[act] = actions.get(act, 0) + 1

        parts = [f"共记录 {len(evts)} 条事件"]
        for act, cnt in sorted(actions.items(), key=lambda x: -x[1]):
            parts.append(f"{act} {cnt} 条")
        lines.append(f"### {proj}")
        lines.append(f"> {' | '.join(parts)}")
        # 取前几条标题
        for e in evts[:5]:
            ts_str = time.strftime("%H:%M", time.localtime(e["ts"] / 1000))
            title = e.get("title", "")
            lines.append(f"- `{ts_str}` {title}")
        lines.append("")

    # 单独列出 @提及
    mentions = []
    for proj, evts in events_by_project.items():
        for e in evts:
            if e.get("source") == "qingtui" and e.get("action") in ("@我", "@所有人"):
                mentions.append(e)
    if mentions:
        lines.append("## 待关注")
        lines.append("")
        for e in sorted(mentions, key=lambda x: x["ts"])[:10]:
            ts_str = time.strftime("%H:%M", time.localtime(e["ts"] / 1000))
            proj = e.get("meta", {}).get("session", e.get("target", ""))
            lines.append(f"- `{ts_str}` [{proj}] {e.get('title', '')}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    # 自测
    test = {
        "财务前端 fs": [
            {"ts": 1789123710000, "source": "git", "action": "提交",
             "title": "fix: resolve dependency version conflicts", "target": "财务前端 fs",
             "meta": {"author": "张浩"}},
        ]
    }
    print(summarize_daily(test, "2026-09-11"))