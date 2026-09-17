#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doubao-web：豆包解析结果本地展示服务

用法:
    python doubao_web.py [端口]        # 默认 8765，浏览器打开 http://127.0.0.1:8765

纯标准库实现。/proxy 反代豆包 CDN（跨域 + Range + 浏览器缓存），/api/convert 无损/快速转 H.264。
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doubao_engine as E  # noqa: E402

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5, user-scalable=yes, viewport-fit=cover">
<title>豆包解析 · 本地结果</title>
<style>
:root{--bg:#f5f6f8;--card:#fff;--ink:#1c1e21;--sub:#65676b;--line:#e4e6eb;--acc:#3b82f6;--ok:#16a34a;--warn:#d97706}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;padding:14px}
.wrap{max-width:1200px;margin:0 auto}
.bar{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap}
.bar input{flex:1;min-width:0;border:1px solid var(--line);border-radius:8px;padding:9px 12px;font-size:13px;background:#fff}
.bar button{white-space:nowrap}
#btnClear{padding:8px 13px;font-size:15px;font-weight:700;line-height:1}
#pasteBox{position:fixed;inset:0;background:rgba(0,0,0,.45);display:none;align-items:center;justify-content:center;z-index:98}
.pbox{background:var(--card);border-radius:14px;padding:16px;width:min(92vw,420px);box-shadow:0 8px 30px rgba(0,0,0,.18)}
.ptitle{font-size:13px;font-weight:600;margin-bottom:10px;color:var(--ink)}
#ptext{width:100%;height:90px;border:1px solid var(--line);border-radius:8px;padding:9px 12px;font-size:13px;box-sizing:border-box;resize:none;background:#fff}
.pbtns{display:flex;gap:8px;justify-content:flex-end;margin-top:10px}
button{border:0;border-radius:8px;padding:8px 14px;font-size:13px;cursor:pointer;background:var(--acc);color:#fff}
button.gray{background:#e4e6eb;color:var(--ink)}
button.ok{background:var(--ok)}
button.warn{background:var(--warn)}
button:disabled{opacity:.5;cursor:wait}
.tabs{display:flex;gap:10px;margin-bottom:10px;flex-wrap:wrap}
.tab{padding:11px 44px;border-radius:12px;background:#e4e6eb;color:var(--sub);cursor:pointer;font-size:15px;font-weight:600;user-select:none;text-align:center;min-width:150px}
.tab.on{background:var(--acc);color:#fff}
.toolbar{display:flex;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:6px}
.toolbar .hint{flex:1;color:var(--sub);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fbar{display:flex;align-items:center;flex-wrap:wrap;gap:6px 10px;margin-bottom:10px;font-size:13px}
.fbar .fleft{flex:1;min-width:0;color:var(--sub)}
.fbar .fleft b{color:var(--ink);font-weight:600}
.fbar .fleft .chip{margin-left:8px}
.fbar .fright{display:flex;gap:8px;align-items:center}
.chip{padding:5px 12px;border-radius:14px;background:#e4e6eb;color:var(--sub);cursor:pointer;font-size:12px;user-select:none}
.chip.on{background:var(--acc);color:#fff}
.fbar select{border:1px solid var(--line);border-radius:8px;padding:6px 8px;font-size:12.5px;background:#fff;color:var(--ink)}
.fbar select.on{border-color:var(--acc);color:var(--acc)}
.tip{background:#fff8e6;border:1px solid #ffe9b3;color:#8a6d1a;border-radius:8px;padding:8px 12px;font-size:12px;margin-bottom:12px;display:none}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.card .media{position:relative;background:#000;height:200px;display:flex;align-items:center;justify-content:center;overflow:hidden}
.card img{max-width:100%;max-height:100%;object-fit:contain;cursor:zoom-in}
.card video{max-width:100%;max-height:100%}
.badge{position:absolute;top:6px;left:6px;background:rgba(0,0,0,.6);color:#fff;font-size:11px;border-radius:6px;padding:1px 7px}
.media .zoom{position:absolute;top:6px;right:6px;background:rgba(0,0,0,.6);color:#fff;font-size:12px;border-radius:6px;padding:2px 9px;cursor:pointer;user-select:none}
.card .meta{padding:7px 10px 2px;font-size:11.5px;color:var(--sub)}
.card .btns{padding:6px 10px 10px;display:flex;gap:6px}
.card .btns button{flex:1;padding:6px 0;font-size:12px}
.empty{min-height:200px}
#lb{position:fixed;inset:0;background:rgba(0,0,0,.92);display:none;flex-direction:column;align-items:center;justify-content:center;z-index:99}
#lbImg{max-width:94vw;max-height:78vh;object-fit:contain;background:transparent}
#lbVid{max-width:94vw;max-height:78vh;background:#000;border-radius:6px}
#lbImg.loading{min-width:120px;min-height:120px;background:url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40"><circle cx="20" cy="20" r="16" stroke="white" stroke-width="3" fill="none" stroke-dasharray="70" stroke-linecap="round"><animateTransform attributeName="transform" type="rotate" from="0 20 20" to="360 20 20" dur="1s" repeatCount="indefinite"/></circle></svg>') center no-repeat}
#lb .lbbar{display:flex;gap:10px;margin-top:14px;align-items:center}
#lb .lbbar button{font-size:14px;padding:9px 18px}
#lb .close{position:absolute;top:12px;right:14px;background:rgba(255,255,255,.15);font-size:20px;width:40px;height:40px;padding:0;border-radius:50%}
#lb .nav{position:absolute;top:50%;transform:translateY(-50%);background:rgba(255,255,255,.15);font-size:22px;width:46px;height:46px;padding:0;border-radius:50%}
#lb .prev{left:10px}#lb .next{right:10px}
#lb .cnt{color:#fff;font-size:12px;margin-top:8px}
/* ===== 移动端适配 ===== */
@media(max-width:600px){
  body{padding:10px 8px calc(10px + env(safe-area-inset-bottom))}
  /* 输入区：链接独占一行，按钮第二行 */
  .bar{gap:6px}
  .bar input{flex:1 1 100%;font-size:16px;padding:10px 12px} /* 16px 防 iOS 聚焦自动放大 */
  #btnClear,#btnPaste,#btnParse{padding:10px 18px;font-size:14px}
  /* 筛选栏：两行自然换行，触摸目标加大 */
  .fbar{font-size:13px}
  .chip{padding:8px 14px;font-size:13px}
  .fbar select{padding:8px 10px;font-size:13px}
  /* 选项卡：均分一行 */
  .tab{flex:1;min-width:0;padding:12px 0;font-size:14px}
  /* 一键下载行 */
  .toolbar button{padding:10px 16px;font-size:13px}
  .toolbar .hint{flex-basis:100%;white-space:normal}
  /* 网格：宽屏两列，窄屏一列 */
  .grid{grid-template-columns:repeat(2,1fr);gap:8px}
  .card .media{height:140px}
  .card .meta{font-size:11px}
  .card .btns button{padding:9px 0;font-size:12px}
  .media .zoom{padding:8px 16px;font-size:14px} /* 视频放大角标加大触摸面积 */
  /* 灯箱：手机上铺满全屏，隐藏箭头（滑动切换） */
  #lbImg{width:100vw;height:calc(100vh - 130px);max-width:none;max-height:none;object-fit:contain}
  #lbVid{width:100vw;height:calc(100vh - 130px);max-width:none;max-height:none;object-fit:contain}
  #lb .nav{display:none}
  #lb .lbbar{margin-top:10px}
  #lb .lbbar button{padding:12px 22px;font-size:15px}
  #lb .close{top:max(10px,env(safe-area-inset-top))}
  #lb .cnt{margin-top:6px}
}
@media(max-width:380px){
  .grid{grid-template-columns:1fr}
  .card .media{height:200px}
}
/* 横屏手机：灯箱留出底部操作行 */
@media(max-height:450px){
  #lbImg,#lbVid{height:calc(100vh - 96px)}
  #lb .lbbar button{padding:8px 18px}
}
</style>
</head>
<body>
<div class="wrap">
  <div class="bar">
    <input id="url" placeholder="https://www.doubao.com/thread/...">
    <button class="gray" id="btnClear" onclick="clearUrl()" title="清空输入框，自己手动粘贴">×</button>
    <button class="gray" id="btnPaste" onclick="pasteUrl()" title="清空旧链接并填入剪贴板内容">粘贴</button>
    <button id="btnParse" onclick="doParse()">解析</button>
  </div>
  <div class="tip" id="mTip"></div>
  <div id="pasteBox" onclick="if(event.target===this)hidePaste()">
    <div class="pbox">
      <div class="ptitle">粘贴链接（Ctrl+V / 长按粘贴）</div>
      <textarea id="ptext" placeholder="按 Ctrl+V 粘贴到这里…"></textarea>
      <div class="pbtns"><button class="gray" onclick="hidePaste()">取消</button><button class="ok" onclick="confirmPaste()">确定</button></div>
    </div>
  </div>
  <div id="main"></div>
</div>
<div id="lb" onclick="if(event.target===this)hideLb()">
  <button class="close" onclick="hideLb()">×</button>
  <button class="nav prev" onclick="lbNav(-1)">‹</button>
  <img id="lbImg" alt="">
  <video id="lbVid" controls playsinline style="display:none"></video>
  <button class="nav next" onclick="lbNav(1)">›</button>
  <div class="lbbar"><button class="ok" id="lbDlBtn" onclick="lbDl()">⬇ 下载</button></div>
  <div class="cnt" id="lbCnt"></div>
</div>
<script>
const isIOS=/iPad|iPhone|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
const isMobile=isIOS||/Android|Mobile/i.test(navigator.userAgent);
let DATA=null,tab='image',lbIdx=0,timeFilter=0;
const $=s=>document.querySelector(s);
// 当前选项卡按时间筛选后的列表（timeFilter=0 表示全部）
function curList(){
  const l=tab==='image'?(DATA.images||[]):(DATA.videos||[]);
  if(!timeFilter)return l;
  const cut=Date.now()-timeFilter*60000;
  return l.filter(it=>(it.epoch||0)*1000>=cut);
}
function setFilter(m){timeFilter=m;render();try{localStorage.setItem('dw_filter',m);}catch(e){}}
if(isMobile){const t=$('#mTip');t.style.display='block';t.innerHTML=isIOS?'📱 iOS：点「⬇ 下载」→ 弹出分享面板 → 点「存储图像 / 存储视频」直接进相册。':'🤖 Android：点「⬇ 下载」保存到「下载」目录，相册里直接能看到；图片也可以长按 →「保存图片」进相册。';}
window.addEventListener('DOMContentLoaded',()=>{
  const q=new URLSearchParams(location.search);
  const qu=q.get('url');
  const qt=q.get('tab');
  if(qu&&qu.includes('/thread/')){
    if(qt==='video')tab='video';
    $('#url').value=qu;doParse();
    return;
  }
  // 刷新恢复：上次链接 + 选项卡 + 时间筛选（服务端有解析缓存，秒回）
  try{
    const su=localStorage.getItem('dw_lastUrl');
    if(su&&su.includes('/thread/')){
      const st=localStorage.getItem('dw_tab');if(st==='video')tab='video';
      timeFilter=+localStorage.getItem('dw_filter')||0;
      $('#url').value=su;doParse();
    }
  }catch(e){}
});

function fmtSize(n){if(!n)return '';const u=['B','KB','MB','GB'];let i=0;while(n>=1024&&i<3){n/=1024;i++;}return n.toFixed(i===0||n>=100?0:1)+u[i];}
function fmtCodec(c){c=(c||'').toLowerCase();return c.includes('265')||c.includes('hevc')||c.includes('bytevc')?'H.265':c.includes('264')||c==='h264'?'H.264':(c?c.toUpperCase():'');}

async function doParse(){
  const u=$('#url').value.trim();
  if(!u.includes('/thread/')){alert('链接需包含 /thread/');return;}
  try{localStorage.setItem('dw_lastUrl',u);}catch(e){}
  const btn=$('#btnParse');
  btn.disabled=true;const oldTxt=btn.textContent;btn.textContent='解析中…';
  $('#main').innerHTML='';
  try{
    const r=await fetch('/api/scan?url='+encodeURIComponent(u));
    DATA=await r.json();
    if(DATA.error){alert('解析失败：'+DATA.error);return;}
    render();
    prefetchImgs();
    loadSizes();
  }catch(e){alert('解析失败：'+e);}
  btn.disabled=false;btn.textContent=oldTxt;
}

// 后台补图片文件大小（不阻塞出图）
async function loadSizes(){
  try{
    const r=await fetch('/api/sizes?url='+encodeURIComponent(DATA.share_url));
    const j=await r.json();
    const m=j.sizes||{};
    (DATA.images||[]).forEach((it,i)=>{
      const s=m[String(it.id)];
      if(s){it.size=s;
        const el=$('#meta_i'+i);
        if(el)el.textContent=[it.time||'',(it.format||'jpg').toUpperCase(),fmtSize(s)].filter(Boolean).join(' · ');}
    });
  }catch(e){}
}

// 后台预取原图（配 Cache-Control，点开大图即秒开）
function prefetchImgs(){
  (DATA.images||[]).slice(0,40).forEach(it=>{const im=new Image();im.src='/proxy?u='+encodeURIComponent(it.url);});
}

function render(){
  const list=curList();
  const cards=list.map((it,i)=>{
    let media;
    if(it.kind==='image'){
      media=`<img loading="lazy" src="/proxy?u=${encodeURIComponent(it.thumb||it.url)}" onclick="showLb(${i})">`;
      var badge=`${it.width||'?'}×${it.height||'?'}`;
      var meta=[it.time||'',(it.format||'jpg').toUpperCase(),fmtSize(it.size)].filter(Boolean).join(' · ');
    }else{
      media=`<video controls preload="none" playsinline poster="/proxy?u=${encodeURIComponent(it.poster||'')}" data-vi="${i}" src=""></video><span class="zoom" onclick="showLb(${i})" title="放大浏览（可切换上一个/下一个）">⤢ 放大</span>`;
      const dur=it.duration?(it.duration<60?it.duration.toFixed(0)+'s':(it.duration/60).toFixed(1)+'min'):'';
      var badge=`▶${dur?' '+dur:''} ${it.width||'?'}×${it.height||'?'}`;
      var meta=[it.time||'',fmtCodec(it.codec)||'',fmtSize(it.size)||''].filter(Boolean).join(' · ')||'解析中…';
    }
    const convBtn=(!isIOS&&it.kind==='video'&&it.codec&&!/264/.test(it.codec))?`<button class="warn" onclick="convItem(${i},this)">转码后下载</button>`:'';
    return `<div class="card"><div class="media">${media}<span class="badge" id="badge_${tab[0]}${i}">${badge}</span></div>
      <div class="meta" id="meta_${tab[0]}${i}">${meta}</div>
      <div class="btns"><button onclick="dlItem('${tab[0]}${i}')">⬇ 下载</button>${convBtn}</div></div>`;
  }).join('');
  $('#main').innerHTML=`
    <div class="fbar">
      <div class="fleft">时间筛选：<span class="chip ${timeFilter===0?'on':''}" onclick="setFilter(0)">全部</span></div>
      <div class="fright">
        <span class="chip ${timeFilter===30?'on':''}" onclick="setFilter(30)">30min</span>
        <span class="chip ${timeFilter===60?'on':''}" onclick="setFilter(60)">1h</span>
        <span class="chip ${timeFilter===360?'on':''}" onclick="setFilter(360)">6h</span>
        <span class="chip ${timeFilter===720?'on':''}" onclick="setFilter(720)">12h</span>
        <select id="fsel" class="${[1440,2880,4320].includes(timeFilter)?'on':''}" onchange="setFilter(+this.value||0)">
          <option value="0" ${![1440,2880,4320].includes(timeFilter)?'selected':''}>更多</option>
          <option value="1440" ${timeFilter===1440?'selected':''}>24h</option>
          <option value="2880" ${timeFilter===2880?'selected':''}>48h</option>
          <option value="4320" ${timeFilter===4320?'selected':''}>72h</option>
        </select>
      </div>
    </div>
    <div class="tabs">
      <div class="tab ${tab==='image'?'on':''}" onclick="setTab('image')">图片 ${tab==='image'?list.length:(DATA.images||[]).length}</div>
      <div class="tab ${tab==='video'?'on':''}" onclick="setTab('video')">视频 ${tab==='video'?list.length:(DATA.videos||[]).length}</div>
    </div>
    <div class="toolbar">
      <div class="hint">${DATA.share_name||''}</div>
      <button class="ok" id="btnAll" onclick="downloadAll(this)">一键下载${tab==='image'?'图片':'视频'}（${list.length}）</button>
    </div>
    <div class="${list.length?'grid':'empty'}">${cards}</div>`;
  if(tab==='video')resolveVideos();
}
function setTab(t){tab=t;render();try{localStorage.setItem('dw_tab',t);}catch(e){}}
// ×清空输入框（手动粘贴用） / 粘贴：优先直接读剪贴板；被环境拦截时弹粘贴框兜底
function clearUrl(){$('#url').value='';$('#url').focus();}
async function pasteUrl(){
  try{
    if(!navigator.clipboard||!navigator.clipboard.readText)throw new Error('unsupported');
    const t=await navigator.clipboard.readText();
    if(t&&t.trim()){$('#url').value=t.trim();flashPaste('已粘贴✓');doParse();return;}
    throw new Error('empty');
  }catch(e){openPasteBox();}
}
function openPasteBox(){
  $('#ptext').value='';
  $('#pasteBox').style.display='flex';
  setTimeout(()=>$('#ptext').focus(),60);
}
function hidePaste(){$('#pasteBox').style.display='none';}
function confirmPaste(){
  const t=$('#ptext').value.trim();
  if(t){$('#url').value=t;flashPaste('已粘贴✓');doParse();}
  hidePaste();
}
function flashPaste(txt){
  const b=$('#btnPaste'),o='粘贴';
  b.textContent=txt;setTimeout(()=>b.textContent=o,1200);
}

// 文件名时间戳：2026-09-17 10:25:25 -> 20260917_102525（保证按名称排序不乱序）
function fstamp(it){const t=(it.time||'').replace(/[-: ]/g,'');return t.length===14?t.slice(0,8)+'_'+t.slice(8):'unknown';}
function fnum(n){return String(n).padStart(3,'0');}

// idx: 'i'+图片序号 / 'v'+视频序号
async function dlItem(idx){
  const isImg=idx[0]==='i';
  const k=+idx.slice(1);
  const it=curList()[k];
  const num=k+1;
  try{
    let u,name;
    if(isImg){
      u='/proxy?u='+encodeURIComponent(it.url);
      name='img_'+fnum(num)+'_'+fstamp(it)+'.'+(it.format==='png'?'png':'jpg');
    }else{
      const vs=await videoVariants(k);
      const best=vs[0]; // 最高清
      u='/proxy?u='+encodeURIComponent(best.url);
      name='video_'+fnum(num)+'_'+fstamp(it)+'_'+best.h+'p.mp4';
    }
    if(isIOS){shareSave(u,name).catch(()=>window.open(u,'_blank'));return;}
    dl(u,name);
  }catch(e){alert('下载失败：'+e);}
}
function dl(u,name){fetch(u).then(r=>r.blob()).then(b=>{const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=name;document.body.appendChild(a);a.click();a.remove();});}
// iOS：拉取文件后调起系统分享面板，用户点「存储图像/存储视频」直接进相册（免长按）
async function shareSave(u,name){
  const r=await fetch(u);const b=await r.blob();
  const f=new File([b],name,{type:b.type||'application/octet-stream'});
  if(navigator.canShare&&navigator.canShare({files:[f]})){
    try{await navigator.share({files:[f]});return;}catch(e){if(e&&e.name==='AbortError')return;}
  }
  window.open(u,'_blank'); // 兜底：新标签长按保存
}

// 视频变体：[{url,codec,w,h,size}]，分辨率从高到低；缓存到 DATA.videos[i]._vs
async function videoVariants(i){
  const v=curList()[i];
  if(v._vs)return v._vs;
  const r=await fetch('/api/video?u='+encodeURIComponent(v.fallback_api));
  const j=await r.json();
  if(j.error)throw j.error;
  v._vs=j.variants;
  // 预览播放优先 H.264（浏览器兼容性最好），没有就最高清
  const play=j.variants.find(x=>/264/.test(x.codec))||j.variants[0];
  v.codec=play.codec;v.size=play.size;
  const el=document.querySelector(`video[data-vi="${i}"]`);if(el)el.src='/proxy?u='+encodeURIComponent(play.url);
  updateVideoMeta(i);
  return j.variants;
}
function updateVideoMeta(i){
  const v=curList()[i],vs=v._vs;if(!vs||!vs.length)return;
  const best=vs[0];
  const m=$('#meta_v'+i),b=$('#badge_v'+i);
  if(m)m.textContent=[v.time||'',fmtCodec(best.codec),fmtSize(best.size)].filter(Boolean).join(' · ');
  if(b&&!best.h)b.textContent='▶ '+(v.width||'?')+'×'+(v.height||'?');
  // 若当前没有转码按钮且编码非H.264，补一个
  const btns=m&&m.parentElement.querySelector('.btns');
  if(btns&&!btns.querySelector('.warn')&&!isIOS&&!/264/.test(best.codec)){
    const w=document.createElement('button');w.className='warn';w.textContent='转码后下载';w.onclick=()=>convItem(i,w);btns.appendChild(w);
  }
}
async function resolveVideos(){const l=curList();for(let i=0;i<l.length;i++){try{await videoVariants(i);}catch(e){const m=$('#meta_v'+i);if(m)m.textContent='解析失败';}}}

// 无损/快速转 H.264：容器不标准优先 -c copy 重封装，编码不兼容才快速转码
async function convItem(i,btn){
  const it=DATA.videos[i];
  const vs=it._vs||await videoVariants(i);
  const best=vs[0];
  btn.disabled=true;const old=btn.textContent;btn.textContent='转换中…';
  try{
    const r=await fetch('/api/convert?u='+encodeURIComponent(best.url)+'&codec='+encodeURIComponent(best.codec||''));
    if(!r.ok){const j=await r.json().catch(()=>({}));throw j.error||('HTTP '+r.status);}
    const b=await r.blob();
    const num=i+1;
    const a=document.createElement('a');a.href=URL.createObjectURL(b);
    a.download='video_'+fnum(num)+'_'+fstamp(it)+'_h264.mp4';
    document.body.appendChild(a);a.click();a.remove();
  }catch(e){alert('转换失败：'+e);}
  btn.disabled=false;btn.textContent=old;
}

async function downloadAll(btn){
  const list=curList();
  if(!list.length)return;
  btn.disabled=true;const old=btn.textContent;btn.textContent='下载中…';
  for(let i=0;i<list.length;i++){
    try{
      if(tab==='image'){
        const u='/proxy?u='+encodeURIComponent(list[i].url);
        const nm='img_'+fnum(i+1)+'_'+fstamp(list[i])+'.'+(list[i].format==='png'?'png':'jpg');
        if(isIOS)await shareSave(u,nm);
        else dl(u,nm);
      }else{
        const vs=await videoVariants(i);
        const best=vs[0];
        const u='/proxy?u='+encodeURIComponent(best.url);
        const nm='video_'+fnum(i+1)+'_'+fstamp(list[i])+'_'+best.h+'p.mp4';
        if(isIOS)await shareSave(u,nm);
        else dl(u,nm);
      }
      if(!isIOS)await new Promise(r=>setTimeout(r,700));
    }catch(e){console.warn(e);}
  }
  btn.disabled=false;btn.textContent=old;
}

/* 大图灯箱：图片/视频统一浏览（预取邻图 + 加载动画） */
let lbToken=0; // 防视频异步解析竞态
function showLb(i){lbIdx=i;updateLb();$('#lb').style.display='flex';}
function hideLb(){$('#lbVid')&&$('#lbVid').pause();$('#lb').style.display='none';}
function lbPlayUrl(it,vs){const play=vs.find(x=>/264/.test(x.codec))||vs[0];return '/proxy?u='+encodeURIComponent(play.url);}
async function updateLb(){
  const items=curList();
  const it=items[lbIdx];
  const img=$('#lbImg'),vid=$('#lbVid');
  $('#lbCnt').textContent=(lbIdx+1)+' / '+items.length;
  $('#lbDlBtn').textContent=it.kind==='video'?'⬇ 下载此视频':'⬇ 下载此图';
  if(it.kind==='video'){
    img.style.display='none';
    vid.style.display='block';
    vid.poster=it.poster?('/proxy?u='+encodeURIComponent(it.poster)):'';
    vid.removeAttribute('src');
    const token=++lbToken;
    try{
      const vs=it._vs||await videoVariants(lbIdx);
      if(token!==lbToken)return; // 用户已切到其他项，放弃本次播放
      vid.src=lbPlayUrl(it,vs);
      vid.play().catch(()=>{});
    }catch(e){}
  }else{
    lbToken++;
    vid.style.display='none';vid.pause&&vid.pause();vid.removeAttribute('src');
    img.style.display='block';
    img.classList.add('loading');
    img.onload=()=>img.classList.remove('loading');
    img.src='/proxy?u='+encodeURIComponent(it.url);
    // 预取左右邻图
    const n=items.length;
    [lbIdx+1,lbIdx-1].forEach(j=>{const p=items[(j+n)%n];if(p.kind==='image'){const im=new Image();im.src='/proxy?u='+encodeURIComponent(p.url);}});
  }
}
function lbNav(d){const n=curList().length;lbIdx=(lbIdx+d+n)%n;updateLb();}
/* 手机滑动切换（灯箱打开时生效） */
let lbTX=0,lbTY=0;
document.addEventListener('touchstart',e=>{
  if($('#lb').style.display!=='flex')return;
  lbTX=e.touches[0].clientX;lbTY=e.touches[0].clientY;
},{passive:true});
document.addEventListener('touchend',e=>{
  if($('#lb').style.display!=='flex')return;
  const dx=e.changedTouches[0].clientX-lbTX,dy=e.changedTouches[0].clientY-lbTY;
  if(Math.abs(dx)>60&&Math.abs(dx)>Math.abs(dy)*1.5)lbNav(dx<0?1:-1);
},{passive:true});
async function lbDl(){
  const it=curList()[lbIdx];
  const num=lbIdx+1;
  if(it.kind==='video'){
    const vs=it._vs||await videoVariants(lbIdx);
    const best=vs[0];
    const nm='video_'+fnum(num)+'_'+fstamp(it)+'_'+best.h+'p.mp4';
    const u='/proxy?u='+encodeURIComponent(best.url);
    if(isIOS){shareSave(u,nm).catch(()=>{});return;}
    dl(u,nm);
  }else{
    const nm='img_'+fnum(num)+'_'+fstamp(it)+'.'+(it.format==='png'?'png':'jpg');
    const u='/proxy?u='+encodeURIComponent(it.url);
    if(isIOS){shareSave(u,nm).catch(()=>{});return;}
    dl(u,nm);
  }
}
document.addEventListener('keydown',e=>{if($('#lb').style.display==='flex'){if(e.key==='Escape')hideLb();if(e.key==='ArrowLeft')lbNav(-1);if(e.key==='ArrowRight')lbNav(1);}});
</script>
</body>
</html>"""


def _guess_type(u):
    low = u.lower().split("?")[0]
    for ext, ct in ((".jpg", "image/jpeg"), (".jpeg", "image/jpeg"), (".png", "image/png"),
                    (".webp", "image/webp"), (".mp4", "video/mp4")):
        if ext in low:
            return ct
    return "application/octet-stream"


def _safe_name(s):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", str(s or "doubao"))[:60]


def _remote_size(u):
    """远端文件大小：先 HEAD，失败退 Range 探测。"""
    try:
        req = urllib.request.Request(u, headers=dict(E.HEADERS), method="HEAD")
        with urllib.request.urlopen(req, timeout=8) as r:
            n = r.headers.get("Content-Length")
            if n:
                return int(n)
    except Exception:
        pass
    try:
        req = urllib.request.Request(u, headers={**E.HEADERS, "Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            cr = r.headers.get("Content-Range") or ""
            if "/" in cr:
                return int(cr.rsplit("/", 1)[1])
    except Exception:
        pass
    return 0


_VV_CACHE = {}   # fallback_api -> variants（进程内缓存，避免重复解密请求）
_SCAN_CACHE = {} # 分享链接 -> 解析结果（scan 秒回；sizes 异步补大小）


def _fetch_all(src, tries=3):
    """带重试的整读：CDN/代理偶发 IncompleteRead / 连接重置时重试。"""
    import http.client
    last = None
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(src, headers=dict(E.HEADERS)), timeout=180) as resp:
                return resp.read()
        except (http.client.IncompleteRead, ConnectionError, urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(1 + k)
    raise last


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # 静默
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _q(self, name):
        return urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get(name, [""])[0]

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/":
                self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/scan":
                self._api_scan()
            elif path == "/api/video":
                self._api_video()
            elif path == "/api/sizes":
                self._api_sizes()
            elif path == "/api/convert":
                self._api_convert()
            elif path == "/api/zip":
                self._api_zip()
            elif path == "/proxy":
                self._proxy()
            elif path == "/favicon.ico":
                self._send(204, b"")
            else:
                self._send(404, b'{"error":"not found"}')
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa: BLE001
            try:
                self._send(500, json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8"))
            except Exception:
                pass

    def _api_scan(self):
        u = self._q("url").strip()
        if "/thread/" not in u:
            self._send(400, json.dumps({"error": "链接需包含 /thread/"}).encode("utf-8"))
            return
        if u not in _SCAN_CACHE:
            _SCAN_CACHE[u] = E.parse_share(u)
        r = _SCAN_CACHE[u]
        images = [{k: it.get(k) for k in ("id", "time", "epoch", "width", "height", "format", "url", "thumb")} | {"kind": "image"} for it in r["images"]]
        videos = [{k: it.get(k) for k in ("id", "time", "epoch", "width", "height", "duration", "poster", "fallback_api")} | {"kind": "video"} for it in r["videos"]]
        slim = {"share_name": r["share_name"], "share_url": r["share_url"],
                "image_count": r["image_count"], "video_count": r["video_count"],
                "images": images, "videos": videos}
        self._send(200, json.dumps(slim, ensure_ascii=False).encode("utf-8"))

    def _api_sizes(self):
        """异步补图片文件大小：复用 scan 缓存，HEAD 并发探测。"""
        u = self._q("url").strip()
        r = _SCAN_CACHE.get(u)
        if not r:
            self._send(404, b'{"error":"scan first"}')
            return
        items = r["images"]

        def _sz(it):
            s = it.get("size")
            if not s:
                s = _remote_size(it["url"])
                it["size"] = s
            return str(it.get("id")), s

        with ThreadPoolExecutor(max_workers=8) as ex:
            pairs = list(ex.map(_sz, items))
        self._send(200, json.dumps({"sizes": dict(pairs)}, ensure_ascii=False).encode("utf-8"))

    def _api_video(self):
        fb = self._q("u").strip()
        if not fb:
            self._send(400, b'{"error":"missing u"}')
            return
        if fb not in _VV_CACHE:
            _VV_CACHE[fb] = E.resolve_video_variants(fb)
        variants = _VV_CACHE[fb]
        # size 字段缺失时补 HEAD
        for v in variants:
            if not v["size"]:
                v["size"] = _remote_size(v["url"])
        self._send(200, json.dumps({"variants": variants}, ensure_ascii=False).encode("utf-8"))

    def _api_convert(self):
        u = self._q("u").strip()
        if not u.startswith(("http://", "https://")):
            self._send(400, b'{"error":"bad url"}')
            return
        ff = shutil.which("ffmpeg")
        if not ff:
            self._send(500, json.dumps({"error": "未找到 ffmpeg，无法转换"}, ensure_ascii=False).encode("utf-8"))
            return
        tmpd = tempfile.mkdtemp(prefix="douconv_")

        def _run(args):
            return subprocess.run(args, capture_output=True, timeout=900)

        def _reencode():
            return _run([ff, "-y", "-i", src, "-c:v", "libx264", "-preset", "veryfast",
                         "-crf", "20", "-c:a", "aac", "-b:a", "128k",
                         "-movflags", "+faststart", dst])

        def _remux():
            return _run([ff, "-y", "-i", src, "-c", "copy", "-movflags", "+faststart", dst])

        def _ok():
            return os.path.exists(dst) and os.path.getsize(dst) > 0

        try:
            src = os.path.join(tmpd, "in.bin")
            dst = os.path.join(tmpd, "out.mp4")
            with urllib.request.urlopen(urllib.request.Request(u, headers=dict(E.HEADERS)), timeout=300) as resp, open(src, "wb") as f:
                shutil.copyfileobj(resp, f, 1 << 20)
            codec = self._q("codec").lower()
            hevc = any(t in codec for t in ("265", "hevc", "bytevc"))
            # H.265/bytevc1：编码本身不兼容，直接快速转 H.264；其余先无损重封装，失败再转码
            r = _reencode() if hevc else _remux()
            if r.returncode != 0 or not _ok():
                if os.path.exists(dst):
                    os.remove(dst)
                r = _reencode() if hevc else _remux()
                if r.returncode != 0 or not _ok():
                    msg = (r.stderr or b"").decode("utf-8", "ignore")[-300:]
                    self._send(500, json.dumps({"error": "ffmpeg 转换失败: " + msg}, ensure_ascii=False).encode("utf-8"))
                    return
            with open(dst, "rb") as f:
                data = f.read()
            fname = urllib.parse.quote("convert_h264.mp4")
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{fname}")
            self.end_headers()
            self.wfile.write(data)
        finally:
            shutil.rmtree(tmpd, ignore_errors=True)

    def _proxy(self):
        u = self._q("u")
        if not u.startswith(("http://", "https://")):
            self._send(400, b'{"error":"bad url"}')
            return
        req = urllib.request.Request(u, headers=dict(E.HEADERS))
        rng = self.headers.get("Range")
        if rng:
            req.add_header("Range", rng)
        with urllib.request.urlopen(req, timeout=120) as resp:
            code = resp.status
            headers = {"Content-Type": resp.headers.get("Content-Type") or _guess_type(u),
                       "Accept-Ranges": "bytes",
                       "Cache-Control": "public, max-age=86400"}
            if resp.headers.get("Content-Length"):
                headers["Content-Length"] = resp.headers["Content-Length"]
            if resp.headers.get("Content-Range"):
                headers["Content-Range"] = resp.headers["Content-Range"]
            self.send_response(code)
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def _api_zip(self):
        share_url = self._q("url").strip()
        typ = self._q("type") or "image"
        if "/thread/" not in share_url:
            self._send(400, b'{"error":"bad url"}')
            return
        r = E.parse_share(share_url)
        items = r["images"] if typ == "image" else r["videos"]
        if typ == "video":
            items = [dict(it, _u=(E.resolve_video_variants(it["fallback_api"]) or [{}])[0].get("url")) for it in items]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
            for i, it in enumerate(items, 1):
                src = it["url"] if typ == "image" else it["_u"]
                if not src:
                    continue
                ext = (it.get("format") or "jpg") if typ == "image" else "mp4"
                name = f"{i:03d}_{(it.get('time') or '').replace('-','').replace(':','').replace(' ','_')}_{typ}_{it.get('id')}.{ext}"
                z.writestr(name, _fetch_all(src))
        data = buf.getvalue()
        fname = urllib.parse.quote(f"{_safe_name(r['share_name'])}_{typ}.zip")
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{fname}")
        self.end_headers()
        self.wfile.write(data)


def main():
    # 云端部署时平台注入 PORT 并要求监听 0.0.0.0；本地无 PORT 环境变量时保持 127.0.0.1:8765
    port = int(os.environ.get("PORT") or (sys.argv[1] if len(sys.argv) > 1 else 8765))
    host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"豆包解析: http://{host}:{port}  (Ctrl+C 退出)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
