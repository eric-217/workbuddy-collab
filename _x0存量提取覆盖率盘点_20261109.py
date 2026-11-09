# -*- coding: utf-8 -*-
"""X0 存量提取覆盖率盘点（机械第一版）
判据：文件名（去扩展名）是否出现在任一出入口件的正文里。
四态：已提 / 未提 / 待人工（名太短或纯数字）/ 纯重复（md5 与他人相同）
"""
import io, os, re, hashlib, collections, json

BASE = r'D:\workbuddy\家庭教育知识库'
ROOT = os.path.join(BASE, '基础理论')

CORPUS = [
    os.path.join(ROOT, '思想资产总索引.md'),
    os.path.join(ROOT, '_术语表.md'),
    os.path.join(ROOT, '_书稿回忆索引.md'),
    os.path.join(BASE, '讨论记录总索引.md'),
    os.path.join(BASE, '__素材交叉索引__.md'),
    os.path.join(BASE, '金句库', '金句总集.md'),
    os.path.join(BASE, '金句库', '_疑似金句_待船长确认.md'),
    os.path.join(BASE, '案例库', '_案例库_登记.md'),
]
EXTRA_DIRS = [
    (r'D:\workbuddy\32B母数据\02_教育主题\思维资产', ('共识问答对', '8维归档')),
    (r'D:\workbuddy\32B母数据\04_DPO偏好对\教育', ('dpo_pairs',)),
    (r'D:\workbuddy\大模型训练\deepseek-7b\inbox', ('',)),
]

def load_corpus():
    buf = []
    used = []
    for p in CORPUS:
        if os.path.exists(p):
            buf.append(io.open(p, encoding='utf-8', errors='ignore').read())
            used.append(p)
    for d, keys in EXTRA_DIRS:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if keys and not any(k in f for k in keys):
                continue
            if not f.endswith(('.md', '.jsonl')):
                continue
            p = os.path.join(d, f)
            try:
                buf.append(io.open(p, encoding='utf-8', errors='ignore').read())
                used.append(p)
            except Exception:
                pass
    return '\n'.join(buf), used

