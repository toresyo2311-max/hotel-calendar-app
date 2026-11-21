/* ── 🌲 자연휴양림 빈자리 탭 ─────────────────────────────────
   자료는 숲나들e(foresttrip.go.kr) 월별 예약현황 스냅샷을 tools/build_forest_data.py 가
   tab7_forest.json 으로 옮긴 것이다. 상태 코드는 수집된 값 그대로이고 추정·보간하지 않는다.
   예약 버튼은 모두 숲나들e 공식 화면으로만 연결한다. */
var frs={region:'부산/경남',type:'all',cap:0,nights:1,range:28,weekend:false,fresh:false,q:'',
           view:'list',forest:'',month:'',day:'',sort:'soon',gmonth:''};
var FRD={meta:null,sidos:[],forests:[],ready:false};
var frLastList=[];
var FR_CACHE={key:'',list:null};   /* 필터 조합이 같으면 다시 집계하지 않는다 */          /* 마지막 렌더의 필터 결과(달력·그리드 클릭 때 다시 계산하지 않는다) */
var FR_OFF='https://www.foresttrip.go.kr/indvz/main.do?hmpgId=';
var FR_MONTH='https://www.foresttrip.go.kr/rep/or/sssn/monthRsrvtStatus.do?hmpgId=FRIP&menuId=001004';

function frMeta(){return FRD.meta||{}}
function frStart(){return frMeta().start||''}
function frDayCount(){return frMeta().days||0}
function frDate(di){const b=new Date(frStart()+'T12:00:00Z').getTime()+di*86400000;return new Date(b).toISOString().slice(0,10)}
function frDi(iso){return Math.round((new Date(iso+'T12:00:00Z')-new Date(frStart()+'T12:00:00Z'))/86400000)}
function frWon(n){return n==null?'요금 미공개':KR(n)+'원'}
function frOffUrl(f){return FR_OFF+encodeURIComponent(f.id)}
/* 예약 링크 열기 — 데스크톱은 새 탭, 새 탭(팝업)을 막는 인앱 브라우저·웹뷰는 같은 탭.
   target="_blank" 만 두면 팝업을 막는 웹뷰에서 눌러도 아무 일도 일어나지 않는다. */
function frOpenExt(url){
  if(!url)return;
  let w=null;
  try{w=window.open(url,'_blank')}catch(err){w=null}
  if(w){try{w.opener=null}catch(err){}}
  else{location.href=url}
}
function frWeekendDi(di){const d=dayNo(frDate(di));return d===5||d===6}   /* 금·토 체크인 */

/* 자료 준비 — 객실마다 예약가능한 날 인덱스를 미리 뽑아 둔다 */
function frPrep(){
  if(FRD.ready||!FRD.forests.length)return;
  const days=frDayCount();
  FRD.forests.forEach(function(f){f.nwx={}});
  (FRD.new||[]).forEach(function(t){
    const f=FRD.forests[t[0]];
    if(f)f.nwx[t[1]+':'+t[2]]=1;
  });
  FRD.forests.forEach(function(f,fi){
    (f.goods||[]).forEach(function(g,gi){
      g.__fi=fi;g.__gi=gi;
      const av=[];
      for(let d=0;d<days;d++)if(g.s.charAt(d)==='A')av.push(d);
      g.__av=av;
    });
  });
  FRD.ready=true;
}

/* 객실 하나의 체크인 가능일(연박 n박 기준). g.__ck<박수> 에 캐시한다. */
function frCheckins(g,n){
  const key='__ck'+n;
  if(g[key])return g[key];
  const s=g.s||'',out=[];
  if(n>1&&typeof g.m==='number'&&g.m>0&&g.m<n){g[key]=out;return out}
  const lim=s.length-n;
  for(let d=0;d<=lim;d++){
    let ok=true;
    for(let k=0;k<n;k++){if(s.charAt(d+k)!=='A'){ok=false;break}}
    if(ok)out.push(d);
  }
  g[key]=out;return out;
}
function frTypeOK(g){
  const t=frs.type;
  if(t==='all')return true;
  if(t==='house')return g.k==='01';
  if(t==='camp')return g.k==='02';
  return g.g===t;
}
function frCapOK(g){return !frs.cap||(g.cap||0)>=frs.cap}
function frMaxDi(){const d=frDayCount()-1,lim=frs.range;return lim>0?Math.min(d,lim):d}
function frPrice(g,d){
  const p=g.p;if(!p||!p.length)return null;
  const v=frWeekendDi(d)?p[1]:p[0];
  return (typeof v==='number'&&v>0)?v:null;
}

