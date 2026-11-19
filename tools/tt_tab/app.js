/* ── ⑥ 땡처리 · 부산 출발 ───────────────────────────────
   상품 데이터는 `const TTANG`(아래 별도 블록)에 있고 tools/master_db.py inject 가 채운다.
   모든 날짜 칸·노선 행·상품 행은 <a target="_blank"> 라서 누르면 곧바로 예약 페이지가 새 탭에서 열린다. */
const ttst={region:'all',city:'all',month:'',day:''};
const ttCh={};
(function(){const cs=(typeof TTANG!=='undefined'&&TTANG.channels)||[];cs.forEach(function(c){ttCh[c.key]=c.label})})();
function ttAll(){return (typeof TTANG!=='undefined'&&TTANG.deals)||[]}
function ttChan(d){return ttCh[d&&d.src]||'특가'}
function ttChanTag(d){return '<span class="tt-chan'+(d.src==='t'?' t':'')+'">'+esc(ttChan(d))+'</span>'}
function ttFiltered(){return ttAll().filter(function(d){
  return (ttst.region==='all'||d.region===ttst.region)&&(ttst.city==='all'||d.code===ttst.city)})}
function ttByPrice(a,b){return (a.price-b.price)||String(a.out).localeCompare(String(b.out))||String(a.city).localeCompare(String(b.city),'ko')}
function ttBestOf(a){return a.slice().sort(ttByPrice)[0]||null}
function ttMinOf(a){return a.length?Math.min.apply(null,a.map(function(d){return d.price})):null}
function ttMonths(){const seen={},out=[];ttAll().forEach(function(d){const k=String(d.out).slice(0,7);if(!seen[k]){seen[k]=1;out.push(k)}});return out.sort()}
function ttNights(d){return typeof d.nights==='number'?d.nights:(d.days?d.days-1:null)}
function ttSpan(d){const n=ttNights(d),p=[];if(d.days)p.push(d.days+'일');if(n!=null)p.push(n+'박');return p.join(' · ')}
function ttRange(d){return dateLabel(d.out)+'–'+dateLabel(d.back)}
function ttSeats(d){if(d.seats!=null)return d.seats+'석';if(d.minPax&&d.minPax>1)return d.minPax+'명 이상';return '미표시'}
function ttAir(d){return d.airline?esc(d.airline):'항공사 미확인'}
function ttRow(cls,href,label,inner,data){
  const d=data?' '+data:'';
  return '<a class="'+cls+'" href="'+esc(href)+'" target="_blank" rel="noopener"'+d+' aria-label="'+esc(label)+' · 예약 페이지가 새 탭에서 열립니다" title="'+esc(label)+' · 예약 페이지가 새 탭에서 열립니다">'+inner+'</a>';
}

/* 상단 요약 */
function renderTtKpi(){
  const all=ttAll(),shown=ttFiltered();
  const cities={};all.forEach(function(d){cities[d.code]=1});
  const best=ttBestOf(shown);
  const avg=shown.length?Math.round(shown.reduce(function(n,d){return n+d.price},0)/shown.length):null;
  const chans={};all.forEach(function(d){const k=ttChan(d);chans[k]=(chans[k]||0)+1});
  const chanTxt=Object.keys(chans).map(function(k){return k+' '+chans[k]}).join(' · ')||'—';
  const kp=[
    {k:'상품',v:KR(all.length)+'건',i:chanTxt,cls:''},
    {k:'노선',v:KR(Object.keys(cities).length)+'개',i:ttst.region==='all'&&ttst.city==='all'?'부산(PUS) 출발':'필터 적용 중',cls:''},
    {k:'최저 왕복',v:best?shortWon(best.price):'—',i:best?esc(best.city)+' · '+ttRange(best):'자료 없음',cls:'red'},
    {k:'평균 왕복',v:avg?shortWon(avg):'—',i:shown.length?KR(shown.length)+'건 기준':'자료 없음',cls:''}
  ];
  $('ttKpi').innerHTML=kp.map(function(o){return '<div class="tt-kpi '+o.cls+'"><span>'+o.k+'</span><b>'+o.v+'</b><i>'+o.i+'</i></div>'}).join('');
  const b=$('ttBanner');
  const cov=(typeof TTANG!=='undefined'&&TTANG.coverage)||'';
  b.hidden=!cov;
  if(cov){b.className='tt-banner'+((typeof TTANG!=='undefined'&&TTANG.coverageOk)?' ok':'');b.innerHTML=cov}
}

