"""Client script for the vidmill studio editor (part 1)."""

SCRIPT_A = r"""
var S={job:null,status:null,assets:[],timeline:null,filter:"all",search:"",preview:null,
  timer:null,aiTimer:null,jobsTimer:null,optsLoaded:false,zoom:0,lastSrc:"",artSig:"",
  aiPending:false,chat:{},dragTl:false,logText:"",aiSkills:[],skills:[],skill:null,
  skillDirs:{}};

function $(s,r){return (r||document).querySelector(s)}
function $$(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))}
function enc(s){return encodeURIComponent(s)}
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){
  return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function clamp(n,a,b){return Math.max(a,Math.min(b,n))}
function fmtClock(s){if(s==null||isNaN(s))return "—";s=Math.max(0,s);var m=Math.floor(s/60),
  x=Math.floor(s%60);return m+":"+(x<10?"0":"")+x}
function fmtTC(s,fps){s=Math.max(0,s||0);fps=Math.max(1,Math.round(fps||30));
  var f=Math.floor((s-Math.floor(s))*fps),t=Math.floor(s),h=Math.floor(t/3600),
  m=Math.floor(t%3600/60),x=t%60;
  function p(n){return (n<10?"0":"")+n}
  return p(h)+":"+p(m)+":"+p(x)+":"+p(f)}
function fmtBytes(n){if(!n)return "—";var u=["B","KB","MB","GB"],i=0;
  while(n>=1024&&i<u.length-1){n/=1024;i++}return n.toFixed(i?1:0)+" "+u[i]}
function fmtDate(s){if(!s)return "—";var d=new Date(s);if(isNaN(d))return String(s).slice(0,16);
  return d.toLocaleDateString(undefined,{month:"short",day:"numeric"})+" "+
  d.toLocaleTimeString(undefined,{hour:"2-digit",minute:"2-digit"})}
function kindLabel(k){return {video:"Video",audio:"Audio",image:"Image"}[k]||"File"}
function assetByName(n){for(var i=0;i<S.assets.length;i++)if(S.assets[i].name===n)return S.assets[i];return null}
function currentName(){return S.status&&S.status.video?S.status.video:(S.status&&S.status.current||null)}

function toast(text,kind){
  var el=document.createElement("div");el.className="toast "+(kind||"");
  el.textContent=text;$("#toasts").appendChild(el);
  setTimeout(function(){el.style.opacity="0";el.style.transition="opacity .25s";
    setTimeout(function(){el.remove()},260)},3800);
}
async function api(path,opts){
  opts=opts||{};var r=await fetch(path,opts),t=await r.text(),d={};
  try{d=t?JSON.parse(t):{}}catch(e){d={raw:t}}
  if(!r.ok)throw new Error(d.error||("HTTP "+r.status));
  return d;
}

/* ------------------------------------------------------------- top state */
function setChrome(state,text){
  var map={run:"run",ok:"ok",err:"err",idle:""};
  $("#topDot").className="dot "+(map[state]||"");
  $("#topStateText").textContent=text;
  $("#chipDot").className="dot "+(map[state]||"");
  $("#chipText").textContent=text;
}
function stateOf(s){
  if(!s)return ["idle","idle"];
  if(s.running)return ["run","editing"];
  if(s.ai_running)return ["run","AI editing"];
  if(s.finished)return ["ok","ready"];
  if(s.video)return ["ok","partial"];
  return ["idle","waiting"];
}

/* ---------------------------------------------------------- project list */
async function refreshJobList(){
  try{
    var jobs=await api("/api/jobs");S.jobs=jobs;
    var el=$("#projectList");el.innerHTML="";
    $("#projectCount").textContent=jobs.length;
    if(!jobs.length){el.innerHTML='<div class="bin-empty" style="margin:4px">No projects yet.</div>';return}
    jobs.forEach(function(j){
      var row=document.createElement("div");row.className="prow"+(j.name===S.job?" sel":"");
      var dot=document.createElement("i");dot.className="dot "+((j.running||j.ai_running)?"run":(j.finished?"ok":""));
      var n=document.createElement("span");n.className="pn";n.textContent=j.name;
      var m=document.createElement("span");m.className="pm";m.textContent=(j.duration?fmtClock(j.duration):"—");
      row.appendChild(dot);row.appendChild(n);row.appendChild(m);
      row.title=j.name;j.rowclick=function(){openJob(j.name)};
      row.onclick=function(){openJob(j.name)};
      el.appendChild(row);
    });
  }catch(e){}
}

/* ------------------------------------------------------------- media bin */
function renderAssets(){
  var grid=$("#assetGrid");grid.innerHTML="";
  var q=(S.search||"").toLowerCase();
  var list=S.assets.filter(function(a){
    if(S.filter!=="all"&&a.kind!==S.filter)return false;
    if(q&&a.name.toLowerCase().indexOf(q)<0)return false;
    return true;
  });
  $("#assetCount").textContent=S.assets.length;
  $("#binEmpty").classList.toggle("hidden",list.length>0||!S.job);
  var cur=currentName();
  list.forEach(function(a){
    var b=document.createElement("button");b.className="asset"+(a.name===(S.preview||cur)?" sel":"");
    b.title=a.name;b.setAttribute("data-name",a.name);
    var badge="",bcls="asset";
    if(a.current||a.name===cur){badge="CUR";bcls="cur"}
    else if(a.source){badge="SRC";bcls="src"}
    else if(a.artifact){badge="OUT";bcls="out"}
    var dur=a.duration?('<span class="dur">'+fmtClock(a.duration)+"</span>"):"";
    var thumb=a.thumb||"";
    var ab=badge?('<span class="ab '+bcls+'">'+badge+"</span>"):"";
    b.innerHTML='<div class="athumb" style="background-image:url('+"'"+thumb+"'"+')">'+ab+dur+
      '</div><div class="aname">'+esc(a.name)+'</div><div class="ameta">'+kindLabel(a.kind)+" · "+
      fmtBytes(a.bytes)+"</div>";
    b.onclick=function(){previewAsset(a.name)};
    grid.appendChild(b);
  });
}
async function refreshAssets(){
  if(!S.job){S.assets=[];renderAssets();return}
  try{var d=await api("/api/jobs/"+enc(S.job)+"/assets");S.assets=d.assets||[];renderAssets();syncMonitor()}
  catch(e){}
}
function previewAsset(name){
  var a=assetByName(name);if(!a)return;
  S.preview=name;showScreen();renderAssets();
  loadSource(name);
  $("#previewFlag").classList.remove("hidden");
  $("#previewName").textContent="Preview · "+name;
  var v=$("#monitor");if(v){try{v.currentTime=0}catch(e){}updateTimeUI(0,v.duration||0)}
}
function useCurrent(){
  S.preview=null;renderAssets();$("#previewFlag").classList.add("hidden");
  if(S.status&&S.status.video){loadSource(S.status.video);return}
  S.lastSrc="";syncMonitor();
  if(!sourceAsset())clearMonitor();
}
function showScreen(){$("#emptyStage").classList.add("hidden");$("#screen").classList.remove("hidden")}
function clearExport(){
  var a=$("#btnExport");a.removeAttribute("href");a.removeAttribute("download");
  a.style.opacity=".45";a.style.pointerEvents="none";$("#btnDownload").disabled=true;
}
function setExport(name){
  if(!S.job||!name)return;
  var src="/media/"+enc(S.job)+"/"+enc(name);
  var a=$("#btnExport");a.href=src;a.setAttribute("download",name);
  a.style.opacity="";a.style.pointerEvents="";$("#btnDownload").disabled=false;
}
function clearMonitor(){
  $("#screen").classList.add("hidden");$("#emptyStage").classList.remove("hidden");
  var v=$("#monitor");v.pause&&v.pause();v.removeAttribute("src");v.load&&v.load();
  $("#monName").textContent="No clip";
}
function sourceAsset(){
  for(var i=0;i<S.assets.length;i++)if(S.assets[i].source)return S.assets[i];
  return null;
}
function syncMonitor(){
  if(!S.status||S.preview)return;
  var name=S.status.video;
  if(!name){var sa=sourceAsset();name=sa&&sa.name}
  if(name)loadSource(name);
}
function loadSource(name){
  if(!S.job||!name)return;
  var a=assetByName(name)||{};
  var src=a.url||("/media/"+enc(S.job)+"/"+enc(name));
  if(S.lastSrc!==src){
    S.lastSrc=src;var v=$("#monitor");v.setAttribute("src",src);v.load&&v.load();
    $("#monName").textContent=name;
    var sourceMode=!!S.preview||!!(S.status&&!S.status.video);
    $("#monMode").textContent=sourceMode?"Source":"Program";
    var fps=a.fps||(S.status&&S.status.fps);
    var hasAudio=(a.has_audio!==undefined)?a.has_audio:(S.status&&S.status.has_audio);
    $("#tagRes").textContent=(a.width||(S.status&&S.status.width)||0)+"×"+
      (a.height||(S.status&&S.status.height)||0);
    $("#tagFps").textContent=fps?(Math.round(fps*100)/100+" fps"):"—";
    $("#tagAudio").textContent=hasAudio===false?"no audio":"audio";
  }
}

/* ------------------------------------------------------------- inspector */
function renderInspector(s){
  var i=s||{};
  $("#jobTitle").textContent=S.job||"No project";
  $("#insSource").textContent=i.source||"—";
  $("#insRes").textContent=(i.width||"?")+" × "+(i.height||"?");
  $("#insFps").textContent=i.fps?(Math.round(i.fps*100)/100+" fps"):"—";
  $("#insDur").textContent=i.duration?fmtTC(i.duration,i.fps||30):"—";
  $("#insSeq").textContent=(i.current&&i.current.duration)?fmtTC(i.current.duration,i.fps||30):"—";
  $("#insSize").textContent=i.size_bytes?fmtBytes(i.size_bytes):"—";
  $("#insCreated").textContent=i.created?fmtDate(i.created):"—";
  $("#insOut").textContent=i.video||"—";
  $("#insBadge").textContent=i.video?"READY":"SETUP";
  $("#tagRes").textContent=(i.width||0)+"×"+(i.height||0);
  $("#tagFps").textContent=i.fps?Math.round(i.fps*100)/100+" fps":"—";
  $("#tagAudio").textContent=i.has_audio===false?"no audio":"audio";
  $("#tlDur").textContent=i.duration?fmtClock(i.duration):"—";
  $("#tlName").textContent=i.video||"no sequence";
  var t=$("#tcTot");if(t)t.textContent=fmtTC(i.duration||0,i.fps||30);
}
function renderLog(text){
  S.logText=text||"";
  var el=$("#log"),stick=el.scrollTop+el.clientHeight>=el.scrollHeight-40;
  el.textContent=S.logText||"No activity yet — start the free pass or ask the AI to see tool output.";
  if(stick)el.scrollTop=el.scrollHeight;
  $("#actSize").textContent=S.logText?fmtBytes(S.logText.length)+" log":"";
}

/* ----------------------------------------------------------------- poll */
async function poll(){
  if(!S.job)return;
  try{
    var s=await api("/api/jobs/"+enc(S.job));S.status=s;
    var st=stateOf(s);setChrome(st[0],st[1]);
    renderInspector(s);
    $("#run").disabled=s.running||s.ai_running;
    $("#cancelRun").disabled=!(s.running||s.ai_running);
    $("#btnCancelRun").disabled=!(s.running||s.ai_running);
    $("#aiSend").disabled=s.running||s.ai_running||!s.ai_available;
    $("#btnRestart").disabled=s.running||s.ai_running;
    $("#insBadge").textContent=s.running?"EDITING":(s.video?"READY":"SETUP");
    $("#actLive").textContent=s.running?"editing":(s.ai_running?"AI editing":(s.finished?"ready":"idle"));
    if(!S.optsLoaded&&s.opts){writeOpts("d_",s.opts);S.optsLoaded=true}
    var keyHint=$("#aiKeyHint"),foot=$("#aiHint"),model=$("#aiModel"),dot=$("#aiDot");
    if(!s.ai_available){
      dot.className="dot err";model.textContent="no key configured";
      keyHint.textContent="Set VIDMILL_AI_KEY to enable";
      foot.innerHTML="AI editing needs <b>VIDMILL_AI_KEY</b> (or <b>OPENAI_API_KEY</b>) in the server environment. The free pass never needs it.";
    }else if(s.running){
      dot.className="dot run";model.textContent=s.ai_model||"ready";
      keyHint.textContent="Free pass is running";foot.innerHTML="The AI waits for the free pass to finish so the two edits never race.";
    }else{
      dot.className="dot ok";model.textContent=s.ai_model||"connected";
      keyHint.textContent="Optional · only runs when you ask";
      foot.innerHTML="The free pass is deterministic and local. AI edits are optional and send only text and tool results.";
    }
    syncMonitor();
    if(s.video)setExport(s.video);else clearExport();
    var sig=(s.video||"")+"|"+s.artifacts.length;
    if(sig!==S.artSig){S.artSig=sig;refreshAssets();loadTimeline()}
    try{var l=await api("/api/jobs/"+enc(S.job)+"/log");renderLog(l.text||"")}catch(e){}
    var v=$("#monitor");if(v&&v.duration&&!isNaN(v.duration))updateTimeUI(v.currentTime,v.duration);
    if(s.ai_running&&!S.aiTimer)pollAI();
  }catch(e){
    setChrome("err","offline");$("#chipText").textContent=String(e.message||e);
  }
}

/* --------------------------------------------------------------- monitor */
function updateTimeUI(cur,total){
  var fps=(S.status&&S.status.fps)||30;
  $("#tcCur").textContent=fmtTC(cur,fps);
  if(total&&isFinite(total))$("#tcTot").textContent=fmtTC(total,fps);
  if(total&&isFinite(total))$("#progress").value=Math.round(clamp(cur/total,0,1)*1000);
  var ph=$("#playhead");
  if(ph&&!ph.classList.contains("hidden")&&total&&S.timeline){
    var d=S.timeline.duration||total;
    ph.style.left=(clamp(cur/d,0,1)*100)+"%";
  }
}
function togglePlay(){
  var v=$("#monitor");if(!v||!v.getAttribute("src"))return;
  if(v.paused){v.play().catch(function(){})}else{v.pause()}
}
function stepFrame(dir){
  var v=$("#monitor");if(!v)return;var fps=(S.status&&S.status.fps)||30;
  v.pause();v.currentTime=clamp((v.currentTime||0)+dir/fps,0,v.duration||0);
  updateTimeUI(v.currentTime,v.duration);
}
function bindMonitor(){
  var v=$("#monitor");
  v.addEventListener("timeupdate",function(){updateTimeUI(v.currentTime,v.duration)});
  v.addEventListener("loadedmetadata",function(){
    updateTimeUI(0,v.duration);
    if(S.preview||!S.timeline)return;
  });
  v.addEventListener("play",function(){$("#btnPlay").innerHTML='<svg class="icon"><use href="#i-pause"/></svg>'});
  v.addEventListener("pause",function(){$("#btnPlay").innerHTML='<svg class="icon"><use href="#i-play"/></svg>'});
  v.addEventListener("ended",function(){$("#btnPlay").innerHTML='<svg class="icon"><use href="#i-play"/></svg>'});
  v.addEventListener("click",togglePlay);
  $("#btnPlay").onclick=togglePlay;
  $("#btnBackFrame").onclick=function(){stepFrame(-1)};
  $("#btnFwdFrame").onclick=function(){stepFrame(1)};
  $("#progress").addEventListener("input",function(){
    var d=v.duration||0;if(!d)return;v.currentTime=d*(this.value/1000);updateTimeUI(v.currentTime,d);
  });
  $("#vol").addEventListener("input",function(){v.volume=this.value/100;v.muted=this.value==0});
  $("#btnMute").onclick=function(){
    v.muted=!v.muted;this.innerHTML='<svg class="icon"><use href="#i-'+(v.muted?"mute":"vol")+'"/></svg>';
    $("#vol").value=v.muted?0:100;
  };
  $("#btnFit").onclick=function(){
    var sc=$("#screen");sc.classList.toggle("cover");
    this.style.color=sc.classList.contains("cover")?"var(--acc2)":"";
  };
  $("#btnFullscreen").onclick=function(){
    var el=$("#screen");
    if(document.fullscreenElement){document.exitFullscreen()}
    else if(el.requestFullscreen){el.requestFullscreen()}
  };
  $("#btnDownload").onclick=function(){var a=$("#btnExport");if(a&&a.getAttribute("href"))a.click()};
  $("#btnUseCurrent").onclick=useCurrent;
}
"""