/* 휴양림 하나의 집계 — 필터(유형·인원·박수·기간·주말)를 적용한 값 */
function frStat(f){
  const n=frs.nights,maxDi=frMaxDi(),dm={},touched={};
  let cells=0,first=null,price=null,newc=0,units=0;
  for(let i=0;i<f.goods.length;i++){
    const g=f.goods[i];
    if(!frTypeOK(g)||!frCapOK(g))continue;
    units++;
    const cs=frCheckins(g,n);
    for(let j=0;j<cs.length;j++){
      const d=cs[j];
      if(d>maxDi)continue;
      if(frs.weekend&&!frWeekendDi(d))continue;
      cells++;touched[d]=1;
      if(!dm[d])dm[d]={c:0,f:0};
      dm[d].c++;
      if(first==null||d<first)first=d;
      if(f.nwx&&f.nwx[g.__gi+':'+d])newc++;
      const p=frPrice(g,d);
      if(p!=null&&(price==null||p<price))price=p;
    }
  }
  Object.keys(touched).forEach(function(d){dm[d].f=1});
  return {f:f,cells:cells,first:first,price:price,newc:newc,units:units,dm:dm};
}

function frForests(){
  const q=(frs.q||'').trim().toLowerCase();
  const key=[frs.region,frs.type,frs.cap,frs.nights,frs.range,frs.weekend?1:0,frs.fresh?1:0,q].join('|');
  if(FR_CACHE.key===key&&FR_CACHE.list)return FR_CACHE.list;
  const out=[];
  for(let i=0;i<FRD.forests.length;i++){
    const f=FRD.forests[i];
    if(frs.region!=='all'&&f.sido!==frs.region)continue;
    if(q&&(String(f.name).toLowerCase().indexOf(q)<0&&String(f.gug).toLowerCase().indexOf(q)<0))continue;
    const s=frStat(f);
    if(!s.cells)continue;
    if(frs.fresh&&!s.newc)continue;
    out.push(s);
  }
  FR_CACHE.key=key;FR_CACHE.list=out;
  return out;
}
function frSorted(list){
  const s=frs.sort,big=9e9;
  return list.slice().sort(function(a,b){
    if(s==='name')return String(a.f.name).localeCompare(String(b.f.name),'ko');
    if(s==='price')return (a.price==null?big:a.price)-(b.price==null?big:b.price);
    if(s==='soon')return (a.first==null?big:a.first)-(b.first==null?big:b.first)||b.cells-a.cells;
    return b.cells-a.cells||(a.first==null?big:a.first)-(b.first==null?big:b.first);
  });
}

/* ── 상단 안내·요약 ── */
function renderFrBanner(){
  const m=frMeta();
  if(!m.at){$('frBanner').innerHTML='';return}
  const last=frDate(frDayCount()-1);
  $('frBanner').innerHTML='<b>숲나들e 월별 예약현황</b> · '+esc(m.at)+' 수집 — 전국 <b>'+KR(m.forests)+'곳</b> · 객실·사이트 '+KR(m.goods)+' · '+m.days+'일('+esc(m.start)+'~'+esc(last)+') · 예약가능 '+KR(m.avail)+'칸'
    +'<span class="fr-b2">직전 수집에서 새로 빈 자리 '+KR(m.new)+'칸(🆕). 예약·결제는 숲나들e에서 진행합니다 — 이 화면은 대신 예약하지 않습니다.</span>';
}
function renderFrKpi(list){
  const m=frMeta();
  let cells=0,units=0,newc=0,wk=0,wkDays={};
  for(let i=0;i<list.length;i++){
    cells+=list[i].cells;units+=list[i].units;newc+=list[i].newc;
    const dm=list[i].dm;
    for(const d in dm){if(frWeekendDi(+d)){wk+=dm[d].c;wkDays[d]=1}}
  }
  const kp=[
    {k:'빈자리 있는 휴양림',v:KR(list.length)+'곳',i:(frs.region==='all'?'전국':frs.region)+' · 필터 적용',cls:'g'},
    {k:'객실 · 사이트',v:KR(units)+'개',i:'필터에 걸린 숙소·야영장',cls:''},
    {k:'예약가능',v:KR(cells)+'칸',i:frs.nights+'박 기준 · '+frs.range+'일 창',cls:'g'},
    {k:'금·토 체크인',v:KR(wk)+'칸',i:Object.keys(wkDays).length?Object.keys(wkDays).length+'일에 걸쳐':'주말 자리 없음',cls:'g'}
  ];
  $('frKpi').innerHTML=kp.map(function(o){return '<div class="'+o.cls+'"><span>'+o.k+'</span><b>'+o.v+'</b><i>'+esc(o.i)+'</i></div>'}).join('');
}

