/* ── ⑦ 마일리지(부산) 탭 ─────────────────────────────────────────
   자료는 항공사가 공개하는 '보너스 좌석 현황'(하루 1회 갱신 · 앞으로 360일)을 옮긴
   스냅샷이다. 원천은 등급별 '있음/없음'만 알려 주고 좌석 수량·수수료 금액·기재는
   알려 주지 않는다. 그래서 이 화면은 그 세 가지를 만들어 내지 않는다.
   필요 마일은 항공사 공제표 값으로 계산하고, 출처는 항공사 공식 주소만 쓴다. */
var mgs={view:'cal',route:'',month:'',dir:0,grade:'all',sort:'date',nights:2,weekend:false,newKind:'all'};
var MGD={meta:null,routes:[],cells:[],chart:[],newSeats:[],goneSeats:[],ready:false,byKey:{},routeMap:{},months:[]};
var MG_KE_SEARCH='https://www.koreanair.com/booking/book-and-manage/award-seat-availability';
var MG_KE_CHART='https://www.koreanair.com/contents/skypass/use-miles';

function mgMeta(){return MGD||{}}   /* 자료는 파일 최상위에 그대로 담긴다 */
function mgWon(n){return n==null?'—':KR(n)+'마일'}
function mgKey(code,dir,date){return code+'|'+dir+'|'+date}

/* 자료 준비 — 노선·방향별 (날짜 → 등급 비트) 색인을 한 번만 만든다 */
function mgPrep(){
  if(MGD.ready||!MGD.cells.length)return;
  MGD.routeMap={};
  MGD.routes.forEach(function(r){MGD.routeMap[r.code]=r});
  MGD.cells.forEach(function(c){MGD.byKey[mgKey(c[0],c[1],c[2])]=c[3]});
  MGD.ready=true;
}
function mgBit(code,dir,date){
  const v=MGD.byKey[mgKey(code,dir,date)];
  return typeof v==='number'?v:null;
}
function mgRoute(code){return MGD.routeMap[code]||(MGD.routes.filter(function(r){return r.code===code})[0])||null}
function mgRouteName(r){return r?(r.code+' '+r.city):''}
function mgFirstRoute(){
  const cur=mgs.route&&mgRoute(mgs.route);
  if(cur)return cur.code;
  const r=MGD.routes[0];
  return r?r.code:'';
}
function mgMonths(){
  const m=mgMeta();
  return m.months||MGD.months||[];
}
function mgCurMonth(){
  const list=mgMonths();
  if(!list.length)return '';
  if(mgs.month&&list.indexOf(mgs.month)>=0)return mgs.month;
  return list[0];
}
function mgDateStr(month,day){return month+'-'+String(day).padStart(2,'0')}
function mgDayBit(code,dir,date){
  const v=mgBit(code,dir,date);
  return v==null?null:v;
}
function mgSeats(v){return v==null?[]:[['E',1],['P',2],['U',4]].filter(function(x){return (v&x[1])!==0})}
function mgNoteFor(code,dir,month){
  const n=(MGD.monthNotes||[]).filter(function(r){return r[0]===code&&r[1]===dir&&r[2]===month})[0];
  return n?n[3]:'';
}

/* 공제표 — [지역키, 이름, 일반 평수기, 일반 성수기, 프레스티지 평수기, 프레스티지 성수기, 일등 평수기, 일등 성수기] (편도) */
function mgChartRow(region){
  const row=(MGD.chart||[]).filter(function(r){return r[0]===region})[0];
  return row||null;
}
function mgMilesFor(region,cabin,season,trip){
  const row=mgChartRow(region);
  if(!row)return null;
  const col=cabin==='eco'?2:cabin==='pre'?4:6;
  let v=row[col+(season==='peak'?1:0)];
  if(v==null)return null;
  return v*(trip==='ow'?1:2);
}
function mgBadgeHtml(v,max){
  const s=mgSeats(v),lim=max||3;
  let out='';
  s.slice(0,lim).forEach(function(x){out+='<span class="bd '+x[0].toLowerCase()+'">'+x[0]+'</span>'});
  if(s.length>lim)out+='<span class="bd more">+'+(s.length-lim)+'</span>';
  return out;
}
function mgDateKo(ds){
  const d=new Date(ds+'T12:00:00Z');
  const wd=['일','월','화','수','목','금','토'][d.getUTCDay()];
  return (d.getUTCMonth()+1)+'/'+d.getUTCDate()+'('+wd+')';
}
function mgToday(){const m=mgMeta();return (m.today||'')}

