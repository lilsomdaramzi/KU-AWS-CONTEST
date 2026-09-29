/* 학업지속 상담 프론트엔드. 모든 데이터는 FastAPI(/api/*)에서 받는다 */
const api=async(u,o={})=>{if(window.__MOCK__)return window.__MOCK__(u,o);const r=await fetch(u,{headers:{'Content-Type':'application/json'},...o});if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||r.statusText);return r.json();};
const LABEL={휴학비율:'휴학 비율',평점_1_1:'1학년 1학기 평점',평균_소득분위:'평균 소득분위',일반휴학_여부:'일반휴학 여부',모집전형:'모집전형',
 성적변화량_분산:'성적 변화량 분산',비교과_참여횟수:'비교과 참여 횟수',휴학학기:'휴학 학기 수',성적변화량:'성적 변화량',성적경고_횟수:'성적경고 횟수',
 직전학기_평점:'직전학기 평점',전체_평점:'전체 평점',최저평점:'최저 평점',저성적_학기수:'저성적 학기 수',최근_성적_증감:'최근 성적 증감',
 초과학기_여부:'초과학기 여부',수능_가중등급:'수능 가중등급',추가합격_여부:'추가합격 여부',응시구분:'응시구분',학과명:'학과(코드)',
 고교유형:'고교 유형',고교지역A:'고교 지역 A',고교지역B:'고교 지역 B',지원자_세부유형:'지원자 세부유형',성별:'성별',소득분위_변화:'소득분위 변화',
 최근_성적경고_상태:'최근 성적경고 상태',성적_분산:'성적 분산',평점_1_1_Ponly:'1-1학기 P/F만 이수',전체_평점_Ponly:'전체 P/F만 이수',
 직전학기_평점_Ponly:'직전학기 P/F만 이수',전과_여부:'전과 여부',다전공_이수_여부:'다전공 이수',교환학생_여부:'교환학생',학점교류_여부:'학점교류',소속변경_여부:'소속변경'};
const lbl=v=>LABEL[v]||v.replace(/_/g,' ');
const MK={조기:'조기이탈',중도:'중도이탈'};
let D,STUDENTS,LOGS={},HEALTH={};
const byId=id=>STUDENTS.find(s=>s.id===id);
const sorted=()=>[...STUDENTS].sort((a,b)=>b.sev-a.sev);
const groupLogs=L=>{LOGS={};L.forEach(l=>(LOGS[l.student_id]||=[]).push(l));};
const allLogs=()=>Object.values(LOGS).flat().map(l=>({...l,s:byId(l.student_id)})).filter(l=>l.s).sort((a,b)=>b.date.localeCompare(a.date)||b.id-a.id);

