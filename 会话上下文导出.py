# -*- coding: utf-8 -*-
r"""
会话上下文导出器
================
承载「降低协作成本」skill · 收束清单第 17 项（2026-10-14 船长令）。

【是什么】
  把本会话的**原始上下文**导出一份 md，供 RAG 检索。
  - 讨论记录   = AI **加工过**的整理稿（有取舍、给人回看）
  - 会话上下文 = **原始料**（AI 不取舍、给检索）
  船长 2026-10-14 原话：「讨论记录是经过你加工过的，而上下文则可以看作是原始料。」

【口径】
  对话全程**不摘要**；**剔三样**——
    ① 系统注入（密语 / skill / hook / <system-reminder>）
    ② 工具回执（function_call_result 全删；function_call 只留一行工具名）
    ③ 压缩摘要（<cb_summary>）
  ＋【AI 推，captain_confirmed: false】④ AI 推理过程（reasoning）默认剔除，
    理由：它不是"对话"，且体量最大；如需保留用 --keep-reasoning（截 300 字）。
  船长原话与 AI 输出**逐字保留**。

【命名】
  {标题}__{会话id前8}.md
  标题**可变** ⇒ 必须带 id 短码，否则改名即断链。

【落点 · 纵切（2026-10-15 船长令）】
  <知识库根>\<主题>\会话上下文\<标题>__<id8>.md
  **同主题集中一处**，而不是在根下开一个横切的 会话上下文\ 再按主题分家。
  主题由**会话标题**定（看得见的信号），不由 AI 判内容——
  ① 标题 == 目录名　② 别名表（少数对不上的）　③ 目录名 ⊂ 标题（最长匹配）　④ 都不中 → 以标题新建目录

【标题从哪来】（不需要 AI 判断归属）
  $CODEBUDDY_SESSION_ID → ~/.workbuddy/workbuddy.db → sessions.custom_title

用法：
  python 会话上下文导出.py                       # dry-run：只统计，不写任何文件
  python 会话上下文导出.py --write               # 落盘（自动分发到 <主题>\会话上下文\）
  python 会话上下文导出.py --session <id> --write
  python 会话上下文导出.py --jsonl <path> --title <标题> --write
  python 会话上下文导出.py --jsonl <清洗件> --clean --title <标题> --write   # 存量：从 32B 按主题切片导
  python 会话上下文导出.py --topic 基础理论 --write        # 手工指定主题目录
  python 会话上下文导出.py --out <dir> --write            # 显式目录（不做分发）
  python 会话上下文导出.py --base <知识库根> --session <id> --write
"""
import argparse
import glob
import json
import os
import re
import sqlite3
import sys
from datetime import datetime

HOME = os.path.expanduser("~")
PROJECTS = os.path.join(HOME, ".workbuddy", "projects")
DB = os.path.join(HOME, ".workbuddy", "workbuddy.db")
DEFAULT_BASE = r"D:\workbuddy\家庭教育知识库"   # 知识库根（--base 可改）
CTX_DIRNAME = "会话上下文"                        # 主题目录下统一的子目录名

# 别名表：仅用于「会话标题」与「主题目录名」对不上的少数情形。
# ⚠️ 能改会话标题的，优先改标题——标题就是信号，别名是补丁（补丁越少越好）。
TOPIC_ALIAS = {
    "教育理论": "基础理论",
    "理论学习": "基础理论",
}

RE_SR = re.compile(r"<system-reminder\b[^>]*>.*?</system-reminder>", re.S)
RE_SR_OPEN = re.compile(r"<system-reminder\b[^>]*>.*\Z", re.S)
RE_SUM = re.compile(r"<cb_summary>.*?</cb_summary>", re.S)
RE_CMD = re.compile(r"<command-name>.*?</command-name>", re.S)
RE_OUTPUT_STYLE = re.compile(r"<output_style>.*?</output_style>", re.S)
RE_BLANKS = re.compile(r"\n{3,}")

KEEP = 300  # reasoning 截断长度（--keep-reasoning 时生效）


def find_jsonl(session_id=None):
    if session_id:
        hits = glob.glob(os.path.join(PROJECTS, "*", session_id + ".jsonl"))
        if not hits:                                   # 允许只给 id 前缀（如 b13339df）
            hits = glob.glob(os.path.join(PROJECTS, "*", session_id + "*.jsonl"))
        if hits:
            return max(hits, key=os.path.getmtime)
        raise SystemExit(f"[x] 找不到会话 {session_id} 的 jsonl（可用 id 前缀）")
    # 未指定：取 cwd 对应项目目录下最新改动的 jsonl
    cwd = os.getcwd()
    slug = cwd.replace(":", "").replace("\\", "-").replace("/", "-")
    cands = glob.glob(os.path.join(PROJECTS, slug, "*.jsonl"))
    if not cands:
        cands = glob.glob(os.path.join(PROJECTS, "*", "*.jsonl"))
    if not cands:
        raise SystemExit("[x] 找不到任何 jsonl")
    return max(cands, key=os.path.getmtime)


