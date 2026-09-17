#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doubao-web：豆包解析结果本地展示服务（jiagev 风格 + 批量下载）

用法:
    python doubao_web.py [端口]        # 默认 8765，浏览器打开 http://127.0.0.1:8765

页面布局（按用户交互稿）：
  顶部：解析网址输入框 + 右侧「解析」按钮（兼刷新）
  选项卡：左「图片」右「视频」，手动切换，默认图片，没有内容就空白
  右上角：「一键下载」（手机端逐个触发保存，存相册）
  每张图下方「下载」按钮，直接下载无弹窗；点图片看大图，大图里可挨个下载

纯标准库实现。/proxy 反代豆包 CDN（跨域 + Range 拖动）。
"""
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doubao_engine as E  # noqa: E402

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>豆包解析 · 本地结果</title>
<style>
:root{--bg:#f5f6f8;--card:#fff;--ink:#1c1e21;--sub:#65676b;--line:#e4e6eb;--acc:#3b82f6;--ok:#16a34a}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;padding:14px}
.wrap{max-width:1200px;margin:0 auto}
.bar{display:flex;gap:8px;margin-bottom:12px}
.bar input{flex:1;border:1px solid var(--line);border-radius:8px;padding:9px 12px;font-size:13px;background:#fff}
.bar button{white-space:nowrap}
button{border:0;border-radius:8px;padding:8px 14px;font-size:13px;cursor:pointer;background:var(--acc);color:#fff}
button.gray{background:#e4e6eb;color:var(--ink)}
button.ok{background:var(--ok)}
button:disabled{opacity:.5;cursor:wait}
.tabs{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.tab{padding:7px 18px;border-radius:20px;background:#e4e6eb;color:var(--sub);cursor:pointer;font-size:13px;user-select:none}
.tab.on{background:var(--acc);color:#fff}
.tabs .sp{flex:1}
.tip{background:#fff8e6;border:1px solid #ffe9b3;color:#8a6d1a;border-radius:8px;padding:8px 12px;font-size:12px;margin-bottom:12px;display:none}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.card .media{position:relative;background:#000;height:200px;display:flex;align-items:center;justify-content:center;overflow:hidden}
.card img{max-width:100%;max-height:100%;object-fit:contain;cursor:zoom-in}
.card video{max-width:100%;max-height:100%}
.badge{position:absolute;top:6px;left:6px;background:rgba(0,0,0,.6);color:#fff;font-size:11px;border-radius:6px;padding:1px 7px}
.card .meta{padding:6px 10px 2px;font-size:11px;color:var(--sub);overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.card .btns{padding:6px 10px 10px;display:flex}
.card .btns button{flex:1;padding:6px 0;font-size:12px}
.empty{min-height:200px}
#lb{position:fixed;inset:0;background:rgba(0,0,0,.92);display:none;flex-direction:column;align-items:center;justify-content:center;z-index:99}
#lb img{max-width:94vw;max-height:78vh;object-fit:contain}
#lb .lbbar{display:flex;gap:10px;margin-top:14px;align-items:center}
#lb .lbbar button{font-size:14px;padding:9px 18px}
#lb .close{position:absolute;top:12px;right:14px;background:rgba(255,255,255,.15);font-size:20px;width:40px;height:40px;padding:0;border-radius:50%}
#lb .nav{position:absolute;top:50%;transform:translateY(-50%);background:rgba(255,255,255,.15);font-size:22px;width:46px;height:46px;padding:0;border-radius:50%}
#lb .prev{left:10px}#lb .next{right:10px}
#lb .cnt{color:#fff;font-size:12px;margin-top:8px}
@media(max-width:600px){.grid{grid-template-columns:repeat(2,1fr)}.card .media{height:150px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="bar">
    <input id="url" placeholder="https://www.doubao.com/thread/...">
    <button onclick="doParse()">解析</button>
  </div>
  <div class="tip" id="iosTip">📱 iOS：点下载后画面会在新标签打开——长按 →「存储到相册 / 存储视频」。</div>
  <div id="main"></div>
</div>
<div id="lb" onclick="if(event.target===this)hideLb()">
  <button class="close" onclick="hideLb()">×</button>
  <button class="nav prev" onclick="lbNav(-1)">‹</button>
  <img id="lbImg" alt="">
  <button class="nav next" onclick="lbNav(1)">›</button>
  <div class="lbbar"><button class="ok" onclick="lbDl()">⬇ 下载此图</button></div>
  <div class="cnt" id="lbCnt"></div>
</div>
<script>
const isIOS=/iPad|iPhone|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
let DATA=null,tab='image',lbIdx=0;
const $=s=>document.querySelector(s);
if(isIOS)$('#iosTip').style.display='block';
window.addEventListener('DOMContentLoaded',()=>{
  const q=new URLSearchParams(location.search);
  const qu=q.get('url');
  const qt=q.get('tab');
  if(qu&&qu.includes('/thread/')){
    if(qt==='video')tab='video';
    $('#url').value=qu;doParse();
  }
});

async function doParse(){
  const u=$('#url').value.trim();
  if(!u.includes('/thread/')){alert('链接需包含 /thread/');return;}
  $('#main').innerHTML='';
  try{
    const r=await fetch('/api/scan?url='+encodeURIComponent(u));
    DATA=await r.json();
    if(DATA.error){alert('解析失败：'+DATA.error);return;}
    render();
  }catch(e){alert('解析失败：'+e);}
}

function render(){
  const imgs=DATA.images||[],vids=DATA.videos||[];
  const list=tab==='image'?imgs:vids;
  const cards=list.map((it,i)=>{
    let media;
    if(it.kind==='image'){
      media=`<img loading="lazy" src="/proxy?u=${encodeURIComponent(it.thumb||it.url)}" onclick="showLb(${i})">`;
    }else{
      media=`<video controls preload="none" playsinline poster="/proxy?u=${encodeURIComponent(it.poster||'')}" data-vi="${i}" src=""></video>`;
    }
    const dur=it.duration?(it.duration<60?it.duration.toFixed(0)+'s':(it.duration/60).toFixed(1)+'min'):'';
    const badge=it.kind==='image'?`${it.width}×${it.height}`:`▶${dur?' '+dur:''} ${it.width}×${it.height}`;
    return `<div class="card"><div class="media">${media}<span class="badge">${badge}</span></div>
      <div class="meta">${(it.prompt||'').replace(/</g,'&lt;')}</div>
      <div class="btns"><button onclick="dlItem('${tab[0]}${i}')">⬇ 下载</button></div></div>`;
  }).join('');
  $('#main').innerHTML=`
    <div class="tabs">
      <div class="tab ${tab==='image'?'on':''}" onclick="setTab('image')">图片 ${imgs.length}</div>
      <div class="tab ${tab==='video'?'on':''}" onclick="setTab('video')">视频 ${vids.length}</div>
      <div class="sp"></div>
      <button class="ok" id="btnAll" onclick="downloadAll(this)">一键下载</button>
    </div>
    <div class="${list.length?'grid':'empty'}">${cards}</div>`;
  if(tab==='video')resolveVideos();
}
function setTab(t){tab=t;render();}

// 稳定下标：'i'+图片序号 / 'v'+视频序号
async function dlItem(idx){
  const isImg=idx[0]==='i';
  const k=+idx.slice(1);
  const it=isImg?DATA.images[k]:DATA.videos[k];
  const num=k+1;
  const name=(isImg?'img_':'video_')+String(num).padStart(2,'0')+'_'+(it.id||'')+(isImg?'.'+(it.format==='png'?'png':'jpg'):'.mp4');
  try{
    const u=isImg?'/proxy?u='+encodeURIComponent(it.url):await videoUrl(k);
    if(isIOS){window.open(u,'_blank');return;}
    dl(u,name);
  }catch(e){alert('下载失败：'+e);}
}
function dl(u,name){fetch(u).then(r=>r.blob()).then(b=>{const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=name;document.body.appendChild(a);a.click();a.remove();});}

async function videoUrl(i){
  const v=DATA.videos[i];
  if(v._url)return v._url;
  const r=await fetch('/api/video?u='+encodeURIComponent(v.fallback_api));
  const j=await r.json();
  if(!j.url)throw j.error||'未知错误';
  v._url=j.url;
  const el=document.querySelector(`video[data-vi="${i}"]`);if(el)el.src='/proxy?u='+encodeURIComponent(j.url);
  return j.url;
}
async function resolveVideos(){for(let i=0;i<DATA.videos.length;i++){try{await videoUrl(i);}catch(e){}}}

async function downloadAll(btn){
  const list=tab==='image'?DATA.images:DATA.videos;
  if(!list.length)return;
  btn.disabled=true;const old=btn.textContent;btn.textContent='下载中…';
  for(let i=0;i<list.length;i++){
    try{
      if(tab==='image'){
        const u='/proxy?u='+encodeURIComponent(list[i].url);
        if(isIOS)window.open(u,'_blank');
        else dl(u,'img_'+String(i+1).padStart(2,'0')+'.'+(list[i].format==='png'?'png':'jpg'));
      }else{
        const u=await videoUrl(i);
        if(isIOS)window.open(u,'_blank');
        else dl(u,'video_'+String(i+1).padStart(2,'0')+'.mp4');
      }
      await new Promise(r=>setTimeout(r,700));
    }catch(e){console.warn(e);}
  }
  btn.disabled=false;btn.textContent=old;
}

/* 大图灯箱 */
function showLb(i){lbIdx=i;updateLb();$('#lb').style.display='flex';}
function hideLb(){$('#lb').style.display='none';}
function updateLb(){
  const it=DATA.images[lbIdx];
  $('#lbImg').src='/proxy?u='+encodeURIComponent(it.url);
  $('#lbCnt').textContent=(lbIdx+1)+' / '+DATA.images.length;
}
function lbNav(d){const n=DATA.images.length;lbIdx=(lbIdx+d+n)%n;updateLb();}
function lbDl(){const it=DATA.images[lbIdx];dl('/proxy?u='+encodeURIComponent(it.url),'img_'+String(lbIdx+1).padStart(2,'0')+'.'+(it.format==='png'?'png':'jpg'));}
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
        r = E.parse_share(u)
        slim = {"share_name": r["share_name"], "share_url": r["share_url"],
                "image_count": r["image_count"], "video_count": r["video_count"],
                "images": [{k: it.get(k) for k in ("id", "time", "width", "height", "format", "prompt", "url", "thumb")} | {"kind": "image"} for it in r["images"]],
                "videos": [{k: it.get(k) for k in ("id", "time", "width", "height", "duration", "prompt", "poster", "fallback_api")} | {"kind": "video"} for it in r["videos"]]}
        self._send(200, json.dumps(slim, ensure_ascii=False).encode("utf-8"))

    def _api_video(self):
        fb = self._q("u").strip()
        if not fb:
            self._send(400, b'{"error":"missing u"}')
            return
        url, _v = E.resolve_video_url({"fallback_api": fb}, prefer_h264=True)
        self._send(200, json.dumps({"url": url}, ensure_ascii=False).encode("utf-8"))

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
                       "Accept-Ranges": "bytes"}
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
            items = [dict(it, _u=E.resolve_video_url(it, prefer_h264=True)[0]) for it in items]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
            for i, it in enumerate(items, 1):
                src = it["url"] if typ == "image" else it["_u"]
                if not src:
                    continue
                ext = (it.get("format") or "jpg") if typ == "image" else "mp4"
                name = f"{i:03d}_{(it.get('time') or '').replace('-','').replace(':','').replace(' ','_')}_{typ}_{it.get('id')}.{ext}"
                with urllib.request.urlopen(urllib.request.Request(src, headers=dict(E.HEADERS)), timeout=180) as resp:
                    z.writestr(name, resp.read())
        data = buf.getvalue()
        fname = urllib.parse.quote(f"{_safe_name(r['share_name'])}_{typ}.zip")
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{fname}")
        self.end_headers()
        self.wfile.write(data)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"豆包解析本地展示: http://127.0.0.1:{port}  (Ctrl+C 退出)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
