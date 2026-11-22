"""Client script for the vidmill studio editor (part 2)."""

SCRIPT_B = r"""
/* -------------------------------------------------------------- timeline */
function timelinePx(){
  if(!S.timeline)return 100;
  var dur=S.timeline.duration||1;
  var avail=Math.max(240,($("#tlScroll").clientWidth||800)-2);
  var fit=avail/dur;
  return Math.max(S.zoom||fit,fit);
}
function setZoom(z){
  S.zoom=clamp(z,20,420);$("#zoom").value=Math.round(S.zoom);renderTimeline();
}
function zoomFit(){
  if(!S.timeline)return;
  var dur=S.timeline.duration||1;
  var avail=Math.max(240,($("#tlScroll").clientWidth||800)-2);
  S.zoom=clamp(avail/dur,20,420);$("#zoom").value=Math.round(S.zoom);renderTimeline();
}
function rulerText(t,step){
  if(step<1){var m=Math.floor(t/60),s=t%60;return m+":"+(s<10?"0":"")+s.toFixed(1)}
  if(step>=120)return Math.round(t/60)+"m";
  return fmtClock(t);
}
function clearTrack(el){if(el)el.innerHTML=""}
function renderTimeline(){
  var T=S.timeline,dur=T?(T.duration||0):0;
  var inner=$("#tlInner"),ruler=$("#ruler"),ph=$("#playhead");
  ["trVideo","trOverlay","trCaptions","trAudio"].forEach(function(id){clearTrack($("#"+id))});
  if(!T||!dur){
    inner.style.width="100%";ruler.innerHTML="";ph.classList.add("hidden");
    $("#tlHint").classList.remove("hidden");$("#tlHint").textContent="Open a project to see its timeline";
    $("#tlDur").textContent="—";$("#tlName").textContent="no sequence";
    inner.querySelectorAll(".seg").forEach(function(n){n.remove()});
    return;
  }
  var avail=Math.max(240,($("#tlScroll").clientWidth||800)-2);
  var fit=avail/dur;
  var px=Math.max(S.zoom||fit,fit);S.px=px;
  inner.style.width=Math.max(avail,Math.ceil(dur*px))+"px";
  $("#tlHint").classList.add("hidden");
  $("#tlDur").textContent=fmtClock(dur);
  $("#tlName").textContent=T.video||"source";

  /* ruler */
  ruler.innerHTML="";
  var steps=[0.1,0.2,0.5,1,2,5,10,15,30,60,120,300,600];
  var major=steps[steps.length-1];
  for(var i=0;i<steps.length;i++){if(steps[i]*px>=62){major=steps[i];break}}
  var minor=major/4;
  var count=Math.floor(dur/minor);
  for(var j=0;j<=count;j++){
    var t=j*minor,isMajor=(j%4===0);
    if(t>dur+0.001)break;
    var tick=document.createElement("div");
    tick.className="tick"+(isMajor?"":" minor");
    tick.style.left=(t/dur*100)+"%";
    if(isMajor){var lab=document.createElement("span");lab.textContent=rulerText(t,major);tick.appendChild(lab)}
    ruler.appendChild(tick);
  }

  /* video segments */
  var segs=(T.segments&&T.segments.length)?T.segments:[{start:0,end:dur,label:"Source",kind:"main"}];
  segs.forEach(function(sg){
    var a=clamp(sg.start||0,0,dur),b=clamp(sg.end||dur,0,dur);
    if(b<=a)return;
    var d=document.createElement("div");d.className="seg "+(sg.kind||"main");
    d.style.left=(a/dur*100)+"%";d.style.width=((b-a)/dur*100)+"%";
    d.title=(sg.label||"Clip")+"  "+fmtClock(a)+" – "+fmtClock(b);
    var sp=document.createElement("span");sp.textContent=sg.label||"Clip";d.appendChild(sp);
    $("#trVideo").appendChild(d);
  });

  /* overlays */
  var ovs=T.overlays||[];
  ovs.forEach(function(ov){
    var a=clamp(ov.start||0,0,dur),b=clamp(ov.end==null?dur:ov.end,0,dur);
    if(b<=a)return;
    var d=document.createElement("div");d.className="seg overlay";
    d.style.left=(a/dur*100)+"%";d.style.width=((b-a)/dur*100)+"%";
    d.title=(ov.label||ov.kind||"overlay")+"  "+fmtClock(a)+" – "+fmtClock(b);
    var sp=document.createElement("span");sp.textContent=(ov.kind==="video"?"▣ ":"◇ ")+(ov.label||ov.kind||"overlay");
    d.appendChild(sp);$("#trOverlay").appendChild(d);
  });

  /* captions */
  if(T.captions&&T.captions.end>T.captions.start){
    var c=T.captions,a=clamp(c.start,0,dur),b=clamp(c.end,0,dur);
    var d=document.createElement("div");d.className="seg caption";
    d.style.left=(a/dur*100)+"%";d.style.width=((b-a)/dur*100)+"%";
    d.title="Captions"+(c.count?" · "+c.count+" lines":"");
    var sp=document.createElement("span");sp.textContent="CC"+(c.count?" · "+c.count+(c.count===1?" line":" lines"):"");
    d.appendChild(sp);$("#trCaptions").appendChild(d);
  }

  /* audio */
  if(T.audio&&T.audio.waveform){
    var img=document.createElement("img");img.className="audio-img";img.alt="";
    img.src=T.audio.waveform;
    $("#trAudio").appendChild(img);
  }else{
    var e=document.createElement("div");e.className="audio-empty";
    e.textContent=T.audio&&T.audio.present?"audio · waveform unavailable":"no audio track";
    $("#trAudio").appendChild(e);
  }

  /* playhead */
  ph.classList.remove("hidden");
  var v=$("#monitor"),cur=(v&&v.currentTime)||0;
  ph.style.left=(clamp(cur/dur,0,1)*100)+"%";
  updateTimeUI(cur,v?v.duration||dur:dur);
}

function seekSequence(t){
  if(!S.timeline)return;
  t=clamp(t,0,S.timeline.duration||0);
  if(S.preview)useCurrent();
  var v=$("#monitor");
  if(v&&v.duration&&isFinite(v.duration)&&v.duration>0){
    v.currentTime=clamp(t,0,v.duration);updateTimeUI(v.currentTime,v.duration);
  }else{S.pendingSeek=t;updateTimeUI(t,S.timeline.duration)}
}
function seekFromEvent(e){
  var rr=$("#ruler").getBoundingClientRect();
  var px=S.px||timelinePx(),dur=S.timeline?S.timeline.duration:0;
  if(!dur)return;
  seekSequence(clamp((e.clientX-rr.left)/px,0,dur));
}
function bindTimeline(){
  var inner=$("#tlInner");
  inner.addEventListener("pointerdown",function(e){
    if(e.button!==0||!S.timeline)return;
    S.dragTl=true;
    try{inner.setPointerCapture(e.pointerId)}catch(x){}
    seekFromEvent(e);
  });
  inner.addEventListener("pointermove",function(e){if(S.dragTl)seekFromEvent(e)});
  ["pointerup","pointercancel"].forEach(function(ev){
    inner.addEventListener(ev,function(e){
      S.dragTl=false;try{inner.releasePointerCapture(e.pointerId)}catch(x){}
    });
  });
  $("#zoom").addEventListener("input",function(){S.zoom=+this.value;renderTimeline()});
  $("#btnZoomIn").onclick=function(){setZoom(timelinePx()*1.35)};
  $("#btnZoomOut").onclick=function(){setZoom(timelinePx()/1.35)};
  $("#btnZoomFit").onclick=zoomFit;
  $("#monitor").addEventListener("loadedmetadata",function(){
    if(S.pendingSeek!=null){var t=S.pendingSeek;S.pendingSeek=null;
      this.currentTime=clamp(t,0,this.duration||t);updateTimeUI(this.currentTime,this.duration)}
  });
  $("#tlScroll").addEventListener("wheel",function(e){
    if(!(e.ctrlKey||e.metaKey))return;
    e.preventDefault();setZoom(timelinePx()*(e.deltaY<0?1.16:1/1.16));
  },{passive:false});

  var rs=$("#tlResize"),resize={on:false,y:0,h:0};
  rs.addEventListener("pointerdown",function(e){
    resize.on=true;resize.y=e.clientY;resize.h=$("#timelinePanel").getBoundingClientRect().height;
    try{rs.setPointerCapture(e.pointerId)}catch(x){}
  });
  window.addEventListener("pointermove",function(e){
    if(!resize.on)return;
    var h=clamp(resize.h+(resize.y-e.clientY),170,540);
    document.documentElement.style.setProperty("--tl-h",h+"px");
  });
  window.addEventListener("pointerup",function(){
    if(resize.on){resize.on=false;try{localStorage.setItem("vmill.tlh",String(Math.round($("#timelinePanel").getBoundingClientRect().height)))}catch(e){}}
  });
}

async function loadTimeline(){
  if(!S.job){S.timeline=null;renderTimeline();return}
  try{S.timeline=await api("/api/jobs/"+enc(S.job)+"/timeline");renderTimeline()}
  catch(e){S.timeline=null;renderTimeline()}
}

/* -------------------------------------------------------------- open job */
async function openJob(name){
  name=String(name||"").trim();if(!name)return;
  if(S.aiTimer){clearTimeout(S.aiTimer);S.aiTimer=null}
  S.job=name;S.preview=null;S.optsLoaded=false;S.lastSrc="";S.artSig="";S.timeline=null;
  S.aiPending=false;S.status=null;S.assets=[];
  try{localStorage.setItem("vmill.last",name)}catch(e){}
  try{history.replaceState(null,"","#"+enc(name))}catch(e){}
  $("#jobTitle").textContent=name;showScreen();$("#previewFlag").classList.add("hidden");
  $("#monName").textContent="loading…";$("#log").textContent="";$("#actSize").textContent="";
  $("#aiLog").textContent="";$("#aiRun").classList.add("hidden");
  var v0=$("#monitor");v0.pause&&v0.pause();v0.removeAttribute("src");v0.load&&v0.load();S.lastSrc="";
  $("#tcCur").textContent="00:00:00:00";$("#tcTot").textContent="00:00:00:00";
  $("#progress").value=0;$("#playhead").classList.add("hidden");clearExport();
  setChrome("run","loading");loadChat();renderChat();renderTimeline();renderAssets();
  try{await Promise.all([poll(),refreshAssets(),loadTimeline()])}catch(e){}
  if(S.timer)clearInterval(S.timer);
  S.timer=setInterval(poll,1500);
  if(S.status&&S.status.ai_running)pollAI();
  refreshJobList();
}

/* --------------------------------------------------------------- ai chat */
var AI_EMPTY='<div class="ai-empty" id="aiEmpty"><div class="big">✦</div>'+
  '<h4>Custom edits, in words</h4><p>The AI can call any vidmill tool — trim, captions, '+
  'overlays, music, HyperFrames, export. Attach a skill when you want a proven recipe.</p></div>';
function chatKey(){return "vmill.chat."+S.job}
function loadChat(){
  S.chat=[];
  try{var raw=localStorage.getItem(chatKey());if(raw)S.chat=JSON.parse(raw)||[]}catch(e){S.chat=[]}
  if(!Array.isArray(S.chat))S.chat=[];
}
function saveChat(){
  try{localStorage.setItem(chatKey(),JSON.stringify(S.chat.slice(-40)))}catch(e){}
}
function renderChat(){
  var feed=$("#aiFeed");
  if(!S.chat.length){feed.innerHTML=AI_EMPTY;return}
  feed.innerHTML="";
  S.chat.forEach(function(m){
    var d=document.createElement("div");
    d.className="msg "+(m.role==="user"?"user":"bot")+(m.work?" work":"");
    d.textContent=m.text||"";
    var t=document.createElement("time");
    try{t.textContent=new Date(m.ts||Date.now()).toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"})}catch(e){}
    d.appendChild(t);feed.appendChild(d);
  });
  feed.scrollTop=feed.scrollHeight;
}
function finishAIMsg(text){
  var done=false;
  for(var i=S.chat.length-1;i>=0;i--){
    if(S.chat[i].role==="bot"&&S.chat[i].work){
      S.chat[i]={role:"bot",text:text,ts:Date.now()};done=true;break;
    }
  }
  if(!done)S.chat.push({role:"bot",text:text,ts:Date.now()});
  saveChat();renderChat();
}
function summary(text){
  var lines=(text||"").split(/\r?\n/).filter(function(x){return x.trim().length});
  var pick=[];
  for(var i=lines.length-1;i>=0&&pick.length<4;i--){
    var ln=lines[i].trim();
    if(ln.indexOf("[tool")===0||ln.indexOf("→")===0||ln.indexOf("->")===0)continue;
    pick.unshift(ln);
  }
  var s=pick.join("\n");if(!s)s=(text||"").trim().slice(-600);
  if(s.length>900)s="…"+s.slice(-900);
  return s||"Finished.";
}
async function pollAI(){
  if(!S.job)return;
  try{
    var a=await api("/api/jobs/"+enc(S.job)+"/ai");
    $("#aiRun").classList.remove("hidden");
    var el=$("#aiLog");el.textContent=a.text||"";
    el.scrollTop=el.scrollHeight;
    $("#aiRunState").textContent=a.running?"running":"done";
    if(a.running){
      S.aiTimer=setTimeout(pollAI,1500);$("#aiSend").disabled=true;
      setChrome("run","AI editing");return;
    }
    S.aiTimer=null;
    if(S.aiPending){
      S.aiPending=false;finishAIMsg(summary(a.text));toast("AI edit finished","ok");
    }
    $("#aiSend").disabled=!S.status||!S.status.ai_available||!!S.status.running;
    poll();loadTimeline();refreshAssets();
  }catch(e){S.aiTimer=null}
}
async function sendPrompt(text){
  var p=(text||"").trim();if(!p)return;
  if(!S.job){toast("Open a project first","warn");return}
  var s=S.status||{};
  if(!s.ai_available){toast("Set VIDMILL_AI_KEY (or OPENAI_API_KEY) in the server environment","warn");return}
  if(s.running){toast("Wait for the free pass to finish","warn");return}
  var useSkills=S.aiSkills.slice();
  S.chat.push({role:"user",text:p,ts:Date.now()});
  S.chat.push({role:"bot",text:"Working on it…",ts:Date.now(),work:true});
  S.aiPending=true;saveChat();renderChat();
  $("#aiPrompt").value="";$("#aiSend").disabled=true;
  $("#aiRun").classList.remove("hidden");$("#aiRunState").textContent="starting";
  $("#aiLog").textContent="starting the AI editor…";
  try{
    await api("/api/jobs/"+enc(S.job)+"/ai",{method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({prompt:p,skills:useSkills})});
    S.aiSkills=[];renderAISkills();
    pollAI();
  }catch(e){
    S.aiPending=false;finishAIMsg("Could not start the AI: "+String(e.message||e));
    $("#aiSend").disabled=false;toast(String(e.message||e),"err");
  }
}
function bindAI(){
  $("#aiSend").onclick=function(){sendPrompt($("#aiPrompt").value)};
  $("#aiPrompt").addEventListener("keydown",function(e){
    if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendPrompt(this.value)}
  });
  $("#aiChips").addEventListener("click",function(e){
    var b=e.target.closest(".chip");if(!b)return;
    sendPrompt(b.getAttribute("data-prompt")||b.textContent);
  });
}

/* --------------------------------------------------------------- skills */
function skillByName(name){
  for(var i=0;i<S.skills.length;i++)if(S.skills[i].name===name)return S.skills[i];
  return null;
}
function renderAISkills(){
  var box=$("#aiSkills");if(!box)return;
  box.innerHTML="";
  if(!S.aiSkills.length){box.classList.add("hidden");return}
  box.classList.remove("hidden");
  var lead=document.createElement("span");lead.className="ai-skills-label";lead.textContent="Skills";box.appendChild(lead);
  S.aiSkills.forEach(function(name){
    var b=document.createElement("button");b.type="button";b.className="ai-skill-tag";
    var meta=skillByName(name);b.title=meta?meta.description:"Remove from this request";
    b.textContent=name+" ×";
    b.onclick=function(){toggleAISkill(name)};
    box.appendChild(b);
  });
}
function toggleAISkill(name){
  if(!name)return;
  var i=S.aiSkills.indexOf(name);
  if(i>=0)S.aiSkills.splice(i,1);
  else{
    if(S.aiSkills.length>=4){toast("Attach up to 4 skills to one request","warn");return}
    S.aiSkills.push(name);
  }
  renderAISkills();
  if(S.skill&&S.skill.name===name)
    $("#skillUse").textContent=i>=0?"Use in AI":"Remove from request";
}
async function refreshSkills(){
  try{
    var d=await api("/api/skills");
    S.skills=d.skills||[];S.skillDirs=d.dirs||{};
    $("#skillCount").textContent=String(S.skills.length);
    var dirs=$("#skillDirs");dirs.innerHTML="";
    ["bundled","user","project"].forEach(function(scope){
      if(!S.skillDirs[scope])return;
      var row=document.createElement("div");row.textContent=scope+": "+S.skillDirs[scope];
      dirs.appendChild(row);
    });
    if(!$("#modalSkills").classList.contains("hidden"))renderSkillList();
    return d;
  }catch(e){return null}
}
function renderSkillList(){
  var box=$("#skillList");if(!box)return;
  var q=($("#skillSearch").value||"").toLowerCase();
  box.innerHTML="";
  var list=(S.skills||[]).filter(function(s){
    return !q||s.name.toLowerCase().indexOf(q)>=0||
      (s.description||"").toLowerCase().indexOf(q)>=0||
      (s.tags||[]).join(" ").toLowerCase().indexOf(q)>=0;
  });
  if(!list.length){box.innerHTML='<div class="skills-empty">No skills match.</div>';return}
  list.forEach(function(s){
    var b=document.createElement("button");b.type="button";
    b.className="skill-row"+(S.skill&&S.skill.name===s.name?" sel":"");
    var h=document.createElement("div");h.className="skill-row-h";
    var n=document.createElement("b");n.textContent=s.name;
    var src=document.createElement("span");src.className="src "+(s.source||"bundled");
    src.textContent=s.source||"bundled";h.appendChild(n);h.appendChild(src);
    var p=document.createElement("p");p.textContent=s.description||"";
    b.appendChild(h);b.appendChild(p);
    b.title=s.description||s.name;
    b.onclick=function(){selectSkill(s.name)};
    box.appendChild(b);
  });
}
function fillSkill(d){
  S.skill=d;
  $("#skillPlaceholder").classList.add("hidden");
  $("#skillForm").classList.remove("hidden");
  var name=d.name||"",isNew=d.source==="new";
  $("#skillName").value=name;$("#skillName").readOnly=!isNew;
  $("#skillDesc").value=d.description||"";
  $("#skillTags").value=(d.tags||[]).join(", ");
  $("#skillBody").value=d.body||"";
  $("#skillSource").textContent=d.source||"new";
  $("#skillSource").className="tag "+(d.source||"new");
  $("#skillPath").textContent=d.path||"not saved yet";
  var hasBundled=d.overrides==="bundled";
  var writable=!isNew&&d.source!=="bundled";
  $("#skillReset").classList.toggle("hidden",!writable||!hasBundled);
  $("#skillDelete").classList.toggle("hidden",!writable||hasBundled);
  $("#skillUse").classList.toggle("hidden",isNew||!name);
  $("#skillUse").textContent=S.aiSkills.indexOf(name)>=0?"Remove from request":"Use in AI";
  $("#skillMsg").textContent="";
  $("#skillSearch").value="";
}
async function selectSkill(name){
  try{
    var d=await api("/api/skills/"+enc(name));
    fillSkill(d.skill);renderSkillList();
  }catch(e){toast(String(e.message||e),"err")}
}
function newSkill(){
  fillSkill({name:"",description:"",tags:[],body:"",source:"new",path:""});
  $("#skillName").readOnly=false;$("#skillName").focus();
}
function resetSkillEditor(){
  S.skill=null;
  $("#skillForm").classList.add("hidden");
  $("#skillPlaceholder").classList.remove("hidden");
  renderSkillList();
}
async function saveSkill(){
  var isNew=!S.skill||S.skill.source==="new";
  var name=$("#skillName").value.trim().toLowerCase();
  var description=$("#skillDesc").value.trim();
  var body=$("#skillBody").value.trim();
  var tags=$("#skillTags").value.split(",").map(function(x){return x.trim()}).filter(Boolean);
  var msg=$("#skillMsg");msg.textContent="";
  if(!name){msg.textContent="Give the skill a name.";return}
  if(!description){msg.textContent="Add a line that tells the AI when to use it.";return}
  if(!body){msg.textContent="Add the Markdown instructions.";return}
  var existing=isNew?skillByName(name):null;
  var scope=(!isNew&&S.skill.source==="project")||
    (existing&&existing.source==="project")?"project":"user";
  if(existing&&!confirm("A "+existing.source+" skill named \""+name+"\" already exists. Save your version in the "+scope+" scope?"))return;
  var payload={name:name,description:description,tags:tags,body:body,scope:scope};
  $("#skillSave").disabled=true;
  try{
    var d;
    if(isNew)d=await api("/api/skills",{method:"POST",
      headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    else d=await api("/api/skills/"+enc(S.skill.name),{method:"PUT",
      headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    fillSkill(d.skill);
    await refreshSkills();
    renderSkillList();
    toast("Skill saved","ok");
  }catch(e){msg.textContent=String(e.message||e)}
  $("#skillSave").disabled=false;
}
async function resetSkill(){
  if(!S.skill||!S.skill.name||S.skill.source==="bundled")return;
  var scope=S.skill.source==="project"?"project":"user";
  if(!confirm("Remove the "+scope+" override for \""+S.skill.name+"\" and restore the bundled skill?"))return;
  try{
    var d=await api("/api/skills/"+enc(S.skill.name)+"/reset",{method:"POST",
      headers:{"Content-Type":"application/json"},body:JSON.stringify({scope:scope})});
    await refreshSkills();
    if(d.skill)fillSkill(d.skill);else resetSkillEditor();
    renderSkillList();toast("Skill reset","ok");
  }catch(e){$("#skillMsg").textContent=String(e.message||e)}
}
async function deleteSkill(){
  if(!S.skill||!S.skill.name||S.skill.source==="bundled"||S.skill.source==="new")return;
  var scope=S.skill.source==="project"?"project":"user";
  if(!confirm("Delete the "+scope+" skill \""+S.skill.name+"\"?"))return;
  try{
    await api("/api/skills/"+enc(S.skill.name)+"?scope="+enc(scope),{method:"DELETE"});
    resetSkillEditor();await refreshSkills();renderSkillList();toast("Skill deleted","ok");
  }catch(e){$("#skillMsg").textContent=String(e.message||e)}
}
function openSkills(){
  showModal("modalSkills");
  refreshSkills().then(function(){renderSkillList()});
}
function bindSkills(){
  $("#btnSkills").onclick=openSkills;
  $("#skillNew").onclick=newSkill;
  $("#skillSave").onclick=saveSkill;
  $("#skillUse").onclick=function(){if(S.skill)toggleAISkill(S.skill.name)};
  $("#skillReset").onclick=resetSkill;
  $("#skillDelete").onclick=deleteSkill;
  $("#skillSearch").addEventListener("input",renderSkillList);
}

/* ------------------------------------------------------------- new/edit */
var newFile=null;
function showModal(id){var m=$("#"+id);if(m)m.classList.remove("hidden")}
function hideModal(id){var m=$("#"+id);if(m)m.classList.add("hidden")}
function readOpts(prefix){
  var on=$("#"+prefix+"watermark").checked;
  var region=$("#"+prefix+"wmregion").value.trim();
  return {
    silences:$("#"+prefix+"silences").checked,
    still:$("#"+prefix+"still").checked,
    mistakes:$("#"+prefix+"mistakes").checked,
    captions:$("#"+prefix+"captions").checked,
    clean:$("#"+prefix+"clean").checked,
    watermark:on?(region||"auto"):"off"
  };
}
function writeOpts(prefix,o){
  o=o||{};
  $("#"+prefix+"silences").checked=o.silences!==false;
  $("#"+prefix+"still").checked=o.still!==false;
  $("#"+prefix+"mistakes").checked=o.mistakes!==false;
  $("#"+prefix+"captions").checked=o.captions!==false;
  $("#"+prefix+"clean").checked=o.clean!==false;
  var wm=o.watermark||"auto";
  $("#"+prefix+"watermark").checked=wm!=="off";
  $("#"+prefix+"wmregion").value=(wm!=="auto"&&wm!=="off")?wm:"";
}
function newPicked(f){
  newFile=f||null;
  $("#picked").textContent=f?(f.name+"  "+(f.size/1048576).toFixed(1)+" MB"):"";
  var path=$("#path").value.trim();
  $("#go").disabled=!(newFile||path);
  $("#go").textContent=(newFile&&!path)?"Upload & edit":"Open & edit";
}
function openNew(){
  newFile=null;$("#picked").textContent="";$("#path").value="";$("#jobname").value="";
  $("#msg").textContent="";$("#go").disabled=true;$("#go").textContent="Upload & edit";
  try{$("#file").value=""}catch(e){}
  showModal("modalNew");setTimeout(function(){$("#path").focus()},60);
}
function openSettings(){
  if(!S.job){toast("Open a project first","warn");return}
  $("#setSub").textContent="Free local pass for “"+S.job+"”.";
  $("#setMsg").textContent="";
  writeOpts("d_",(S.status&&S.status.opts)||{});
  showModal("modalSettings");
}
async function startNew(){
  var o=readOpts("n_"),name=$("#jobname").value.trim(),path=$("#path").value.trim();
  $("#msg").textContent="";$("#go").disabled=true;
  try{
    var job;
    if(newFile&&!path){
      $("#msg").textContent="uploading…";
      var q=new URLSearchParams({filename:newFile.name});if(name)q.set("name",name);
      var d=await api("/api/upload?"+q,{method:"PUT",body:newFile});
      job=d.name;
    }else{
      if(!path)throw new Error("choose a video or paste a path on this machine");
      var d=await api("/api/jobs",{method:"POST",
        headers:{"Content-Type":"application/json"},body:JSON.stringify({name:name||undefined,path:path})});
      job=d.name;
    }
    $("#msg").textContent="starting the free local pass…";
    await api("/api/jobs/"+enc(job)+"/run",{method:"POST",
      headers:{"Content-Type":"application/json"},body:JSON.stringify(o)});
    hideModal("modalNew");
    newFile=null;$("#picked").textContent="";$("#path").value="";$("#jobname").value="";
    try{$("#file").value=""}catch(e){}
    openJob(job);refreshJobList();toast("Free pass started for "+job,"ok");
  }catch(e){
    $("#msg").textContent=String(e.message||e);$("#go").disabled=false;
  }
}
async function rerun(){
  if(!S.job)return;
  if(!confirm("Reset this project's outputs and run the free pass again from the original source?"))return;
  $("#run").disabled=true;$("#setMsg").textContent="restarting…";
  try{
    await api("/api/jobs/"+enc(S.job)+"/run",{method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify(Object.assign(readOpts("d_"),{restart:true}))});
    hideModal("modalSettings");$("#log").textContent="";S.optsLoaded=false;
    toast("Re-running from source","ok");poll();
  }catch(e){$("#setMsg").textContent=String(e.message||e);$("#run").disabled=false}
}
async function cancelRun(){
  if(!S.job)return;
  try{await api("/api/jobs/"+enc(S.job)+"/cancel",{method:"POST"});toast("Run cancelled","warn");poll()}
  catch(e){toast(String(e.message||e),"err")}
}
function bindModals(){
  $$("[data-close]").forEach(function(b){b.onclick=function(){hideModal(b.getAttribute("data-close"))}});
  $$(".backdrop").forEach(function(b){
    b.addEventListener("click",function(e){if(e.target===b)hideModal(b.id)});
  });
  $("#btnNew").onclick=openNew;$("#btnNew2").onclick=openNew;$("#btnNewProject").onclick=openNew;
  $("#btnSettings").onclick=openSettings;$("#btnRestart").onclick=openSettings;
  $("#btnNew").onclick=openNew;
  $("#file").addEventListener("change",function(e){newPicked(e.target.files[0]||null)});
  $("#path").addEventListener("input",function(){newPicked(newFile)});
  $("#drop").addEventListener("dragover",function(e){e.preventDefault();this.classList.add("hot")});
  $("#drop").addEventListener("dragleave",function(){this.classList.remove("hot")});
  $("#drop").addEventListener("drop",function(e){
    e.preventDefault();this.classList.remove("hot");newPicked(e.dataTransfer.files[0]||null);
  });
  $("#go").onclick=startNew;$("#run").onclick=rerun;
  $("#cancelRun").onclick=cancelRun;$("#btnCancelRun").onclick=cancelRun;
  $("#btnOpenFolder").onclick=async function(){
    var p=S.status&&S.status.job_dir;
    if(!p){toast("Open a project first","warn");return}
    try{await navigator.clipboard.writeText(p);toast("Job folder path copied","ok")}
    catch(e){toast(p)}
  };
}

/* -------------------------------------------------------------- importing */
async function uploadAssets(files){
  if(!S.job){toast("Open a project first","warn");return}
  if(!files||!files.length)return;
  var ok=0;
  for(var i=0;i<files.length;i++){
    var f=files[i];
    setChrome("run","importing "+f.name+"…");
    try{
      await api("/api/jobs/"+enc(S.job)+"/assets?filename="+enc(f.name),{method:"PUT",body:f});
      ok++;
    }catch(e){toast(f.name+": "+String(e.message||e),"err")}
  }
  try{$("#assetFile").value=""}catch(e){}
  await refreshAssets();poll();
  if(ok)toast(ok+" asset"+(ok>1?"s":"")+" imported","ok");
}
function bindAssets(){
  $("#assetFilters").addEventListener("click",function(e){
    var b=e.target.closest("button[data-filter]");if(!b)return;
    S.filter=b.getAttribute("data-filter");
    $$("#assetFilters button").forEach(function(x){x.classList.toggle("on",x===b)});
    renderAssets();
  });
  $("#assetSearch").addEventListener("input",function(){S.search=this.value;renderAssets()});
  $("#btnImport").onclick=function(){$("#assetFile").click()};
  $("#assetFile").addEventListener("change",function(){uploadAssets(this.files)});
}

/* ------------------------------------------------------------------ init */
function bindKeys(){
  document.addEventListener("keydown",function(e){
    if(e.key==="Escape"){$$(".backdrop").forEach(function(b){b.classList.add("hidden")});return}
    var tag=(e.target.tagName||"").toLowerCase();
    if(tag==="input"||tag==="textarea"||tag==="select")return;
    if(e.code==="Space"){e.preventDefault();togglePlay()}
    else if(e.key==="ArrowLeft"){e.preventDefault();stepFrame(e.shiftKey?-10:-1)}
    else if(e.key==="ArrowRight"){e.preventDefault();stepFrame(e.shiftKey?10:1)}
    else if(e.key==="Home"){e.preventDefault();seekSequence(0)}
    else if(e.key==="End"&&S.timeline){e.preventDefault();seekSequence(S.timeline.duration)}
    else if(e.key==="f"||e.key==="F"){$("#btnFit").click()}
  });
}
function boot(){
  bindMonitor();bindTimeline();bindAI();bindSkills();bindModals();bindAssets();bindKeys();
  renderAISkills();refreshSkills();
  var act=$("#activity");
  try{
    if(localStorage.getItem("vmill.act")==="0")act.classList.add("collapsed");
    var th=parseInt(localStorage.getItem("vmill.tlh")||"",10);
    if(th&&th>=170&&th<=540)document.documentElement.style.setProperty("--tl-h",th+"px");
  }catch(e){}
  $("#actHead").onclick=function(){
    act.classList.toggle("collapsed");
    try{localStorage.setItem("vmill.act",act.classList.contains("collapsed")?"0":"1")}catch(e){}
  };
  window.addEventListener("resize",function(){if(S.timeline)renderTimeline()});
  refreshJobList().then(function(){
    var last=null;
    try{last=localStorage.getItem("vmill.last")}catch(e){}
    var hash="";
    try{hash=decodeURIComponent(location.hash.replace(/^#/,""))}catch(e){hash=""}
    var want=hash||last;
    var found=null;
    (S.jobs||[]).forEach(function(j){if(j.name===want)found=j.name});
    if(found)openJob(found);
  });
  S.jobsTimer=setInterval(refreshJobList,7000);
}
boot();
"""
