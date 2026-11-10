"""points.yaml を、書式を変えずに直す道具（移動・新設・改名・テーマ・統合）。科目は hourei など1つに固定して使う。"""
import re
PATH='data/master/points.yaml'
class Pts:
    def __init__(s,subj):
        s.subj=subj; s.lines=open(PATH,encoding='utf-8').read().split('\n'); s.log=[]
    def span(s,pid):
        a=s.lines.index(f'- id: {pid}'); b=a+1
        while b<len(s.lines) and not s.lines[b].startswith('- id: '): b+=1
        return a,b
    def exists(s,pid): return f'- id: {pid}' in s.lines
    def members(s,pid):
        a,b=s.span(pid); return [l[4:] for l in s.lines[a:b] if l.startswith('  - ')]
    def _set(s,pid,key,val):
        a,b=s.span(pid)
        for i in range(a,b):
            if s.lines[i].startswith(f'  {key}:'): s.lines[i]=f'  {key}: {val}'; return
        raise KeyError(key)
    def rename(s,pid,name):
        assert ': ' not in name and ' #' not in name and not name[0] in '\'"[{&*!|>%@`-?', name
        s._set(pid,'name',name)
    def theme(s,pid,th): s._set(pid,'theme',th if th else "''")
    def family(s,pid):
        """pid と、pid に統合された論点（子孫）"""
        par={}; cur=None
        for l in s.lines:
            if l.startswith('- id: '): cur=l[6:]
            elif l.startswith('  merged_into: '): par[cur]=l[15:]
        def root(i):
            while i in par: i=par[i]
            return i
        return [pid]+[c for c in par if root(c)==pid]
    def remove(s,pid,keys):
        keys=list(keys); left=set(keys)
        for f in s.family(pid):
            a,b=s.span(f); hit=[k for k in s.members(f) if k in left]
            if not hit: continue
            left-=set(hit)
            s.lines[a:b]=[l for l in s.lines[a:b] if not (l.startswith('  - ') and l[4:] in hit)]
            if not s.members(f):
                assert f!=pid,('空になる',pid)
                a,b=s.span(f); del s.lines[a:b]; s.log.append(('deleted_empty_child',f,pid,hit))
        assert not left,(pid,left)
    def add(s,pid,keys):
        a,b=s.span(pid); ms=sorted(set(s.members(pid))|set(keys))
        i0=[i for i in range(a,b) if s.lines[i]=='  members:'][0]
        j=i0+1
        while j<b and s.lines[j].startswith('  - '): j+=1
        s.lines[i0+1:j]=['  - '+k for k in ms]
    def move(s,keys,src,dst): s.remove(src,keys); s.add(dst,keys); s.log.append(('move',src,dst,keys))
    def new(s,pid,name,th,src,keys):
        assert not s.exists(pid)
        s.remove(src,keys)
        # 同じ科目の pt- の最後の後ろに入れる
        last=max(i for i,l in enumerate(s.lines) if l.startswith(f'- id: pt-{s.subj}-'))
        _,b=s.span(s.lines[last][6:])
        blk=[f'- id: {pid}',f'  subject: {s.subj}','  name: x',f"  theme: {th if th else chr(39)*2}",'  members:']+['  - '+k for k in sorted(keys)]
        s.lines[b:b]=blk; s.rename(pid,name); s.log.append(('new',src,pid,keys))
    def merge(s,src,dst):
        a,b=s.span(src); assert not any(l.startswith('  merged_into') for l in s.lines[a:b])
        s.lines[b:b]=[f'  merged_into: {dst}']; s.log.append(('merge',src,dst,s.members(src)))
    def save(s): open(PATH,'w',encoding='utf-8').write('\n'.join(s.lines))
