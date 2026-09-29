"""학업지속 상담 API. 실행: uvicorn app.main:app --port 8000"""
import json, os, sqlite3, datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from . import rules

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / 'data' / 'app.db'
app = FastAPI(title='학업지속 상담 API')

def q(sql, args=()):
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute(sql, args)]

def x(sql, args=()):
    with sqlite3.connect(DB) as c: c.execute(sql, args); c.commit()

now = lambda: datetime.datetime.now().isoformat(timespec='seconds')
MODEL_DIR = ROOT / 'models'
MODELS = {}
try:  # 노트북에서 model.save_model('models/조기.cbm') 로 저장하면 실시간 예측 활성화
    from catboost import CatBoostClassifier
    for k in ('조기', '중도'):
        f = MODEL_DIR / f'{k}.cbm'
        if f.exists(): MODELS[k] = CatBoostClassifier().load_model(str(f))
except ImportError:
    pass
BEDROCK = os.getenv('BEDROCK_MODEL_ID')  # 설정 시 AI 브리핑을 Bedrock으로 생성

@app.get('/api/health')
def health():
    return dict(api='ok', db=DB.exists(), students=q('select count(*) n from students')[0]['n'],
                model='실시간 추론' if MODELS else '학기 배치 예측', model_version='CatBoost, 2026-2학기 배치',
                briefing='Bedrock' if BEDROCK else 'Claude 사전 작성 + 규칙 초안',
                claude_briefs=q("select count(*) n from briefs where source='claude'")[0]['n'])

def students_payload():
    S = {r['id']: dict(id=r['id'], type=r['type'], sev=r['severity'], tier=r['tier'], tags=json.loads(r['tags']), m={}, prog=[], sch=[])
         for r in q('select * from students')}
    for r in q('select student_id,model,prob,threshold from predictions'):
        S[r['student_id']]['m'][r['model']] = dict(p=r['prob'], thr=r['threshold'], up=[], dn=[])
    for r in q('select * from prediction_factors order by rank'):  # 민감값은 마스킹해서 전달
        v, b = (None, None) if r['sensitive'] else (r['value'], r['baseline'])
        S[r['student_id']]['m'][r['model']][r['direction']].append([r['feature'], v, b, r['shap'], r['sensitive']])
    for r in q('select * from student_matches order by rank'):
        s = S[r['student_id']]
        (s['prog'].append([r['support_id'], json.loads(r['hit_tags'])]) if r['kind'] == 'program' else s['sch'].append(r['support_id']))
    return list(S.values())

@app.get('/api/bootstrap')
def bootstrap():
    meta = json.loads(q('select json from model_performance')[0]['json'])
    imgs = {p.stem: f'/static/img/{p.name}' for p in (ROOT / 'static' / 'img').glob('*.png')}
    return dict(**meta, students=students_payload(), images=imgs, guides=rules.GUIDE, crisis=rules.CRISIS,
                programs=[dict(n=r['name'], c=r['main_comp'], cs=r['comps'], d=r['dept'], y=r['years']) for r in q('select * from programs order by id')],
                scholarships=[dict(n=r['title'], k=r['kind'], t=r['period'], a=r['target'], m=r['amount']) for r in q('select * from scholarships order by id')],
                logs=q('select * from counsel_logs order by date desc, id desc'))

def one(sid):
    s = next((s for s in students_payload() if s['id'] == sid), None)
    if not s: raise HTTPException(404, '학생을 찾을 수 없습니다')
    return s

@app.post('/api/students/{sid}/brief')
def brief(sid: str, refresh: bool = False):
    c = q('select * from briefs where student_id=?', (sid,))
    if c and (not refresh or c[0]['source'] == 'claude'):  # 배치로 작성된 Claude 브리핑은 유지
        return dict(source=c[0]['source'], created_at=c[0]['created_at'], **json.loads(c[0]['json']))
    s = one(sid)
    P = [dict(n=r['name']) for r in q('select name from programs order by id')]
    Sch = [dict(n=r['title']) for r in q('select title from scholarships order by id')]
    b, src = rules.rule_brief(s, P, Sch), 'rule'
    if BEDROCK:
        try: b, src = bedrock_brief(s, b), 'bedrock'
        except Exception as e: print('bedrock 실패, 규칙 브리핑 사용:', e)
    x('insert or replace into briefs values(?,?,?,?)', (sid, src, json.dumps(b, ensure_ascii=False), now()))
    return dict(source=src, created_at=now(), **b)

