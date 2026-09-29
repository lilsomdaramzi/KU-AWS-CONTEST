"""data.json → data/app.db (SQLite) + static/img. 사용: python build_data.py <원본폴더> data && python load_db.py"""
import json, sqlite3, base64
from pathlib import Path
from app import rules
D = json.loads(Path('data/data.json').read_text(encoding='utf-8'))
db = Path('data/app.db'); db.unlink(missing_ok=True)
c = sqlite3.connect(db)
c.executescript("""
CREATE TABLE students(id TEXT PRIMARY KEY, type TEXT, severity REAL, tier TEXT, tags TEXT);
CREATE TABLE predictions(student_id TEXT, model TEXT, prob REAL, threshold REAL, explanation TEXT, model_version TEXT);
CREATE TABLE prediction_factors(student_id TEXT, model TEXT, direction TEXT, rank INT, feature TEXT, value TEXT, baseline TEXT, shap REAL, tag TEXT, sensitive INT);
CREATE TABLE programs(id INT PRIMARY KEY, name TEXT, main_comp TEXT, comps TEXT, dept TEXT, years TEXT);
CREATE TABLE scholarships(id INT PRIMARY KEY, title TEXT, kind TEXT, period TEXT, target TEXT, amount TEXT);
CREATE TABLE student_matches(student_id TEXT, kind TEXT, support_id INT, rank INT, hit_tags TEXT);
CREATE TABLE model_performance(json TEXT);
CREATE TABLE counsel_logs(id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, date TEXT, method TEXT, note TEXT, next_action TEXT, created_by TEXT);
CREATE TABLE briefs(student_id TEXT PRIMARY KEY, source TEXT, json TEXT, created_at TEXT);
CREATE TABLE access_logs(id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, action TEXT, created_at TEXT);
""")
P, S = D['programs'], D['scholarships']
c.executemany('INSERT INTO programs VALUES(?,?,?,?,?,?)', [(i, p['n'], p['c'], p['cs'], p['d'], p['y']) for i, p in enumerate(P)])
c.executemany('INSERT INTO scholarships VALUES(?,?,?,?,?,?)', [(i, x['n'], x['k'], x['t'], x['a'], x['m']) for i, x in enumerate(S)])
for st in D['students']:
    sid, m = st['id'], st['m']
    tags, w = rules.tags_of(m); sev = rules.severity(m)
    c.execute('INSERT INTO students VALUES(?,?,?,?,?)', (sid, '둘 다' if len(m) == 2 else list(m)[0], sev, '위험' if sev >= .5 else '경고', json.dumps(tags, ensure_ascii=False)))
    for k, x in m.items():
        c.execute('INSERT INTO predictions VALUES(?,?,?,?,?,?)', (sid, k, x['p'], x['thr'], x['ex'], 'catboost-batch-test'))
        for d, arr in (('up', x['up']), ('dn', x['dn'])):
            c.executemany('INSERT INTO prediction_factors VALUES(?,?,?,?,?,?,?,?,?,?)',
                          [(sid, k, d, r + 1, f, None if v is None else str(v), None if b is None else str(b), sh, rules.tag_of(f), int(bool(rules.SENS.search(f))))
                           for r, (f, v, b, sh) in enumerate(arr)])
    for r, (i, hit) in enumerate(rules.match_programs(tags, w, P)):
        c.execute('INSERT INTO student_matches VALUES(?,?,?,?,?)', (sid, 'program', i, r, json.dumps(hit, ensure_ascii=False)))
    for r, i in enumerate(rules.match_scholar(tags, S)):
        c.execute('INSERT INTO student_matches VALUES(?,?,?,?,?)', (sid, 'scholarship', i, r, '[]'))
meta = {k: D[k] for k in ('models', 'perf', 'perfCols', 'groups', 'groupCols', 'importance')}
c.execute('INSERT INTO model_performance VALUES(?)', (json.dumps(meta, ensure_ascii=False),))
cb = Path('data/claude_briefs.json')  # 학기 배치: Claude Opus 5.5가 사전 작성한 브리핑
if cb.exists():
    for sid, b in json.loads(cb.read_text(encoding='utf-8')).items():
        c.execute('INSERT INTO briefs VALUES(?,?,?,?)', (sid, 'claude', json.dumps(b, ensure_ascii=False), '2026-09-29 (2026-2학기 배치)'))
c.commit()
img = Path('static/img'); img.mkdir(parents=True, exist_ok=True)
for k, v in D['images'].items(): (img / f'{k}.png').write_bytes(base64.b64decode(v.split(',', 1)[1]))
print('db ok:', c.execute('select count(*) from students').fetchone()[0], 'students')