/* ── 화면 ─────────────────────────────────────────────────── */
function renderMileage(){
  mgPrep();
  setDealPanels('mileage');
  const m=mgMeta();
  const p=document.getElementById('mgPanel');
  if(!p)return;
  const b=document.getElementById('mgBanner');
  if(b){
    const miss=(m.counts&&m.counts.miss)||0;
    const cov=mgCoverageText();
    b.innerHTML='<b>'+esc(m.sourceLabel||'대한항공 공개 보너스 좌석 현황')+'</b> · 기준 <b>'+esc(m.observedLabel||'—')+'</b>'
      +' · 하루 1회 갱신(앞으로 360일) · 부산/김해(PUS) 출발'
      +'<span class="mg-b2">좌석 수량·수수료 금액·기재는 원천에 없어 표시하지 않습니다(항공사 예약 화면에서 확인). '
      +'필요 마일은 항공사 공제표(편도 기준)로 계산한 값입니다. '
      +'예약·조회는 <a href="'+MG_KE_SEARCH+'" target="_blank" rel="noopener">koreanair.com 공식 화면</a>으로 이어집니다.'
      +(cov?' · <b>이번 초기 수집</b> '+esc(cov):'')
      +(miss?' · 받지 못한 칸 '+KR(miss)+'개는 <b>미수집</b> 점선으로 남겼습니다(값을 채우지 않음).':'')
      +'</span>';
  }
  mgRenderKpi();
  mgRenderViews();
  mgRenderRoutes();
  mgRenderCal();
  mgRenderRound();
  mgRenderNew();
  mgRenderCalc();
  mgTabBadge();
}

function mgRenderKpi(){
  const el=document.getElementById('mgKpi');
  if(!el)return;
  const c=(mgMeta().counts)||{};
  const openDays=mgOpenDayCount();
  el.innerHTML=''
    +'<div><span>수집한 노선</span><b>'+KR((MGD.coverage||[]).filter(function(c){return (c.months||[]).length}).length)+'</b><i>노선 목록 '+KR(MGD.routes.length)+'곳 중 · 나머지는 미수집</i></div>'
    +'<div><span>보너스 좌석 있는 날</span><b>'+KR(openDays)+'</b><i>수집 '+KR(c.cells||MGD.cells.length)+'칸 중</i></div>'
    +'<div class="new"><span>새로 열린 좌석</span><b>'+KR((MGD.newSeats||[]).length)+'</b><i>'+(mgMeta().hasPrev?'직전 수집 대비':'첫 수집 — 다음 수집부터 비교')+'</i></div>'
    +'<div class="miss"><span>미수집</span><b>'+KR(c.miss||0)+'</b><i>원천 범위 밖·조회 실패는 점선</i></div>';
}
function mgCoverageText(){
  const rows=(MGD.coverage||[]).filter(function(c){return (c.months||[]).length});
  if(!rows.length)return '';
  return rows.map(function(c){return c.code+' '+c.months.length+'개월'+(c.noted&&c.noted.length?'(조회 불가 '+c.noted.length+')':'')}).join(' · ');
}
function mgOpenDayCount(){
  let n=0;
  (MGD.cells||[]).forEach(function(c){if(c[3])n++});
  return n;
}

function mgRenderViews(){
  document.querySelectorAll('#mgViews button').forEach(function(b){
    const on=b.getAttribute('data-mg-view')===mgs.view;
    b.classList.toggle('on',on);b.setAttribute('aria-selected',on?'true':'false');
  });
  ['cal','round','new','calc'].forEach(function(v){
    const el=document.getElementById('mgView'+v.charAt(0).toUpperCase()+v.slice(1));
    if(el)el.hidden=(mgs.view!==v);
  });
}

