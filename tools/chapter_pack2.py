"""素材パック（軽い形。2026-11-15 の執筆方針の見直し後）。
使い方:  python3 tools/chapter_pack2.py <章ID> [--add 論点ID,…] [--drop 論点ID,…] [--q 4] > packs/NNN_<章ID>.md
- 「表に入れる論点」＝ランク S・A・B の論点（--drop で外す、--add で足す）。3つに満たないときは、2回以上出た論点を、多い順に足す。
- 「表に入れない論点」は、名前と回数だけ。
- 出た回の並びは付けない（回数とランクだけ）。例題用の過去問は、表に入れる論点が多く入っている問を、新しい順に。
標準エラーに、表に入れる論点の一覧（話題｜論点｜回数｜ランク）を出す（README・HANDOFF 用）。
"""
import sys, os, re, collections
import yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from srch import chids, kai, era, exams, full, root
from point_inspect import pts, members

TH = {'ippan': (11, 8, 6), 'hourei': (17, 13, 9), 'design': (22, 10, 8), 'bunseki': (11, 10, 8),
      'yuki': (6, 4, 3), 'tokka': (5, 4, 3), 'kinzoku': (6, 4, 3), 'funjin': (8, 5, 3)}
JP = {'ippan': '労働衛生一般', 'hourei': '関係法令', 'design': 'デザイン・サンプリング', 'bunseki': '分析に関する概論',
      'yuki': '有機溶剤', 'tokka': '特定化学物質', 'kinzoku': '金属類', 'funjin': '鉱物性粉じん'}
N = {'ippan': 23, 'hourei': 23, 'design': 23, 'bunseki': 23, 'yuki': 12, 'tokka': 12, 'kinzoku': 12, 'funjin': 12}


def rk(s, n):
    S, A, B = TH[s]
    return 'S' if n >= S else 'A' if n >= A else 'B' if n >= B else 'C'


def load(path, key):
    d = yaml.load(open(path, encoding='utf-8'), Loader=yaml.CSafeLoader)
    return d if isinstance(d, list) else d.get(key)


def choices(s, pid):
    """論点の選択肢を、同じ文で畳む → [(正誤, 文, 回数, 例の参照)]"""
    g = collections.OrderedDict()
    for e, d in exams(s):
        for x in d['questions']:
            fr = x.get('freq') or {}
            if fr.get('kind') == 'choice' and fr.get('points'):
                for i, c in enumerate(x.get('choices') or [], 1):
                    if root(fr['points'][i - 1]) == pid:
                        tf = (fr.get('truths') or '?????')[i - 1]
                        k = (tf, re.sub(r'\s+', '', str(c)))
                        g.setdefault(k, [str(c), []])[1].append(f"{e}|{s}|{x['num']}")
    return [(k[0], v[0], len(v[1]), v[1][-1]) for k, v in g.items()]


def qrefs(s, pid):
    """問題論点（qp-）の問"""
    o = []
    for k in members(pid):
        e, n, i = str(k).split('|')
        if i == '0': o.append((e, int(n)))
    return sorted(set(o))