/* ── 목록 ── */
function frChips(s){
  const ds=Object.keys(s.dm).map(Number).sort(function(a,b){return a-b}).slice(0,8);
  return ds.map(function(d){
    const n=s.dm[d].c;
    return '<span class="fr-chip2'+(frWeekendDi(d)?' wk':'')+'">'+dateLabel(frDate(d))+' '+weekday(frDate(d))+' <b>'+n+'</b></span>';
  }).join('');
}
function renderFrCards(list){
  const box=$('frCards');
  if(!list.length){
    box.innerHTML='<div class="fr-empty">조건에 맞는 빈자리가 없습니다 — 기간을 넓히거나(앞으로 2주 → 4주 → 수집 기간 전체), 인원·유형 필터를 풀어 보세요. 수집 시각 이후 예약이 찬 자리는 다음 수집에 반영됩니다.</div>';
    $('frListSub').textContent='0곳';return;
  }
  box.innerHTML=list.slice(0,120).map(function(s){
    const f=s.f;
    const typeBadge=f.type==='국립'?'<span class="fr-badge nat">국립</span>':(f.type==='사립'?'<span class="fr-badge pri">사립</span>':'<span class="fr-badge">공립</span>');
    const f2=s.first==null?'':('다음 빈 날 '+dateLabel(frDate(s.first))+'('+weekday(frDate(s.first))+')');
    return '<div class="fr-card">'
      +'<div class="fr-card-head"><div class="fr-card-name">'+esc(f.name)+typeBadge+'</div>'
      +'<a class="fr-go" href="'+esc(frOffUrl(f))+'" target="_blank" rel="noopener" title="'+esc(f.name)+' 숲나들e 예약 화면이 새 탭에서 열립니다">숲나들e 예약 ↗</a></div>'
      +'<div class="fr-meta">'+esc(f.sido)+' '+esc(f.gug)+(f.ci?' · 입실 '+esc(f.ci)+' / 퇴실 '+esc(f.co):'')+(f.tel?' · '+esc(f.tel):'')+'</div>'
      +'<div class="fr-line"><span class="fr-big">빈자리 '+KR(s.cells)+'칸</span>'
        +(f2?'<span>'+f2+'</span>':'')
        +'<span>1박 '+(s.price!=null?KR(s.price)+'원~':'요금 미공개')+'</span>'
        +(s.newc?'<span class="fr-newtag">🆕 '+s.newc+'</span>':'')+'</div>'
      +'<div class="fr-meta">객실·사이트 '+s.units+'개'+(f.op?' · 예약 '+esc(f.op):'')+(f.rw!=null?' · 주말 예약률 '+f.rw+'%':'')+'</div>'
      +'<div class="fr-chips">'+frChips(s)+'</div>'
      +'<div class="fr-acts"><button type="button" data-fr-grid="'+esc(f.id)+'">월간 그리드</button>'
        +'<a href="'+esc(frOffUrl(f))+'" target="_blank" rel="noopener">숲나들e 예약</a></div>'
      +'</div>';
  }).join('');
  $('frListSub').textContent=KR(list.length)+'곳'+(list.length>120?' 중 120곳 표시':'')+' · '+frs.nights+'박 기준';
}