function mgRenderRoutes(){
  const el=document.getElementById('mgRoutes');
  if(!el)return;
  if(mgs.route!==mgFirstRoute())mgs.route=mgFirstRoute();
  el.innerHTML=MGD.routes.map(function(r){
    const on=r.code===mgs.route;
    const cov=(MGD.coverage||[]).filter(function(x){return x.code===r.code})[0];
    const has=cov&&(cov.months||[]).length;
    return '<button type="button" class="'+(on?'on':'')+'" data-mg-route="'+esc(r.code)+'" aria-pressed="'+(on?'true':'false')+'"'
      +' title="'+(has?'수집 '+cov.months.length+'개월':'아직 수집하지 않은 노선')+'">'
      +'<b>'+esc(r.code)+'</b>'+esc(r.city)+(has?'':' <span style="color:#b6bac1">·</span>')+'</button>';
  }).join('');
}

/* 달력 */
function mgRenderCal(){
  const body=document.getElementById('mgCalBody');
  if(!body)return;
  const code=mgs.route||mgFirstRoute();
  const r=mgRoute(code);
  const month=mgCurMonth();
  const monEl=document.getElementById('mgMon');
  if(monEl)monEl.textContent=month?(month.slice(0,4)+'년 '+(+month.slice(5,7))+'월'):'—';
  const list=mgMonths();
  const i=list.indexOf(month);
  const prev=document.getElementById('mgPrev'),next=document.getElementById('mgNext');
  if(prev)prev.disabled=(i<=0);
  if(next)next.disabled=(i<0||i>=list.length-1);
  const dirSel=document.getElementById('mgDir');
  if(dirSel)dirSel.value=String(mgs.dir);
  if(!r||!month){body.innerHTML='<tr><td colspan="7"><div class="mg-empty">자료를 받지 못했습니다.</div></td></tr>';return}
  const m=mgMeta();
  const winEnd=m.windowEnd||'';
  const monthNote=mgNoteFor(code,mgs.dir,month);
  const [yy,mm]=month.split('-').map(Number);
  const first=new Date(Date.UTC(yy,mm-1,1));
  const startWd=first.getUTCDay();
  const days=new Date(Date.UTC(yy,mm,0)).getUTCDate();
  let cells=[];
  for(let k=0;k<startWd;k++)cells.push(null);
  for(let d=1;d<=days;d++)cells.push(d);
  let rows='',cur='';
  cells.forEach(function(d,idx){
    if(idx%7===0)cur+='<tr>';
    const wd=idx%7;
    if(d==null){cur+='<td></td>';}
    else{
      const ds=mgDateStr(month,d);
      const v=mgBit(code,mgs.dir,ds);
      const cls=['mg-cell'];
      if(wd===0)cls.push('sun');if(wd===6)cls.push('sat');
      let inner='<span class="d">'+d+'</span>';
      if(monthNote){
        cls.push('out');inner+='<span class="t">조회 불가</span>';
      }else if(winEnd&&ds>winEnd){
        cls.push('out');
        inner+='<span class="t">미제공</span>';
      }else if(v==null){
        cls.push('miss');
        inner+='<span class="t">미수집</span>';
      }else if(v&16){
        cls.push('out');inner+='<span class="t">운항 없음</span>';
      }else if(!v){
        cls.push('none');inner+='<span class="t" style="color:#b6bac1">—</span>';
      }else{
        cls.push('has');
        if(mgs.grade!=='all'&&(v&+mgs.grade)===0)cls.push('dim');
        inner+='<span class="bg">'+mgBadgeHtml(v,2)+'</span>';
      }
      cur+='<td><button type="button" class="'+cls.join(' ')+'" data-mg-day="'+ds+'" aria-label="'+esc(mgDateKo(ds)+' '+mgAriaFor(v,ds,winEnd))+'">'+inner+'</button></td>';
    }
    if(idx%7===6){cur+='</tr>';rows+=cur;cur=''}
  });
  if(cur){cur+='</tr>';rows+=cur}
  body.innerHTML=rows;
  const note=document.getElementById('mgCalNote');
  if(note){
    const ch=mgChartRow(r.region);
    note.innerHTML=(monthNote?'<b>'+esc(month)+'</b> 이 달은 원천이 <b>조회를 거절</b>했습니다('+esc(monthNote)+') — 값을 채우지 않았습니다. ':'')
      +'<b>'+esc(r.code)+' '+esc(r.city)+'</b> · '+(mgs.dir?'오는 편(현지→부산)':'가는 편(부산→현지)')
      +' · 원천은 날짜마다 <b>등급별 있음/없음</b>만 알려 줍니다. 좌석 수량은 항공사 화면에서 확인해 주세요.'
      +(ch?' · 편도 필요 마일(공제표) 일반 '+KR(ch[2])+'~'+KR(ch[3])+' · 프레스티지 '+KR(ch[4])+'~'+KR(ch[5]):'')
      +'<br>원천이 앞으로 360일만 제공하므로 <b>'+esc(winEnd)+'</b> 이후는 <b>미제공</b>입니다. 조회하지 못한 날은 <b>미수집</b>으로 남기고 값을 채우지 않습니다.';
  }
  mgRenderLegendAvail();
}
function mgAriaFor(v,ds,winEnd){
  if(winEnd&&ds>winEnd)return '원천 미제공';
  if(v==null)return '미수집';
  if(v&16)return '운항편 없음';
  if(!v)return '보너스 좌석 없음';
  return mgSeats(v).map(function(x){return x[0]==='E'?'일반석 보너스':x[0]==='P'?'프레스티지 보너스':'프레스티지 승급'}).join(' ');
}
function mgRenderLegendAvail(){
  const el=document.getElementById('mgLegend');
  if(!el)return;
  el.innerHTML='<span><span class="bd e">E</span> 일반석 보너스</span>'
    +'<span><span class="bd p">P</span> 프레스티지 보너스</span>'
    +'<span><span class="bd u">U</span> 프레스티지 승급</span>'
    +'<span>— = 원천에 없음</span><span>점선 = 미수집 / 미제공</span>';
}

