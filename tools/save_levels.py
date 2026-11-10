import yaml,json,glob
lv={}
for f in glob.glob('data/exams/*/*.yaml'):
    d=yaml.load(open(f,encoding='utf8'),Loader=yaml.CSafeLoader); e=f.split('/')[-2]
    for q in d['questions']:
        fr=q.get('freq') or {}
        if fr: lv[f"{e}|{d['subject']}|{q['num']}"]=[fr.get('level'),fr.get('why')]
json.dump(lv,open('/tmp/levels_before.json','w')); print(len(lv))