/* ── 달력 ── */
function frCalMonths(){
  const seen={},out=[];
  for(let d=0;d<=frMaxDi();d++){const k=frDate(d).slice(0,7);if(!seen[k]){seen[k]=1;out.push(k)}}
  return out;
}
function renderFrCal(list){
  const months=frCalMonths();
  if(!months.length){$('frDays').innerHTML='<div class="fr-empty">자료가 없습니다.</div>';return}
  if(months.indexOf(frs.month)<0)frs.month=months[0];
  const idx=months.indexOf(frs.month);
  $('frMonthTitle').textContent=monlabel(frs.month);
  $('frPrevMonth').disabled=idx<=0;$('frNextMonth').disabled=idx>=months.length-1;
  const agg={};
  let mx=1;
  list.forEach(function(s){for(const d in s.dm){const k=d;if(!agg[k])agg[k]={c:0,f:0};agg[k].c+=s.dm[d].c;agg[k].f+=s.dm[d].f;if(agg[k].c>mx)mx=agg[k].c}});
  const [y,m]=frs.month.split('-').map(Number);
  const lead=new Date(Date.UTC(y,m-1,1)).getUTCDay();
  let html='';
  for(let i=0;i<lead;i++)html+='<div class="cal-day empty" aria-hidden="true"></div>';
  daysOf(frs.month).forEach(function(date){
    const di=frDi(date);
    const dow=dayNo(date);
    const wdCls=dow===0?'sunday ':dow===6?'saturday ':'';
    const num='<span class="daynum">'+Number(date.slice(-2))+'</span>';
    if(di<0||di>frMaxDi()){
      html+='<button type="button" class="cal-day fr-day out '+wdCls+'" aria-label="'+fullDate(date)+' 조회 기간 밖">'+num+'<span class="fr-df">·</span></button>';
      return;
    }
    const a=agg[String(di)];
    if(!a||!a.c){
      html+='<button type="button" class="cal-day fr-day none '+wdCls+'" aria-label="'+fullDate(date)+' 빈자리 없음">'+num+'<span class="fr-df">—</span></button>';
      return;
    }
    const lv=Math.max(1,Math.min(5,Math.ceil(a.c/mx*5)));
    html+='<button type="button" class="cal-day fr-day hm'+lv+' '+(frs.day===date?'sel ':'')+wdCls+'" data-fr-date="'+date+'" aria-label="'+fullDate(date)+' 체크인 빈자리 '+a.c+'칸">'
      +num+'<span class="fr-dn">'+a.c+'</span><span class="fr-df">'+a.f+'곳</span></button>';
  });
  $('frDays').innerHTML=html;
  const tot={};let totC=0;
  daysOf(frs.month).forEach(function(date){const di=frDi(date);const a=di>=0&&di<=frMaxDi()?agg[String(di)]:null;if(a&&a.c){totC+=a.c}});
  $('frCalSub').textContent=monlabel(frs.month)+' · 이 달 체크인 가능 '+KR(totC)+'칸 · 칸을 누르면 그 날 어느 휴양림·객실이 비었는지 나옵니다 · 금·토 칸은 아래에 밑줄';
  renderFrDay(list);
}
function renderFrDay(list){
  const box=$('frDayDetail');
  if(!frs.day){
    box.innerHTML='<p class="fl-empty">달력 칸을 누르면 <strong>그 날 체크인할 수 있는 휴양림과 객실</strong>이 여기에 나옵니다. 숫자는 그 날 예약가능한 객실·사이트 수이고, 아래 작은 숫자는 그 자리가 있는 휴양림 수입니다. 빈칸(—)은 그 날 빈자리가 없다는 뜻이며 추정하지 않았습니다.</p>';
    return;
  }
  const di=frDi(frs.day);
  const rows=[];
  list.forEach(function(s){
    const a=s.dm[String(di)];
    if(!a)return;
    const rooms=[];
    s.f.goods.forEach(function(g){
      if(!frTypeOK(g)||!frCapOK(g))return;
      const cs=frCheckins(g,frs.nights);
      for(let i=0;i<cs.length;i++){if(cs[i]===di){rooms.push(g);break}}
    });
    rows.push({s:s,n:a.c,rooms:rooms});
  });
  rows.sort(function(a,b){return b.n-a.n});
  let html='<div class="fl-detail-head"><div><h3>'+fullDate(frs.day)+' ('+weekday(frs.day)+') 체크인 · '+frs.nights+'박</h3>'
    +'<div class="meta">'+(rows.length?rows.length+'곳 · 객실 '+KR(rows.reduce(function(n,r){return n+r.n},0))+'개':'이 날 빈자리가 없습니다')+'</div></div>'
    +'<button type="button" class="fl-close" id="frDayClose" aria-label="상세 닫기">✕</button></div>';
  if(rows.length){
    html+='<div class="fr-detail-list">';
    rows.slice(0,16).forEach(function(r){
      const f=r.s.f;
      const names=r.rooms.slice(0,6).map(function(g){
        const p=frPrice(g,di);
        return esc(g.n)+'('+g.cap+'인'+(p!=null?' · '+KR(p)+'원':'')+')';
      }).join(', ')+(r.rooms.length>6?' 외 '+(r.rooms.length-6)+'개':'');
      html+='<div class="fr-dcard"><b>'+esc(f.name)+'</b><small>'+esc(f.type)+' · '+esc(f.sido)+' '+esc(f.gug)+' · '+esc(f.ci)+'~'+esc(f.co)+'</small>'
        +'<div class="fr-drooms">'+names+'</div>'
        +'<div class="fr-acts" style="margin-top:5px"><button type="button" data-fr-grid="'+esc(f.id)+'">월간 그리드</button>'
        +'<a href="'+esc(frOffUrl(f))+'" target="_blank" rel="noopener">숲나들e 예약 ↗</a></div></div>';
    });
    if(rows.length>16)html+='<p class="hint">'+rows.length+'곳 중 16곳만 표시했습니다 — 권역·유형 필터로 좁히면 그 안에서 다시 보여 드립니다.</p>';
    html+='</div>';
  }
  box.innerHTML=html;
}

