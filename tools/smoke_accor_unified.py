#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""② 아코르 통합 개편 스모크 테스트 — 브라우저 없이 index.html 의 화면 코드를 돌려 본다.

QuickJS 로 index.html 의 본 스크립트를 실행하고, DOM 은 최소 스텁으로 바꾼다.
`render()` 가 예외 없이 끝나고, 탭·지역·모드·상세 창·위챗 창·해시 주소가
기대한 값을 내는지 본다(화면 모양은 브라우저 검수에서 본다).

실행: PYTHONPATH=/workspace/.local/lib/python3.12/site-packages python3 tools/smoke_accor_unified.py
"""
import json
import os
import re
import sys

import quickjs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, 'data', 'app')

PRELUDE = r"""
var __log=[];
function __out(x){__log.push(x)}
if(typeof Intl==='undefined'||!Intl.NumberFormat){
  var NF=function(loc,opt){this.format=function(n){
    if(n===null||n===undefined||isNaN(n))return 'NaN';
    var s=String(Math.round(n*1000)/1000),neg=false;
    if(s.charAt(0)==='-'){neg=true;s=s.slice(1)}
    var parts=s.split('.'),ip=parts[0],fp=parts[1],out='';
    for(var i=0;i<ip.length;i++){if(i&&((ip.length-i)%3===0))out+=',';out+=ip.charAt(i)}
    if(fp)out+='.'+fp;
    return (neg?'-':'')+out};
    this.resolvedOptions=function(){return {minimumFractionDigits:0,maximumFractionDigits:3}}};
  Intl={NumberFormat:NF,DateTimeFormat:function(){this.format=function(){return ''}}};
}