/* TOP 5 — 카드를 누르면 그 상품 예약 페이지가 새 탭에서 열린다 */
function renderTtTop(){
  const top=ttFiltered().slice().sort(ttByPrice).slice(0,5);
  $('ttTop5').innerHTML=top.length?top.map(function(d,i){
    return ttRow('rank-item tt-hit',d.url,d.city+' '+ttRange(d)+' '+KR(d.price)+'원',
      '<span class="rank-n">'+String(i+1).padStart(2,'0')+'</span>'+
      '<div class="rank-entity"><div class="rank-name">'+esc(d.city)+' <span class="fl-code">'+esc(d.code)+'</span>'+ttChanTag(d)+'</div>'+
      '<div class="rank-meta">'+esc(ttRange(d))+' · '+esc(ttSpan(d))+' · '+ttAir(d)+' · 잔여 '+esc(ttSeats(d))+'</div></div>'+
      '<div class="rank-num'+(i===0?' red':'')+'">'+shortWon(d.price)+'</div>');
  }).join(''):'<div class="rank-empty">아직 수집된 상품이 없습니다 — 팀원 수집분이 들어오면 여기부터 채워집니다.</div>';
  $('ttTopSub').textContent=ttFiltered().length?'싼 순서 · '+KR(ttFiltered().length)+'건 중':'자료 없음';
  const b=ttBestOf(ttFiltered());
  $('ttTopHint').innerHTML=b?('가장 싼 상품은 <strong>'+esc(b.city)+' '+esc(ttRange(b))+' '+KR(b.price)+'원</strong>('+ttAir(b)+' · '+esc(ttSpan(b))+'). 카드를 누르면 그 상품 예약 페이지가 <strong>새 탭에서 바로</strong> 열립니다.'):'';
}

/* 노선별 최저가 목록 — 행을 누르면 노선 최저 상품 예약 페이지 */
function renderTtRoutes(){
  const by={};
  ttFiltered().forEach(function(d){const k=d.code;if(!by[k])by[k]={code:d.code,city:d.city,region:d.region,deals:[]};by[k].deals.push(d)});
  const rows=Object.keys(by).map(function(k){return {g:by[k],b:ttBestOf(by[k].deals)}}).sort(function(a,b){return ttByPrice(a.b,b.b)});
  $('ttRoutes').innerHTML=rows.length?rows.map(function(o){
    return ttRow('tt-rt',o.b.url,o.g.city+' '+ttRange(o.b)+' '+KR(o.b.price)+'원',
      '<div><div class="tt-rt-name">'+esc(o.g.city)+' <span class="fl-code">'+esc(o.g.code)+'</span></div>'+
      '<div class="tt-rt-meta">'+esc(ttRange(o.b))+' · '+esc(ttSpan(o.b))+' · '+ttAir(o.b)+' · '+o.g.deals.length+'건</div></div>'+
      '<div class="tt-rt-price">'+shortWon(o.b.price)+'</div>');
  }).join(''):'<div class="rank-empty">표시할 노선이 없습니다.</div>';
  $('ttRouteSub').textContent=rows.length?rows.length+'개 노선':'자료 없음';
  $('ttRouteHint').innerHTML='노선마다 <strong>가장 싼 출발일</strong>을 한 줄씩 놓았습니다. 줄을 누르면 그 상품 예약 페이지가 새 탭에서 열립니다.';
}

