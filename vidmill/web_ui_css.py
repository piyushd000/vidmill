"""Design system for the vidmill studio editor.

Dark, dense and quiet: the picture is the loudest thing on screen.
"""

CSS = r"""
:root{
  --bg:#090b0f;--panel:#11141a;--panel2:#151922;--elev:#1a1f29;--well:#0c0f14;
  --line:#232a36;--line2:#303a49;--fg:#e8edf6;--dim:#8a95a8;--dim2:#5b6679;
  --acc:#5b8cff;--acc2:#93adff;--ok:#3ddc97;--warn:#f2b84b;--danger:#ff6b7a;
  --purple:#a78bfa;--teal:#2dd4bf;--pink:#f472b6;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Inter,sans-serif;
  --r:8px;--tl-h:clamp(228px,34vh,320px);
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:13px/1.45 var(--sans);
  overflow:hidden;-webkit-font-smoothing:antialiased}
button,input,textarea,select{font:inherit;color:inherit}
button{cursor:pointer}
button:disabled{cursor:not-allowed;opacity:.42}
a{color:var(--acc2);text-decoration:none}
.hidden{display:none!important}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-thumb{background:#2b3442;border-radius:9px;border:2px solid transparent;background-clip:padding-box}
::-webkit-scrollbar-thumb:hover{background:#3a4556;border:2px solid transparent;background-clip:padding-box}
::-webkit-scrollbar-track{background:transparent}
::selection{background:rgba(91,140,255,.35)}

/* ---------------------------------------------------------------- shell */
.app{display:grid;grid-template-rows:50px minmax(0,1fr);height:100vh}
.topbar{display:flex;align-items:center;gap:14px;padding:0 14px;background:
  linear-gradient(180deg,#12161d,#0d1015);border-bottom:1px solid var(--line);z-index:20}
.brand{display:flex;align-items:center;gap:9px;min-width:0;flex:none}
.mark{width:27px;height:27px;border-radius:8px;display:grid;place-items:center;flex:none;
  background:linear-gradient(135deg,#5b8cff,#a06cff);box-shadow:0 2px 14px rgba(91,140,255,.35);
  font-weight:800;font-size:13px;color:#fff}
.brand b{font-size:14.5px;letter-spacing:.2px;font-weight:750}
.brand span{font-size:10px;color:var(--dim2);letter-spacing:1.4px;text-transform:uppercase;
  border:1px solid var(--line);border-radius:99px;padding:1px 6px;margin-left:1px}
.sep{width:1px;height:22px;background:var(--line);flex:none}
.crumbwrap{display:flex;align-items:center;gap:7px;min-width:0;flex:1}
.crumbwrap .dim{color:var(--dim2);font-size:12px}
#jobTitle{font-weight:620;font-size:13.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:340px}
.tstate{display:flex;align-items:center;gap:6px;font-size:11.5px;color:var(--dim);
  border:1px solid var(--line);border-radius:99px;padding:3px 9px;white-space:nowrap;flex:none}
.dot{width:6px;height:6px;border-radius:50%;background:var(--dim2);flex:none}
.dot.ok{background:var(--ok);box-shadow:0 0 7px rgba(61,220,151,.7)}
.dot.run{background:var(--warn);box-shadow:0 0 7px rgba(242,184,75,.7);animation:pulse 1.3s infinite}
.dot.err{background:var(--danger)}
@keyframes pulse{50%{opacity:.35}}
.top-actions{display:flex;align-items:center;gap:7px;flex:none}
.btn{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:7px;
  border:1px solid var(--line2);background:var(--elev);color:var(--fg);font-size:12px;font-weight:520;
  transition:background .14s,border-color .14s,color .14s;white-space:nowrap}
.btn:hover:not(:disabled){background:#222936;border-color:#3b475a}
.btn.primary{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:650}
.btn.primary:hover:not(:disabled){background:#709bff;border-color:#709bff}
.btn.ghost{background:transparent;border-color:transparent;color:var(--dim)}
.btn.ghost:hover:not(:disabled){background:var(--elev);color:var(--fg)}
.btn.danger{color:var(--danger);border-color:rgba(255,107,122,.35);background:rgba(255,107,122,.07)}
.btn.sm{padding:4px 8px;font-size:11px;border-radius:6px}
.icon{width:13px;height:13px;display:block;flex:none}
.kbd{font:10px var(--mono);color:var(--dim2);border:1px solid var(--line);border-radius:4px;padding:0 4px}

.layout{display:grid;grid-template-columns:286px minmax(0,1fr) 336px;min-height:0}
.col{min-height:0;min-width:0;display:flex;flex-direction:column;background:var(--panel)}
.col.left{border-right:1px solid var(--line)}
.col.right{border-left:1px solid var(--line);background:linear-gradient(180deg,#101319,#0d1015)}
.col.center{background:radial-gradient(1100px 500px at 50% -10%,#141925 0%,#0b0e13 62%);
  overflow:hidden}

/* --------------------------------------------------------------- panels */
.panel{display:flex;flex-direction:column;min-height:0;border-bottom:1px solid var(--line)}
.panel:last-child{border-bottom:0}
.ph{height:36px;display:flex;align-items:center;gap:7px;padding:0 11px;flex:none;
  color:var(--dim);font-size:10.5px;font-weight:700;letter-spacing:1.25px;text-transform:uppercase;
  user-select:none}
.ph .count{font-weight:600;letter-spacing:0;color:var(--dim2);font-size:10px;background:var(--well);
  border:1px solid var(--line);border-radius:99px;padding:0 6px}
.ph .grow{flex:1}
.phbtn{width:23px;height:23px;border:1px solid transparent;border-radius:6px;background:transparent;
  color:var(--dim);display:grid;place-items:center;padding:0}
.phbtn:hover{background:var(--elev);border-color:var(--line);color:var(--fg)}
.phbtn .icon{width:14px;height:14px}
.panel-body{overflow:auto;min-height:0}
.bin{flex:1 1 auto}
.bin-tools{padding:0 10px 8px;display:grid;gap:7px;flex:none}
.search{display:flex;align-items:center;gap:6px;background:var(--well);border:1px solid var(--line);
  border-radius:7px;padding:0 8px;height:29px}
.search .icon{color:var(--dim2)}
.search input{flex:1;background:none;border:0;outline:0;font-size:12px;min-width:0}
.filters{display:flex;gap:3px;background:var(--well);border:1px solid var(--line);border-radius:7px;padding:2px}
.filters button{flex:1;border:0;background:transparent;color:var(--dim);border-radius:5px;
  padding:3px 2px;font-size:10.5px;font-weight:560}
.filters button.on{background:var(--elev);color:var(--fg);box-shadow:0 1px 2px rgba(0,0,0,.3)}
.assets{padding:0 10px 12px;display:grid;grid-template-columns:1fr 1fr;gap:8px}
.asset{border:1px solid var(--line);background:var(--panel2);border-radius:8px;padding:0;overflow:hidden;
  text-align:left;position:relative;transition:border-color .13s,transform .13s;min-width:0}
.asset:hover{border-color:#3b475a;transform:translateY(-1px)}
.asset.sel{border-color:var(--acc);box-shadow:0 0 0 1px rgba(91,140,255,.4)}
.athumb{position:relative;aspect-ratio:16/10;background:#07090d center/cover no-repeat;overflow:hidden}
.athumb .dur{position:absolute;right:4px;bottom:4px;background:rgba(5,7,10,.82);border-radius:4px;
  padding:0 4px;font:10px var(--mono);color:#dbe3f2}
.athumb .ab{position:absolute;left:4px;top:4px;border-radius:4px;padding:0 4px;font:9px var(--mono);
  font-weight:700;letter-spacing:.4px;text-transform:uppercase}
.ab.src{background:rgba(91,140,255,.9);color:#fff}
.ab.cur{background:rgba(61,220,151,.92);color:#04150d}
.ab.out{background:rgba(167,139,250,.85);color:#120a2b}
.ab.asset{background:rgba(242,184,75,.88);color:#221703}
.asset .aname{padding:5px 6px 4px;font-size:10.5px;font-weight:560;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis}
.asset .ameta{padding:0 6px 5px;font-size:9px;color:var(--dim2);white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;font-family:var(--mono)}
.bin-empty{margin:10px;padding:14px;border:1px dashed var(--line2);border-radius:8px;color:var(--dim2);
  font-size:11.5px;text-align:center;line-height:1.5}

/* inspector */
.inspector{flex:none}
.rows{padding:0 11px 10px;display:grid;gap:5px}
.row{display:flex;justify-content:space-between;gap:10px;font-size:11px;min-width:0}
.row .k{color:var(--dim2);flex:none}
.row .v{color:#c8d2e3;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  font-family:var(--mono);font-size:10.5px}
.row .v.ok{color:var(--ok)}
.row .v.acc{color:var(--acc2)}
.ins-foot{padding:0 11px 10px;display:flex;gap:6px}
.ins-foot .btn{flex:1;justify-content:center}

/* projects */
.projects{flex:0 0 auto;max-height:196px}
.plist{overflow:auto;padding:0 7px 8px}
.prow{display:flex;align-items:center;gap:8px;padding:6px 7px;border-radius:6px;cursor:pointer;min-width:0}
.prow:hover{background:var(--elev)}
.prow.sel{background:#1b2333;box-shadow:inset 2px 0 var(--acc)}
.prow .pn{flex:1;font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.prow .pm{font:9.5px var(--mono);color:var(--dim2);white-space:nowrap}
.prow .dot{width:5px;height:5px}

/* -------------------------------------------------------------- center */
.monitor{flex:1 1 auto;display:flex;flex-direction:column;min-height:0;position:relative;overflow:hidden}
.mon-head{height:36px;display:flex;align-items:center;gap:8px;padding:0 14px;flex:none}
.mon-title{font-size:11.5px;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mon-title b{color:#d6dfef;font-weight:600}
.mon-badge{margin-left:auto;display:flex;gap:5px;align-items:center;flex:none}
.tag{font:9.5px var(--mono);color:var(--dim);border:1px solid var(--line);border-radius:4px;
  padding:1px 5px;background:var(--well);letter-spacing:.3px}
.stage{flex:1;min-height:0;display:grid;place-items:center;padding:0 20px;position:relative;overflow:hidden}
.screen{position:relative;width:100%;height:100%;min-height:0;display:flex;align-items:center;justify-content:center}
video#monitor{display:block;max-width:100%;max-height:100%;width:auto;height:auto;background:#000;
  border-radius:3px;box-shadow:0 18px 60px rgba(0,0,0,.6);outline:1px solid #1c2230}
.empty-stage{display:flex;flex-direction:column;align-items:center;gap:12px;color:var(--dim2);
  text-align:center;padding:30px;max-width:420px}
.empty-logo{width:56px;height:56px;border-radius:16px;display:grid;place-items:center;
  background:linear-gradient(135deg,rgba(91,140,255,.18),rgba(160,108,255,.12));
  border:1px solid rgba(91,140,255,.25);font-size:22px}
.empty-stage h3{margin:0;color:#cfd8e8;font-size:15px;font-weight:600}
.empty-stage p{margin:0;font-size:12px;line-height:1.6}
.drop-mini{margin-top:2px}
.preview-flag{position:absolute;left:10px;top:8px;background:rgba(12,15,20,.86);border:1px solid var(--line);
  border-radius:5px;padding:2px 7px;font-size:10px;color:var(--warn);display:flex;gap:6px;align-items:center}
.transport{height:46px;flex:none;display:flex;align-items:center;gap:9px;padding:0 14px;
  border-top:1px solid rgba(35,42,54,.55);background:rgba(11,14,19,.55);overflow:hidden}
.tc{flex:none}
.tbtn{width:29px;height:29px;border:1px solid transparent;background:transparent;border-radius:6px;
  display:grid;place-items:center;color:#b9c3d4;padding:0}
.tbtn:hover:not(:disabled){background:var(--elev);border-color:var(--line)}
.tbtn.play{width:34px;height:34px;border-radius:50%;background:#e9edf6;color:#0a0c10;
  border-color:#e9edf6;box-shadow:0 2px 10px rgba(0,0,0,.4)}
.tbtn.play:hover:not(:disabled){background:#fff}
.tbtn .icon{width:15px;height:15px}
.tc{font:11px var(--mono);color:#cfd8e8;letter-spacing:.4px;white-space:nowrap}
.tc .tot{color:var(--dim2)}
.progress{flex:1;min-width:40px;height:3px;background:#2a3240;border-radius:9px;appearance:none;outline:0;cursor:pointer}
.progress::-webkit-slider-thumb{appearance:none;width:10px;height:10px;border-radius:50%;background:#dfe7f5;
  box-shadow:0 0 0 3px rgba(91,140,255,.25)}
.progress::-moz-range-thumb{width:10px;height:10px;border:0;border-radius:50%;background:#dfe7f5}
.vol{display:flex;align-items:center;gap:4px}
.vol input{width:56px;height:3px;accent-color:var(--acc)}
.tsep{flex:1}
.status-chip{display:flex;align-items:center;gap:6px;font-size:10.5px;color:var(--dim);
  background:rgba(12,15,20,.7);border:1px solid var(--line);border-radius:99px;padding:2px 8px;
  max-width:280px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.status-chip b{color:var(--fg);font-weight:600}
.status-chip .dot{width:5px;height:5px}

/* timeline */
.timeline{height:var(--tl-h);flex:none;display:flex;flex-direction:column;border-top:1px solid var(--line);
  background:linear-gradient(180deg,#10141b,#0c0f14);min-height:150px;position:relative}
.tl-resize{position:absolute;top:-4px;left:0;right:0;height:7px;cursor:ns-resize;z-index:5}
.tl-head{height:34px;display:flex;align-items:center;gap:8px;padding:0 10px;flex:none;
  border-bottom:1px solid var(--line)}
.tl-title{font-size:11px;font-weight:650;color:#c9d3e3;white-space:nowrap}
.tl-sub{font:9.5px var(--mono);color:var(--dim2);white-space:nowrap;overflow:hidden;\n  text-overflow:ellipsis;min-width:0}
.tl-tools{margin-left:auto;display:flex;align-items:center;gap:6px}
.zbtn{width:22px;height:22px;display:grid;place-items:center;border:1px solid var(--line);background:var(--well);
  color:var(--dim);border-radius:5px;padding:0}
.zbtn:hover{color:var(--fg);border-color:var(--line2)}
.zbtn .icon{width:12px;height:12px}
#zoom{width:88px;height:3px;accent-color:var(--acc)}
.tl-body{flex:1;min-height:0;display:grid;grid-template-columns:82px minmax(0,1fr);overflow:hidden}
.tl-labels{display:flex;flex-direction:column;border-right:1px solid var(--line);background:#0d1015;z-index:2}
.lbl{display:flex;align-items:center;gap:5px;padding:0 8px;border-bottom:1px solid rgba(35,42,54,.65);
  font:9px var(--mono);color:var(--dim2);white-space:nowrap;overflow:hidden}
.lbl .tag{font-size:8px;padding:0 3px;border-color:var(--line);color:var(--dim)}
.lbl.ruler-lbl{height:26px;font-size:8.5px;letter-spacing:1px}
.lbl.v1{height:48px;color:#93adff}
.lbl.ov{height:30px;color:#f2b84b}
.lbl.c1{height:30px;color:#7dd3fc}
.lbl.a1{height:46px;color:#2dd4bf}
.tl-scroll{overflow-x:auto;overflow-y:hidden;position:relative;min-width:0}
.tl-inner{position:relative;height:100%;min-width:100%;background-image:
  linear-gradient(90deg,rgba(48,58,73,.16) 1px,transparent 1px);background-size:100px 100%}
.ruler{height:26px;position:relative;border-bottom:1px solid var(--line);background:#0b0e13;cursor:pointer;
  user-select:none}
.tick{position:absolute;top:0;bottom:0;border-left:1px solid #242c39}
.tick span{position:absolute;left:3px;top:5px;font:9px var(--mono);color:var(--dim2);white-space:nowrap}
.tick.minor{border-left-color:#1a202b}
.track{position:relative;border-bottom:1px solid rgba(35,42,54,.65);cursor:crosshair}
.track.v1{height:48px}
.track.ov{height:30px}
.track.c1{height:30px}
.track.a1{height:46px}
.track::after{content:"";position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(180deg,rgba(255,255,255,.015),transparent)}
.seg{position:absolute;top:4px;bottom:4px;border-radius:5px;overflow:hidden;border:1px solid rgba(255,255,255,.1);
  display:flex;align-items:center;padding:0 6px;font-size:9.5px;min-width:2px;cursor:pointer;
  box-shadow:inset 0 1px rgba(255,255,255,.18),0 1px 3px rgba(0,0,0,.35);user-select:none}
.seg span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-shadow:0 1px 2px rgba(0,0,0,.5)}
.seg.main{background:linear-gradient(180deg,#3b5fbd,#2b468d);color:#e8eeff}
.seg.intro{background:linear-gradient(180deg,#6d52c7,#4f3899);color:#f0eaff}
.seg.outro{background:linear-gradient(180deg,#2a8f83,#1f6a61);color:#e2fffa}
.seg.overlay{background:linear-gradient(180deg,#a77721,#7d5818);color:#fff6e2;top:3px;bottom:3px}
.seg.caption{background:repeating-linear-gradient(135deg,rgba(56,142,189,.3),rgba(56,142,189,.3) 6px,
  rgba(56,142,189,.18) 6px,rgba(56,142,189,.18) 12px);border:1px dashed rgba(125,211,252,.6);
  color:#bfe9ff;font-style:italic}
.seg.audio{background:transparent;border:0;box-shadow:none;padding:0}
.audio-img{position:absolute;inset:2px 0;width:100%;height:calc(100% - 4px);object-fit:fill;opacity:.85;
  filter:drop-shadow(0 1px 2px rgba(0,0,0,.4))}
.audio-empty{position:absolute;left:8px;top:50%;transform:translateY(-50%);font:9px var(--mono);
  color:var(--dim2)}
.playhead{position:absolute;top:0;bottom:0;width:1px;background:#ff4d67;z-index:8;pointer-events:none;
  box-shadow:0 0 5px rgba(255,77,103,.6)}
.playhead::before{content:"";position:absolute;left:-5px;top:0;border:5px solid transparent;
  border-top:8px solid #ff4d67}
.tl-hint{position:absolute;left:50%;top:60%;transform:translate(-50%,-50%);color:var(--dim2);
  font-size:11px;pointer-events:none;text-align:center;line-height:1.6}

/* activity */
.activity{flex:none;border-top:1px solid var(--line);background:#0a0d12;max-height:170px;
  display:flex;flex-direction:column}
.activity.collapsed{max-height:32px}
.act-head{height:32px;display:flex;align-items:center;gap:7px;padding:0 12px;cursor:pointer;flex:none;
  color:var(--dim);font-size:10px;letter-spacing:1.1px;text-transform:uppercase;font-weight:700;user-select:none}
.act-head:hover{color:var(--fg)}
.act-head .grow{flex:1}
.act-head .live{font:9px var(--mono);letter-spacing:0;text-transform:none;color:var(--dim2)}
.act-head .chev{transition:transform .15s}
.activity.collapsed .chev{transform:rotate(-90deg)}
.log{flex:1;overflow:auto;margin:0;padding:0 12px 9px;font:10.5px/1.55 var(--mono);
  color:#a9b5c9;white-space:pre-wrap;word-break:break-word}
.activity.collapsed .log{display:none}

/* ------------------------------------------------------------------ ai */
.ai-head{height:44px;display:flex;align-items:center;gap:9px;padding:0 12px;flex:none;
  border-bottom:1px solid var(--line)}
.ai-orb{width:24px;height:24px;border-radius:8px;display:grid;place-items:center;flex:none;
  background:linear-gradient(135deg,rgba(91,140,255,.3),rgba(244,114,182,.25));
  border:1px solid rgba(147,173,255,.35);color:#cdd9ff;font-size:12px}
.ai-head b{font-size:12px;font-weight:650;display:block;line-height:1.2}
.ai-head small{display:block;font-size:9px;color:var(--dim2);font-family:var(--mono)}
.ai-head .grow{flex:1}
.skill-btn{display:inline-flex;align-items:center;gap:4px;border:1px solid var(--line);background:transparent;
  color:var(--dim);border-radius:99px;padding:2px 7px;font-size:9.5px;flex:none;transition:.13s}
.skill-btn b{font:9px var(--mono);color:var(--acc2);min-width:10px;text-align:center}
.skill-btn:hover{border-color:rgba(167,139,250,.55);color:#d6c9ff;background:rgba(167,139,250,.08)}
.ai-feed{flex:1;overflow:auto;padding:12px 12px 6px;display:flex;flex-direction:column;gap:10px;min-height:0}
.ai-empty{margin:auto 0;text-align:center;color:var(--dim2);padding:10px 18px}
.ai-empty .big{font-size:26px;margin-bottom:8px;opacity:.75}
.ai-empty h4{margin:0 0 5px;color:#cfd8e8;font-size:12.5px;font-weight:600}
.ai-empty p{margin:0;font-size:11px;line-height:1.55}
.msg{max-width:92%;padding:7px 10px;border-radius:9px;font-size:11.5px;line-height:1.5;
  white-space:pre-wrap;word-break:break-word;animation:in .16s ease-out}
@keyframes in{from{opacity:0;transform:translateY(3px)}}
.msg.user{align-self:flex-end;background:linear-gradient(180deg,#3556a8,#2b4587);color:#f0f4ff;
  border-bottom-right-radius:3px}
.msg.bot{align-self:flex-start;background:var(--elev);border:1px solid var(--line);color:#c7d1e2;
  border-bottom-left-radius:3px}
.msg.bot.work{color:var(--dim)}
.msg time{display:block;font:8.5px var(--mono);color:rgba(255,255,255,.38);margin-top:3px}
.ai-run{flex:none;margin:0 10px 8px;border:1px solid var(--line);border-radius:7px;background:var(--well);
  overflow:hidden;max-height:150px;display:flex;flex-direction:column}
.ai-run.hidden{display:none!important}
.ai-run-h{height:24px;display:flex;align-items:center;gap:6px;padding:0 8px;border-bottom:1px solid var(--line);
  font:9px var(--mono);letter-spacing:.6px;color:var(--dim2);text-transform:uppercase}
.ai-run-h .grow{flex:1}
.ai-run pre{margin:0;padding:6px 8px;overflow:auto;font:9.5px/1.5 var(--mono);color:#9fb0c7;
  white-space:pre-wrap;word-break:break-word}
.ai-skills{display:flex;flex-wrap:wrap;align-items:center;gap:5px;padding:0 10px 7px;flex:none}
.ai-skills-label{font:8.5px var(--mono);letter-spacing:.8px;text-transform:uppercase;color:var(--dim2)}
.ai-skill-tag{border:1px solid rgba(167,139,250,.45);background:rgba(167,139,250,.12);color:#c9b8ff;
  border-radius:99px;padding:2px 7px;font:9.5px var(--mono);transition:.13s}
.ai-skill-tag:hover{border-color:var(--danger);color:#ffc7ce;background:rgba(255,107,122,.1)}
.chips{display:flex;flex-wrap:wrap;gap:5px;padding:0 10px 8px;flex:none}
.chip{border:1px solid var(--line);background:rgba(21,25,34,.8);color:var(--dim);border-radius:99px;
  padding:3px 8px;font-size:9.5px;transition:.13s}
.chip:hover{border-color:rgba(91,140,255,.55);color:var(--acc2);background:rgba(91,140,255,.08)}
.compose{padding:0 10px 8px;flex:none}
.compose-box{border:1px solid var(--line2);background:var(--well);border-radius:9px;padding:6px;
  transition:border-color .14s}
.compose-box:focus-within{border-color:rgba(91,140,255,.7);box-shadow:0 0 0 2px rgba(91,140,255,.12)}
#aiPrompt{width:100%;min-height:52px;max-height:130px;resize:none;background:none;border:0;outline:0;
  font-size:11.5px;line-height:1.5}
.compose-foot{display:flex;align-items:center;gap:6px;margin-top:3px}
.compose-foot .hint{font:8.5px var(--mono);color:var(--dim2);flex:1;line-height:1.3}
#aiSend{padding:4px 10px;font-size:11px}
.ai-foot{padding:0 12px 10px;font-size:9.5px;line-height:1.45;color:var(--dim2);flex:none}
.ai-foot b{color:var(--dim)}

/* --------------------------------------------------------------- modals */
.backdrop{position:fixed;inset:0;background:rgba(4,6,10,.72);backdrop-filter:blur(3px);z-index:60;
  display:grid;place-items:center;padding:24px;animation:fade .14s}
@keyframes fade{from{opacity:0}}
.modal{width:min(620px,100%);max-height:calc(100vh - 48px);overflow:auto;background:#12161d;
  border:1px solid var(--line2);border-radius:13px;box-shadow:0 26px 90px rgba(0,0,0,.65);
  animation:pop .16s ease-out}
@keyframes pop{from{transform:translateY(7px) scale(.99);opacity:0}}
.m-head{display:flex;align-items:center;gap:10px;padding:15px 18px 11px;border-bottom:1px solid var(--line)}
.m-head h2{margin:0;font-size:14px;font-weight:650}
.m-head p{margin:2px 0 0;font-size:10.5px;color:var(--dim2)}
.m-head .grow{flex:1}
.m-x{width:26px;height:26px;border:1px solid transparent;background:transparent;color:var(--dim);border-radius:6px;
  display:grid;place-items:center}
.m-x:hover{background:var(--elev);color:var(--fg);border-color:var(--line)}
.m-body{padding:15px 18px}
.m-foot{display:flex;align-items:center;gap:8px;padding:11px 18px;border-top:1px solid var(--line);
  background:#0f1218;position:sticky;bottom:0}
.m-foot .grow{flex:1}
.drop{border:1.5px dashed var(--line2);border-radius:10px;padding:20px;text-align:center;color:var(--dim);
  transition:.16s;background:var(--well)}
.drop.hot{border-color:var(--acc);background:rgba(91,140,255,.07);color:var(--fg)}
.drop b{color:#cfd8e8}
.drop .small{font-size:10.5px;color:var(--dim2);margin-top:3px}
.field{display:flex;flex-direction:column;gap:5px;margin-top:11px}
.field label{font-size:10px;color:var(--dim);letter-spacing:.5px;text-transform:uppercase;font-weight:650}
.field input{height:33px;border:1px solid var(--line);background:var(--well);border-radius:7px;
  padding:0 9px;outline:0;font-size:12px}
.field input:focus{border-color:rgba(91,140,255,.7)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.checks{display:grid;grid-template-columns:1fr 1fr;gap:7px 14px;margin-top:13px}
.checks label{display:flex;align-items:center;gap:7px;font-size:11.5px;color:#c2ccdc;cursor:pointer}
.checks input{accent-color:var(--acc);width:13px;height:13px}
.wmrow{grid-column:1/-1;display:flex;align-items:center;gap:7px}
.wmrow input[type=text]{flex:1;height:28px;border:1px solid var(--line);background:var(--well);
  border-radius:6px;padding:0 8px;font-size:10.5px;outline:0;font-family:var(--mono)}
.note{margin-top:11px;color:var(--dim2);font-size:10.5px;line-height:1.55;border-left:2px solid var(--line2);
  padding-left:9px}
.msgline{margin-top:9px;color:var(--warn);font-size:11.5px;min-height:16px}
.checklist-h{font-size:10px;letter-spacing:1px;text-transform:uppercase;color:var(--dim);font-weight:700;
  margin:16px 0 0}

/* toasts */
.toasts{position:fixed;right:16px;bottom:16px;display:flex;flex-direction:column;gap:7px;z-index:80;
  max-width:340px;pointer-events:none}
.toast{background:#171c26;border:1px solid var(--line2);border-left:3px solid var(--acc);border-radius:7px;
  padding:8px 11px;font-size:11.5px;color:#d7dfee;box-shadow:0 8px 30px rgba(0,0,0,.5);
  animation:in .16s ease-out;pointer-events:auto}
.toast.ok{border-left-color:var(--ok)}
.toast.warn{border-left-color:var(--warn)}
.toast.err{border-left-color:var(--danger)}

/* skills */
.modal.wide{width:min(880px,100%)}
.skills-layout{display:grid;grid-template-columns:236px minmax(0,1fr);gap:14px;min-height:420px}
.skills-side{display:flex;flex-direction:column;gap:8px;min-height:0;padding-right:12px;
  border-right:1px solid var(--line)}
.skills-toolbar{display:flex;gap:6px}
.skills-toolbar input{flex:1;min-width:0;height:30px;border:1px solid var(--line);background:var(--well);
  border-radius:7px;padding:0 8px;outline:0;font-size:11px}
.skills-toolbar input:focus{border-color:rgba(91,140,255,.7)}
.skills-list{flex:1;overflow:auto;display:flex;flex-direction:column;gap:4px;max-height:430px;min-height:80px}
.skill-row{text-align:left;border:1px solid transparent;background:transparent;border-radius:7px;
  padding:7px 8px;color:var(--fg);transition:.12s}
.skill-row:hover{background:var(--elev);border-color:var(--line)}
.skill-row.sel{background:rgba(91,140,255,.1);border-color:rgba(91,140,255,.45)}
.skill-row-h{display:flex;align-items:center;gap:6px}
.skill-row b{font-size:11px;font-weight:620;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.skill-row p{margin:3px 0 0;font-size:10px;line-height:1.4;color:var(--dim2);
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.src{font:8px var(--mono);letter-spacing:.4px;text-transform:uppercase;border:1px solid var(--line);
  border-radius:99px;padding:0 4px;color:var(--dim2);flex:none;margin-left:auto}
.src.user{color:var(--ok);border-color:rgba(61,220,151,.4)}
.src.project{color:var(--warn);border-color:rgba(242,184,75,.4)}
.skills-dirs{font:8.5px/1.45 var(--mono);color:var(--dim2);word-break:break-all;flex:none;
  border-top:1px solid var(--line);padding-top:7px}
.skills-editor{min-width:0;min-height:0;display:flex;flex-direction:column}
.skills-placeholder{margin:auto 0;text-align:center;color:var(--dim2);padding:40px 20px;max-width:360px}
.skills-placeholder .big{font-size:24px;opacity:.7;margin-bottom:7px}
.skills-placeholder b{display:block;color:#cfd8e8;font-size:13px;margin-bottom:5px}
.skills-placeholder p{margin:0;font-size:11px;line-height:1.55}
.skill-form-head{display:flex;align-items:center;gap:8px;margin-bottom:2px}
#skillSource.user{color:var(--ok);border-color:rgba(61,220,151,.4)}
#skillSource.project{color:var(--warn);border-color:rgba(242,184,75,.4)}
.skill-path{font:9px var(--mono);color:var(--dim2);white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;min-width:0}
.skill-form .field{margin-top:8px}
.skill-form .field textarea{min-height:230px;max-height:46vh;resize:vertical;border:1px solid var(--line);
  background:var(--well);border-radius:7px;padding:8px 9px;outline:0;font:11px/1.55 var(--mono);color:#cbd6e6}
.skill-form .field textarea:focus{border-color:rgba(91,140,255,.7)}
.skill-actions{display:flex;align-items:center;gap:7px;margin-top:10px;flex-wrap:wrap}
.skill-actions .grow{flex:1}
.skill-msg{margin-top:7px;color:var(--warn);font-size:11px;min-height:15px}
.skills-empty{padding:12px 6px;color:var(--dim2);font-size:11px;text-align:center}
@media (max-width:760px){
  .skills-layout{grid-template-columns:1fr}
  .skills-side{border-right:0;border-bottom:1px solid var(--line);padding:0 0 10px;min-height:0}
  .skills-list{max-height:170px}
  .skills-editor{min-height:300px}
}

/* vision panel */
.vision-tools{display:flex;align-items:center;gap:6px;padding:0 10px 6px}
.vision-model{display:flex;align-items:center;gap:4px;font-size:9.5px;color:var(--dim);
  cursor:pointer;user-select:none;white-space:nowrap}
.vision-model input{accent-color:var(--acc);width:12px;height:12px}
.vision-foot{gap:6px}
.vres{display:flex;flex-direction:column;gap:5px;padding:0 10px 10px}
.vrow{display:flex;gap:8px;align-items:center;border:1px solid var(--line);
  background:var(--panel2);border-radius:8px;padding:5px 7px;cursor:pointer;
  transition:border-color .12s,transform .12s}
.vrow:hover{border-color:#3b475a;transform:translateY(-1px)}
.vrow img{width:76px;height:44px;object-fit:cover;border-radius:5px;background:#000;flex:none}
.vrow img.noph{opacity:.35}
.vmeta{min-width:0;text-align:left}
.vtop{display:flex;gap:6px;align-items:baseline;font-size:11px}
.vtop b{color:var(--fg)}
.vscore{font-size:9.5px;color:var(--dim2)}
.vtext{font-size:10px;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.vtags{font-size:9.5px;color:var(--dim2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.vhead{font-size:10.5px;color:var(--dim);padding:2px 2px 0}
.vrun{font-size:10.5px;color:var(--dim);padding:6px 2px}

/* responsive */
@media (max-width:1240px){.layout{grid-template-columns:250px minmax(0,1fr) 300px}
  .assets{grid-template-columns:1fr 1fr}.asset .aname{font-size:10px}}
@media (max-width:1160px){
  .transport #btnBackFrame,.transport #btnFwdFrame,.transport .vol,
  .transport #btnFit,.transport #btnDownload{display:none}
  .transport .status-chip{max-width:130px}
}
@media (max-width:1020px){.layout{grid-template-columns:230px minmax(0,1fr) 280px}
  .brand span{display:none}
  .rows{gap:3px}
  .row{font-size:10.5px}
  .row .v{font-size:10px}
  .assets{grid-template-columns:1fr;gap:4px;padding:0 8px 10px}
  .asset{display:grid;grid-template-columns:58px minmax(0,1fr);grid-template-rows:1fr 1fr;
    column-gap:7px;align-items:center;padding:3px}
  .athumb{grid-row:1/3;width:58px;aspect-ratio:16/10;border-radius:5px}
  .asset .aname{padding:0;align-self:end;font-size:10.5px}
  .asset .ameta{padding:0;align-self:start}
  .transport .status-chip{display:none}
  .transport .tsep{display:none}
  .transport{gap:7px;padding:0 10px}
  .mon-head{padding:0 10px}
  .tag{font-size:9px;padding:0 4px}
}
@media (max-width:860px){.layout{grid-template-columns:minmax(0,1fr) 280px}.col.left{display:none}}
@media (max-width:700px){.layout{grid-template-columns:1fr}.col.right{display:none}}
"""