/* ── 월간 그리드 ── */
function frGridMonths(){return frCalMonths()}
function frGridForest(list){
  const hit=list.filter(function(s){return s.f.id===frs.forest})[0];
  if(hit)return hit;
  const all=FRD.forests.filter(function(f){return f.id===frs.forest})[0];
  if(all){const s=frStat(all);if(s.cells)return s}
  return list[0]||null;
}
function frSChar(ch){
  if(ch==='A')return {t:'예',c:'A',l:'예약가능'};
  if(ch>='1'&&ch<='9')return {t:'대'+ch,c:'W',l:'대기'+ch};
  if(ch==='F')return {t:'완',c:'F',l:'예약완료'};
  if(ch==='C')return {t:'휴',c:'C',l:'휴무'};
  if(ch==='R')return {t:'공',c:'R',l:'공사·점검'};
  if(ch==='P')return {t:'추',c:'P',l:'추첨·우선예약'};
  return {t:'·',c:'N',l:'표시 없음'};
}
function renderFrGrid(list){
  const months=frGridMonths();
  const sel=$('frForestSel');
  const opts=list.slice(0,200).map(function(s){return '<option value="'+esc(s.f.id)+'">'+esc(s.f.name)+' ('+KR(s.cells)+'칸)</option>'}).join('');
  sel.innerHTML=opts||'<option value="">빈자리 있는 휴양림 없음</option>';
  const pick=frGridForest(list);
  if(!pick){
    $('frGridWrap').innerHTML='<div class="fr-empty" style="padding:14px">조건에 맞는 휴양림이 없습니다.</div>';
    $('frGridSub').textContent='';$('frGridFoot').innerHTML='';$('frGMonthTitle').textContent='—';return;
  }
  frs.forest=pick.f.id;
  sel.value=pick.f.id;
  if(months.indexOf(frs.gmonth)<0)frs.gmonth=months[0];
  const idx=months.indexOf(frs.gmonth);
  $('frGMonthTitle').textContent=monlabel(frs.gmonth);
  $('frGPrevMonth').disabled=idx<=0;$('frGNextMonth').disabled=idx>=months.length-1;
  const dates=daysOf(frs.gmonth).filter(function(d){const di=frDi(d);return di>=0&&di<=frMaxDi()});
  if(!dates.length){
    $('frGridWrap').innerHTML='<div class="fr-empty" style="padding:14px">이 달은 조회 기간 밖입니다 — 기간 필터를 넓히면 표시됩니다.</div>';
    $('frGridSub').textContent=monlabel(frs.gmonth);$('frGridFoot').innerHTML='';return;
  }
  let head='<thead><tr><th class="frs">객실 · 유형</th>';
  dates.forEach(function(d){
    const dow=dayNo(d);
    head+='<th class="'+(dow===5||dow===6?'wk':'')+'" title="'+fullDate(d)+'">'+Number(d.slice(-2))+'</th>';
  });
  head+='</tr></thead>';
  const goods=pick.f.goods.filter(function(g){return frTypeOK(g)&&frCapOK(g)});
  let body='<tbody>';
  let monthCells=0;
  goods.forEach(function(g){
    const ck=frs.nights>1?frCheckins(g,frs.nights):null;
    const pr=g.p&&g.p.length?('평일 '+KR(g.p[0])+' / 주말 '+KR(g.p[1])+'원'):'요금 미공개';
    const sub=(g.n.indexOf(g.c)>=0?'':g.c+(g.cap?' · ':''))+(g.cap?g.cap+'인':'');
    body+='<tr><td class="frs" title="'+esc(g.n+' · '+g.c+' · '+g.cap+'인 · '+g.ar+' · '+pr)+'"><b>'+esc(g.n)+'</b><small>'+esc(sub)+'</small></td>';
    dates.forEach(function(d){
      const di=frDi(d);
      const ch=g.s.charAt(di)||'.';
      const s=frSChar(ch);
      if(frs.nights>1?ck.indexOf(di)>=0:ch==='A')monthCells++;
      const nw=pick.f.nwx&&pick.f.nwx[g.__gi+':'+di]?' new':'';
      body+='<td class="c-'+s.c+nw+'" title="'+esc(g.n+' · '+fullDate(d)+' · '+s.l)+'">'+s.t+'</td>';
    });
    body+='</tr>';
  });
  body+='</tbody>';
  $('frGridWrap').innerHTML='<table class="fr-g">'+head+body+'</table>';
  $('frGLegend').innerHTML=['A:예약가능','W:대기','F:예약완료','C:휴무','R:공사·점검','P:추첨·우선예약','N:표시 없음'].map(function(x){
    const c=x.slice(0,1);
    return '<span><i class="c-'+c+'" style="background:'+({A:'#e7f6ec',W:'#fdf3e3',F:'#f2f0f7',C:'#fbf0ef',R:'#f7f1ea',P:'#efeafd',N:'#fff'}[c])+'"></i>'+esc(x.slice(2))+'</span>';
  }).join('')+'<span style="display:inline-flex;align-items:center;gap:3px"><i style="background:#e7f6ec;border:2px solid #e0872f"></i>🆕 직전 수집에서 새로 빈 자리</span>';
  const f=pick.f;
  const pr=f.goods.filter(function(g){return g.p&&g.p.length}).length;
  $('frGridSub').textContent=f.name+' · 객실·사이트 '+goods.length+'개 · '+monlabel(frs.gmonth)+' 예약가능 '+KR(monthCells)+'칸'+(frs.nights>1?' ('+frs.nights+'박 연속 기준)':'');
  $('frGridFoot').innerHTML='<b>'+esc(f.name)+'</b> · '+esc(f.type)+' · '+esc(f.sido)+' '+esc(f.gug)+' · 입실 '+esc(f.ci)+' / 퇴실 '+esc(f.co)
    +(f.op?' · 예약 오픈 '+esc(f.op):'')
    +(f.rw!=null||f.rd!=null?' · 수집 기간 예약률 '+(f.rw!=null?'주말 '+f.rw+'%':'')+(f.rd!=null?(f.rw!=null?' · ':'')+'평일 '+f.rd+'%':''):'')
    +' · 요금표 있는 객실 '+pr+'/'+f.goods.length+'개 (요금은 요금표의 비수기 평일·주말 값)'
    +' · <a href="'+esc(frOffUrl(f))+'" target="_blank" rel="noopener" style="color:var(--violet-d);font-weight:800">숲나들e에서 예약 ↗</a>';
}