/* 왕복 후보 */
function mgRenderRound(){
  const listEl=document.getElementById('mgRoundList');
  if(!listEl)return;
  const code=mgs.route||mgFirstRoute();
  const r=mgRoute(code);
  const rows=[];
  if(r){
    const dats=mgDatesOf(code,0).filter(function(d){
      const v=mgBit(code,0,d);
      if(!v)return false;
      if(mgs.weekend){const w=new Date(d+'T12:00:00Z').getUTCDay();if(w!==5&&w!==6)return false}
      return true;
    });
    const returnSet={};
    mgDatesOf(code,1).forEach(function(d){returnSet[d]=mgBit(code,1,d)});
    const dates0=mgDatesOf(code,0);
    dats.forEach(function(d){
      const back=mgAddDays(d,mgs.nights);
      const rv=returnSet[back];
      if(!dats.length)return;
      rows.push({out:d,back:back,ov:mgBit(code,0,d),rv:(rv===undefined?null:rv)});
    });
  }
  const cnt=document.getElementById('mgRoundCount');
  if(cnt)cnt.textContent=rows.length?('후보 '+KR(rows.length)+'개'):'';
  if(!rows.length){
    listEl.innerHTML='<div class="mg-empty">이 조건에 맞는 후보가 없습니다.<br>숙박 일수나 주말 조건을 바꿔 보세요.</div>';
    mgRoundNote('');return;
  }
  const limit=20;
  listEl.innerHTML=rows.slice(0,limit).map(function(x){
    const ch=mgChartRow(r.region);
    const cabin=(x.ov&2)?'pre':'eco';
    const m1=mgMilesFor(r.region,cabin,'off','ow');
    const total=m1==null?null:m1*2;
    const backTxt=(x.rv==null)?'귀국편 좌석 미수집':(x.rv?'귀국편 보너스 좌석 있음':'귀국편 보너스 좌석 없음');
    return '<div class="mg-card">'
      +'<div class="top"><b>'+esc(r.code)+' '+esc(r.city)+'</b><span>'+esc(mgDateKo(x.out))+' → '+esc(mgDateKo(x.back))+' · '+mgs.nights+'박</span></div>'
      +'<div class="mg-leg"><span class="k">가는 편</span><span class="v">'+esc(mgDateKo(x.out))+' '+mgBadgeHtml(x.ov,3)+'</span>'
      +'<span class="k">오는 편</span><span class="v">'+(x.rv==null?'<span style="color:#9aa0a6">미수집</span>':esc(mgDateKo(x.back))+' '+(x.rv?mgBadgeHtml(x.rv,3):'<span style="color:#9aa0a6">좌석 없음</span>'))+'</span></div>'
      +'<div class="miles">필요 마일 1인 <b>'+(total==null?'—':KR(total)+'마일')+'</b> <span style="color:#6b7280">('+(cabin==='pre'?'프레스티지':'일반석')+' 왕복·평수기 · 편도 '+KR(m1)+'×2)</span></div>'
      +'<div class="miles" style="border-top:0;padding-top:0;font-size:10px;color:#6b7280">'+esc(backTxt)+' · 2인 좌석 수량은 항공사 화면 확인 · 수수료 별도</div>'
      +'<div class="acts"><button type="button" data-mg-day="'+esc(x.out)+'">가는 편 상세</button>'
      +'<a class="go" href="'+MG_KE_SEARCH+'" target="_blank" rel="noopener">대한항공 예약</a></div>'
      +'</div>';
  }).join('');
  mgRoundNote(rows.length>limit?'후보가 많아 마일·날짜가 앞선 '+limit+'개만 보여 줍니다.':'');
}
function mgRoundNote(t){
  const el=document.getElementById('mgRoundNote');
  if(!el)return;
  el.innerHTML=(t?esc(t)+'<br>':'')
    +'가는 편에 보너스 좌석이 있는 날만 골라 '+mgs.nights+'박 뒤 같은 노선 귀국편을 붙였습니다. '
    +'필요 마일은 <b>편도 공제표 × 2(평수기)</b>로 계산한 값이고, 성수기 탑승일은 더 큽니다. '
    +'귀국편 좌석은 원천의 반대 방향 조회분만 표시하며, 받지 않은 날은 <b>미수집</b>으로 둡니다. '
    +'2인 이상 동시 예약 가능 여부는 원천에 수량이 없어 단정하지 않습니다 — 항공사 화면에서 확인해 주세요.';
}
function mgDatesOf(code,dir){
  const m=mgMeta();
  return (MGD.cells||[]).filter(function(c){return c[0]===code&&c[1]===dir}).map(function(c){return c[2]}).sort();
}
function mgAddDays(ds,n){
  const d=new Date(ds+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10);
}

