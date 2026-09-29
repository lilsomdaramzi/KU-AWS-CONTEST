"""서버 없이 열어 보는 미리보기 HTML (발표·공유용). API 응답을 미리 받아 파일 하나에 넣는다"""
import json, shutil, base64, tempfile
from pathlib import Path
import app.main as M
tmp = Path(tempfile.mkdtemp()) / 'app.db'; shutil.copy(M.DB, tmp); M.DB = tmp  # 원본 DB 오염 방지
from fastapi.testclient import TestClient
c = TestClient(M.app)
boot = c.get('/api/bootstrap').json(); health = c.get('/api/health').json()
ids = [s['id'] for s in boot['students']]
briefs = {i: c.post(f'/api/students/{i}/brief').json() for i in ids}
reveal = {i: c.post(f'/api/students/{i}/reveal').json() for i in ids}
root = Path('static')
boot['images'] = {k: 'data:image/png;base64,' + base64.b64encode((root / v.replace('/static/', '')).read_bytes()).decode() for k, v in boot['images'].items()}
mock = """window.__MOCK__=(()=>{const B=%s,H=%s,BR=%s,RV=%s,L={};
return async(u,o={})=>{await new Promise(r=>setTimeout(r,u.includes('/brief')?700:60));let m;
if(u.startsWith('/api/bootstrap'))return B; if(u.startsWith('/api/health'))return H;
if(m=u.match(/students\\/(\\w+)\\/brief/))return BR[m[1]]; if(m=u.match(/students\\/(\\w+)\\/reveal/))return RV[m[1]];
if(m=u.match(/students\\/(\\w+)\\/logs/)){const id=m[1];if(o.method==='POST'){const b=JSON.parse(o.body);if(!b.note)throw new Error('상담 내용을 입력해야 저장할 수 있습니다');
 (L[id]||=[]).unshift({id:Date.now(),student_id:id,date:new Date().toISOString().slice(0,10),method:b.method,note:b.note,next_action:b.next_action});}return L[id]||[];}
throw new Error('미리보기에서 지원하지 않는 요청: '+u);};})();""" % tuple(json.dumps(x, ensure_ascii=False).replace('</', '<\\/') for x in (boot, health, briefs, reveal))
h = (root / 'index.html').read_text(encoding='utf-8')
h = h.replace('<link rel="stylesheet" href="/static/style.css">', '<style>' + (root / 'style.css').read_text(encoding='utf-8') + '</style>')
h = h.replace('<script src="/static/app.js"></script>', '<script>' + mock + '</script><script>' + (root / 'app.js').read_text(encoding='utf-8') + '</script>')
Path('preview.html').write_text(h, encoding='utf-8'); print('preview.html', len(h) // 1024, 'KB')