/* ── 안내문 ── */
function renderFrNotes(){
  const m=frMeta(),last=frDate(frDayCount()-1);
  $('frBasis').innerHTML='<p class="hint">자료: 숲나들e(foresttrip.go.kr)에 공개된 <strong>월별 예약현황</strong> · 수집 <strong>'+esc(m.at||'—')+'</strong> KST · 범위 '+esc(m.start||'')+'~'+esc(last)+' ('+m.days+'일). 전국 <strong>'+KR(m.forests||0)+'곳</strong> · 객실·사이트 <strong>'+KR(m.goods||0)+'</strong> · 예약가능 <strong>'+KR(m.avail||0)+'칸</strong>.<br>'
    +'<strong>예</strong> 예약가능 · <strong>대1~9</strong> 예약은 찼지만 대기 신청을 받는 날 · <strong>완</strong> 예약완료 · <strong>휴</strong> 휴무 · <strong>공</strong> 공사·점검 · <strong>추</strong> 추첨·우선예약. 빈자리를 찾을 때는 <strong>예</strong>만 세고, 대기·완·휴·공·추는 세지 않습니다.<br>'
    +'2박·3박을 고르면 <strong>그 박수만큼 연속으로 예약가능한 체크인 날</strong>만 셉니다(객실마다 최대 연박이 짧으면 그 객실은 빠집니다). 요금은 숲나들e 요금표의 <strong>비수기 평일·주말 1박 값</strong>이고, 성수기·지역주민 할인 등에 따라 실제 결제액과 다릅니다. 요금표가 없는 객실은 <strong>요금 미공개</strong>로 둡니다.</p>';
  $('frCaution').innerHTML='<ul class="hint" style="margin:0;padding-left:16px">'
    +'<li>빈자리는 <strong>수집 시각 기준</strong>입니다. 그 뒤 예약이 찰 수 있으니 예약 전 숲나들e에서 다시 확인하세요. 인기 휴양림은 몇 분 만에 찹니다.</li>'
    +'<li>예약 버튼·행은 모두 <strong>숲나들e 공식 화면</strong>으로 열립니다(각 휴양림 페이지 · <a href="'+FR_MONTH+'" target="_blank" rel="noopener">월별현황조회</a>). 예약·결제·취소는 숲나들e에서 하고, 이 화면은 예약을 대신하지 않습니다.</li>'
    +'<li>숙소·야영장은 휴양림마다 <strong>입실·퇴실 시간과 최대 연박</strong>이 다릅니다. 카드와 그리드에 적힌 시간을 먼저 보세요.</li>'
    +'<li>국립·공립·사립의 예약 규칙(오픈 요일·추첨·지역주민 우선)이 서로 다릅니다. 그리드 아래의 <strong>예약 오픈</strong> 표기를 확인하세요.</li>'
    +'<li>요금·예약률은 수집된 값으로 계산한 참고 값입니다. 실제 금액은 숲나들e 예약 화면의 값을 따릅니다.</li>'
    +'</ul>';
}