/* 새로 열린 좌석 */
function mgRenderNew(){
  const el=document.getElementById('mgNewBody');
  if(!el)return;
  const m=mgMeta();
  let rows=[];
  if(!m.hasPrev){
    el.innerHTML='<div class="mg-empty"><b>첫 수집입니다.</b><br>오늘 스냅샷을 기준으로 저장해 두었고, 다음 수집부터 <b>새로 열린 좌석</b>과 <b>사라진 좌석</b>을 이 자리에서 보여 드립니다.<br>'
      +'지금은 달력에서 날짜별 좌석을 먼저 확인해 보세요.</div>';
  }else{
    const nw=(MGD.newSeats||[]),gn=(MGD.goneSeats||[]);
    if(mgs.newKind==='all')rows=nw.map(function(x){return {k:'new',x:x}}).concat(gn.map(function(x){return {k:'gone',x:x}}));
    else if(mgs.newKind==='new')rows=nw.map(function(x){return {k:'new',x:x}});
    else rows=gn.map(function(x){return {k:'gone',x:x}});
    if(!rows.length)el.innerHTML='<div class="mg-empty">직전 수집과 비교해 바뀐 좌석이 없습니다.</div>';
    else el.innerHTML='<table class="mg-tbl"><thead><tr><th>노선</th><th>날짜</th><th>방향</th><th>등급</th><th>변화</th><th></th></tr></thead><tbody>'
      +rows.slice(0,120).map(function(o){
        const r=mgRoute(o.x[0]);
        return '<tr><td class="b">'+esc(o.x[0])+' '+esc(r?r.city:'')+'</td><td>'+esc(o.x[2]?mgDateKo(o.x[2]):'')+'</td>'
          +'<td>'+(o.x[1]?'오는 편':'가는 편')+'</td><td>'+mgBadgeHtml(o.x[3],3)+'</td>'
          +'<td>'+(o.k==='new'?'<b style="color:#c2410c">새로 열림</b>':'<b style="color:#6b7280">사라짐</b>')+'</td>'
          +'<td><button type="button" class="open" data-mg-day="'+esc(o.x[2])+'" data-mg-route="'+esc(o.x[0])+'" data-mg-dir="'+o.x[1]+'">보기</button></td></tr>';
      }).join('')+'</tbody></table>';
  }
  const cnt=document.getElementById('mgNewCount');
  if(cnt)cnt.textContent=m.hasPrev?('새로 열림 '+KR((MGD.newSeats||[]).length)+' · 사라짐 '+KR((MGD.goneSeats||[]).length)):'';
  const note=document.getElementById('mgNewNote');
  if(note)note.innerHTML='직전 수집 스냅샷과 비교해 <b>없음 → 있음</b>으로 바뀐 칸을 새로 열린 좌석으로 셉니다(비교 기준 '+(m.prevLabel?esc(m.prevLabel):'—')+'). '
    +'원천이 하루 1회만 갱신되므로, 하루 안에 열렸다 닫힌 좌석은 잡히지 않을 수 있습니다.';
}

