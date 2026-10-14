# -*- coding: utf-8 -*-
"""
「待定稿」巡检 —— 机制件（不是整理期临时件，长期常驻）

建立：2026-10-14（船长令：「把机制弄好，然后先用，再调整」）
规则出处：D:\\workbuddy\\家庭教育知识库\\_目录契约与分层登记.md §四点六
用法：  python 待定稿巡检.py

机制三块（与契约同口径）：
  ① 判定：产出物先判类别 —— 甲类即成稿／乙类待讨论稿／丙类非稿
  ② 事件：出队只有三条路 —— 定稿落根下／退回原属／到期重判
  ③ 期限：≤14 天 活跃 ｜ 15~30 天 待重判 ｜ >30 天 超期（强制三选一）
本脚本只做第③块的「列清单」，判定权始终在船长 —— 定稿与否不在文件名里。
"""
import os
import re
import sys
import datetime

KB = r'D:\workbuddy\家庭教育知识库'
TODAY = datetime.date.today()

WARN_DAYS = 14    # 提醒档：进入「待重判」清单
OVER_DAYS = 30    # 强判档：进入「超期」，强制三选一

# ── 巡检范围 ──────────────────────────────────────────────
# 甲组：有稿待定（做年龄分档）
DRAFT_GROUP = [
    (r'公众号文章\待定稿', '待定稿（★主线）'),
    (r'待定稿文章',        '旧·待定稿文章'),
    (r'待发布',            '旧·待发布'),
    (r'待审阅',            '旧·待审阅'),
]
# 乙组：只报件数，不做年龄分档（语义不同）
PLAIN_GROUP = [
    (r'待讨论话题',  '话题池（还没成稿）'),
    (r'待整理资料',  '整理类 · 未消化'),
    (r'待精读',      '整理类 · 已读待定归属'),
    (r'已完稿文章',  '成品类'),
    (r'已定稿待发表', '成品类'),
]

# 丙类嫌疑特征（本不以定稿为目的的配套材料）
C_SUFFIX = ('_素材版_', '_预览_')
C_KEYWORD = ('可成文清单', '对照表', '索引')


def age_of(path, name):
    """优先取文件名里的 8 位日期（＝产出日）；缺失则退回 mtime（＝最后动过）"""
    m = re.search(r'(20\d{2})(\d{2})(\d{2})', name)
    if m:
        try:
            d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if d <= TODAY:
                return (TODAY - d).days, '名'
        except ValueError:
            pass
    d = datetime.date.fromtimestamp(os.path.getmtime(path))
    return (TODAY - d).days, 'mt'


def classify(name):
    low = name.lower()
    if '_发布版_' in name:
        return '发布版'
    if any(s in name for s in C_SUFFIX) or any(k in name for k in C_KEYWORD) \
            or low.endswith('.html'):
        return '丙类嫌疑'
    return '其它'


def band(days):
    if days <= WARN_DAYS:
        return '活跃'
    if days <= OVER_DAYS:
        return '待重判'
    return '超期'


def scan(rel):
    """返回 [(name, size, days, src, kind), ...]"""
    d = os.path.join(KB, rel)
    if not os.path.isdir(d):
        return None
    out = []
    for r, _, fs in os.walk(d):
        for f in sorted(fs):
            p = os.path.join(r, f)
            try:
                days, src = age_of(p, f)
                out.append((f, os.path.getsize(p), days, src, classify(f)))
            except OSError:
                pass
    out.sort(key=lambda x: -x[2])
    return out


def main():
    print('=' * 66)
    print(f'  待定稿巡检    {TODAY:%Y-%m-%d}    阈值: {WARN_DAYS}天提醒 / {OVER_DAYS}天强判')
    print('=' * 66)

    # ── 第一块：主线（公众号文章\待定稿）──────────────────
    main_rel = r'公众号文章\待定稿'
    items = scan(main_rel)
    print(f'\n【一】主线  {main_rel}\\')
    if items is None:
        print('   目录不存在')
    else:
        print(f'   合计 {len(items)} 件')
        kinds = {}
        for _, _, _, _, k in items:
            kinds[k] = kinds.get(k, 0) + 1
        print('   构成：' + ' ｜ '.join(f'{k} {v}' for k, v in sorted(kinds.items())))
        for b in ('超期', '待重判', '活跃'):
            grp = [x for x in items if band(x[2]) == b]
            mark = {'超期': '⛔', '待重判': '⚠', '活跃': '✓'}[b]
            print(f'   {mark} {b}：{len(grp)} 件')
            if b != '活跃':
                for f, s, d, src, k in grp:
                    print(f'        {d:>4}天({src})  [{k}]  {f}')
        c = [x for x in items if x[4] == '丙类嫌疑']
        if c:
            print(f'\n   ⚑ 丙类嫌疑 {len(c)} 件（本不以定稿为目的 ⇒ 不该在待定稿队列里）')
            print('      → 建议退回原属（主题目录／思想资产），待船长判')

    # ── 第二块：其它「待」目录（只报告）──────────────────
    print(f'\n【二】其它「待/已」状态目录（只报告，不动作）')
    for rel, label in PLAIN_GROUP:
        it = scan(rel)
        if it is None:
            print(f'   {label:<22} —')
            continue
        oldest = max((x[2] for x in it), default=0)
        print(f'   {label:<22} {len(it):>4} 件   最老 {oldest} 天')

    # ── 第三块：旧状态目录分档（暴露历史欠账）──────────
    print(f'\n【三】旧状态目录分档（同一机制回头检查历史）')
    for rel, label in DRAFT_GROUP[1:]:
        it = scan(rel)
        if it is None:
            print(f'   {label:<18} —')
            continue
        bands = {}
        for x in it:
            bands[band(x[2])] = bands.get(band(x[2]), 0) + 1
        summary = ' ｜ '.join(f'{k} {bands.get(k, 0)}'
                              for k in ('超期', '待重判', '活跃'))
        print(f'   {label:<18} {len(it):>3} 件   {summary}')

    print('\n' + '=' * 66)
    print('  说明：本脚本只出清单，不定稿。「定稿与否」由船长一句话定。')
    print('=' * 66)


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    main()
