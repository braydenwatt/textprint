/* Textprint browser app — the import + narration logic for the live phone shell.
   Loaded after the report's app script (render.py). It renders the import UI into
   the Settings app (#importmount), runs the whole pipeline in the browser via
   Pyodide, populates APPS in place, and streams the AI reads from the proxy by
   calling the shell's TP_UPDATE / TP_HL / TP_MEM directly. */
(function(){
  const PYODIDE_URL="https://cdn.jsdelivr.net/pyodide/v0.26.2/full/";
  let pyodide=null, ready=null;
  const LS=k=>localStorage.getItem("tp_"+k)||"";
  const setLS=(k,v)=>localStorage.setItem("tp_"+k,v);
  const $=id=>document.getElementById(id);

  // ---- cache the built report so a return visit needs no re-upload ----
  const CACHE_KEY="tp_report", CACHE_VER=1;
  let cacheFull=false;   // true once cached; used to warn on quota
  function saveCache(){
    try{ localStorage.setItem(CACHE_KEY, JSON.stringify({v:CACHE_VER, name:APP.name, apps:APPS}));
         cacheFull=false; return true; }
    catch(e){ cacheFull=true; console.warn("cache save failed (probably quota)", e); return false; }
  }
  function loadCache(){
    try{ const raw=localStorage.getItem(CACHE_KEY); if(!raw)return null; const j=JSON.parse(raw);
         return (j&&j.v===CACHE_VER&&j.apps&&j.apps.length)?j:null; }
    catch(e){ return null; }
  }
  function clearCache(){ localStorage.removeItem(CACHE_KEY); }
  function restoreCache(){
    const j=loadCache(); if(!j) return false;
    APP.name=j.name||"You"; APPS.length=0; j.apps.forEach(a=>APPS.push(a));
    window.TP_NARRATING=false; window.showHome(); return true;
  }

  function prog(pct,msg){ const b=$("tp_bar"), s=$("tp_step"); if(b&&pct!=null)b.style.width=pct+"%"; if(s&&msg!=null&&msg!=="")s.textContent=msg; }

  async function checkHost(){
    const el=$("tp_proxy"); const url=(el?el.value.trim():"")||LS("proxy");
    const pill=$("tp_hstat"), msg=$("tp_hmsg");
    const set=(c,t,m)=>{ if(pill){pill.className="ipill "+c;pill.textContent=t;} if(m&&msg)msg.textContent=m; };
    if(!url){ set("wait","not set","No host — you still get every stat, just no AI reads."); return false; }
    try{ const r=await fetch(url.replace(/\/$/,"")+"/health"); const j=await r.json();
      if(j.ok){ set("ok","online","Model "+j.model+" · queue "+j.inflight+"/"+j.max_queue); return true; }
      set("bad","error", j.status||"model not ready"); return false;
    }catch(e){ set("bad","offline","Couldn’t reach the host — reads skipped."); return false; }
  }

  async function boot(){ if(ready) return ready; ready=(async()=>{
    prog(6,"loading the Python engine (~6 MB, one-time)…");
    pyodide=await loadPyodide({indexURL:PYODIDE_URL});
    try{ prog(12,"loading the sentiment model…"); await pyodide.loadPackage("micropip");
         await pyodide.runPythonAsync("import micropip\nawait micropip.install('vaderSentiment')"); }
    catch(e){ console.warn("vaderSentiment unavailable", e); }
    prog(18,"loading the analysis engine…");
    const manifest=await (await fetch("pysrc/manifest.json")).json();
    pyodide.runPython("import sys,os\nos.makedirs('/app/textprint/parsers',exist_ok=True)\nif '/app' not in sys.path: sys.path.insert(0,'/app')");
    for(const rel of manifest){ const code=await (await fetch("pysrc/"+rel)).text(); pyodide.FS.writeFile("/app/"+rel, code); }
    pyodide.runPython(
      "import json, textprint.webbuild as wb\n"+
      "def _run(tj, name, md):\n"+
      "    threads=[(t['folder'], t['data']) for t in json.loads(tj)]\n"+
      "    return json.dumps(wb.build_ig(threads, name=name or 'You', min_date=(md or None)), ensure_ascii=False)\n");
  })(); return ready; }

  const RE=/messages\/inbox\/([^\/]+)\/message_(\d+)\.json$/;
  async function extractThreads(blob){
    const zip=await JSZip.loadAsync(blob);
    const files=Object.values(zip.files).filter(f=>!f.dir && RE.test(f.name));
    if(!files.length) throw new Error("No Instagram messages in that ZIP — export Messages in JSON format.");
    const byF={}; let n=0;
    for(const f of files){ const folder=f.name.match(RE)[1]; const data=JSON.parse(await f.async("string"));
      if(!byF[folder]) byF[folder]={...data, messages:[...(data.messages||[])]};
      else byF[folder].messages.push(...(data.messages||[]));
      if(++n%20===0) prog(20+Math.min(15,n/files.length*15), "reading threads… "+n+"/"+files.length);
    }
    return Object.entries(byF).map(([folder,data])=>({folder,data}));
  }

  async function callProxy(job){
    const url=LS("proxy").replace(/\/$/,""); const tok=LS("token");
    const h={"Content-Type":"application/json"}; if(tok) h["Authorization"]="Bearer "+tok;
    for(let a=0;a<4;a++){ const r=await fetch(url+"/complete",{method:"POST",headers:h,
      body:JSON.stringify({system:job.system,prompt:job.prompt,temperature:job.temperature,max_tokens:job.max_tokens})});
      if(r.status===429){ await new Promise(z=>setTimeout(z,(+r.headers.get("Retry-After")||20)*1000)); continue; }
      if(!r.ok) throw new Error("host "+r.status); return (await r.json()).text; }
    throw new Error("host busy");
  }
  function parseHL(raw){ const o=[]; raw.split("\n").forEach(l=>{ if(l.indexOf("||")<0)return; const p=l.split("||"); const num=(p[0].match(/\d+/)||[])[0]; if(num!=null) o.push([+num, p.slice(1).join("||").trim().replace(/^"|"$/g,"").slice(0,44)]); }); return o.slice(0,3); }
  function parseMem(raw){ const o={}; raw.split("\n").forEach(l=>{ const i=l.indexOf("||"); if(i<0)return; const nm=l.slice(0,i).trim().replace(/^[-•\s]+/,"").trim(); if(nm) o[nm]=l.slice(i+2).trim(); }); return o; }
  function deliver(job,text){
    if(job.post==="highlights"){ const items=[]; parseHL(text).forEach(([idx,label])=>{ const m=job.pool&&job.pool[idx]; if(m) items.push({text:m.text,who:m.who,me:m.me,date:m.date,tag:label,react:m.react}); }); window.TP_HL(job.slot,items); }
    else if(job.post==="member_reads"){ window.TP_MEM(job.slot, parseMem(text)); }
    else window.TP_UPDATE(job.slot,text);
  }
  async function narrate(jobs){
    const ok=await checkHost(); if(!ok){ prog(100,"Report ready — no host, so AI reads were skipped."); saveCache(); return; }
    window.TP_NARRATING=true;
    const indep=jobs.filter(j=>!j.dep), dep=jobs.filter(j=>j.dep), results={}; let done=0; const total=jobs.length;
    const tick=()=>prog(80+done/total*20, "writing reads… "+done+"/"+total); tick();
    const queue=[...indep];
    async function worker(){ while(queue.length){ const job=queue.shift();
      try{ const t=await callProxy(job); if(job.slot.kind==="synopsis") results["synopsis"]=t; deliver(job,t);
        for(const d of dep.slice()){ if(results[d.dep]!=null){ dep.splice(dep.indexOf(d),1);
          const jb=Object.assign({},d,{prompt:d.prompt.replace("{{SYNOPSIS}}",results[d.dep])}); try{ deliver(jb, await callProxy(jb)); }catch(e){} done++; tick(); } }
      }catch(e){ if(!job.post) window.TP_UPDATE(job.slot,"The host couldn’t write this one."); }
      done++; tick();
    }}
    await Promise.all([worker(),worker(),worker()]);
    window.TP_NARRATING=false;
    saveCache();   // persist the full report (with reads) for return visits
    prog(100, "Done — "+done+"/"+total+" reads written." + (cacheFull?" (too big to cache)":" Saved — no re-upload next time."));
  }

  async function run(blob){
    try{
      $("tp_stage").style.display="block"; prog(4,"");
      await boot(); prog(20,"unzipping in your browser…");
      const threads=await extractThreads(blob); prog(38,"parsing "+threads.length+" chats + computing every stat locally…");
      await new Promise(r=>setTimeout(r,20));
      pyodide.globals.set("_tj", JSON.stringify(threads));
      pyodide.globals.set("_nm", ($("tp_name")?$("tp_name").value.trim():LS("name")));
      const res=JSON.parse(pyodide.runPython("_run(_tj,_nm,'2023-01-01')"));
      if(res.stats && res.stats.error) throw new Error(res.stats.error);
      APP.name=res.name||"You";
      res.apps.forEach(a=>{ const i=APPS.findIndex(x=>x.id===a.id); if(i>=0) APPS[i]=a; else APPS.push(a); });
      prog(74,"rendering — "+res.stats.people+" people, "+res.stats.groups+" groups.");
      window.openApp("instagram");            // jump into the now-populated app
      await narrate(res.jobs);
    }catch(e){ prog(0,""); const s=$("tp_step"); if(s){ s.innerHTML='<span style="color:#b91c1c;font-weight:700">'+((e&&e.message)||e)+"</span>"; } }
  }

  window.tpMountImport=function(){
    const m=$("importmount"); if(!m) return;
    const have=window.hasData&&window.hasData();
    const dataCard=have?
     ('<div class=card><div class=rowh><h3 class=f>Your data</h3><span class="ipill ok">saved on this device</span></div>'+
      '<div class=legend style="margin:0 0 10px;line-height:1.6">Your report is cached in this browser, so it loads instantly and you don’t need to re-upload. Clearing removes it from this device only.</div>'+
      '<button class="impbtn" id=tp_open>Open Instagram</button> <button class="impbtn sec" id=tp_clear>Clear data</button></div>'):'';
    m.innerHTML= dataCard +
     '<div class=card><div class=rowh><h3 class=f>'+(have?'Re-import':'Import your Instagram')+'</h3><span class="ipill ok">on-device</span></div>'+
      '<div class=legend style="margin:0 0 10px;line-height:1.6">Everything is parsed and analysed in your browser — your export never leaves this device.</div>'+
      '<div class=idrop id=tp_drop><div class=big>📩</div><div class=t>Drop your Instagram export ZIP</div><div class=s>or tap to choose · no need to unzip</div><input type=file id=tp_file accept=".zip,application/zip" hidden></div>'+
      '<div id=tp_stage style="margin-top:10px;display:none"><div class=legend id=tp_step style=margin:0>starting…</div><div class=iprog><i id=tp_bar></i></div></div></div>'+
     '<div class=card><div class=rowh><h3 class=f>Narration host</h3><span class="ipill wait" id=tp_hstat>checking…</span></div>'+
      '<div style=margin-bottom:8px><div class=ilabel>Ollama proxy URL</div><input class=ifield type=url id=tp_proxy placeholder="https://xxxx.trycloudflare.com"></div>'+
      '<div style=margin-bottom:8px><div class=ilabel>Access token (optional)</div><input class=ifield type=password id=tp_token placeholder="if the host set one"></div>'+
      '<div style=margin-bottom:8px><div class=ilabel>Your first name</div><input class=ifield type=text id=tp_name placeholder="e.g. Alex"></div>'+
      '<button class="impbtn sec" id=tp_test>Test host</button> <span class=legend id=tp_hmsg style="margin:0">The stats work without a host — it only writes the AI reads.</span></div>'+
     '<div class=card><div class=rowh><h3 class=f>How to get your export</h3><span class=pill>~ minutes–days</span></div>'+
      '<ol class=steps>'+
       '<li>In the Instagram app, open <b>Settings → Accounts Centre</b>.</li>'+
       '<li>Go to <b>Your information and permissions → Download your information</b>.</li>'+
       '<li>Select <span class="kbd hot">Messages</span> only.</li>'+
       '<li>Set format <span class=kbd>JSON</span> and quality <span class=kbd>Low</span>, then submit.</li>'+
      '</ol>'+
      '<div class=legend style="margin:10px 0 0;line-height:1.55">Instagram emails a ZIP download link — drop it above, no need to unzip.</div></div>';
    ["proxy","token","name"].forEach(k=>{ const el=$("tp_"+k); if(el){ el.value=LS(k); el.addEventListener("change",e=>setLS(k,e.target.value.trim())); } });
    checkHost();
    $("tp_test").addEventListener("click",checkHost);
    const drop=$("tp_drop"), file=$("tp_file"), start=f=>run(f);
    drop.addEventListener("click",()=>file.click());
    file.addEventListener("change",e=>{ if(e.target.files[0]) start(e.target.files[0]); });
    ["dragenter","dragover"].forEach(ev=>drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.add("over");}));
    ["dragleave","drop"].forEach(ev=>drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.remove("over");}));
    drop.addEventListener("drop",e=>{ const f=e.dataTransfer.files[0]; if(f) start(f); });
    if($("tp_open")) $("tp_open").addEventListener("click",()=>window.openApp("instagram"));
    if($("tp_clear")) $("tp_clear").addEventListener("click",()=>{ clearCache(); APPS.length=0; APP.name="You"; window.TP_NARRATING=false; window.showHome(); });
  };

  // on load: restore a previously cached report so return visits need no re-upload
  restoreCache();
  if(document.getElementById("importmount")) window.tpMountImport();
})();
