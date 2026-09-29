"""원본 자료 → data.json 변환. 사용(레포 루트 기준): python WEB/build_data.py DATA WEB/data
원본폴더 아래를 하위 폴더까지 뒤져서 파일을 찾는다"""
import sys, json, base64, math, pandas as pd
from pathlib import Path
root = Path(sys.argv[1] if len(sys.argv) > 1 else '.'); out = Path(sys.argv[2] if len(sys.argv) > 2 else '.')
class _Src:  # src/'파일명' → 하위 폴더에서 같은 이름 파일을 찾아 줌
    def __truediv__(self, name):
        hit = next(root.rglob(name), None)
        return hit if hit else root / name
    def glob(self, pat): return root.rglob(pat)
src = _Src()

def clean(v):
    if v is None or (isinstance(v, float) and math.isnan(v)): return None
    if isinstance(v, float): return round(v, 3)
    return v

# 1) 모델 성능·위험군 요약
perf = pd.read_excel(src/'모델_성능요약.xlsx')
models = {}
for _, r in perf[perf['데이터'] == 'Test'].iterrows():
    models[r['모델'][:2]] = dict(thr=round(r['임계값'], 3), auc=round(r['ROC-AUC'], 3), prauc=round(r['PR-AUC'], 3),
                               recall=round(r['Recall'], 3), precision=round(r['Precision'], 3), acc=round(r['Accuracy'], 3),
                               n=int(r['N']), pos=int(r['양성']))
perf_rows = [[clean(x) for x in row] for row in perf.values.tolist()]
grp = pd.read_excel(src/'중도이탈_위험군_요약.xlsx')
grp_rows = [[clean(x) for x in row] for row in grp.values.tolist()]

# 2) SHAP 중요도 상위 8
imp = {}
for key, sh in [('조기', '조기_중요도'), ('중도', '중도_중요도')]:
    d = pd.read_excel(src/'SHAP_분석결과.xlsx', sheet_name=sh).head(8)
    imp[key] = [[r['변수'], round(r['비중(%)'], 1)] for _, r in d.iterrows()]

# 3) 대상 학생 (조기 예측자 + 중도 위험군). 실제 라벨/정오탐은 서비스에 넣지 않음
x = pd.read_excel(src/'ID별_판정사유.xlsx', sheet_name=None)
target = {'조기': x['조기이탈_예측자'], '중도': x['중도이탈_위험군']}
long = x['요인상세(long)']
long = long[long['판정'].isin(['조기이탈 예측', '위험군'])]
students = {}
for key, df in target.items():
    for _, r in df.iterrows():
        sid = str(r['ID'])
        f = long[(long['ID'] == r['ID']) & (long['모델'].str.startswith(key))].sort_values(['구분', '순위'])
        up = [[a, clean(b), clean(c), round(d, 3)] for a, b, c, d in f[f['구분'] == '위험↑'][['변수', '학생값', '전체기준값', 'SHAP']].values]
        dn = [[a, clean(b), clean(c), round(d, 3)] for a, b, c, d in f[f['구분'] == '위험↓'][['변수', '학생값', '전체기준값', 'SHAP']].values]
        students.setdefault(sid, {'id': sid, 'm': {}})['m'][key] = dict(p=round(r['예측확률'], 3), thr=round(r['판정기준(임계값)'], 3), up=up, dn=dn, ex=r['설명'])

# 4) 비교과 / 장학
prog = pd.read_excel(src/'비교과프로그램_프로그램별_그룹화_1.xlsx')
programs = [dict(n=r['프로그램명'], c=r['대표역량'], cs=r['핵심역량'], d=r['운영부서'], y=str(r['운영년도'])) for _, r in prog.iterrows()]
sch = pd.read_csv(src/'장학공지_crawling.csv', encoding='utf-8-sig')
sch = sch[sch['성격'] != '공지/안내'].drop_duplicates('제목')
scholarships = [dict(n=r['제목'], k=r['성격'], t=clean(r['신청날짜']), a=clean(r['지원대상']), m=clean(r['금액'])) for _, r in sch.iterrows()]

# 5) 시각화 이미지
imgs = {}
for f in ['roc_early', 'roc_mid', 'shap_조기이탈_summary', 'shap_중도이탈_summary'] + [p.stem for p in src.glob('shap_ID_*.png')]:
    p = src/f'{f}.png'
    if p.exists(): imgs[f] = 'data:image/png;base64,' + base64.b64encode(p.read_bytes()).decode()

data = dict(models=models, perf=perf_rows, perfCols=perf.columns.tolist(), groups=grp_rows, groupCols=grp.columns.tolist(),
            importance=imp, students=list(students.values()), programs=programs, scholarships=scholarships, images=imgs)
(out/'data.json').write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print(f"students={len(students)} programs={len(programs)} scholarships={len(scholarships)} images={len(imgs)}")