/* 필터 */
function renderTtFilters(){
  const rg={};ttAll().forEach(function(d){rg[d.region]=(rg[d.region]||0)+1});
  $('ttRegion').innerHTML='<option value="all">전체 권역 ('+ttAll().length+')</option>'+
    Object.keys(rg).map(function(k){return '<option value="'+esc(k)+'">'+esc(k)+' ('+rg[k]+')</option>'}).join('');
  $('ttRegion').value=ttst.region;
  const base=ttAll().filter(function(d){return ttst.region==='all'||d.region===ttst.region});
  const ct={};base.forEach(function(d){if(!ct[d.code])ct[d.code]={city:d.city,n:0,min:d.price};ct[d.code].n++;if(d.price<ct[d.code].min)ct[d.code].min=d.price});
  const keys=Object.keys(ct).sort(function(a,b){return ct[a].min-ct[b].min});
  $('ttCity').innerHTML='<option value="all">전체 도시 ('+keys.length+'개 노선)</option>'+
    keys.map(function(k){return '<option value="'+esc(k)+'">'+esc(ct[k].city)+' ('+esc(k)+') · '+ct[k].n+'건</option>'}).join('');
  if(keys.indexOf(ttst.city)<0)ttst.city='all';
  $('ttCity').value=ttst.city;
  $('ttCount').textContent='표시 '+KR(ttFiltered().length)+'건 / 전체 '+KR(ttAll().length)+'건';
}

/* 출발일 달력 — 칸을 누르면 그 날 최저 상품 예약 페이지가 새 탭에서 열린다 */
function renderTtCal(){
  const months=ttMonths();
  const box=$('ttDays');
  if(!months.length){
    $('ttMonthTitle').textContent='—';$('ttPrevMonth').disabled=true;$('ttNextMonth').disabled=true;
    box.innerHTML='<div class="tt-none" style="grid-column:1/-1">아직 수집된 출발일이 없습니다. 수집분이 병합되면 월별 달력이 채워집니다.</div>';
    $('ttCalSub').textContent='자료 없음';return;
  }
  if(months.indexOf(ttst.month)<0)ttst.month=months[0];
  const idx=months.indexOf(ttst.month);
  $('ttMonthTitle').textContent=monlabel(ttst.month);
  $('ttPrevMonth').disabled=idx<=0;$('ttNextMonth').disabled=idx>=months.length-1;
  const deals=ttFiltered().filter(function(d){return String(d.out).slice(0,7)===ttst.month});
  const dayMap={};
  deals.forEach(function(d){(dayMap[d.out]=dayMap[d.out]||[]).push(d)});
  const dayMin={};Object.keys(dayMap).forEach(function(k){dayMin[k]=ttMinOf(dayMap[k])});
  const bands=heatBands(Object.keys(dayMin).map(function(k){return dayMin[k]}));
  const monthMin=deals.length?ttMinOf(deals):null;
  const [y,m]=ttst.month.split('-').map(Number);
  const lead=new Date(Date.UTC(y,m-1,1)).getUTCDay();
  let html='';
  for(let i=0;i<lead;i++)html+='<div class="cal-day empty" aria-hidden="true"></div>';
  daysOf(ttst.month).forEach(function(date){
    const list=(dayMap[date]||[]).slice().sort(ttByPrice);
    const low=list[0];
    const dow=dayNo(date);
    const cls='cal-day tt-day '+(low?'hm'+heatLevel(bands,low.price):'hm5 empty-day')+(low&&low.price===monthMin?' low ':'')+' '+(dow===0?'sunday ':dow===6?'saturday ':'');
    let inner='<span class="daynum">'+Number(date.slice(-2))+'</span>';
    if(low){
      inner+='<span class="dayprice">'+shortWon(low.price)+'</span>';
      inner+='<span class="tt-day-city">'+esc(low.city)+' · '+esc(ttSpan(low))+'</span>';
      if(list.length>1)inner+='<span class="tt-day-cnt">'+list.length+'</span>';
      html+=ttRow(cls,low.url,fullDate(date)+' '+low.city+' '+KR(low.price)+'원',inner+'<span class="daynum" style="position:absolute;bottom:3px;right:4px;opacity:.45;font-size:7px">↗</span>','data-tt-date="'+date+'"');
    }else{
      inner+='<span class="daymiss">—</span>';
      html+='<button type="button" class="'+cls+'" aria-label="'+fullDate(date)+' 수집된 상품 없음">'+inner+'</button>';
    }
  });
  box.innerHTML=html;
  const nRoutes=Object.keys(dayMap).length?[...new Set(deals.map(function(d){return d.code}))].length:0;
  $('ttCalSub').textContent=monlabel(ttst.month)+' · 이 달 '+deals.length+'건 · '+nRoutes+'개 노선 · '+Object.keys(dayMap).length+'일'+(monthMin!=null?' · 최저 '+shortWon(monthMin):'')+' · 칸을 누르면 예약 페이지가 새 탭에서 열립니다';
}

