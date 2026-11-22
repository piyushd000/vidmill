"""Markup for the vidmill studio editor."""

BODY = r"""
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
<symbol id="i-play" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" fill="currentColor"/></symbol>
<symbol id="i-pause" viewBox="0 0 24 24"><path d="M7 5h4v14H7zM13 5h4v14h-4z" fill="currentColor"/></symbol>
<symbol id="i-back" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6l-8 6 8 6M6 5v14"/></g></symbol>
<symbol id="i-fwd" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l8 6-8 6M18 5v14"/></g></symbol>
<symbol id="i-vol" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5L6 9H3v6h3l5 4zM15 9a4 4 0 010 6M18 6a8 8 0 010 12"/></g></symbol>
<symbol id="i-mute" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5L6 9H3v6h3l5 4zM17 9l4 6M21 9l-4 6"/></g></symbol>
<symbol id="i-expand" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/></g></symbol>
<symbol id="i-download" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 17v3h16v-3"/></g></symbol>
<symbol id="i-plus" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></g></symbol>
<symbol id="i-gear" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 00.3 1.9l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.9-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.9.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.9 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.9l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.9.3H11a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.9-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.9V11a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z"/></g></symbol>
<symbol id="i-search" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></g></symbol>
<symbol id="i-chev" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></g></symbol>
<symbol id="i-x" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></g></symbol>
<symbol id="i-stop" viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/></symbol>
<symbol id="i-fit" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></g></symbol>
<symbol id="i-zin" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><path d="M12 6v12M6 12h12"/></g></symbol>
<symbol id="i-zout" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><path d="M6 12h12"/></g></symbol>
<symbol id="i-folder" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2z"/></g></symbol>
<symbol id="i-import" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v11m0 0l-4-4m4 4l4-4M4 19h16"/></g></symbol>
<symbol id="i-film" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4"/></g></symbol>
<symbol id="i-spark" viewBox="0 0 24 24"><path d="M12 2l1.9 5.7L20 9.6l-5.4 2.6L13 18l-1.9-5.8L5 9.6l5.4-1.9z" fill="currentColor"/><path d="M18.5 15l.9 2.6 2.6.9-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9z" fill="currentColor" opacity=".7"/></symbol>
</defs></svg>

<div class="app">
  <header class="topbar">
    <div class="brand"><div class="mark">v</div><b>vidmill</b><span>studio</span></div>
    <div class="sep"></div>
    <div class="crumbwrap"><span class="dim">Projects /</span><span id="jobTitle">No project</span></div>
    <div class="tstate" id="topState"><i class="dot" id="topDot"></i><span id="topStateText">idle</span></div>
    <div class="top-actions">
      <button class="btn" id="btnNew"><svg class="icon"><use href="#i-plus"/></svg>New project</button>
      <button class="btn" id="btnSettings"><svg class="icon"><use href="#i-gear"/></svg>Edit settings</button>
      <a class="btn primary" id="btnExport" download><svg class="icon"><use href="#i-download"/></svg>Export</a>
    </div>
  </header>

  <div class="layout">
    <aside class="col left">
      <section class="panel bin">
        <div class="ph">Media bin <span class="count" id="assetCount">0</span><span class="grow"></span>
          <button class="phbtn" id="btnImport" title="Import video, audio or image"><svg class="icon"><use href="#i-import"/></svg></button>
        </div>
        <div class="bin-tools">
          <div class="search"><svg class="icon"><use href="#i-search"/></svg>
            <input id="assetSearch" placeholder="Search media" autocomplete="off"></div>
          <div class="filters" id="assetFilters">
            <button data-filter="all" class="on">All</button>
            <button data-filter="video">Video</button>
            <button data-filter="audio">Audio</button>
            <button data-filter="image">Images</button>
          </div>
        </div>
        <div class="panel-body"><div class="assets" id="assetGrid"></div>
          <div class="bin-empty hidden" id="binEmpty">No media matches this view.</div></div>
        <input type="file" id="assetFile" accept="video/*,audio/*,image/*" multiple hidden>
      </section>

      <section class="panel inspector">
        <div class="ph">Project <span class="grow"></span><span class="tag" id="insBadge">—</span></div>
        <div class="rows">
          <div class="row"><span class="k">Source</span><span class="v" id="insSource">—</span></div>
          <div class="row"><span class="k">Resolution</span><span class="v" id="insRes">—</span></div>
          <div class="row"><span class="k">Frame rate</span><span class="v" id="insFps">—</span></div>
          <div class="row"><span class="k">Source length</span><span class="v" id="insDur">—</span></div>
          <div class="row"><span class="k">Sequence</span><span class="v" id="insSeq">—</span></div>
          <div class="row"><span class="k">Source size</span><span class="v" id="insSize">—</span></div>
          <div class="row"><span class="k">Created</span><span class="v" id="insCreated">—</span></div>
          <div class="row"><span class="k">Current output</span><span class="v acc" id="insOut">—</span></div>
        </div>
        <div class="ins-foot"><button class="btn sm" id="btnOpenFolder"><svg class="icon"><use href="#i-folder"/></svg>Job folder</button>
          <button class="btn sm" id="btnRestart"><svg class="icon"><use href="#i-gear"/></svg>Re-run</button></div>
      </section>

      <section class="panel projects">
        <div class="ph">Projects <span class="count" id="projectCount">0</span><span class="grow"></span>
          <button class="phbtn" id="btnNewProject" title="New project"><svg class="icon"><use href="#i-plus"/></svg></button></div>
        <div class="plist" id="projectList"></div>
      </section>
    </aside>

    <main class="col center">
      <section class="monitor">
        <div class="mon-head">
          <div class="mon-title"><span id="monMode">Program</span> · <b id="monName">No clip</b></div>
          <div class="mon-badge"><span class="tag" id="tagRes">—</span><span class="tag" id="tagFps">—</span><span class="tag" id="tagAudio">—</span></div>
        </div>
        <div class="stage" id="stage">
          <div class="empty-stage" id="emptyStage">
            <div class="empty-logo">▸</div>
            <h3>Your edit lands here</h3>
            <p>Drop a video and the free local pass removes pauses, still frames, retakes and watermarks, burns captions and cleans the audio. No AI, no key, no upload.</p>
            <button class="btn primary drop-mini" id="btnNew2"><svg class="icon"><use href="#i-plus"/></svg>New project</button>
          </div>
          <div class="screen hidden" id="screen">
            <video id="monitor" playsinline></video>
            <div class="preview-flag hidden" id="previewFlag"><span id="previewName">Preview</span><button class="btn sm ghost" id="btnUseCurrent">Current</button></div>
          </div>
        </div>
        <div class="transport">
          <button class="tbtn" id="btnBackFrame" title="Previous frame (←)"><svg class="icon"><use href="#i-back"/></svg></button>
          <button class="tbtn play" id="btnPlay" title="Play / pause (space)"><svg class="icon"><use href="#i-play"/></svg></button>
          <button class="tbtn" id="btnFwdFrame" title="Next frame (→)"><svg class="icon"><use href="#i-fwd"/></svg></button>
          <div class="tc"><span id="tcCur">00:00:00:00</span> <span class="tot">/ <span id="tcTot">00:00:00:00</span></span></div>
          <input type="range" class="progress" id="progress" min="0" max="1000" value="0" aria-label="Seek">
          <div class="vol"><button class="tbtn" id="btnMute" title="Mute"><svg class="icon"><use href="#i-vol"/></svg></button>
            <input type="range" id="vol" min="0" max="100" value="100" aria-label="Volume"></div>
          <div class="tsep"></div>
          <div class="status-chip" id="statusChip"><i class="dot" id="chipDot"></i><span id="chipText">No project open</span></div>
          <button class="tbtn" id="btnCancelRun" title="Cancel the running edit" disabled><svg class="icon"><use href="#i-stop"/></svg></button>
          <button class="tbtn" id="btnDownload" title="Download current cut" disabled><svg class="icon"><use href="#i-download"/></svg></button>
          <button class="tbtn" id="btnFit" title="Fit preview"><svg class="icon"><use href="#i-fit"/></svg></button>
          <button class="tbtn" id="btnFullscreen" title="Fullscreen"><svg class="icon"><use href="#i-expand"/></svg></button>
        </div>
      </section>

      <section class="timeline" id="timelinePanel">
        <div class="tl-resize" id="tlResize" title="Drag to resize the timeline"></div>
        <div class="tl-head">
          <svg class="icon" style="color:var(--dim2)"><use href="#i-film"/></svg>
          <span class="tl-title">Timeline</span><span class="tl-sub" id="tlName">no sequence</span>
          <div class="tl-tools"><span class="tag" id="tlDur">—</span>
            <button class="zbtn" id="btnZoomOut" title="Zoom out"><svg class="icon"><use href="#i-zout"/></svg></button>
            <input type="range" id="zoom" min="20" max="420" value="110" aria-label="Timeline zoom">
            <button class="zbtn" id="btnZoomIn" title="Zoom in"><svg class="icon"><use href="#i-zin"/></svg></button>
            <button class="zbtn" id="btnZoomFit" title="Fit timeline"><svg class="icon"><use href="#i-fit"/></svg></button>
          </div>
        </div>
        <div class="tl-body">
          <div class="tl-labels">
            <div class="lbl ruler-lbl">TC</div>
            <div class="lbl v1"><span class="tag">V1</span>Video</div>
            <div class="lbl ov"><span class="tag">OV</span>Overlay</div>
            <div class="lbl c1"><span class="tag">C1</span>Captions</div>
            <div class="lbl a1"><span class="tag">A1</span>Audio</div>
          </div>
          <div class="tl-scroll" id="tlScroll">
            <div class="tl-inner" id="tlInner">
              <div class="ruler" id="ruler"></div>
              <div class="track v1" id="trVideo"></div>
              <div class="track ov" id="trOverlay"></div>
              <div class="track c1" id="trCaptions"></div>
              <div class="track a1" id="trAudio"></div>
              <div class="playhead hidden" id="playhead"></div>
              <div class="tl-hint" id="tlHint">Open a project to see its timeline</div>
            </div>
          </div>
        </div>
      </section>

      <section class="activity collapsed" id="activity">
        <div class="act-head" id="actHead"><svg class="icon chev" style="width:12px;height:12px"><use href="#i-chev"/></svg>
          Activity <span class="live" id="actLive">idle</span><span class="grow"></span><span class="live" id="actSize"></span></div>
        <pre class="log" id="log"></pre>
      </section>
    </main>

    <aside class="col right">
      <div class="ai-head"><div class="ai-orb">✦</div>
        <div><b>AI editor</b><small id="aiModel">not connected</small></div>
        <div class="grow"></div>
        <button class="skill-btn" id="btnSkills" title="Browse, edit and attach editing skills">Skills <b id="skillCount">0</b></button>
        <span class="dot" id="aiDot"></span></div>
      <div class="ai-feed" id="aiFeed">
        <div class="ai-empty" id="aiEmpty"><div class="big">✦</div>
          <h4>Custom edits, in words</h4>
          <p>The AI can call any vidmill tool — trim, captions, overlays, music, HyperFrames, export. Skills are reusable recipes it can load when they match. It only runs when you ask.</p></div>
      </div>
      <div class="ai-run hidden" id="aiRun">
        <div class="ai-run-h">Run output <span class="grow"></span><span id="aiRunState">idle</span></div>
        <pre id="aiLog"></pre>
      </div>
      <div class="ai-skills hidden" id="aiSkills"></div>
      <div class="chips" id="aiChips">
        <button class="chip" data-prompt="Cut the pause at the beginning of the video.">Trim the start</button>
        <button class="chip" data-prompt="Remove the watermark from this video.">Remove watermark</button>
        <button class="chip" data-prompt="Add my logo at the top-right corner, scaled to 18% and 90% opacity.">Add a logo</button>
        <button class="chip" data-prompt="Make the captions larger and easier to read.">Bigger captions</button>
        <button class="chip" data-prompt="Add a quiet background music bed under the whole video.">Add music</button>
      </div>
      <div class="compose"><div class="compose-box">
        <textarea id="aiPrompt" placeholder="Tell the AI what to change — it can call any vidmill tool…"></textarea>
        <div class="compose-foot"><span class="hint" id="aiKeyHint">Optional · only runs when you ask</span>
          <button class="btn primary" id="aiSend">Ask AI</button></div>
      </div></div>
      <div class="ai-foot" id="aiHint">The free pass is deterministic and local. AI edits are optional and send only text and tool results.</div>
    </aside>
  </div>
</div>

<div class="backdrop hidden" id="modalNew">
  <div class="modal" role="dialog" aria-modal="true" aria-label="New project">
    <div class="m-head"><div><h2>New project</h2><p>Drop a video — the free local edit starts immediately.</p></div>
      <div class="grow"></div><button class="m-x" data-close="modalNew" title="Close"><svg class="icon"><use href="#i-x"/></svg></button></div>
    <div class="m-body">
      <div class="drop" id="drop"><b>Drop a video here</b>
        <div class="small">MP4, MOV, MKV, WebM, M4V or AVI · stays on this machine</div>
        <div id="picked" class="small" style="color:var(--acc2);margin-top:5px"></div>
        <label class="btn sm" style="margin-top:9px">Browse<input type="file" id="file" accept="video/*" hidden></label></div>
      <div class="grid2">
        <div class="field"><label>or a path on this machine</label><input id="path" placeholder="/home/you/clip.mp4" autocomplete="off"></div>
        <div class="field"><label>Project name</label><input id="jobname" placeholder="optional" autocomplete="off"></div>
      </div>
      <div class="checklist-h">Free local pass · all included</div>
      <div class="checks">
        <label><input type="checkbox" id="n_silences" checked> Remove silences</label>
        <label><input type="checkbox" id="n_still" checked> Remove still frames</label>
        <label><input type="checkbox" id="n_mistakes" checked> Remove retakes</label>
        <label><input type="checkbox" id="n_captions" checked> Burn captions</label>
        <label><input type="checkbox" id="n_clean" checked> Clean audio</label>
        <div class="wmrow"><label><input type="checkbox" id="n_watermark" checked> Remove watermark</label>
          <input type="text" id="n_wmregion" placeholder="auto-detect or X:Y:W:H"></div>
      </div>
      <div class="note">Every non-AI step runs in this pass. Nothing is uploaded, no key is needed, and the edit starts as soon as the video is in.</div>
      <div class="msgline" id="msg"></div>
    </div>
    <div class="m-foot"><span class="grow"></span><button class="btn" data-close="modalNew">Cancel</button>
      <button class="btn primary" id="go" disabled>Upload &amp; edit</button></div>
  </div>
</div>

<div class="backdrop hidden" id="modalSettings">
  <div class="modal" role="dialog" aria-modal="true" aria-label="Edit settings">
    <div class="m-head"><div><h2>Edit settings</h2><p id="setSub">Free local pass for this project.</p></div>
      <div class="grow"></div><button class="m-x" data-close="modalSettings" title="Close"><svg class="icon"><use href="#i-x"/></svg></button></div>
    <div class="m-body">
      <div class="checks" style="margin-top:2px">
        <label><input type="checkbox" id="d_silences" checked> Remove silences</label>
        <label><input type="checkbox" id="d_still" checked> Remove still frames</label>
        <label><input type="checkbox" id="d_mistakes" checked> Remove retakes</label>
        <label><input type="checkbox" id="d_captions" checked> Burn captions</label>
        <label><input type="checkbox" id="d_clean" checked> Clean audio</label>
        <div class="wmrow"><label><input type="checkbox" id="d_watermark" checked> Remove watermark</label>
          <input type="text" id="d_wmregion" placeholder="auto-detect or X:Y:W:H"></div>
      </div>
      <div class="note">Re-running resets this project's outputs and starts again from the original source. The source file is never modified.</div>
      <div class="msgline" id="setMsg"></div>
    </div>
    <div class="m-foot"><button class="btn danger" id="cancelRun">Cancel run</button><span class="grow"></span>
      <button class="btn" data-close="modalSettings">Close</button>
      <button class="btn primary" id="run">Apply &amp; re-run</button></div>
  </div>
</div>

<div class="backdrop hidden" id="modalSkills">
  <div class="modal wide" role="dialog" aria-modal="true" aria-label="Editing skills">
    <div class="m-head"><div><h2>Skills</h2><p>Reusable recipes the AI loads on demand. Bundled skills can be overridden; edits are stored as plain Markdown.</p></div>
      <div class="grow"></div><button class="m-x" data-close="modalSkills" title="Close"><svg class="icon"><use href="#i-x"/></svg></button></div>
    <div class="m-body">
      <div class="skills-layout">
        <div class="skills-side">
          <div class="skills-toolbar"><input id="skillSearch" placeholder="Search skills" autocomplete="off"><button class="btn sm" id="skillNew">New</button></div>
          <div class="skills-list" id="skillList"></div>
          <div class="skills-dirs" id="skillDirs"></div>
        </div>
        <div class="skills-editor">
          <div class="skills-placeholder" id="skillPlaceholder"><div class="big">✦</div>
            <b>Pick a skill</b>
            <p>Read the instructions, tweak them for your workflow, or start a new skill. Attach up to four skills to an AI request with <em>Use in AI</em>.</p></div>
          <div class="skill-form hidden" id="skillForm">
            <div class="skill-form-head"><span class="tag" id="skillSource">bundled</span><span class="skill-path" id="skillPath"></span></div>
            <div class="field"><label>Name</label><input id="skillName" placeholder="my-house-style" autocomplete="off" spellcheck="false"></div>
            <div class="field"><label>When to use it</label><input id="skillDesc" placeholder="One line that tells the AI when this skill applies" autocomplete="off"></div>
            <div class="field"><label>Tags</label><input id="skillTags" placeholder="cut, captions, social" autocomplete="off"></div>
            <div class="field"><label>Instructions · Markdown</label><textarea id="skillBody" spellcheck="false" placeholder="# My skill&#10;&#10;When to use...&#10;&#10;## Steps&#10;..."></textarea></div>
            <div class="skill-actions">
              <button class="btn sm" id="skillUse">Use in AI</button>
              <button class="btn sm" id="skillDelete">Delete skill</button>
              <span class="grow"></span>
              <button class="btn sm" id="skillReset">Reset to bundled</button>
              <button class="btn primary sm" id="skillSave">Save</button>
            </div>
            <div class="skill-msg" id="skillMsg"></div>
          </div>
        </div>
      </div>
    </div>
    <div class="m-foot"><span class="hint" id="skillFoot">Bundled skills ship with vidmill. Saving an edit creates or updates a user override; the bundled file is never changed.</span><span class="grow"></span>
      <button class="btn" data-close="modalSkills">Close</button></div>
  </div>
</div>

<div class="toasts" id="toasts"></div>
"""