if(typeof URLSearchParams==='undefined'){
  var URLSearchParams=function(str){
    this._o={};this._k=[];
    var s=String(str==null?'':str).replace(/^#/,'');
    if(!s)return;
    var self=this;
    s.split('&').forEach(function(pair){
      if(!pair)return;
      var i=pair.indexOf('='),k=i<0?pair:pair.slice(0,i),v=i<0?'':pair.slice(i+1);
      k=decodeURIComponent(k.replace(/\+/g,' '));v=decodeURIComponent(v.replace(/\+/g,' '));
      if(!(k in self._o))self._k.push(k);
      self._o[k]=v;
    });
    this.get=function(k){return (k in this._o)?this._o[k]:null};
    this.set=function(k,v){if(!(k in this._o))this._k.push(k);this._o[k]=String(v)};
    this.forEach=function(fn){var self2=this;this._k.forEach(function(k){fn(self2._o[k],k,self2)})};
    this.toString=function(){var self2=this;return this._k.map(function(k){return encodeURIComponent(k)+'='+encodeURIComponent(self2._o[k])}).join('&')};
    this.entries=function(){var self2=this;return this._k.map(function(k){return [k,self2._o[k]]})};
  };
}

var __store={};
var __els={};
function El(id){
  this.id=id||'';this._html='';this.textContent='';this.value='';this.hidden=false;this.disabled=false;
  this.dataset={};this.options=[];this.checked=false;this.type='';this.href='';this.title='';
  this.style={};this.children=[];this.tagName='DIV';this.offsetLeft=0;this.offsetWidth=100;this.clientWidth=300;this.scrollWidth=300;this.scrollLeft=0;
  var self=this;
  this.classList={_s:{},add:function(c){this._s[c]=1},remove:function(c){delete this._s[c]},
    toggle:function(c,v){if(v===undefined)v=!this._s[c];if(v)this._s[c]=1;else delete this._s[c];return !!this._s[c]},
    contains:function(c){return !!this._s[c]}};
  this.setAttribute=function(k,v){this[k]=v};this.removeAttribute=function(k){delete this[k]};
  this.getAttribute=function(k){return this.dataset[k]!==undefined?this.dataset[k]:(this[k]!==undefined?this[k]:null)};
  this.addEventListener=function(){};this.removeEventListener=function(){};
  this.appendChild=function(c){this.children.push(c);return c};this.removeChild=function(){};
  this.remove=function(){};this.focus=function(){};this.select=function(){};this.click=function(){};
  this.closest=function(){return null};this.querySelector=function(){return null};
  this.querySelectorAll=function(){return []};this.scrollIntoView=function(){};
  this.getBoundingClientRect=function(){return {top:0,left:0,width:100,height:20}};
  Object.defineProperty(this,'innerHTML',{get:function(){return self._html},set:function(v){self._html=String(v)}});
}
function getEl(id){if(!__els[id])__els[id]=new El(id);return __els[id]}
function fakeEl(){return new El('')}
var document={
  getElementById:function(id){return getEl(id)},
  querySelector:function(){return null},
  querySelectorAll:function(){return []},
  createElement:function(t){var e=new El('');e.tagName=String(t||'').toUpperCase();return e},
  addEventListener:function(){},removeEventListener:function(){},
  documentElement:new El('html'),body:new El('body'),
  title:'',readyState:'complete'
};
var __hash='';
var location={href:'https://example.test/app/',pathname:'/app/',search:'',hash:'',hostname:'example.test',protocol:'https:',
  reload:function(){},assign:function(){}};
var history={replaceState:function(a,b,u){if(u!==undefined){var i=String(u).indexOf('#');__hash=i>=0?String(u).slice(i):'';location.hash=__hash}}};
var navigator={clipboard:null,serviceWorker:{controller:null,addEventListener:function(){},register:function(){return Promise.resolve({update:function(){return Promise.resolve()}})}},userAgent:'smoke'};
var window={addEventListener:function(){},removeEventListener:function(){},open:function(){return null},crypto:{},localStorage:null,location:location,history:history,navigator:navigator};
var localStorage={getItem:function(k){return __store[k]!==undefined?__store[k]:null},setItem:function(k,v){__store[k]=String(v)},removeItem:function(k){delete __store[k]}};
window.localStorage=localStorage;
/* __parts 는 parts JSON 을 파싱해 채운다 */
var fetch=function(url){var name=String(url).split('/').pop().split('?')[0];
  var body=__parts[name];
  return Promise.resolve({ok:!!body,status:body?200:404,json:function(){return Promise.resolve(body||{})}})};
var URL={createObjectURL:function(){return 'blob:x'},revokeObjectURL:function(){}};
var Blob=function(){};
var requestAnimationFrame=function(f){return 0};
var setTimeout=function(f){return 0};
var clearTimeout=function(){};
var alert=function(){};
"""

POSTLUDE = r"""
var __res={log:__log};
__res.render=function(){try{render();return 'ok'}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.setTab=function(t){try{setTab(t);return 'ok'}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.sync=function(t){st.tab=t;st.city='all';st.hotel='all';st.zone='all';st.mode='cash';st.month=tabs[t].default||tabs[t].start||'2026-12';st.selectedDay='';st.prog='all';st.brand='all';st.ctier='all';st.apcOnly=false;st.apcDaysOnly=false;st.nights=1;st.favOnly=false;st.budget=0;return 'ok'};
__res.state=function(){return {tab:st.tab,zone:st.zone,mode:st.mode,month:st.month,hotel:st.hotel,nights:st.nights}};
__res.hotels=function(g){return allHotels.filter(function(h){return h.group===g}).length};
__res.cities=function(){return getEl('citySelect').innerHTML.length};
__res.html=function(id){return getEl(id).innerHTML};
__res.text=function(id){return getEl(id).textContent};
__res.hidden=function(id){return getEl(id).hidden};
__res.days=function(){return getEl('days').innerHTML.length};
__res.openDetail=function(d){try{openDetail(d);return 'ok'}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.openWx=function(hid,d,n){try{openWxSheet(hid,d,n);return 'ok'}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.wxClose=function(){try{closeWxSheet();return getEl('wxSheet').classList.contains('show')?'open':'closed'}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.applyHash=function(h){try{location.hash=h;var p=hashParams();applyHashState(p);activate(st.tab);return JSON.stringify({tab:st.tab,zone:st.zone,mode:st.mode,hotel:st.hotel})}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.hashBuild=function(){try{return hashBuild()}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.setZone=function(z){try{st.zone=z;render();return 'ok'}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.setMode=function(m){try{switchMode(m);return 'ok'}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.pick=function(id){try{setHotel(id);return 'ok'}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.counts=function(){try{return JSON.stringify({filtered:filteredHotels().length,group:groupHotels().length,zone:st.zone,mode:st.mode})}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.detailHtml=function(){return getEl('dialogBody').innerHTML.length};
__res.heroHtml=function(){return getEl('heroMain').innerHTML.length};
__res.basisHtml=function(){return getEl('basis').innerHTML.length};
__res.has=function(id,needle){try{return getEl(id).innerHTML.indexOf(needle)>=0?'yes':'no'}catch(e){return 'ERR: '+(e&&e.message||e)}};
__res.count=function(id,needle){try{var h=getEl(id).innerHTML,n=0,i=0;while((i=h.indexOf(needle,i))>=0){n++;i+=needle.length}return String(n)}catch(e){return 'ERR: '+(e&&e.message||e)}};
__res.filtered=function(){return String(filteredHotels().length)};
__res.monthHi=function(){return getEl('monthHighlight').innerHTML};
__res.csv=function(){try{exportCsv();return 'ok'}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.zones=function(){return getEl('zoneChips').innerHTML};
__res.apcDay=function(d){try{var h=apcDayHotel(d);return h?(h.id+' accor='+Boolean(h.accor)+' zone='+h.zone):'null'}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.nights=function(n){try{st.nights=Number(n);render();return 'ok'}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.prog=function(v){try{st.prog=v;render();return 'ok'}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.brand=function(v){try{st.brand=v;render();return 'ok'}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.city=function(v){try{setCity(v);return 'ok'}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.bkSheet=function(hid,d,n){try{openBkSheet(hid,d,n);return getEl('bkSheet').classList.contains('show')?'open':'closed'}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.plan=function(hid,d,n){try{return planHotelText(wxHotel(hid),d,n).slice(0,60)}catch(e){return 'ERR: '+(e&&e.stack||e)}};
__res.tmpl=function(id){try{return (TEMPLATES&&TEMPLATES[id])?'yes':'no'}catch(e){return 'n/a'}};
"""


def load_parts():
    parts = {}
    for name in os.listdir(APP):
        if name.endswith('.json'):
            with open(os.path.join(APP, name), encoding='utf-8') as fp:
                parts[name] = json.load(fp)
    return parts


def main():
    src = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    blocks = re.findall(r'<script>(.*?)</script>', src, re.S)
    code = blocks[-1]
    ctx = quickjs.Context()
    ctx.eval(PRELUDE)
    parts = load_parts()
    ctx.set('__partsJson', json.dumps(parts, ensure_ascii=False))
    ctx.eval('var __parts=JSON.parse(__partsJson);')
    total = int(ctx.eval('Object.keys(__parts).length'))
    print('part files loaded:', total)
    ctx.eval(code)
    ctx.eval(POSTLUDE)
    fails = []

    def run(call, label):
        try:
            v = ctx.eval('__res.' + call)
        except Exception as exc:  # noqa: BLE001
            v = 'THROW: %s' % str(exc)[:400]
        print('  %-42s %s' % (label, v))
        if isinstance(v, str) and ('ERR' in v or 'THROW' in v):
            fails.append(label + ' → ' + v)
        return v

    run('sync("accor")', 'state=accor')
    for name in ('accor', 'lux', 'marriott', 'flight', 'tt'):
        ctx.eval('loadPart("%s")' % name)
        for _ in range(200):
            if not ctx.execute_pending_job():
                break
    ctx.eval('Object.assign(lg,{view:"hotel"})')
    run('hotels("accor")', 'accor hotels (기대 536)')
    run('render()', 'render accor cash 전체')
    run('counts()', 'filtered count')
    print('  citySelect html len:', ctx.eval('__res.cities()'))
    print('  days html len:', ctx.eval('__res.days()'))
    print('  hero html len:', ctx.eval('__res.heroHtml()'))
    print('  basis html len:', ctx.eval('__res.basisHtml()'))
    for z in ('kr', 'sea', 'cn', 'etc'):
        run('setZone("%s")' % z, 'zone %s render' % z)
        run('counts()', '  filtered')
    run('setZone("cn")', 'zone cn')
    for m in ('sp2', 'sp3', 'rhr', 'apc', 'cash'):
        run('setMode("%s")' % m, 'mode %s render' % m)
    run('setZone("all")', 'zone all')
    run('setMode("cash")', 'cash')
    # 의미 검증
    run('setZone("cn")', 'zone cn')
    run('setMode("cash")', 'cash')
    print('  cn cash — APC 배지:', ctx.eval('__res.has("days","APC ")'), '· 위챗 칸:', ctx.eval('__res.count("days","wx-cell")'))
    run('setMode("apc")', 'apc')
    print('  apc zone (기대 cn):', ctx.eval('__res.state().zone'), '· 대표 호텔:', ctx.eval('__res.apcDay("2026-12-01")'))
    print('  apc — 가능 칸:', ctx.eval('__res.count("days","APC 가능")'), '· month:', ctx.eval('__res.monthHi()')[:80])
    print('  apc filtered:', ctx.eval('__res.filtered()'))
    print('  apc detail — APC 문구:', end=' ')
    run('openDetail("2026-12-05")', 'detail apc')
    print('  ', ctx.eval('__res.has("dialogBody","APC")'))
    run('setMode("rhr")', 'rhr')
    print('  rhr filtered (기대 32):', ctx.eval('__res.filtered()'))
    run('setMode("sp2")', 'sp2')
    print('  sp2 filtered:', ctx.eval('__res.filtered()'))
    run('setMode("cash")', 'cash')
    run('setZone("kr")', 'zone kr')
    print('  kr cash — 위챗 칸(기대 0):', ctx.eval('__res.count("days","wx-cell")'))
    run('setZone("all")', 'zone all')
    run('pick("aB9G8")', 'merged hotel')
    run('openDetail("2026-12-05")', 'merged detail')
    print('  merged detail — 위챗:', ctx.eval('__res.has("dialogBody","위챗 예약")'), '· 아코르 공홈:', ctx.eval('__res.has("dialogBody","아코르 공홈")'))
    run('pick("all")', 'all hotels')
    run('pick("dB200")', 'pick 서울 페어몬트')
    run('setMode("sp2")', 'sp2 single')
    run('openDetail("2027-01-08")', 'sp2 detail')
    run('setMode("sp3")', 'sp3 single')
    run('openDetail("2027-01-09")', 'sp3 detail')
    run('nights(2)', '2박 연속 render')
    run('nights(1)', '1박')
    run('setMode("cash")', 'cash')
    run('setZone("cn")', 'cn')
    run('prog("snu")', 'SNU 필터')
    print('  snu filtered:', ctx.eval('__res.filtered()'))
    run('prog("all")', 'prog all')
    run('brand("소피텔")', '브랜드 필터')
    print('  소피텔 filtered:', ctx.eval('__res.filtered()'))
    run('brand("all")', 'brand all')
    run('city("상하이")', '도시 상하이')
    print('  상하이 filtered:', ctx.eval('__res.filtered()'))
    run('city("all")', 'city all')
    run('setZone("all")', 'zone all')
    run('csv()', 'CSV 저장')
    run('bkSheet("aA5G7","2026-12-05",1)', '이중 연결 창(아코르↔호텔럭스)')
    run('plan("aB9G8","2026-12-05",1)', '일정 복사 문구')
    print('  zoneChips:', ctx.eval('__res.zones()')[:160])
    run('openDetail("2026-12-05")', 'detail 2026-12-05')
    print('  detail html len:', ctx.eval('__res.detailHtml()'))
    run('openWx("aB9G8","2026-12-05",1)', 'wechat sheet')
    run('wxClose()', 'wechat close (기대 closed)')
    run('pick("aB9G8")', 'pick merged hotel')
    run('openDetail("2026-12-05")', 'detail merged')
    run('applyHash("#tab=china")', 'old #tab=china')
    run('applyHash("#tab=domestic&hotel=ap052")', 'old #tab=domestic&hotel=ap052 (기대 aB9G8)')
    run('applyHash("#tab=accor&zone=cn&mode=apc")', 'new hash zone/mode')
    run('applyHash("#tab=accor&mode=apc")', 'new hash mode=apc only (기대 zone cn)')
    run('hashBuild()', 'hashBuild')
    for t in ('lux', 'marriott', 'flight', 'tt', 'combo', 'forest', 'mileage', 'partner-mileage', 'valet'):
        run('setTab("%s")' % t, 'tab %s' % t)
    print()
    if fails:
        print('SMOKE FAIL (%d)' % len(fails))
        for f in fails:
            print('  - ' + f)
        return 1
    print('SMOKE OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