def bedrock_brief(s, base):
    """본선: Bedrock Claude로 브리핑 생성. 입력은 비민감 요인·매칭 결과만"""
    import boto3
    facts = [(rules.label(f[0]), f[1], round(f[3], 2)) for k in s['m'] for f in s['m'][k]['up'] if not f[4]]
    prompt = ("너는 대학 상담교수를 돕는 조수다. 아래 예측 결과로 상담 브리핑을 JSON {summary, questions[3], connects[3]} 으로만 답해라. "
              "SHAP 요인은 원인이 아니라 관련 요인으로 표현하고, 진단·낙인 표현을 쓰지 마라.\n"
              f"확률: {[(k, v['p'], v['thr']) for k, v in s['m'].items()]}\n요인: {facts}\n태그: {s['tags']}\n후보 지원: {base['connects']}")
    r = boto3.client('bedrock-runtime').converse(modelId=BEDROCK, messages=[{'role': 'user', 'content': [{'text': prompt}]}], inferenceConfig={'maxTokens': 800})
    t = r['output']['message']['content'][0]['text']
    return json.loads(t[t.find('{'):t.rfind('}') + 1])

@app.post('/api/students/{sid}/reveal')
def reveal(sid: str):
    one(sid); x('insert into access_logs(student_id,action,created_at) values(?,?,?)', (sid, 'reveal_sensitive', now()))
    out = {}
    for r in q('select model,explanation from predictions where student_id=?', (sid,)):
        out[r['model']] = dict(ex=r['explanation'], up=[], dn=[])
    for r in q('select * from prediction_factors where student_id=? order by rank', (sid,)):
        out[r['model']][r['direction']].append([r['feature'], r['value'], r['baseline'], r['shap'], r['sensitive']])
    return out

class Log(BaseModel):
    method: str; note: str; next_action: str = ''

@app.get('/api/students/{sid}/logs')
def get_logs(sid: str): return q('select * from counsel_logs where student_id=? order by date desc, id desc', (sid,))

@app.post('/api/students/{sid}/logs')
def add_log(sid: str, l: Log):
    one(sid)
    if not l.note.strip(): raise HTTPException(400, '상담 내용을 입력해야 저장할 수 있습니다')
    x('insert into counsel_logs(student_id,date,method,note,next_action,created_by) values(?,?,?,?,?,?)',
      (sid, datetime.date.today().isoformat(), l.method, l.note.strip(), l.next_action.strip(), 'counselor'))
    return get_logs(sid)

@app.get('/api/logs')
def logs(): return q('select * from counsel_logs order by date desc, id desc')

class PredictIn(BaseModel):
    model: str; features: dict

@app.post('/api/predict')
def predict(inp: PredictIn):
    """모델 연동: models/{조기|중도}.cbm 이 있으면 신규 학생 실시간 예측 + SHAP"""
    m = MODELS.get(inp.model)
    if not m: raise HTTPException(503, '모델 파일이 없습니다. 노트북에서 save_model 후 models/ 에 넣어 주세요')
    import pandas as pd
    from catboost import Pool
    X = pd.DataFrame([inp.features])[m.feature_names_]
    p = float(m.predict_proba(X)[0, 1])
    sv = m.get_feature_importance(Pool(X, cat_features=m.get_cat_feature_indices()), type='ShapValues')[0][:-1]
    top = sorted(zip(m.feature_names_, sv), key=lambda t: -abs(t[1]))[:8]
    return dict(prob=p, shap=[[f, round(float(v), 3)] for f, v in top])

app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
@app.get('/')
def index(): return FileResponse(ROOT / 'static' / 'index.html')