def get_title(session_id):
    """从 workbuddy.db 读船长自定标题（custom_title），退回 title。
    支持**id 前缀**（清洗件文件名常只有 32 位纯 id，或只给 8 位短码）。"""
    try:
        c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        row = c.execute(
            "select custom_title, title from sessions where id=?", (session_id,)
        ).fetchone()
        if not row:                                    # 退回前缀匹配（取最近活动的一条）
            row = c.execute(
                "select custom_title, title from sessions where id like ? "
                "order by last_activity_at desc limit 1",
                (session_id + "%",),
            ).fetchone()
        c.close()
        if row:
            return (row[0] or row[1] or "").strip()
    except Exception as e:
        print(f"  [warn] 读标题失败（{e}），改用 --title 或首条提问")
    return ""


def clean_text(t):
    """剥系统注入 + 压缩摘要 + skill 注入块。返回 (净文本, 剥离计数)。"""
    n = 0
    for pat in (RE_SUM, RE_CMD, RE_OUTPUT_STYLE):
        t, k = pat.subn("", t)
        n += k
    t, k = RE_SR.subn("", t)
    n += k
    if "<system-reminder" in t:  # 未闭合的（被截断）
        t, k = RE_SR_OPEN.subn("", t)
        n += k
    return t.strip(), n


def tool_name(rec):
    for k in ("name", "tool_name", "toolName"):
        if rec.get(k):
            return str(rec[k])
    return "?"


