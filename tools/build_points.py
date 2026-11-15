#!/usr/bin/env python3
"""論点（問われている知識のまとまり）の候補を、自動でグループ化する。
使い方: python3 tools/build_points.py <科目ID> [しきい値=0.70]   → /tmp/points_<科目>.json に書き出す（見直し用）
キーワード（名詞・サ変名詞）と数値の TF-IDF コサイン類似度で、科目ごとに、選択肢をグループ化する。
確定した論点は data/master/knowledge_points.yaml に保存する（人が見直して、論点名をつける）。"""
import yaml,glob,re,math,collections,json,sys
from janome.tokenizer import Tokenizer
tk=Tokenizer()
STOP=set('もの こと 場合 とき ため 必要 事業 者 場 作業 以上 以下 超える 場所 等 他 第 種 的 内 外 間 中 上 下 前 後'.split())
def terms(text):
    t=re.sub(r'<[^>]+>','',str(text)).translate(str.maketrans('０１２３４５６７８９','0123456789'))
    out=set()
    for m in re.finditer(r'\d+(?:\.\d+)?\s*[%％℃mkcgLµμ人日月年時間分秒回種類号条]{0,3}',t): out.add('#'+re.sub(r'\s','',m.group(0)))
    for x in tk.tokenize(t):
        p=x.part_of_speech.split(',')
        if p[0]=='名詞' and p[1] in ('一般','サ変接続','固有名詞','形容動詞語幹') and x.surface not in STOP and len(x.surface)>=2: out.add(x.surface)
    return out
def stmt_like(c):
    """文の選択肢か：12文字以上、または、句点で終わる9文字以上（物質名だけの短い選択肢は除く）"""
    t=str(c).strip()
    return len(t)>=12 or (len(t)>=9 and t.endswith('。'))
def load(subj):
    items=[]
    for f in sorted(glob.glob('data/exams/*/*.yaml')):
        d=yaml.safe_load(open(f,encoding='utf-8'))
        if d.get('excluded') or d['subject']!=subj: continue
        e=f.split('/')[2]
        for q in d['questions']:
            if q.get('status')!='published' or not q.get('choices') or q.get('columns'): continue
            ans=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
            if ans[0]=='all' or not all(stmt_like(c) for c in q['choices']): continue
            if all(re.search(r'\d',str(c)) and not re.search(r'[ぁ-んァ-ヶ一-龥]{3,}',str(c)) for c in q['choices']): continue   # 数値だけの選択肢（計算問題）は、論点にしない
            neg=bool(re.search(r'誤っているもの|不適当|不適切|適切でない|誤っている',q['stem']))
            for i,c in enumerate(q['choices'],1):
                items.append(dict(e=e,n=q['num'],i=i,truth=(i not in ans) if neg else (i in ans),text=re.sub(r'\s+',' ',str(c)),isans=(i==ans[0])))
    return items
def group(items,thr=0.70):
    T=[sorted(terms(it['text'])) for it in items]; N=len(items)
    df=collections.Counter(x for t in T for x in t); V=[]
    for t in T:
        v={x:math.log((N+1)/(df[x]+1))+1 for x in t}; nr=math.sqrt(sum(sorted(a*a for a in v.values()))) or 1
        V.append({k:a/nr for k,a in v.items()})
    inv=collections.defaultdict(list)
    for i,v in enumerate(V):
        for k in v: inv[k].append(i)
    # リーダー方式：既存グループの「中心（平均ベクトル）」との類似度がしきい値以上のときだけ、そのグループに入れる（連鎖を防ぐ）
    cents=[]; members=[]
    order=sorted(range(N),key=lambda i:-len(V[i]))
    def cosv(a,b):
        if len(a)>len(b): a,b=b,a
        return sum(sorted(w*b.get(k,0) for k,w in a.items()))
    gidx=collections.defaultdict(set)
    for i in order:
        cand=collections.Counter()
        for k in V[i]:
            for g in sorted(gidx.get(k,())): cand[g]+=1
        best=None
        for g in cand:
            c=cosv(V[i],cents[g])
            if c>=thr and (best is None or c>best[0]): best=(c,g)
        if best is None:
            cents.append(dict(V[i])); members.append([i]); g=len(cents)-1
            for k in V[i]: gidx[k].add(g)
        else:
            g=best[1]; members[g].append(i); n=len(members[g])
            c=cents[g]
            for k in sorted(set(c)|set(V[i])): c[k]=(c.get(k,0)*(n-1)+V[i].get(k,0))/n
            nr=math.sqrt(sum(sorted(a*a for a in c.values()))) or 1
            for k in list(c): c[k]/=nr
            for k in c: gidx[k].add(g)
    comp=dict(enumerate(members))
    return list(comp.values())
if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--update':
        import points_master as PM
        PM.run(sys.argv[2:] or None); sys.exit(0)
    subj=sys.argv[1]; thr=float(sys.argv[2]) if len(sys.argv)>2 else 0.70
    items=load(subj); groups=group(items,thr)
    out=[]
    for g in groups:
        ex=sorted({items[i]['e'] for i in g})
        out.append(dict(exams=len(ex),size=len(g),members=[dict(items[i]) for i in g]))
    out.sort(key=lambda x:(-x['exams'],-x['size']))
    json.dump(out,open(f'/tmp/points_{subj}.json','w'),ensure_ascii=False)
    print(subj,'記述',len(items),'グループ',len(out),'2回以上',sum(1 for o in out if o['exams']>=2),'5回以上',sum(1 for o in out if o['exams']>=5))
