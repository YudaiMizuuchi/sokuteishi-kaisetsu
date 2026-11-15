import yaml,sys,os,re,functools
L=yaml.CSafeLoader
pts={p['id']:p for p in yaml.load(open('data/master/points.yaml',encoding='utf-8'),Loader=L)['points']}
@functools.lru_cache(None)
def exam(s,e):
    p=f'data/exams/{e}/{s}.yaml'
    return yaml.load(open(p,encoding='utf-8'),Loader=L) if os.path.exists(p) else None
def q(s,e,n):
    for x in exam(s,e)['questions']:
        if str(x['num'])==str(n): return x
def members(pid):
    out=[]
    for i,p in pts.items():
        r=i
        while pts[r].get('merged_into'): r=pts[r]['merged_into']
        if r==pid: out+=p['members']
    return sorted(set(out))
def dump(pid,w=400):
    p=pts[pid]; s=p['subject']; o=[f"### {pid} [{p.get('theme')}] {p['name']}"]
    for k in members(pid):
        e,n,i=k.split('|'); x=q(s,e,n); i=int(i)
        fr=x.get('freq') or {}
        if i==0: o.append(f"  {k} (問題) {str(x['stem'])[:w]} => 正答{x['answer']}: {x['choices'][x['answer']-1] if isinstance(x['answer'],int) else ''}")
        else:
            t=(fr.get('truths') or '?????')[i-1] if fr.get('kind')=='choice' else '・'
            o.append(f"  {k} {t} {str(x['choices'][i-1])[:w]}")
    return '\n'.join(o)
if __name__=='__main__':
    open('/tmp/insp.txt','w',encoding='utf-8').write('\n'.join(dump(a) for a in sys.argv[1:]))
    print(open('/tmp/insp.txt',encoding='utf-8').read())

def root(i):
    while pts[i].get('merged_into'): i=pts[i]['merged_into']
    return i
def stem_points(subj,pat):
    import re
    seen={}
    for e in sorted(os.listdir('data/exams')):
        d=exam(subj,e)
        if not d or d.get('excluded'): continue
        for x in d['questions']:
            fr=x.get('freq') or {}
            if re.search(pat,str(x['stem'])):
                if fr.get('kind')=='choice':
                    for i,pid in enumerate(fr['points'],1): seen.setdefault(root(pid),[]).append(f'{e}|{x["num"]}|{i}')
                else: seen.setdefault('Q:'+str(fr.get('kind')),[]).append(f'{e}|{x["num"]}')
    return seen