/* 계산기 */
function mgRenderCalc(){
  const out=document.getElementById('mgCalcOut');
  if(!out)return;
  const milesEl=document.getElementById('mgMiles');
  const have=parseInt(String(milesEl?milesEl.value:'').replace(/[^0-9]/g,''),10)||0;
  const cabin=(document.getElementById('mgCabin')||{}).value||'pre';
  const region=(document.getElementById('mgRegion')||{}).value||'jp_cn_ne';
  const trip=(document.getElementById('mgTrip')||{}).value||'rt';
  const season=(document.getElementById('mgSeason')||{}).value||'off';
  const need=mgMilesFor(region,cabin,season,trip);
  const row=mgChartRow(region);
  const label=row?row[1]:region;
  let html='';
  if(need==null){
    html='<div class="big">—</div><div class="sub">이 등급은 공제표에 값이 없습니다(일등석은 국내선 미운영).</div>';
  }else{
    const rest=have-need;
    html='<div class="big">'+KR(need)+'마일</div>'
      +'<div class="sub">'+esc(label)+' · '+(cabin==='eco'?'일반석':cabin==='pre'?'프레스티지':'일등석')+' · '+(trip==='ow'?'편도':'왕복')+' · '+(season==='peak'?'성수기':'평수기')+'</div>'
      +'<div class="rest">'+(rest>=0
        ?'보유 마일로 <b>가능</b> — 남는 마일 <b>'+KR(rest)+'</b>'
        :'<b style="color:#c2410c">'+KR(-rest)+'마일 부족</b>')+'</div>';
  }
  /* 보유 마일로 갈 수 있는 지역 */
  const opts=[['jp_cn_ne','일본·중국·동북아'],['sea_guam','동남아·괌'],['sw_asia','서남아'],['us_eu_me_oc','미주·유럽·중동·대양주']];
  html+='<ul class="regions">'+opts.map(function(o){
    const n=mgMilesFor(o[0],cabin,season,trip);
    if(n==null)return '';
    const ok=have>=n;
    return '<li class="'+(ok?'':'nope')+'"><span>'+esc(o[1])+'</span><b>'+KR(n)+'마일'+(ok?' ✓':'')+'</b></li>';
  }).join('')+'</ul>';
  out.innerHTML=html;
  const note=document.getElementById('mgCalcNote');
  if(note)note.innerHTML='공제표는 항공사가 공개한 <b>편도</b> 값이며, 왕복은 ×2(같은 지역 기준)로 계산했습니다. '
    +'실제 왕복은 <b>가는 편과 오는 편의 탑승일 시즌을 각각</b> 적용하므로 두 값의 합이 위 계산과 다를 수 있습니다. '
    +'성수기 지정일(명절·연휴·성수기 기간)은 항공사 공지 기준이며, <a href="'+MG_KE_CHART+'" target="_blank" rel="noopener">공식 공제표</a>에서 확인해 주세요. '
    +'수수료(세금·유류할증료)는 마일과 별도입니다 — 국제선 최소 미화 30달러 수준이며 실제 금액은 예약 화면 값입니다.';
}