/* ── 전체 ── */
function renderFrTabs(){
  const on=frs.view;
  document.querySelectorAll('[data-fr-view]').forEach(function(b){
    const sel=b.getAttribute('data-fr-view')===on;
    b.classList.toggle('on',sel);b.setAttribute('aria-pressed',String(sel));
  });
  document.querySelectorAll('[data-fr-nights]').forEach(function(b){
    const sel=Number(b.getAttribute('data-fr-nights'))===frs.nights;
    b.classList.toggle('on',sel);b.setAttribute('aria-pressed',String(sel));
  });
  const w=$('frWeekend'),fr2=$('frFresh');
  if(w)w.setAttribute('aria-pressed',String(!!frs.weekend));
  if(fr2)fr2.setAttribute('aria-pressed',String(!!frs.fresh));
  $('frListBlock').hidden=on!=='list';
  $('frCalBlock').hidden=on!=='cal';
  $('frGridBlock').hidden=on!=='grid';
}
function renderFrFilters(){
  const cnt={};
  FRD.forests.forEach(function(f){cnt[f.sido]=(cnt[f.sido]||0)+1});
  const sidos=(FRD.sidos&&FRD.sidos.length?FRD.sidos:Object.keys(cnt));
  $('frRegion').innerHTML='<option value="all">전국 ('+FRD.forests.length+'곳)</option>'+sidos.map(function(s){
    return '<option value="'+esc(s)+'">'+esc(s)+' ('+(cnt[s]||0)+'곳)</option>';
  }).join('');
  if(frs.region!=='all'&&!(sidos.indexOf(frs.region)>=0))frs.region='all';
  $('frRegion').value=frs.region;
  $('frType').value=frs.type;$('frCap').value=String(frs.cap);$('frRange').value=String(frs.range);$('frSort').value=frs.sort;
  if($('frQ').value!==frs.q)$('frQ').value=frs.q;
}
function renderForest(){
  setDealPanels('forest');
  if(!FRD.forests.length){
    $('frKpi').innerHTML='';$('frCards').innerHTML='<div class="fr-empty">자료를 받지 못했습니다 — 새로고침하면 다시 받습니다.</div>';return;
  }
  frPrep();
  renderFrBanner();renderFrFilters();
  const list=frSorted(frForests());
  frLastList=list;
  renderFrKpi(list);
  $('frCount').textContent='빈자리 있는 휴양림 '+KR(list.length)+'곳 · '+(frs.view==='list'?'목록':frs.view==='cal'?'달력':'월간 그리드');
  try{
    if(frs.view==='list')renderFrCards(list);
    else if(frs.view==='cal')renderFrCal(list);
    else renderFrGrid(list);
    renderFrNotes();renderFrTabs();
  }catch(err){
    /* 한 화면에서 오류가 나도 탭 전체를 잃지 않는다 — 무엇이 잘못됐는지 그대로 적는다 */
    const box={list:'frCards',cal:'frDays',grid:'frGridWrap'}[frs.view]||'frCards';
    const el=$(box);if(el)el.innerHTML='<div class="fr-empty">이 화면을 그리지 못했습니다 — '+(err&&err.message?String(err.message):'알 수 없는 오류')+'. 목록으로 돌아가면 나머지는 그대로 보입니다.</div>';
    renderFrTabs();
  }
  const t=tabs.forest;
  if(t){$('sectionTitle').textContent=t.title;$('sectionSubtitle').textContent=t.sub;$('checktime').textContent=t.checked}
  const tb=document.querySelector('[data-tab="forest"] b');
  if(tb)tb.textContent=KR(FRD.meta?FRD.meta.forests:FRD.forests.length);
  hashSync();
}
function frGo(id){
  frs.forest=id;frs.view='grid';frs.gmonth='';
  const f=FRD.forests.filter(function(x){return x.id===id})[0];
  if(f){
    const s=frStat(f);
    if(s.first!=null)frs.gmonth=frDate(s.first).slice(0,7);
  }
  renderForest();
  const b=$('frGridBlock');if(b&&b.scrollIntoView)b.scrollIntoView({block:'start',behavior:'smooth'});
}