def pack(ch, add=(), drop=(), nq=4):
    chs = load('data/master/book_map.yaml', 'chapters')
    c = [x for x in chs if x['id'] == ch][0]
    s = c['subject']
    prs = {p['id']: p for p in load('data/master/principles.yaml', 'principles')}
    P = pts
    ids = chids(ch)
    cnt = {p: len(kai(p)) for p in ids}
    inc = [p for p in ids if (rk(s, cnt[p]) in 'SAB' or p in add) and p not in drop]
    if len(inc) < 3:
        for p in sorted(ids, key=lambda p: -cnt[p]):
            if p not in inc and p not in drop and cnt[p] >= 2 and len(inc) < 3:
                inc.append(p)
    inc.sort(key=lambda p: -cnt[p])
    exc = sorted([p for p in ids if p not in inc], key=lambda p: -cnt[p])
    name = lambda p: P[p]['name'] if p in P else p
    o = [f"# 素材：{ch} {c['title']}", '',
         f"- 科目：{JP[s]}（{N[s]}回）　種類：{c.get('kind')}　ランクの境目（S／A／B）：{TH[s][0]}回以上／{TH[s][1]}回以上／{TH[s][2]}回以上", '']
    rows = []
    mypr = c.get('principles') or []
    for pr in mypr:
        p = prs[pr]
        u = set()
        for q in p.get('points') or []:
            if root(q) in ids: u |= set(kai(root(q)))
        o += [f"## 原理：{p['name']}（{pr}。原理としての回数 {len(u)}回・{rk(s, len(u))}）", '', p.get('statement') or '']
        if p.get('formula'): o += ['', f"公式：{p['formula']}"]
        o.append('')
        rows.append((f"**原理：{p['name']}**", pr, len(u), rk(s, len(u))))
        for q in inc:
            if q in [root(x) for x in p.get('points') or []]: rows.append(('　' + name(q), q, cnt[q], rk(s, cnt[q])))
    inpr = {root(x) for pr in mypr for x in prs[pr].get('points') or []}
    for q in inc:
        if q not in inpr: rows.append((name(q), q, cnt[q], rk(s, cnt[q])))
    o += ['## 表に入れる論点（章の「頻出の表」の行は、これだけ）', '', '| 話題 | 論点 | 回数 | ランク |', '|---|---|---|---|']
    o += [f"| {a} | {b} | {n} | {r} |" for a, b, n, r in rows]
    o += ['', '各論点の選択肢（同じ文は畳んである。×n は、その文が出た回数。参照は、例の1つ）：', '']
    for p in inc:
        o.append(f"- **{p}**　{name(p)}　〔{cnt[p]}回・{rk(s, cnt[p])}〕")
        cs = choices(s, p)
        for tf, tx, n, ref in sorted(cs, key=lambda x: (x[0] != '正', -x[2]))[:7]:
            o.append(f"    - {'正しい形' if tf == '正' else '誤りの形' if tf == '誤' else tf}×{n}（{ref}）：{tx}")
        if not cs:
            qs = qrefs(s, p)
            o.append(f"    - 問題単位の論点（計算・穴埋め・組合せ）。問：" + '、'.join(f"{e}|{s}|{n}" for e, n in qs[-6:]))
    o += ['', f"## 表に入れない論点（{len(exc)}件。名前だけ。行にしない。原理の説明に要るときだけ、本文で1行触れてよい）", '']
    o += [f"- {name(p)}（{cnt[p]}回）" for p in exc]
    # 例題用の問：表に入れる論点が多く入っている問を、新しい順に
    sc = []
    qset = {q for p in inc for q in qrefs(s, p)}
    for e, d in exams(s):
        for x in d['questions']:
            fr = x.get('freq') or {}
            if fr.get('kind') == 'choice':
                k = len({root(p) for p in fr.get('points') or []} & set(inc))
            else:
                k = 2 if (e, int(x['num'])) in qset else 0
            if k: sc.append((k, e, x['num']))
    best = sorted(sc, key=lambda t: (t[0], t[1]), reverse=True)[:nq]
    o += ['', f"## 例題用の過去問（{len(best)}問。全選択肢。正誤・論点つき。この章の論点でない選択肢は、要旨だけにする）", '']
    for k, e, n in best:
        o += [f"**{e}|{s}|{n}**（{era(e)} 問{n}）", '```', full(s, e, n), '```', '']
    sys.stderr.write(f"{ch}\t論点{len(ids)}\t入れる{len(inc)}\t入れない{len(exc)}\n" + '\n'.join(f"  {a[:40]}\t{b}\t{n}\t{r}" for a, b, n, r in rows) + '\n')
    return '\n'.join(o)


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d='': (a[a.index(k) + 1] if k in a else d)
    print(pack(a[0], add=[x for x in opt('--add').split(',') if x], drop=[x for x in opt('--drop').split(',') if x], nq=int(opt('--q', '4'))))