/* 상세 시트 */
function mgOpenSheet(code,dir,date){
  const dlg=document.getElementById('mgSheet');
  const body=document.getElementById('mgSheetBody');
  if(!dlg||!body)return;
  const r=mgRoute(code)||{code:code,city:''};
  const v=mgBit(code,dir,date);
  const ch=mgChartRow(r.region);
  const ecoOff=ch?ch[2]:null,ecoPeak=ch?ch[3]:null,preOff=ch?ch[4]:null,prePeak=ch?ch[5]:null;
  let rows='';
  rows+='<div class="line"><span>노선</span><b>'+esc(r.code)+' '+esc(r.city)+' '+esc(mgs.dir?'(오는 편)':'(가는 편)')+'</b></div>';
  rows+='<div class="line"><span>날짜</span><b>'+esc(mgDateKo(date))+'</b></div>';
  rows+='<div class="line"><span>원천 표시</span><b>'+(v==null?'<span style="color:#9aa0a6">미수집</span>':(v?'보너스 좌석 있음':'보너스 좌석 없음'))+'</b></div>';
  if(v){
    rows+='<div class="line"><span>등급</span><b>'+mgBadgeHtml(v,3)+'</b></div>';
    if(v&1)rows+='<div class="line"><span>일반석 보너스</span><b>편도 '+KR(ecoOff)+' / 성수기 '+KR(ecoPeak)+'</b></div>';
    if(v&2)rows+='<div class="line"><span>프레스티지 보너스</span><b>편도 '+KR(preOff)+' / 성수기 '+KR(prePeak)+'</b></div>';
    if(v&4)rows+='<div class="line"><span>프레스티지 승급</span><b>마일 차감 없이 승급(현금 운임 필요)</b></div>';
  }
  rows+='<div class="foot"><a class="go" href="'+MG_KE_SEARCH+'" target="_blank" rel="noopener">대한항공에서 확인</a>'
    +'<a href="'+MG_KE_CHART+'" target="_blank" rel="noopener">공제표 보기</a>'
    +'<button type="button" id="mgSheetClose">닫기</button></div>';
  rows+='<div class="fee">좌석 수량과 수수료(세금·유류할증료)는 원천에 없어 표시하지 않습니다. 편명·출발 시각과 실제 예약 가능 여부는 항공사 화면에서 확인해 주세요. '
    +'이 화면은 항공사가 공개한 하루 1회 갱신 자료입니다.</div>';
  body.innerHTML='<h3>'+esc(r.code)+' '+esc(r.city)+' · '+esc(mgDateKo(date))+'</h3><div class="s">'+esc(mgs.dir?'현지 → 부산/김해':'부산/김해 → 현지')+' · 원천 기준 '+(mgMeta().observedLabel||'—')+'</div>'+rows;
  const close=document.getElementById('mgSheetClose');
  if(close)close.addEventListener('click',function(){dlg.close()});
  if(dlg.showModal)dlg.showModal();else dlg.setAttribute('open','');
}

/* 탭 배지 — 새로 열린 좌석 건수 */
function mgTabBadge(){
  const tb=document.querySelector('[data-tab="mileage"] b');
  if(tb){
    const n=(MGD.newSeats||[]).length;
    tb.textContent=n?KR(n):'—';
    tb.hidden=!n;
  }
  const nb=document.getElementById('mgNewBadge');
  if(nb){const n=(MGD.newSeats||[]).length;nb.textContent=KR(n);nb.hidden=!n}
}