/* ======================= 공통 UI ======================= */
const $=q=>document.querySelector(q);
const esc=t=>String(t??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function box({cls='',title,api:a,body,more,moreTab,flush,after='',head='',pre=''}){
  return `<section class="box ${cls}"><div class="bh"><h3>${title}</h3>${head}${more?`<button class="more" data-go="${moreTab}">${more}</button>`:''}</div>
  <div class="api">${a}</div>${pre}<div class="bb ${flush?'flush':''}">${body}</div>${after}</section>`;
}
function toast(m){const t=$('#toast');t.textContent=m;t.classList.add('on');clearTimeout(t._h);t._h=setTimeout(()=>t.classList.remove('on'),1800);}
const pct=x=>(x*100).toFixed(1)+'%';
const tierOfM=x=>x.p>=(x.thr+1)/2?'위험':'경고';
const typeBadges=s=>Object.keys(s.m).map(k=>`<span class="badge t-${tierOfM(s.m[k])}">${MK[k]}</span>`).join(' ');
const srow=(s,attr='data-sel')=>`<button class="srow t-${s.tier}" ${attr}="${s.id}" aria-current="${s.id===state.sel}"><span class="nm">학생 ${s.id}</span><span class="sc">${Object.keys(s.m).map(k=>pct(s.m[k].p)).join(' / ')}</span>
  <span class="mt">${Object.keys(s.m).map(k=>MK[k]).join(', ')}${s.tags.length?`, ${s.tags.slice(0,2).join('·')} 요인`:''}</span><span class="st ${LOGS[s.id]?'done':''}">${LOGS[s.id]?'상담 완료':'미상담'}</span></button>`;

let state={tab:'dash',sel:null,type:'전체',q:'',mview:null,shapImg:false,supKind:'비교과',comp:'',supQ:'',sup:0,alertView:'new',
  rev:{},briefs:{},leftTab:'guide',rightTab:'match'};
const TABS={
 dash:{title:'대시보드',sub:'Test 데이터 기준 조기·중도 이탈 위험 현황입니다.'},
 stu:{title:'위험학생',sub:'학생을 선택하면 AI 상담 브리핑과 판정 사유, 상담 가이드가 열립니다.'},
 sup:{title:'장학·비교과',sub:'KUSEUM 비교과 프로그램과 장학 공지에서 위험 요인별로 연결할 학생을 찾습니다.'},
 log:{title:'상담기록',sub:'상담 기록과 후속 조치를 관리합니다.'},
 model:{title:'모델 성능',sub:'CatBoost 조기·중도 이탈 예측 모델의 검증 결과와 SHAP 해석입니다.'},
 data:{title:'시스템 구조',sub:'데이터, 모델, API, 화면이 어떻게 연결되는지 보여 줍니다.'},
};

/* ======================= 프로필 ======================= */
function renderProfile(){
  const c=k=>STUDENTS.filter(s=>s.m[k]).length;
  $('#pAll').textContent=STUDENTS.length; $('#pE').textContent=c('조기'); $('#pM').textContent=c('중도');
  const pend=sorted().filter(s=>s.tier==='위험'&&!LOGS[s.id]), done=sorted().filter(s=>LOGS[s.id]);
  $('#ptNew').textContent=`미상담 위험(${pend.length})`; $('#ptSeen').textContent=`상담 완료(${done.length})`;
  $('#ptNew').setAttribute('aria-pressed',state.alertView==='new'); $('#ptSeen').setAttribute('aria-pressed',state.alertView==='seen');
  const L=(state.alertView==='new'?pend:done).slice(0,60);
  $('#palerts').innerHTML=L.length?L.map(s=>`<button data-open="${s.id}"><div class="an">학생 ${s.id} ${typeBadges(s)}</div>
   <div class="ad">${Object.keys(s.m).map(k=>`${MK[k]} <em>${pct(s.m[k].p)}</em>`).join(', ')}</div></button>`).join('')
   :`<p class="empty" style="padding:24px 12px;text-align:center">${state.alertView==='new'?'미상담 위험 학생이 없습니다.':'아직 상담한 학생이 없습니다.'}</p>`;
}
function renderStatus(){
  $('#sys').innerHTML=[['API',HEALTH.api==='ok'],['DB',HEALTH.db],['모델 2026-2',true],['AI 브리핑',true]]
    .map(([n,ok])=>`<span class="dot ${ok?'on':''}" title="${n}">${n}</span>`).join('');
  $('#sys').title=`DB 학생 ${HEALTH.students}명, 모델: ${HEALTH.model}, 브리핑: ${HEALTH.briefing}`;
}

/* ======================= 대시보드 ======================= */
function vDash(){
  const n=f=>STUDENTS.filter(f).length, tot=STUDENTS.length;
  const lines=[['조기이탈 예측',s=>s.m.조기,'위험'],['중도이탈 위험군',s=>s.m.중도,'경고'],['두 모델 모두',s=>s.type==='둘 다','위험']];
  const stat=`<div class="bigs"><div><small>상담 대상 학생</small><b>${tot}명</b></div><div><small>긴급(위험 등급)</small><b>${n(s=>s.tier==='위험')}명</b></div></div>`
   +lines.map(([l,f,t])=>`<div class="tierline t-${t}" style="grid-template-columns:110px 1fr 52px"><span class="lb">${l}</span><span class="tr"><i style="width:${n(f)/tot*100}%"></i></span><span class="n">${n(f)}명</span></div>`).join('');
  const top=sorted().slice(0,12).map(s=>`<button class="item" data-open="${s.id}"><div class="it">학생 ${s.id} ${typeBadges(s)}</div><div class="id">${Object.keys(s.m).map(k=>`${MK[k]} ${pct(s.m[k].p)}`).join(', ')}, 주요 요인 ${esc(lbl((s.m.중도||s.m.조기).up[0]?.[0]||'-'))}</div></button>`).join('');
  const imp=k=>D.importance[k].slice(0,6).map(([v,w])=>`<div class="deptrow"><div class="dn"><span>${lbl(v)}</span><span>${w}%</span></div><div class="stack"><i style="width:${w/D.importance[k][0][1]*100}%;background:var(--ku)"></i></div></div>`).join('');
  const impBox=`<div class="imgs" style="gap:18px"><div><div class="id" style="font-weight:600;margin-bottom:4px">조기이탈</div>${imp('조기')}</div><div><div class="id" style="font-weight:600;margin-bottom:4px">중도이탈</div>${imp('중도')}</div></div>`;
  const todo=allLogs().filter(l=>l.next_action).map(l=>`<button class="item" data-open="${l.s.id}"><div class="it">${esc(l.next_action)}</div><div class="id">학생 ${l.s.id}, ${l.date} 상담</div></button>`).join('')||'<p class="empty">대기 중인 후속 조치가 없습니다. 상담 기록에 다음 조치를 적으면 여기에 모입니다.</p>';
  const M=D.models, perf=['조기','중도'].map(k=>`<div class="kv"><span>${MK[k]} AUC / Recall</span><b>${M[k].auc} / ${M[k].recall}</b></div><div class="kv"><span>${MK[k]} 판정 임계값</span><b>${M[k].thr}</b></div>`).join('');
  const comp={}; D.programs.forEach(p=>comp[p.c]=(comp[p.c]||0)+1);
  const prog=Object.entries(comp).sort((a,b)=>b[1]-a[1]).map(([c,v])=>`<div class="kv"><span>${c}</span><b>${v}개</b></div>`).join('')+`<div class="kv"><span>장학 공지</span><b>${D.scholarships.length}건</b></div>`;
  return box({title:'위험 현황',api:'GET /api/bootstrap  |  students, predictions',body:stat,more:'목록 보기',moreTab:'stu'})
   +box({title:'우선 상담 대상',api:'students.severity 내림차순',body:top,more:'더보기',moreTab:'stu'})
   +box({title:'후속 조치 대기',api:'counsel_logs.next_action',body:todo,more:'더보기',moreTab:'log'})
   +box({title:'주요 위험 요인 (SHAP 비중)',api:'model_performance.importance',body:impBox,more:'모델 성능',moreTab:'model'})
   +box({title:'모델 요약 (Test)',api:'model_performance',body:perf,more:'자세히',moreTab:'model'})
   +box({title:'연결 가능한 지원',api:'programs, scholarships',body:prog,more:'더보기',moreTab:'sup'});
}

/* ======================= 위험학생 ======================= */
function filtered(){const q=state.q.trim();
  return sorted().filter(s=>(state.type==='전체'||(state.type==='둘 다'?s.type==='둘 다':!!s.m[state.type]))&&(!q||s.id.includes(q)));}
function listHTML(){const r=filtered();return r.length?r.slice(0,300).map(s=>srow(s)).join(''):'<p class="empty" style="padding:16px">조건에 맞는 학생이 없습니다. 필터를 바꿔 보세요.</p>';}
async function loadBrief(id,refresh=false){
  state.briefs[id]='loading'; if(state.sel===id&&state.tab==='stu') render();
  try{state.briefs[id]=await api(`/api/students/${id}/brief${refresh?'?refresh=true':''}`,{method:'POST'});}
  catch(e){state.briefs[id]={error:e.message};}
  if(state.sel===id&&state.tab==='stu') render();
}
const SRC={claude:'Claude Opus 5.5 작성 (학기 배치)',bedrock:'AWS Bedrock 생성',rule:'예측 결과 기반 자동 초안 (Claude 배치 대상 외)'};
function briefHTML(s){
  const b=state.briefs[s.id], ks=Object.keys(s.m), rv=state.rev[s.id];
  const meters=ks.map(k=>{const x=s.m[k];return `<div class="mrow t-${tierOfM(x)}"><span class="ml">${k}</span><div>
    <div class="meter-top" style="margin-bottom:4px"><span class="val" style="font-size:20px">${pct(x.p)}</span><span class="lbl">${MK[k]} 확률, 기준 ${pct(x.thr)}</span></div>
    <div class="scale" style="background:linear-gradient(90deg,var(--calm-soft) 0 ${x.thr*100}%,var(--warn-soft) ${x.thr*100}% ${(x.thr+1)*50}%,var(--ku-soft) ${(x.thr+1)*50}%)"><span class="thr" style="left:${x.thr*100}%"></span><span class="pin" style="left:${x.p*100}%"></span></div></div></div>`;}).join('');
  const body=!b||b==='loading'?`<div class="ai-loading"><span class="spark"></span>AI가 예측 결과와 판정 사유를 읽고 브리핑을 쓰는 중입니다…</div>`
   :b.error?`<p class="empty">브리핑을 불러오지 못했습니다: ${esc(b.error)}</p>`
   :`<div class="bf-cols"><div><h4>한눈에 보기</h4><p>${esc(b.summary)}</p></div>
     <div><h4>상담 때 확인할 것</h4><ul>${b.questions.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>
     <div><h4>먼저 연결할 지원</h4><ul>${b.connects.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div></div>`;
  return `<div class="bf t-${s.tier}"><div class="bf-top"><div class="who"><b>학생 ${s.id}</b><span class="badge">${s.tier}</span>${typeBadges(s)}</div><div class="bf-meters">${meters}</div></div>
   ${body}${rv?ks.map(k=>`<div class="ex"><b>${MK[k]} 판정 설명</b> ${esc(rv[k].ex)}</div>`).join(''):''}
   ${b&&b.caution?`<div class="bf-caution"><b>상담 시 유의</b> ${esc(b.caution)}</div>`:''}
   <p class="bf-note">${b&&b.source?`${SRC[b.source]||b.source}, ${esc((b.created_at||'').replace('T',' '))}. `:''}예측 요인은 관련성이며 원인을 뜻하지 않습니다.</p></div>`;
}
function vStu(){
  if(!state.sel||!byId(state.sel)) state.sel=filtered()[0]?.id;
  const s=byId(state.sel), ks=Object.keys(s.m);
  if(!state.briefs[s.id]) loadBrief(s.id);
  if(!state.mview||!s.m[state.mview]) state.mview=ks[0];
  const rv=state.rev[s.id], m=rv?{...s.m[state.mview],...rv[state.mview]}:s.m[state.mview];
  const filters=`<div class="filters"><div class="chips">${['전체','조기','중도','둘 다'].map(t=>`<button data-type="${t}" aria-pressed="${state.type===t}">${t}</button>`).join('')}</div>
   <div class="frow"><input id="fq" type="search" placeholder="학생 ID 검색" value="${esc(state.q)}" aria-label="학생 ID 검색"></div></div>`;
  const list=`<section class="box a-list"><div class="bh"><h3>상담 대상 (${filtered().length}명)</h3></div><div class="api">GET /api/bootstrap  |  students ⋈ predictions</div>${filters}<div class="bb flush" id="slist">${listHTML()}</div></section>`;
  const mx=Math.max(...[...m.up,...m.dn].map(f=>Math.abs(f[3])));
  const fr=f=>{const h=f[4]&&!rv;return `<div class="factor"><div>${esc(lbl(f[0]))} <span class="fv">${h?'<span class="lock">비공개</span>':esc(f[1]??'값없음')}</span><div class="fb">${h?'민감정보':'전체 기준 '+esc(f[2]??'-')}</div></div>
    <div class="bar"><i class="${f[3]>0?'up':'down'}" style="width:${Math.abs(f[3])/mx*50}%"></i></div><div class="sv">${f[3]>0?'+':''}${f[3].toFixed(2)}</div></div>`;};
  const imgKey=`shap_ID_${MK[state.mview]}_${s.id}`, hasImg=!!D.images[imgKey]&&rv;
  const shap=(state.shapImg&&hasImg?`<img class="shapimg" src="${D.images[imgKey]}" alt="학생 ${s.id} SHAP 그림">`:[...m.up,...m.dn].map(fr).join('')
    +`<div class="legend"><span><i style="background:var(--risk)"></i>위험을 높임</span><span><i style="background:var(--protect)"></i>위험을 낮춤</span></div>`)
    +(hasImg?`<p style="margin:8px 0 0"><button class="more" style="margin:0;color:var(--ku)" id="togImg">${state.shapImg?'막대로 보기':'원본 SHAP 그림 보기'}</button></p>`:'');
  const seg=ks.length>1?`<div class="seg2">${ks.map(k=>`<button data-mview="${k}" aria-pressed="${state.mview===k}">${k}</button>`).join('')}</div>`:'';
  const guide=`<div class="guide">${['기본',...s.tags.filter(t=>D.guides[t]).slice(0,3)].map(t=>`<h4>${D.guides[t].t}</h4><ul>${D.guides[t].li.map(x=>`<li>${x}</li>`).join('')}</ul><div class="gs">${D.guides[t].src}</div>`).join('')}<div class="crisis">${D.crisis}</div></div>`;
  const match=(s.prog.map(([i,hit])=>{const p=D.programs[i];return `<div class="item match"><div class="it"><span class="mk">비교과</span>${esc(p.n)}</div>
     <div class="mr">관련 요인 <em>${hit.join(', ')}</em>, 대표역량 ${esc(p.c)}</div><div class="id">${esc(p.d)}, ${esc(p.y)} <a href="https://kuseum.korea.ac.kr" target="_blank" rel="noopener">쿠세움 신청</a></div></div>`;}).join('')
    +s.sch.map(i=>{const x=D.scholarships[i];return `<div class="item match"><div class="it"><span class="mk">${esc(x.k)}</span>${esc(x.n)}</div><div class="id">${x.m?esc(x.m)+', ':''}${x.t?esc(x.t)+' 신청':'공고 확인'}</div></div>`;}).join(''))
    ||'<p class="empty">위험 요인과 연결되는 지원 항목이 없습니다.</p>';
  const logs=LOGS[s.id]||[];
  const logBody=`<div class="logform" style="padding:0 0 10px"><select id="lmethod" aria-label="방식"><option>대면</option><option>전화</option><option>메일</option></select>
    <input id="lnext" placeholder="다음 조치 (예: 학습코칭 신청 안내)" aria-label="다음 조치"><textarea id="lnote" placeholder="상담 내용" aria-label="상담 내용"></textarea><button id="saveLog">기록 저장</button></div>`
    +(logs.length?logs.map(l=>`<div class="item"><div class="id">${l.date} ${l.method}</div><div>${esc(l.note)}</div>${l.next_action?`<div class="id">다음 조치: ${esc(l.next_action)}</div>`:''}</div>`).join(''):'<p class="empty">아직 상담 기록이 없습니다.</p>');
  const tabs=(side,items)=>`<div class="btabs" role="tablist">${items.map(([k,n])=>`<button role="tab" data-${side}="${k}" aria-selected="${state[side+'Tab']===k}">${n}</button>`).join('')}</div>`;
  const L={guide:[`상담 가이드`,guide,'guides × 요인 태그'],shap:[`판정 사유 (${MK[state.mview]})`,shap,'prediction_factors']};
  const R={match:['연결할 지원',match,'student_matches → programs, scholarships'],log:[`상담 기록 (${logs.length})`,logBody,'GET|POST /api/students/{id}/logs  |  counsel_logs']};
  const revealBtn=`<button class="reveal" id="reveal" aria-pressed="${!!rv}">${rv?'민감정보 숨기기':'민감정보 보기'}</button>`;
  return list
   +box({cls:'a-brief ai',title:'<span class="ai-chip">AI</span> 상담 브리핑',head:`${state.briefs[s.id]?.source?`<span class="src-chip ${state.briefs[s.id].source}">${state.briefs[s.id].source==='claude'?'Claude':'초안'}</span>`:''}${state.briefs[s.id]?.source&&state.briefs[s.id].source!=='claude'?'<button class="more regen" id="regen">다시 생성</button>':''}${revealBtn}`,api:'POST /api/students/{id}/brief  |  predictions + prediction_factors + student_matches → briefs',body:briefHTML(s)})
   +`<section class="box a-left"><div class="bh">${tabs('left',[['guide','상담 가이드'],['shap','판정 사유']])}${state.leftTab==='shap'?seg:''}</div><div class="api">${L[state.leftTab][2]}</div><div class="bb big">${L[state.leftTab][1]}</div></section>`
   +`<section class="box a-right"><div class="bh">${tabs('right',[['match','연결할 지원'],['log',`상담 기록 (${logs.length})`]])}</div><div class="api">${R[state.rightTab][2]}</div><div class="bb big">${R[state.rightTab][1]}</div></section>`;
}

/* ======================= 장학·비교과 ======================= */
function supList(){const q=state.supQ.trim();
  if(state.supKind==='비교과') return D.programs.filter(p=>(!state.comp||p.c===state.comp)&&(!q||p.n.includes(q)));
  return D.scholarships.filter(p=>!q||p.n.includes(q));}
const supTargets=i=>sorted().filter(s=>state.supKind==='비교과'?s.prog.some(x=>x[0]===i):s.sch.includes(i));
function vSup(){
  const L=supList(); if(!L.find(p=>p.i===state.sup)) state.sup=L[0]?.i;
  const arr=state.supKind==='비교과'?D.programs:D.scholarships, p=arr[state.sup];
  const comps=[...new Set(D.programs.map(p=>p.c))];
  const rows=L.map(x=>`<button class="suprow" data-supsel="${x.i}" aria-current="${x.i===state.sup}"><span class="kind">${esc(state.supKind==='비교과'?x.c:x.k.replace('/일반',''))}</span>
    <span><div class="sn">${esc(x.n)}</div><div class="sd">${esc(state.supKind==='비교과'?`${x.d}, ${x.y}`:`${x.t||'신청시기 공고 확인'}${x.m?', '+x.m:''}`)}</div></span><span class="cnt">${supTargets(x.i).length}명</span></button>`).join('')||'<p class="empty" style="padding:16px">검색 결과가 없습니다.</p>';
  const filt=`<div class="filters"><div class="chips">${['비교과','장학'].map(k=>`<button data-kind="${k}" aria-pressed="${state.supKind===k}">${k}</button>`).join('')}</div>
    <div class="frow">${state.supKind==='비교과'?`<select id="scomp" aria-label="핵심역량"><option value="">전체 역량</option>${comps.map(c=>`<option ${state.comp===c?'selected':''}>${c}</option>`).join('')}</select>`:''}
    <input id="sq" type="search" placeholder="이름 검색" value="${esc(state.supQ)}" aria-label="지원 검색"></div></div>`;
  const det=!p?'<p class="empty">항목을 선택하세요.</p>':state.supKind==='비교과'
    ?`<div class="detail"><h4>${esc(p.n)}</h4><div class="kv"><span>핵심역량</span><b>${esc(p.cs)}</b></div><div class="kv"><span>운영부서</span><b>${esc(p.d)}</b></div><div class="kv"><span>운영년도</span><b>${esc(p.y)}</b></div>
      <a class="apply" href="https://kuseum.korea.ac.kr" target="_blank" rel="noopener">쿠세움에서 보기</a></div>`
    :`<div class="detail"><h4>${esc(p.n)}</h4><div class="kv"><span>구분</span><b>${esc(p.k)}</b></div><div class="kv"><span>신청시기</span><b>${esc(p.t||'공고 확인')}</b></div>
      <div class="kv"><span>금액</span><b>${esc(p.m||'-')}</b></div><div class="item"><div class="id">지원대상</div>${esc(p.a||'공고 원문 확인')}</div></div>`;
  const tg=p?supTargets(state.sup):[];
  return `<section class="box a-slist"><div class="bh"><h3>${state.supKind==='비교과'?'비교과 프로그램':'장학 공지'} (${L.length})</h3></div><div class="api">${state.supKind==='비교과'?'programs':'scholarships'}</div>${filt}<div class="bb flush">${rows}</div></section>`
   +box({cls:'a-sdet',title:'상세',api:'programs / scholarships',body:det})
   +box({cls:'a-sstu',title:`연결할 학생 (${tg.length}명)`,api:'student_matches 역조회',body:tg.length?tg.slice(0,200).map(s=>srow(s,'data-open')).join(''):'<p class="empty" style="padding:16px">이 항목과 요인이 맞는 학생이 없습니다.</p>',flush:true});
}

/* ======================= 상담기록 ======================= */
function vLog(){
  const L=allLogs();
  const tbl=`<table><thead><tr><th>날짜</th><th>학생</th><th>방식</th><th>내용</th><th>다음 조치</th></tr></thead><tbody>${L.map(l=>`<tr>
    <td class="nw">${l.date}</td><td class="nw"><button class="more" style="margin:0;color:var(--ku);font-weight:600" data-open="${l.s.id}">학생 ${l.s.id}</button></td>
    <td class="nw">${l.method}</td><td>${esc(l.note)}</td><td>${esc(l.next_action)||'-'}</td></tr>`).join('')}</tbody></table>`;
  const cnt=m=>L.filter(l=>l.method===m).length;
  const sum=`<div class="kv"><span>전체 상담</span><b>${L.length}건</b></div>${['대면','전화','메일'].map(m=>`<div class="kv"><span>${m}</span><b>${cnt(m)}건</b></div>`).join('')}<div class="kv"><span>후속 조치 대기</span><b>${L.filter(l=>l.next_action).length}건</b></div>`;
  const wait=sorted().filter(s=>s.tier==='위험'&&!LOGS[s.id]);
  return box({cls:'a-ltab',title:'전체 상담 기록',api:'GET /api/logs  |  counsel_logs',body:L.length?tbl:'<p class="empty" style="padding:16px">아직 상담 기록이 없습니다. 위험학생 탭에서 기록을 저장하면 DB에 쌓입니다.</p>',flush:true})
   +box({cls:'a-lsum',title:'상담 현황',api:'counsel_logs 집계',body:sum})
   +box({cls:'a-lwait',title:`상담이 필요한 위험 학생 (${wait.length}명)`,api:'students ⟕ counsel_logs',body:wait.slice(0,200).map(s=>srow(s,'data-open')).join(''),flush:true});
}

/* ======================= 모델 성능 ======================= */
function vModel(){
  const fmt=v=>typeof v==='number'&&v<1.5&&v%1?v.toFixed(3):v;
  const t=(cols,rows,num)=>`<table><thead><tr>${cols.map(c=>`<th>${c}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map((v,i)=>`<td class="${num(i)?'num':''}">${fmt(v)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  const fig=(k,c)=>D.images[k]?`<figure><img src="${D.images[k]}" alt="${c}"><figcaption>${c}</figcaption></figure>`:'';
  return box({title:'모델 성능 요약',api:'model_performance',body:t(D.perfCols,D.perf,i=>i>1),flush:true})
   +box({title:'중도이탈 위험군 요약',api:'model_performance',body:t(D.groupCols,D.groups,i=>i>0&&i<5),flush:true})
   +box({title:'ROC 곡선',api:'/static/img/roc_*.png',body:`<div class="imgs">${fig('roc_early','조기이탈')}${fig('roc_mid','중도이탈')}</div>`})
   +box({title:'SHAP 요약',api:'/static/img/shap_*_summary.png',body:`<div class="imgs">${fig('shap_조기이탈_summary','조기이탈')}${fig('shap_중도이탈_summary','중도이탈')}</div>`});
}

/* ======================= 시스템 구조 (관리자) ======================= */
function vData(){
  const col=(h,n)=>`<div class="fcol"><h5>${h}</h5>${n}</div>`, nd=(b,s,c='')=>`<div class="node ${c}"><b>${b}</b><span>${s}</span></div>`;
  const flow=`<div class="flow">
   ${col('학기마다 갱신',nd('예측 결과·판정사유','ID별_판정사유.xlsx')+nd('모델 성능·SHAP','모델_성능요약, SHAP_분석결과')+nd('비교과 프로그램','KUSEUM 263개')+nd('장학 공지','장학공지_crawling.csv')+nd('상담 가이드북','교수용, 울산대 면담'))}
   ${col('적재 (ETL)',nd('build_data.py','원천 → data.json')+nd('load_db.py','data.json → SQLite, 매칭 사전 계산')+nd('정답 라벨 제외','실제, 정탐·오탐 미적재'))}
   ${col('DB (SQLite)',nd('students · predictions','','db')+nd('prediction_factors','민감 플래그 포함','db')+nd('programs · scholarships','','db')+nd('student_matches','','db')+nd('counsel_logs · briefs · access_logs','','db'))}
   ${col('모델·AI',nd('CatBoost 학기 배치','성적 확정 후 학기마다 예측 → predictions','ai')+nd('SHAP','get_feature_importance(ShapValues)','ai')+nd('AI 브리핑','학기 배치로 Claude가 작성 → briefs, 본선: Bedrock 자동화','ai'))}
   ${col('FastAPI → 화면',nd('/api/bootstrap','대시보드, 목록','ui')+nd('/api/students/{id}/brief','AI 브리핑','ui')+nd('/api/students/{id}/reveal','민감정보, 열람 기록','ui')+nd('/api/students/{id}/logs','상담 기록','ui')+nd('AWS Elastic Beanstalk','배포','ui'))}</div>`;
  const rows=[['GET','/api/health','시스템 상태'],['GET','/api/bootstrap','목록·요약·지원·가이드 (민감값 마스킹)'],['POST','/api/students/{id}/brief','AI 상담 브리핑 생성·캐시'],
   ['POST','/api/students/{id}/reveal','민감정보 조회, access_logs 기록'],['GET·POST','/api/students/{id}/logs','상담 기록'],['GET','/api/logs','전체 상담 기록'],['POST','/api/predict','(선택) 신규 학생 수시 예측']];
  const tbl=`<table><thead><tr><th>메서드</th><th>경로</th><th>역할</th></tr></thead><tbody>${rows.map(r=>`<tr><td class="nw">${r[0]}</td><td><code>${r[1]}</code></td><td>${r[2]}</td></tr>`).join('')}</tbody></table>`;
  return box({title:'시스템 구조',api:'',body:flow})+box({title:'API 목록',api:'',body:tbl,flush:true});
}

/* ======================= 렌더 ======================= */
const VIEWS={dash:vDash,stu:vStu,sup:vSup,log:vLog,model:vModel,data:vData};
function render(){
  document.querySelectorAll('.rail button[data-tab]').forEach(b=>b.dataset.tab===state.tab?b.setAttribute('aria-current','page'):b.removeAttribute('aria-current'));
  $('#crumbTab').textContent=$('#pageTitle').textContent=TABS[state.tab].title; $('#pageSub').textContent=TABS[state.tab].sub;
  const c=$('#content'); c.className='content v-'+state.tab; c.innerHTML=VIEWS[state.tab](); renderProfile(); bind();
}
function bind(){
  if(state.tab==='stu'){
    $('#fq').oninput=e=>{state.q=e.target.value;$('#slist').innerHTML=listHTML();};
    const ti=$('#togImg'); if(ti) ti.onclick=()=>{state.shapImg=!state.shapImg;render();};
    const rg=$('#regen'); if(rg) rg.onclick=()=>loadBrief(state.sel,true);
    $('#reveal').onclick=async()=>{const id=state.sel;
      if(state.rev[id]){delete state.rev[id];state.shapImg=false;return render();}
      if(!confirm('소득분위, 성별, 출신 고교, 입학전형 등 민감정보를 표시합니다. 열람 기록이 남으며 상담 목적 외 사용을 금지합니다. 계속할까요?'))return;
      try{state.rev[id]=await api(`/api/students/${id}/reveal`,{method:'POST'});render();}catch(e){toast(e.message);}};
    const sv=$('#saveLog'); if(sv) sv.onclick=async()=>{const note=$('#lnote').value.trim();
      if(!note){toast('상담 내용을 입력해야 저장할 수 있습니다');$('#lnote').focus();return;}
      try{LOGS[state.sel]=await api(`/api/students/${state.sel}/logs`,{method:'POST',body:JSON.stringify({method:$('#lmethod').value,note,next_action:$('#lnext').value.trim()})});
        render();toast('상담 기록을 저장했습니다');}catch(e){toast(e.message);}};
  }
  if(state.tab==='sup'){const sc=$('#scomp'); if(sc) sc.onchange=e=>{state.comp=e.target.value;render();}; $('#sq').onchange=e=>{state.supQ=e.target.value;render();};}
}
function openStudent(id){state.tab='stu';state.sel=id;state.type='전체';state.q='';state.mview=null;state.shapImg=false;render();}
document.addEventListener('click',e=>{
  const t=e.target.closest('button'); if(!t||!D) return; const d=t.dataset;
  if(d.tab){state.tab=d.tab;render();} else if(d.go){state.tab=d.go;render();}
  else if(d.open){openStudent(d.open);} else if(d.sel){state.sel=d.sel;state.mview=null;state.shapImg=false;render();}
  else if(d.type){state.type=d.type;state.sel=null;render();} else if(d.mview){state.mview=d.mview;state.shapImg=false;render();}
  else if(d.left){state.leftTab=d.left;render();} else if(d.right){state.rightTab=d.right;render();}
  else if(d.kind){state.supKind=d.kind;state.sup=0;state.supQ='';render();} else if(d.supsel!==undefined){state.sup=+d.supsel;render();}
});
$('#ptNew').onclick=()=>{state.alertView='new';renderProfile();};
$('#ptSeen').onclick=()=>{state.alertView='seen';renderProfile();};
$('#pHot').onclick=()=>{state.alertView='new';renderProfile();};
$('#fold').onclick=()=>{const on=document.body.classList.toggle('folded');$('#fold').setAttribute('aria-expanded',!on);$('#fold').lastChild.textContent=on?'펼치기':'접기';};
$('#devbtn').onclick=e=>{const on=document.body.classList.toggle('dev');e.target.setAttribute('aria-pressed',on);};
const setAdmin=()=>{document.body.classList.toggle('admin',location.hash==='#admin');if(!document.body.classList.contains('admin')&&state.tab==='data')state.tab='dash';};
window.addEventListener('hashchange',()=>{setAdmin();D&&render();});

(async()=>{
  setAdmin();
  try{
    [D,HEALTH]=await Promise.all([api('/api/bootstrap'),api('/api/health')]);
    STUDENTS=D.students; D.programs.forEach((p,i)=>p.i=i); D.scholarships.forEach((p,i)=>p.i=i); groupLogs(D.logs);
    renderStatus(); render();
  }catch(e){$('#content').innerHTML=`<p class="empty" style="padding:24px">서버에 연결하지 못했습니다 (${esc(e.message)}). uvicorn이 실행 중인지 확인해 주세요.</p>`;}
})();