def parse(jsonl, keep_reasoning=False):
    turns = []          # [(who, text)]
    stat = {"msg": 0, "inject": 0, "receipt": 0, "call": 0, "reason": 0, "empty": 0}
    with open(jsonl, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            ty = o.get("type")
            if ty == "message":
                c = o.get("content")
                if isinstance(c, list):
                    txt = "".join(
                        b.get("text", "") for b in c
                        if isinstance(b, dict) and b.get("type") in ("input_text", "output_text")
                    )
                elif isinstance(c, str):
                    txt = c
                else:
                    txt = ""
                txt, n = clean_text(txt)
                stat["inject"] += n
                if not txt:
                    stat["empty"] += 1
                    continue
                stat["msg"] += 1
                turns.append(("船长" if o.get("role") == "user" else "AI", txt))
            elif ty == "function_call":
                stat["call"] += 1
                turns.append(("tool", tool_name(o)))
            elif ty == "function_call_result":
                stat["receipt"] += 1          # 全剔，不落文
            elif ty == "reasoning":
                stat["reason"] += 1
                if keep_reasoning:
                    t = (o.get("text") or o.get("content") or "")
                    if isinstance(t, list):
                        t = "".join(b.get("text", "") for b in t if isinstance(b, dict))
                    t = str(t).strip()[:KEEP]
                    if t:
                        turns.append(("思考", t))
    return turns, stat


def parse_clean(jsonl):
    """读「清洗件」格式（`32B母数据\\_对话记录_按主题\\` 等）：
    每行 {role: captain|ai, source: verbatim|ai_output, idx, text, date, src}
    —— 该格式已由 32B 清洗器剔过注入与回执；此处再剥一遍残留注入。"""
    turns = []
    stat = {"msg": 0, "inject": 0, "receipt": 0, "call": 0, "reason": 0, "empty": 0}
    dates = []
    with open(jsonl, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            t = (o.get("text") or "").strip()
            if not t:
                stat["empty"] += 1
                continue
            who = "船长" if str(o.get("role", "")).lower() in ("captain", "user") else "AI"
            t, n = clean_text(t)
            stat["inject"] += n
            stat["msg"] += 1
            turns.append((who, t, str(o.get("date") or "")))
            if o.get("date"):
                dates.append(str(o["date"]))
    span = f"{min(dates)} ~ {max(dates)}" if dates else ""
    return turns, stat, span


def render(title, sid, turns, span=""):
    L = [
        f"# 会话上下文：{title}",
        "",
        f"> **会话 ID**：`{sid}`",
        f"> **导出时间**：{datetime.now():%Y-%m-%d %H:%M}",
    ]
    if span:
        L.append(f"> **对话日期**：{span}")
    L += [
        "> **口径**：对话全程不摘要；已剔——① 系统注入（密语／skill／hook）② 工具回执 ③ 压缩摘要 ④ AI 推理过程。"
        "**船长原话与 AI 输出逐字保留。**",
        "> **本件是原始料**（AI 未取舍）；经加工的整理稿见 `讨论记录\\`。二者互补，**勿互相替代**。",
        "",
        "---",
        "",
    ]
    for turn in turns:
        who, txt = turn[0], turn[1]
        d = turn[2] if len(turn) > 2 else ""
        tag = f"**{who}**" + (f"　`{d}`" if d else "") + "："
        if who == "tool":
            L += [f"`[工具] {txt}`", ""]
        elif who == "思考":
            L += [f"> *[思考]* {txt}", ""]
        else:
            L += [tag, "", txt, "", "---", ""]
    return RE_BLANKS.sub("\n\n", "\n".join(L))


def safe(name):
    return re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name).strip()[:60] or "未命名"


def list_topics(base):
    """知识库根下的一级主题目录（排除 _开头 与 __开头 的机制目录）。"""
    if not os.path.isdir(base):
        return []
    return sorted(
        d for d in os.listdir(os.path.join(base))
        if os.path.isdir(os.path.join(base, d))
        and not d.startswith("_")
    )


def route_topic(title, base):
    """按**会话标题**定主题目录。只用看得见的信号（标题 ↔ 目录名），不判内容。

    ① 标题 == 目录名             → 该目录
    ② 别名表命中                 → 映射目录
    ③ 目录名 ⊂ 标题（或反之）     → 最长匹配者
    ④ 都不中                     → 以标题新建目录
    返回 (目录名, 是否新建)
    """
    t = (title or "").strip()
    topics = list_topics(base)
    if t and t in topics:
        return t, False
    for key, val in TOPIC_ALIAS.items():
        if key in t and (not topics or val in topics):
            return val, False
    cands = [d for d in topics if d in t or t in d]
    if cands:
        return max(cands, key=len), False
    return safe(t), True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", help="会话 ID（默认读 $CODEBUDDY_SESSION_ID / 最新 jsonl）")
    ap.add_argument("--jsonl", help="直接指定 jsonl 路径")
    ap.add_argument("--title", help="直接指定标题（跳过数据库查询）")
    ap.add_argument("--base", default=DEFAULT_BASE,
                    help=f"知识库根；按会话标题分发到 <主题>\\{CTX_DIRNAME}\\（默认 {DEFAULT_BASE}）")
    ap.add_argument("--topic", help="手工指定主题目录名（覆盖自动判定）")
    ap.add_argument("--no-route", action="store_true",
                    help=f"不做主题分发，直接落到 <base>\\{CTX_DIRNAME}\\")
    ap.add_argument("--out", help="显式输出目录（给了就按此目录落，完全不分发）")
    ap.add_argument("--write", action="store_true", help="真正落盘（缺省 = dry-run）")
    ap.add_argument("--keep-reasoning", action="store_true", help="保留 AI 推理（截 300 字）")
    ap.add_argument(
        "--clean",
        action="store_true",
        help="输入是「清洗件」格式（role/source/idx/text/date，见 32B母数据\\_对话记录_按主题\\）",
    )
    a = ap.parse_args()

    jl = a.jsonl or find_jsonl(a.session)
    if not os.path.exists(jl):
        raise SystemExit(f"[x] jsonl 不存在：{jl}")
    sid = os.path.basename(jl)[:-6]
    title = a.title or get_title(sid)
    if not title:
        title = sid[:8]
        print("  [warn] 未取到标题，暂用会话 ID 前 8 位（请在 WorkBuddy 里给会话改个主题名）")

    span = ""
    if a.clean:
        turns, st, span = parse_clean(jl)
    else:
        turns, st = parse(jl, a.keep_reasoning)
    body = render(title, sid, turns, span)
    fn = f"{safe(title)}__{sid[:8]}.md"

    # ---- 落点：纵切（<主题>\会话上下文\）----
    if a.out:
        out_dir, created = a.out, False
        topic_line = "(显式 --out，不做分发)"
    elif a.no_route:
        out_dir, created = os.path.join(a.base, CTX_DIRNAME), False
        topic_line = f"( --no-route → 根下 {CTX_DIRNAME}\\ )"
    else:
        topic, created = (a.topic, False) if a.topic else route_topic(title, a.base)
        out_dir = os.path.join(a.base, topic, CTX_DIRNAME)
        topic_line = f"{topic}\\{CTX_DIRNAME}\\" + ("   ★新建主题目录" if created else "")
    dest = os.path.join(out_dir, fn)

    print(f"  jsonl   : {jl}")
    print(f"  会话 ID : {sid}")
    print(f"  标题    : {title}   → 文件名 {fn}")
    print(f"  主题    : {topic_line}")
    print(f"  保留    : {st['msg']} 条对话 ＋ {st['call']} 条工具足迹")
    print(f"  剔除    : 注入块 {st['inject']} 处 ／ 工具回执 {st['receipt']} 条 ／ "
          f"推理 {st['reason']} 条 ／ 空消息 {st['empty']} 条")
    print(f"  净正文  : {len(body):,} 字 ≈ {len(body.encode('utf-8'))/1024:.0f} KB")
    print(f"  落点    : {dest}")

    if not a.write:
        print("  [dry-run] 未写任何文件。加 --write 落盘。")
        return
    os.makedirs(out_dir, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"  [ok] 已写 {dest}")
    if created:
        print(f"  [注意] 主题目录 {topic} 是**新建**的 —— 若非你所愿，"
              f"请把会话标题改成已有主题名，或把本件手工归到别的主题下。")
    print("  [next] 收束最后一步须跑：python D:\\workbuddy\\同步工具\\scan_pollution.py --since 120")


if __name__ == "__main__":
    main()