/* ── 이벤트 ───────────────────────────────────────────────── */
document.addEventListener('click',function(e){
  const v=e.target.closest&&e.target.closest('#mgViews button');
  if(v){mgs.view=v.getAttribute('data-mg-view');mgRenderViews();return}
  const rb=e.target.closest&&e.target.closest('#mgRoutes button');
  if(rb){mgs.route=rb.getAttribute('data-mg-route');mgs.month='';renderMileage();return}
  const day=e.target.closest&&e.target.closest('[data-mg-day]');
  if(day){
    const code=day.getAttribute('data-mg-route')||mgs.route||mgFirstRoute();
    const dir=day.getAttribute('data-mg-dir')!=null?+day.getAttribute('data-mg-dir'):mgs.dir;
    mgOpenSheet(code,dir,day.getAttribute('data-mg-day'));return;
  }
});
document.addEventListener('change',function(e){
  const t=e.target;
  if(!t||!t.id)return;
  if(t.id==='mgGrade'){mgs.grade=t.value;mgRenderCal()}
  else if(t.id==='mgSort'){mgs.sort=t.value;mgSortCal()}
  else if(t.id==='mgDir'){mgs.dir=+t.value;mgRenderCal()}
  else if(t.id==='mgNights'){mgs.nights=+t.value;mgRenderRound()}
  else if(t.id==='mgNewKind'){mgs.newKind=t.value;mgRenderNew()}
  else if(t.id==='mgMiles'||t.id==='mgCabin'||t.id==='mgRegion'||t.id==='mgTrip'||t.id==='mgSeason'){mgRenderCalc()}
});
function mgSortCal(){
  /* 정렬은 달력 안에서 날짜를 옮기지 않는다 — 대신 서브 목록(날짜 목록)을 붙여 보여 준다 */
  const body=document.getElementById('mgCalBody');
  if(!body)return;
  if(mgs.sort==='date'){mgRenderCal();return}
  mgRenderCal();
  const code=mgs.route||mgFirstRoute(),r=mgRoute(code);
  if(!r)return;
  const rows=mgDatesOf(code,mgs.dir).filter(function(d){return mgBit(code,mgs.dir,d)})
    .map(function(d){return {d:d,v:mgBit(code,mgs.dir,d)}})
    .sort(function(a,b){const ma=mgCheapMiles(r,a.v),mb=mgCheapMiles(r,b.v);return ma-mb||a.d.localeCompare(b.d)});
  const grid=document.getElementById('mgCal');
  if(grid)grid.style.display='none';
  const note=document.getElementById('mgCalNote');
  let html='<table class="mg-tbl"><thead><tr><th>날짜</th><th>등급</th><th>필요 마일(편도·평수기)</th><th></th></tr></thead><tbody>'
    +rows.slice(0,60).map(function(x){
      return '<tr><td class="b">'+esc(mgDateKo(x.d))+'</td><td>'+mgBadgeHtml(x.v,3)+'</td>'
        +'<td>'+KR(mgCheapMiles(r,x.v))+'</td>'
        +'<td><button type="button" class="open" data-mg-day="'+esc(x.d)+'">보기</button></td></tr>';
    }).join('')+'</tbody></table>';
  const box=document.getElementById('mgSortBox');
  if(box)box.remove();
  const wrap=document.createElement('div');wrap.id='mgSortBox';wrap.innerHTML=html;
  grid.parentNode.insertBefore(wrap,grid);
}
function mgCheapMiles(r,v){
  const cabin=(v&1)?'eco':'pre';
  const m=mgMilesFor(r.region,cabin,'off','ow');
  return m==null?999999:m;
}
document.addEventListener('click',function(e){
  const nav=e.target.closest&&e.target.closest('#mgPrev,#mgNext');
  if(nav){
    const list=mgMonths(),i=list.indexOf(mgCurMonth());
    const j=nav.id==='mgPrev'?i-1:i+1;
    if(j>=0&&j<list.length){mgs.month=list[j];const sb=document.getElementById('mgSortBox');if(sb)sb.remove();const g=document.getElementById('mgCal');if(g)g.style.display='';mgRenderCal()}
    return;
  }
  if(e.target.closest&&e.target.closest('#mgWeekend')){
    mgs.weekend=!mgs.weekend;
    e.target.closest('#mgWeekend').setAttribute('aria-pressed',mgs.weekend?'true':'false');
    mgRenderRound();
  }
});