/* 선택한 출발일 상세 */
function renderTtDay(){
  const box=$('ttDayDetail');
  if(!ttst.day){
    box.innerHTML='<p class="fl-empty">달력 날짜 칸·표 행을 누르면 <strong>그 상품의 예약 페이지가 새 탭에서 바로</strong> 열리고, 이 자리에는 같은 출발일의 다른 상품(노선·항공사·잔여석)이 표시됩니다. 빈칸(—)은 그 날 수집된 상품이 없다는 뜻이며 추정하지 않았습니다.</p>';
    return;
  }
  const ds=ttFiltered().filter(function(d){return d.out===ttst.day}).slice().sort(ttByPrice);
  const min=ttMinOf(ds);
  let html='<div class="fl-detail-head"><div><h3>'+fullDate(ttst.day)+' ('+weekday(ttst.day)+') 출발</h3><div class="meta">'+(ds.length?ds.length+'건 · 싼 순서':'이 날짜에 수집된 상품이 없습니다')+'</div></div><button type="button" class="fl-close" id="ttDayClose" aria-label="상세 닫기">✕</button></div>';
  if(ds.length){
    html+='<div class="fl-detail-grid">';
    ds.forEach(function(d){
      html+='<div class="fl-pcard"><div class="fl-pcard-head"><b>'+esc(d.city)+' <span class="fl-code">'+esc(d.code)+'</span>'+ttChanTag(d)+'</b><span>'+esc(ttRange(d))+' · '+esc(ttSpan(d))+'</span></div>'+
        '<div class="fl-prow"><div class="fl-pname">'+ttAir(d)+(d.times?' · '+esc(d.times):'')+'<div class="fl-pair">잔여 '+esc(ttSeats(d))+(d.note?' · '+esc(d.note):'')+'</div></div>'+
        '<div class="fl-pprice'+(d.price===min?' is-min':'')+'">'+shortWon(d.price)+'</div>'+
        '<a class="fl-plink" href="'+esc(d.url)+'" target="_blank" rel="noopener">예약</a></div></div>';
    });
    html+='</div>';
  }
  box.innerHTML=html;
}