def md5(p, blocksize=1 << 20):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        while True:
            b = f.read(blocksize)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def main():
    corpus, used = load_corpus()
    print('索引语料件数', len(used), '总字符', len(corpus))
    rows = []
    for root, dirs, files in os.walk(ROOT):
        for f in files:
            p = os.path.join(root, f)
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            rel = os.path.relpath(p, ROOT)
            stem, ext = os.path.splitext(f)
            rows.append({'rel': rel, 'f': f, 'stem': stem, 'ext': ext, 'size': size, 'path': p})
    print('全目录文件数', len(rows))

    # md5 只在 >0 字节上算
    for r in rows:
        r['md5'] = md5(r['path']) if r['size'] > 0 else 'EMPTY'
    grp = collections.defaultdict(list)
    for r in rows:
        if r['md5'] != 'EMPTY':
            grp[r['md5']].append(r)
    dup_groups = {k: v for k, v in grp.items() if len(v) > 1}

    idx_nums = set(re.findall(r'教育-(\d+)', io.open(os.path.join(ROOT,'思想资产总索引.md'),encoding='utf-8').read()))
    for r in rows:
        s = r['stem']
        top = r['rel'].split(os.sep)[0]
        m = re.match(r'教育-(\d+)', s)
        if top == '思想资产' and m:
            r['state'] = '已提' if m.group(1) in idx_nums else '未提'
        elif top == '待精读':
            r['state'] = '流程件'
        elif top == '原版书稿':
            r['state'] = '参照系'
        elif top == '会话上下文':
            r['state'] = '已提' if s in corpus else '未提'
        elif len(s) < 6 or re.fullmatch(r'[\d_\-\s]+', s):
            r['state'] = '待人工'
        elif s in corpus:
            r['state'] = '已提'
        else:
            r['state'] = '未提'
        r['dup'] = len(grp.get(r['md5'], [])) > 1 if r['md5'] != 'EMPTY' else False
        r['content'] = r['ext'].lower() in ('.md', '.txt', '.docx', '.jsonl')

    # 统计
    by_dir = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        top = r['rel'].split(os.sep)[0]
        by_dir[top][r['state']] += 1
        by_dir[top]['合计'] += 1
        by_dir[top]['重复件'] += 1 if r['dup'] else 0
        by_dir[top]['非料件'] += 0 if r['content'] else 1

    out = []
    out.append('# X0 · 存量提取覆盖率盘点（机械第一版）\n')
    out.append('> 判据：**文件名（去扩展名）是否出现在任一出入口件的正文里**。')
    out.append('> 四态：`已提`（被某个出口件提名）｜`未提`（没有任何出口件提到它）｜`待人工`（名字太短或纯数字，机械匹配不可靠）｜`重复件`（与他文件 md5 相同）\n')
    out.append('> ⚠️ 本表是**第一遍机械匹配**，只作盘点起点，不作处置依据（R9/E026：结论要回读核实）。\n')
    out.append('## 一、索引语料（比对底本，共 %d 件）\n' % len(used))
    for u in used:
        out.append('- `%s`' % os.path.relpath(u, BASE))
    out.append('\n## 二、按目录的总账\n')
    out.append('| 目录 | 合计 | 已提 | 未提 | 待人工 | 重复件 | 非料件 |')
    out.append('|---|---|---|---|---|---|---|')
    tot = collections.Counter()
    for d in sorted(by_dir, key=lambda x: -by_dir[x]['合计']):
        c = by_dir[d]
        out.append('| `%s` | %d | %d | %d | %d | %d | %d |' % (d, c['合计'], c['已提'], c['未提'], c['待人工'], c['重复件'], c['非料件']))
        for k, v in c.items():
            tot[k] += v
    out.append('| **合计** | **%d** | **%d** | **%d** | **%d** | **%d** | **%d** |' % (tot['合计'], tot['已提'], tot['未提'], tot['待人工'], tot['重复件'], tot['非料件']))

    out.append('\n## 三、未提名清单（按目录，供逐份判读）\n')
    by_dir_un = collections.defaultdict(list)
    for r in rows:
        if r['state'] in ('未提',) and r['content']:
            by_dir_un[r['rel'].split(os.sep)[0]].append(r)
    for d in sorted(by_dir_un, key=lambda x: -len(by_dir_un[x])):
        out.append('\n### %s（%d 件）\n' % (d, len(by_dir_un[d])))
        for r in sorted(by_dir_un[d], key=lambda x: x['rel']):
            out.append('- `%s`（%d KB）' % (r['rel'], r['size'] // 1024 or 1))

    out.append('\n## 四、重复簇（md5 相同，%d 簇 / %d 件）\n' % (len(dup_groups), sum(len(v) for v in dup_groups.values())))
    out.append('| # | 件数 | 体积 | 主本建议 | 其余 |')
    out.append('|---|---|---|---|---|')
    for i, (h, v) in enumerate(sorted(dup_groups.items(), key=lambda kv: -len(kv[1])), 1):
        v = sorted(v, key=lambda x: x['rel'])
        out.append('| %d | %d | %d KB | `%s` | %s |' % (
            i, len(v), v[0]['size'] // 1024 or 1, v[0]['rel'],
            '；'.join('`%s`' % x['rel'] for x in v[1:])[:400]))

    out.append('\n## 五、待人工判读（名太短／纯数字，%d 件）\n' % tot['待人工'])
    for r in sorted([x for x in rows if x['state'] == '待人工'], key=lambda x: x['rel'])[:80]:
        out.append('- `%s`（%d KB）' % (r['rel'], r['size'] // 1024 or 1))
    if tot['待人工'] > 80:
        out.append('- …（余 %d 件，见附表 csv）' % (tot['待人工'] - 80))

    p_out = os.path.join(ROOT, '待精读', '_X0_存量提取覆盖率盘点_20261109.md')
    io.open(p_out, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print('写出', p_out)

    # 附 csv 全量
    p_csv = os.path.join(ROOT, '待精读', '_X0_存量清单_20261109.csv')
    with io.open(p_csv, 'w', encoding='utf-8-sig') as f:
        f.write('相对路径,字节,状态,是否重复,md5前8\n')
        for r in rows:
            f.write('%s,%d,%s,%s,%s\n' % (r['rel'], r['size'], r['state'], 'Y' if r['dup'] else '', r['md5'][:8]))
    print('写出', p_csv)
    print('统计', dict(tot))

if __name__ == '__main__':
    main()