/* 이벤트 */
$('frRegion').addEventListener('change',function(e){frs.region=e.target.value;frs.day='';renderForest()});
$('frType').addEventListener('change',function(e){frs.type=e.target.value;frs.day='';renderForest()});
$('frCap').addEventListener('change',function(e){frs.cap=Number(e.target.value)||0;frs.day='';renderForest()});
$('frRange').addEventListener('change',function(e){frs.range=Number(e.target.value)||0;frs.day='';renderForest()});
$('frSort').addEventListener('change',function(e){frs.sort=e.target.value;renderForest()});
var frQTimer=null;
$('frQ').addEventListener('input',function(e){
  frs.q=e.target.value;frs.day='';
  clearTimeout(frQTimer);frQTimer=setTimeout(renderForest,160);
});
$('frReset').addEventListener('click',function(){frs.type='all';frs.cap=0;frs.range=28;frs.weekend=false;frs.fresh=false;frs.q='';frs.nights=1;frs.sort='soon';frs.day='';frs.view='list';renderForest()});
$('frWeekend').addEventListener('click',function(){frs.weekend=!frs.weekend;frs.day='';renderForest()});
$('frFresh').addEventListener('click',function(){frs.fresh=!frs.fresh;frs.day='';renderForest()});
$('frPanel').addEventListener('click',function(e){
  const a=e.target.closest('a[href]');
  if(a){e.preventDefault();frOpenExt(a.href);return}
  const v=e.target.closest('[data-fr-view]');
  if(v){frs.view=v.getAttribute('data-fr-view');renderForest();return}
  const n=e.target.closest('[data-fr-nights]');
  if(n){frs.nights=Number(n.getAttribute('data-fr-nights'))||1;frs.day='';renderForest();return}
  const g=e.target.closest('[data-fr-grid]');
  if(g){e.preventDefault();frGo(g.getAttribute('data-fr-grid'));return}
  const d=e.target.closest('[data-fr-date]');
  if(d){frs.day=d.getAttribute('data-fr-date');renderFrCal(frLastList);return}
  if(e.target.closest('#frDayClose')){frs.day='';renderFrCal(frLastList);return}
  const m=e.target.closest('#frPrevMonth,#frNextMonth,#frGPrevMonth,#frGNextMonth');
  if(m){
    const cal=m.id.indexOf('frG')<0;
    const months=cal?frCalMonths():frGridMonths();
    const cur=cal?frs.month:frs.gmonth;
    const i=months.indexOf(cur);
    const k=m.id.indexOf('Prev')>=0?i-1:i+1;
    if(k<0||k>=months.length)return;
    if(cal){frs.month=months[k];frs.day=''}else{frs.gmonth=months[k]}
    renderForest();
  }
});
$('frForestSel').addEventListener('change',function(e){frs.forest=e.target.value;renderForest()});