/* 노선별 표 — 행 전체가 예약 링크 */
function renderTtTable(){
  const by={};
  ttFiltered().forEach(function(d){const k=d.code;if(!by[k])by[k]={code:d.code,city:d.city,region:d.region,deals:[]};by[k].deals.push(d)});
  const rows=Object.keys(by).map(function(k){return {g:by[k],b:ttBestOf(by[k].deals)}}).sort(function(a,b){return ttByPrice(a.b,b.b)});
  let html='<div class="tt-thead"><span class="r-name">노선</span><span class="r-price">최저 왕복</span><span class="r-date">출발–귀국</span><span class="r-span">기간</span><span class="r-air">항공사</span><span class="r-go">예약</span></div>';
  if(!rows.length){
    html+='<div class="tt-none">표시할 노선이 없습니다.</div>';
  }else{
    rows.forEach(function(o){
      const b=o.b;
      html+=ttRow('tt-trow',b.url,o.g.city+' '+ttRange(b)+' '+KR(b.price)+'원',
        '<span class="tt-cell r-name"><b>'+esc(o.g.city)+'</b><small>'+esc(o.g.code)+' · '+esc(o.g.region)+' · '+o.g.deals.length+'건</small></span>'+
        '<span class="tt-cell price low r-price"><b>'+KR(b.price)+'원</b><small>'+esc(ttChan(b))+'</small></span>'+
        '<span class="tt-cell r-date"><b>'+esc(ttRange(b))+'</b><small>'+esc(weekday(b.out))+' 출발 · '+esc(weekday(b.back))+' 귀국</small></span>'+
        '<span class="tt-cell r-span">'+esc(ttSpan(b))+'<small>잔여 '+esc(ttSeats(b))+'</small></span>'+
        '<span class="tt-cell r-air">'+ttAir(b)+'<small>'+esc(b.times||'시각 미표시')+'</small></span>'+
        '<span class="tt-cell go r-go"><span class="tt-go">예약 ↗</span></span>');
    });
  }
  $('ttTable').className='tt-table tt-rtable';
  $('ttTable').innerHTML=html;
  $('ttTableSub').textContent=rows.length?'노선 '+rows.length+'개 · 상품 '+ttFiltered().length+'건 · 노선별 가장 싼 상품 기준':'자료 없음';
}

/* 전체 상품 목록 — 행 전체가 예약 링크 */
function renderTtList(){
  const ds=ttFiltered().slice().sort(ttByPrice);
  const min=ttMinOf(ds);
  let html='<div class="tt-thead"><span class="d-date">출발–귀국</span><span class="d-name">노선</span><span class="d-span">기간</span><span class="d-seat">잔여석</span><span class="d-air">항공사</span><span class="d-go">예약</span></div>';
  if(!ds.length){
    html+='<div class="tt-none">아직 수집된 상품이 없습니다.</div>';
  }else{
    ds.forEach(function(d){
      html+=ttRow('tt-drow',d.url,d.city+' '+ttRange(d)+' '+KR(d.price)+'원',
        '<span class="tt-cell d-date"><b>'+esc(ttRange(d))+'</b><small>'+esc(weekday(d.out))+'–'+esc(weekday(d.back))+'</small></span>'+
        '<span class="tt-cell d-name"><b>'+esc(d.city)+'</b><small>'+esc(d.code)+' · '+esc(d.region)+ttChanTag(d)+'</small></span>'+
        '<span class="tt-cell d-span">'+esc(ttSpan(d))+'</span>'+
        '<span class="tt-cell d-seat">'+esc(ttSeats(d))+'</span>'+
        '<span class="tt-cell d-air">'+ttAir(d)+'</span>'+
        '<span class="tt-cell price d-go'+(d.price===min?' low':'')+'"><b>'+KR(d.price)+'원</b><span class="tt-go">예약 ↗</span></span>');
    });
  }
  $('ttList').className='tt-table tt-dtable';
  $('ttList').innerHTML=html;
  $('ttListSub').textContent=ds.length?KR(ds.length)+'건 · 싼 순서 · 1인 왕복 총액(유류·세금 포함) 기준':'자료 없음';
}

