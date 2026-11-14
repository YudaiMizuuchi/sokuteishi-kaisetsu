"""論点の点検に使う小さな道具（サイト側の作業用。リポジトリのルートで使う）。
使い方:  python3 - <<'X'
          import sys; sys.path.insert(0,'tools')
          from srch import *
          print('\\n'.join(show('design','ステアリン酸',90)))      # 科目の全選択肢を正規表現で探し、論点つきで並べる
          print(full('bunseki','2026-08',8))                       # 1問の全選択肢（正誤・論点つき）
          print(folded('pt-design-0096'))                          # 論点の選択肢を、同じ文で畳んで並べる（正誤と出た回）
          print(chids('bk-design-tp06'))                           # 章の論点（points＋qpoint_chapters＋原理の points。統合先に直したもの）
          print(kai('pt-design-0096'))                             # 論点が出た回
          print(art('酸素欠乏症等防止規則','第二十五条の二',300))  # data/law の原文から、条の書き出しを切って出す
          X
結果が長いときは、ファイルに書いて、必要な行だけを読む。"""
import sys, re, os, collections
import yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from point_inspect import pts, exam, q, members, root, L

def era(e):
    y, m = map(int, e.split('-')); fy = y - 1 if m <= 3 else y; r = 2 if m <= 3 else 1
    n = fy - 2018 if fy >= 2019 else fy - 1988
    return f"{'令和' if fy >= 2019 else '平成'}{'元' if n == 1 and fy >= 2019 else n}年度第{r}回"

def exams(s):
    for e in sorted(os.listdir('data/exams')):
        d = exam(s, e)
        if d and not d.get('excluded'): yield e, d

def _pt(fr, i):
    return root(fr['points'][i - 1]) if fr.get('kind') == 'choice' and fr.get('points') else 'Q:' + str(fr.get('kind'))

def _tf(fr, i):
    return (fr.get('truths') or '?????')[i - 1] if fr.get('kind') == 'choice' else '・'

def show(s, pat, w=200, stem=None):
    o = []
    for e, d in exams(s):
        for x in d['questions']:
            if stem and not re.search(stem, str(x['stem'])): continue
            fr = x.get('freq') or {}
            for i, c in enumerate(x.get('choices') or [], 1):
                if re.search(pat, str(c)):
                    o.append(f"{_pt(fr, i)} {e}|{x['num']}|{i} {_tf(fr, i)} {str(c)[:w]}")
    return sorted(o)

def full(s, e, n):
    x = q(s, e, n); fr = x.get('freq') or {}
    o = [f"{e}|{n} 正答{x['answer']} kind={fr.get('kind')} {str(x['stem'])}"]
    for i, c in enumerate(x['choices'], 1):
        pid = _pt(fr, i) if fr.get('kind') == 'choice' else ''
        o.append(f"  {i} {_tf(fr, i)} {pid} {c}")
    return '\n'.join(o)

def kai(pid):
    return sorted({k.split('|')[0] for k in members(pid)})

def _maps():
    ld = lambda p: yaml.load(open(p, encoding='utf-8'), Loader=L)
    bm = ld('data/master/book_map.yaml'); qc = ld('data/master/qpoint_chapters.yaml'); pr = ld('data/master/principles.yaml')
    return bm, qc, {p['id']: p for p in (pr['principles'] if isinstance(pr, dict) else pr)}

def chids(chid):
    bm, qc, prs = _maps()
    c = [x for x in bm['chapters'] if x['id'] == chid][0]
    ids = set(c.get('points') or []) | set(qc.get(chid, []))
    for p in c.get('principles') or []: ids |= set(prs[p].get('points') or [])
    return sorted({root(i) for i in ids if i in pts})

def where(pid):
    """論点が入っている章（book_map の points と、qpoint_chapters）"""
    bm, qc, _ = _maps()
    return [c['id'] + '(' + c['status'] + ')' for c in bm['chapters'] if pid in (c.get('points') or [])] + [k + '(qc)' for k, v in qc.items() if pid in v]

def folded(pid, w=110):
    s = pts[pid]['subject']; d = collections.OrderedDict()
    for k in members(pid):
        e, n, i = k.split('|'); x = q(s, e, n); i = int(i); fr = x.get('freq') or {}
        if i == 0:
            a = x['answer']
            key = ('問', re.sub(r'\s+', ' ', str(x['stem']))[:w] + ' ⇒ ' + str(x['choices'][a - 1] if isinstance(a, int) else a)[:40])
        else:
            key = (_tf(fr, i), re.sub(r'\s+', ' ', str(x['choices'][i - 1]))[:w])
        d.setdefault(key, []).append(k)
    o = [f"### {pid} {len(kai(pid))}回 {pts[pid]['name'][:70]}"]
    for (t, c), ks in d.items(): o.append(f"  {t} {c}  [{' '.join(ks)}]")
    return '\n'.join(o)

def art(head, name, n=500):
    f = [x for x in os.listdir('data/law') if x.startswith(head) and x.endswith('.txt')][0]
    t = open('data/law/' + f, encoding='utf-8').read()
    return [t[m.start():m.start() + n] for m in re.finditer(r'\n' + name + '　', t)]