/* 조회 기준 · 주의 */
function renderTtNotes(){
  const o=(typeof TTANG!=='undefined'&&TTANG.observedAt)||'—';
  $('ttBasis').innerHTML='<p class="hint">수집 시각 <strong>'+esc(o)+'</strong>. 부산(PUS) 출발 <strong>왕복</strong> 상품만 담았고, 금액은 <strong>성인 1인 왕복 총액</strong>(유류할증료·공항시설사용료·세금 포함 예약 화면 표시가)입니다. 출발일·귀국일은 상품에 적힌 날짜를 그대로 옮겼고, 기간(일수)은 출발일~귀국일과 일치합니다.<br>달력의 칸은 <strong>그 출발일에서 가장 싼 상품</strong>의 금액이고, 오른쪽 위 작은 숫자는 같은 날짜에 있는 상품 수입니다. 빈칸(—)은 그 날 수집된 상품이 없다는 뜻으로, 추정해서 채우지 않았습니다.</p>';
  $('ttCaution').innerHTML='<ul class="hint" style="margin:0;padding-left:16px">'+
    '<li>예약 페이지는 <strong>각 상품의 예약 화면</strong>으로 바로 열립니다. 날짜 칸·노선 행·상품 행 어디를 눌러도 새 탭에서 열립니다.</li>'+
    '<li>땡처리 상품은 <strong>잔여석이 적고</strong> 최소 인원 조건(2명 이상 등)이 붙는 경우가 있습니다. 목록의 잔여석·인원 조건을 먼저 확인하세요.</li>'+
    '<li>표시 금액은 조회 시점 값이고, 결제 화면에서 유류할증료·수하물·좌석 지정이 더해질 수 있습니다.</li>'+
    '<li>같은 노선·같은 날짜에 여러 항공사 상품이 있으면 표에는 <strong>가장 싼 한 줄</strong>만 놓고, 전체는 아래 상품 목록에 남깁니다.</li>'+
    '<li>수집은 노선·권역별로 나눠 진행하며, 새 보고가 들어오면 같은 노선·출발일·귀국일 키로 덮어써 중복 없이 합칩니다.</li>'+
    '</ul>';
}

function renderTt(){
  setDealPanels('tt');
  renderTtKpi();renderTtTop();renderTtRoutes();renderTtFilters();renderTtCal();renderTtDay();renderTtTable();renderTtList();renderTtNotes();
  const n=ttAll().length;
  const tb=document.querySelector('[data-tab="tt"] b');
  if(tb)tb.textContent=KR(n);
  const t=tabs.tt;
  $('sectionTitle').textContent='부산 출발 땡처리 항공권 — '+KR(n)+'건';
  $('sectionSubtitle').textContent=t.sub;
  $('checktime').textContent=t.checked;
}
/* 첫 렌더 전에도 탭 배지 숫자가 실제 건수로 보이게 */
(function(){const tb=document.querySelector('[data-tab="tt"] b');if(tb)tb.textContent=KR(ttAll().length)})();
$('ttRegion').addEventListener('change',function(e){ttst.region=e.target.value;ttst.city='all';renderTtFilters();renderTtKpi();renderTtTop();renderTtRoutes();renderTtCal();renderTtTable();renderTtList();});
$('ttCity').addEventListener('change',function(e){ttst.city=e.target.value;renderTtKpi();renderTtTop();renderTtRoutes();renderTtCal();renderTtTable();renderTtList();});
$('ttPrevMonth').addEventListener('click',function(){const ms=ttMonths();const i=ms.indexOf(ttst.month);if(i<=0)return;ttst.month=ms[i-1];ttst.day='';renderTtCal();renderTtDay();});
$('ttNextMonth').addEventListener('click',function(){const ms=ttMonths();const i=ms.indexOf(ttst.month);if(i<0||i>=ms.length-1)return;ttst.month=ms[i+1];ttst.day='';renderTtCal();renderTtDay();});
$('ttDays').addEventListener('click',function(e){
  const a=e.target.closest('[data-tt-date]');
  if(!a)return;
  /* 링크는 그대로 새 탭에서 열리고(기본 동작), 이 화면에는 같은 날 상품만 다시 그린다 */
  ttst.day=a.getAttribute('data-tt-date');renderTtDay();
});
$('ttDayDetail').addEventListener('click',function(e){if(e.target.closest('#ttDayClose')){ttst.day='';renderTtDay()}});
