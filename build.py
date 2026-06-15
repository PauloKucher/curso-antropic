#!/usr/bin/env python3
"""Merge raw question banks into questions.json and generate a standalone index.html study app."""
import json, os, re, random

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "raw")
LETTERS = ["A", "B", "C", "D"]


def remap_letters(text, remap):
    """Remap standalone option-letter references (A/B/C/D) in explanation prose.
    Only matches a single capital A-D not glued to other alphanumerics, so words
    like APAC, MCP, SQL, DROP, CTA are left untouched."""
    return re.sub(r"(?<![A-Za-z0-9])([ABCD])(?![A-Za-z0-9])",
                  lambda m: remap[m.group(1)], text)


def spread_answers(questions, seed=7):
    """Reorder questions so no two consecutive items share the same answer letter
    (greedy: always take the letter with the most remaining that differs from the
    previous one). With a balanced bank this is always achievable."""
    rnd = random.Random(seed)
    buckets = {l: [] for l in LETTERS}
    for q in questions:
        buckets[q["answer"]].append(q)
    for l in LETTERS:
        rnd.shuffle(buckets[l])
    result, last = [], None
    for _ in range(len(questions)):
        cand = [l for l in LETTERS if buckets[l] and l != last]
        if not cand:
            cand = [l for l in LETTERS if buckets[l]]
        mx = max(len(buckets[l]) for l in cand)
        l = rnd.choice([c for c in cand if len(buckets[c]) == mx])
        result.append(buckets[l].pop())
        last = l
    return result


def balance_answers(questions, seed=42):
    """Permute each question's options so the correct answer is evenly spread
    across A/B/C/D, remapping any letter references inside the explanation."""
    rnd = random.Random(seed)
    targets = (LETTERS * ((len(questions) // 4) + 1))[:len(questions)]
    rnd.shuffle(targets)
    for q, target in zip(questions, targets):
        old_ans = q["answer"]
        opts = q["options"]
        correct_text = opts[old_ans]
        others = [opts[l] for l in LETTERS if l != old_ans]
        rnd.shuffle(others)
        new_opts = {target: correct_text}
        for l, txt in zip([l for l in LETTERS if l != target], others):
            new_opts[l] = txt
        text_to_new = {v: k for k, v in new_opts.items()}
        remap = {l: text_to_new[opts[l]] for l in LETTERS}
        q["explanation"] = remap_letters(q["explanation"], remap)
        q["options"] = {l: new_opts[l] for l in LETTERS}  # keep A-D key order
        q["answer"] = target

META = {
    "title": "Claude Certified Architect — Foundations",
    "passMark": 720,
    "scaleMin": 100,
    "scaleMax": 1000,
    "domains": {
        "D1": {"name": "Agentic Architecture & Orchestration", "tag": "D1 · AGENTIC",     "weight": 0.27, "color": "#7c5cff"},
        "D2": {"name": "Tool Design & MCP Integration",        "tag": "D2 · TOOLS/MCP",   "weight": 0.18, "color": "#5b8def"},
        "D3": {"name": "Claude Code Configuration & Workflows","tag": "D3 · CLAUDE CODE",  "weight": 0.20, "color": "#3fb37f"},
        "D4": {"name": "Prompt Engineering & Structured Output","tag": "D4 · PROMPTING",   "weight": 0.20, "color": "#e0823d"},
        "D5": {"name": "Context Management & Reliability",     "tag": "D5 · CONTEXT",     "weight": 0.15, "color": "#9aa0aa"},
    },
}

# order: new domain banks first, then the earlier v1 set
FILES = ["d1.json", "d2.json", "d3.json", "d4.json", "d5.json", "v1.json",
         "hard_d1.json", "hard_d2.json", "hard_d3.json", "hard_d4.json", "hard_d5.json"]

questions = []
for fn in FILES:
    with open(os.path.join(RAW, fn), encoding="utf-8") as f:
        arr = json.load(f)
    src = fn.replace(".json", "")
    for obj in arr:
        obj["src"] = src
        obj.setdefault("difficulty", "normal")  # files without the field are Foundations/normal
        questions.append(obj)

for i, q in enumerate(questions, 1):
    q["id"] = i

# balance letters + spread consecutive WITHIN each difficulty tier, so each tier is
# independently fair (Hard-only and Normal-only both stay balanced and non-repetitive)
groups = []
for diff in ("normal", "hard"):
    g = [q for q in questions if q["difficulty"] == diff]
    balance_answers(g)
    g = spread_answers(g)
    groups.append(g)
questions = groups[0] + groups[1]

# sanity: every answer key exists in options, domain known
for q in questions:
    assert q["answer"] in q["options"], f"bad answer in q{q['id']}"
    assert q["domain"] in META["domains"], f"bad domain in q{q['id']}"

payload = {"meta": META, "questions": questions}

with open(os.path.join(ROOT, "questions.json"), "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

# counts per domain
counts = {}
for q in questions:
    counts[q["domain"]] = counts.get(q["domain"], 0) + 1
print("Total questions:", len(questions))
print("Per domain:", counts)
diffc = {}
for q in questions:
    diffc[q["difficulty"]] = diffc.get(q["difficulty"], 0) + 1
print("Per difficulty:", diffc)
for diff in ("normal", "hard"):
    adist = {}
    for q in questions:
        if q["difficulty"] == diff:
            adist[q["answer"]] = adist.get(q["answer"], 0) + 1
    print(f"Answer distribution [{diff}]:", {k: adist.get(k, 0) for k in LETTERS})

HTML = r'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Claude Architect · Exam Trainer</title>
<style>
:root{
  --bg:#0a0a0b; --panel:#141416; --panel2:#1b1b1f; --line:#2a2a30;
  --txt:#ededf0; --mut:#8b8b94; --acc:#e0823d; --ok:#3fb37f; --bad:#e0574b;
  --d1:#7c5cff; --d2:#5b8def; --d3:#3fb37f; --d4:#e0823d; --d5:#9aa0aa;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--txt);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;letter-spacing:.06em}
.wrap{max-width:920px;margin:0 auto;padding:24px 20px 80px}
header.top{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);padding:14px 20px;position:sticky;top:0;background:rgba(10,10,11,.92);backdrop-filter:blur(8px);z-index:5}
.brand{display:flex;align-items:center;gap:14px}
.brand b{font-weight:800}
.brand .sub{color:var(--mut);font-size:12px}
.btn{cursor:pointer;border:1px solid var(--line);background:var(--panel2);color:var(--txt);border-radius:999px;padding:9px 16px;font-size:13px;transition:.15s}
.btn:hover{border-color:#3a3a44}
.btn.primary{background:#fff;color:#000;border-color:#fff;font-weight:700}
.btn.primary:hover{opacity:.9}
.btn.ghost{background:transparent}
.btn:disabled{opacity:.4;cursor:not-allowed}
h1{font-size:22px;margin:6px 0 2px}
.lead{color:var(--mut);font-size:14px;margin:0 0 22px}
.grid{display:grid;gap:14px}
@media(min-width:680px){.grid.c3{grid-template-columns:1fr 1fr 1fr}.grid.c2{grid-template-columns:1fr 1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px}
.card h3{margin:0 0 6px;font-size:16px}
.card p{margin:0;color:var(--mut);font-size:13px;line-height:1.5}
.card.click{cursor:pointer;transition:.15s}
.card.click:hover{border-color:#3a3a44;transform:translateY(-1px)}
.tag{display:inline-block;border-radius:999px;padding:5px 12px;font-size:11px;font-weight:700;color:#0a0a0b}
.row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.sp{flex:1}
.muted{color:var(--mut)}
.opts{display:flex;gap:10px;margin:16px 0}
.seg{flex:1;text-align:center;border:1px solid var(--line);border-radius:10px;padding:10px;font-size:12px;cursor:pointer;color:var(--mut)}
.seg.on{background:var(--panel2);color:var(--txt);border-color:#3a3a44}
.toggle{display:flex;align-items:center;gap:10px;font-size:13px;color:var(--mut);cursor:pointer;user-select:none}
.toggle .box{width:38px;height:22px;border-radius:999px;background:#2a2a30;position:relative;transition:.15s}
.toggle .box i{position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:50%;background:#777;transition:.15s}
.toggle.on .box{background:var(--acc)}
.toggle.on .box i{left:18px;background:#fff}
.progress{height:4px;background:var(--panel2);border-radius:999px;overflow:hidden;margin:10px 0 22px}
.progress i{display:block;height:100%;background:#fff;transition:.3s}
.qtag{margin-bottom:14px}
.qtext{font-size:21px;line-height:1.35;font-weight:600;margin:0 0 22px}
.choice{display:flex;gap:14px;align-items:flex-start;border:1px solid var(--line);background:var(--panel);border-radius:14px;padding:16px 18px;margin-bottom:12px;cursor:pointer;transition:.12s}
.choice:hover{border-color:#3a3a44}
.choice .k{flex:none;width:26px;height:26px;border-radius:50%;border:1px solid var(--line);display:flex;align-items:center;justify-content:center;font-size:12px;color:var(--mut)}
.choice .t{font-size:15px;line-height:1.45}
.choice.sel{border-color:#5a5a66;background:var(--panel2)}
.choice.correct{border-color:var(--ok);background:rgba(63,179,127,.08)}
.choice.wrong{border-color:var(--bad);background:rgba(224,87,75,.08)}
.choice .badge{margin-left:auto;font-size:11px;font-weight:700;display:flex;align-items:center;gap:6px}
.expl{border:1px solid var(--line);background:var(--panel2);border-radius:12px;padding:14px 16px;margin-top:6px;font-size:13.5px;line-height:1.55;color:#cfcfd6}
.expl b{color:var(--ok)}
.foot{display:flex;align-items:center;gap:12px;margin-top:18px}
.score-big{font-size:64px;font-weight:800;line-height:1}
.pill{display:inline-block;padding:6px 14px;border-radius:999px;font-weight:700;font-size:14px}
.pill.pass{background:rgba(63,179,127,.15);color:var(--ok);border:1px solid rgba(63,179,127,.4)}
.pill.fail{background:rgba(224,87,75,.15);color:var(--bad);border:1px solid rgba(224,87,75,.4)}
.bar{height:8px;background:var(--panel2);border-radius:999px;overflow:hidden}
.bar i{display:block;height:100%}
.dgrid{display:grid;grid-template-columns:auto 1fr auto;gap:10px 14px;align-items:center;font-size:13px}
.rev{border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:10px;background:var(--panel)}
.rev .qh{font-size:14px;font-weight:600;margin:8px 0}
.rev .opt{font-size:13px;padding:4px 0;color:var(--mut)}
.rev .opt.c{color:var(--ok)}
.rev .opt.x{color:var(--bad)}
.hist{font-size:13px}
.hist .hrow{display:flex;gap:12px;align-items:center;padding:8px 0;border-bottom:1px solid var(--line)}
small.k{color:var(--mut);font-size:11px}
a.link{color:var(--acc);cursor:pointer}
</style>
</head>
<body>
<header class="top">
  <div class="brand"><b class="mono">brq</b><span class="sub mono">CLAUDE ARCHITECT · EXAM TRAINER</span></div>
  <div class="row">
    <button class="btn ghost mono" onclick="go('home')">HOME</button>
    <button class="btn ghost mono" onclick="go('history')">HISTÓRICO</button>
  </div>
</header>
<div class="wrap" id="app"></div>

<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const Q = DATA.questions, M = DATA.meta, D = M.domains;
const LS_HIST='cca_history', LS_OPT='cca_opts';
let opts = loadOpts();
let state = null; // active quiz

function loadOpts(){ try{return Object.assign({shuffleQ:true,shuffleOpt:true,instant:false,difficulty:'normal'}, JSON.parse(localStorage.getItem(LS_OPT)||'{}'));}catch(e){return {shuffleQ:true,shuffleOpt:true,instant:false,difficulty:'normal'};} }
function saveOpts(){ localStorage.setItem(LS_OPT, JSON.stringify(opts)); }
function hist(){ try{return JSON.parse(localStorage.getItem(LS_HIST)||'[]');}catch(e){return [];} }
function pushHist(r){ const h=hist(); h.unshift(r); localStorage.setItem(LS_HIST, JSON.stringify(h.slice(0,50))); }
function shuffle(a){ a=a.slice(); for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]];} return a; }
function spreadByAnswer(items){
  // reordena para que a letra da resposta certa nunca se repita em questões consecutivas
  const buckets={A:[],B:[],C:[],D:[]};
  items.forEach(it=>buckets[it.q.answer].push(it));
  const out=[]; let last=null;
  for(let n=0;n<items.length;n++){
    let cand=['A','B','C','D'].filter(l=>buckets[l].length>0 && l!==last);
    if(!cand.length) cand=['A','B','C','D'].filter(l=>buckets[l].length>0);
    const mx=Math.max(...cand.map(l=>buckets[l].length));
    const top=cand.filter(l=>buckets[l].length===mx);
    const l=top[Math.floor(Math.random()*top.length)];
    out.push(buckets[l].shift()); last=l;
  }
  return out;
}
function pool(){ return opts.difficulty==='all' ? Q.slice() : Q.filter(q=>q.difficulty===opts.difficulty); }
function byDomain(d){ return pool().filter(q=>q.domain===d); }
function el(h){ const t=document.createElement('template'); t.innerHTML=h.trim(); return t.content.firstChild; }
function esc(s){ return (s+'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
const app = ()=>document.getElementById('app');

function go(view, arg){ if(view==='home') renderHome(); else if(view==='history') renderHistory(); else if(view==='quiz') renderQuiz(); else if(view==='result') renderResult(); }

/* ---------- HOME ---------- */
function renderHome(){
  const h = hist();
  const best = h.length? Math.max(...h.map(x=>x.scaled)) : null;
  const last = h.length? h[0].scaled : null;
  const nNorm=Q.filter(q=>q.difficulty==='normal').length, nHard=Q.filter(q=>q.difficulty==='hard').length;
  const P=pool(); const poolN=P.length;
  const counts = {}; P.forEach(q=>counts[q.domain]=(counts[q.domain]||0)+1);
  const diffLabel = opts.difficulty==='hard'?'Hard':(opts.difficulty==='all'?'Ambas':'Normal');
  let domCards = Object.keys(D).map(k=>`
    <div class="card click" onclick="startDomain('${k}')">
      <span class="tag mono" style="background:${D[k].color}">${D[k].tag}</span>
      <h3 style="margin-top:12px">${esc(D[k].name)}</h3>
      <p>${counts[k]||0} questões · peso ${Math.round(D[k].weight*100)}%</p>
    </div>`).join('');
  const dseg=(key,label)=>`<div class="seg ${opts.difficulty===key?'on':''}" onclick="setDiff('${key}')">${label}</div>`;
  app().innerHTML = `
    <h1>Treino para a certificação</h1>
    <p class="lead">Banco: ${nNorm} normais + ${nHard} hard = ${Q.length} · nota na escala ${M.scaleMin}–${M.scaleMax} · corte ${M.passMark} · pesos por domínio iguais aos do exame.</p>

    <div class="grid c3" style="margin-bottom:14px">
      <div class="card"><small class="k mono">MELHOR NOTA</small><div class="score-big" style="font-size:40px;margin-top:6px">${best??'—'}</div></div>
      <div class="card"><small class="k mono">ÚLTIMA NOTA</small><div class="score-big" style="font-size:40px;margin-top:6px">${last??'—'}</div></div>
      <div class="card"><small class="k mono">SIMULADOS FEITOS</small><div class="score-big" style="font-size:40px;margin-top:6px">${h.length}</div></div>
    </div>

    <div class="card" style="margin-bottom:18px">
      <small class="k mono">DIFICULDADE</small>
      <div class="opts" style="margin:10px 0 4px">${dseg('normal','Normal · '+nNorm)}${dseg('hard','Hard · '+nHard)}${dseg('all','Ambas · '+Q.length)}</div>
      <p class="muted" style="font-size:12px;margin:6px 0 14px">${opts.difficulty==='hard'?'Hard: duas opções defensáveis, melhor-vs-segundo-melhor; exige decidir pela restrição do enunciado.':(opts.difficulty==='all'?'Mistura normais e hard.':'Normal (Foundations): uma resposta claramente certa.')}</p>
      <div class="row" style="gap:18px">
        <label class="toggle ${opts.shuffleQ?'on':''}" onclick="tog('shuffleQ')"><span class="box"><i></i></span>Embaralhar ordem das questões</label>
        <label class="toggle ${opts.instant?'on':''}" onclick="tog('instant')"><span class="box"><i></i></span>Feedback imediato</label>
      </div>
    </div>

    <h3 class="mono" style="color:var(--mut);font-size:12px;letter-spacing:.1em;margin:6px 0 12px">SIMULADO PONDERADO (distribuído por peso)</h3>
    <div class="grid c3" style="margin-bottom:22px">
      <div class="card click" onclick="startWeighted(15)"><h3>Rápido · 15</h3><p>Amostra ponderada de 15 questões. ~10 min.</p></div>
      <div class="card click" onclick="startWeighted(30)"><h3>Médio · 30</h3><p>Amostra ponderada de 30 questões. ~20 min.</p></div>
      <div class="card click" onclick="startWeighted(45)"><h3>Longo · 45</h3><p>Amostra ponderada de 45 questões. ~30 min.</p></div>
    </div>

    <h3 class="mono" style="color:var(--mut);font-size:12px;letter-spacing:.1em;margin:6px 0 12px">PROVA COMPLETA</h3>
    <div class="grid c2" style="margin-bottom:22px">
      <div class="card click" onclick="startAll()"><h3>Banco inteiro · ${poolN}</h3><p>Todas as questões (${diffLabel}), ponderadas por domínio no resultado.</p></div>
      <div class="card click" onclick="startWeighted(60)"><h3>Simulado oficial · ${Math.min(60,poolN)}</h3><p>Proporção do exame (${diffLabel}); usa até ${poolN} disponíveis.</p></div>
    </div>

    <h3 class="mono" style="color:var(--mut);font-size:12px;letter-spacing:.1em;margin:6px 0 12px">TREINO POR DOMÍNIO</h3>
    <div class="grid c2">${domCards}</div>
  `;
}
function tog(k){ opts[k]=!opts[k]; saveOpts(); renderHome(); }

/* ---------- QUIZ SETUP ---------- */
function weightedSample(n){
  // allocate counts per domain by weight, capped by availability
  const keys = Object.keys(D);
  let alloc = {}; let sum = keys.reduce((s,k)=>s+D[k].weight,0);
  let total=0;
  keys.forEach(k=>{ alloc[k]=Math.round(n*D[k].weight/sum); total+=alloc[k]; });
  // fix rounding to hit n
  let diff=n-total; let i=0;
  while(diff!==0){ const k=keys[i%keys.length]; if(diff>0){alloc[k]++;diff--;} else if(alloc[k]>0){alloc[k]--;diff++;} i++; if(i>1000)break; }
  let picked=[];
  keys.forEach(k=>{ const pool=shuffle(byDomain(k)); picked=picked.concat(pool.slice(0, Math.min(alloc[k], pool.length))); });
  return picked;
}
function buildState(list, label){
  let qs = opts.shuffleQ ? shuffle(list) : list.slice();
  let items = qs.map(q=>({ q, order:['A','B','C','D'], picked:null, revealed:false }));
  // evita que a resposta certa caia na mesma letra de duas questões seguidas
  if(opts.shuffleQ) items = spreadByAnswer(items);
  state = { label, i:0, items };
  go('quiz');
}
function startWeighted(n){ buildState(weightedSample(n), `Simulado ponderado · ${n}`); }
function startAll(){ const p=pool(); buildState(p, `Prova completa · ${p.length}`); }
function setDiff(d){ opts.difficulty=d; saveOpts(); renderHome(); }
function startDomain(k){ buildState(byDomain(k), `Domínio ${D[k].tag}`); }

/* ---------- QUIZ ---------- */
function renderQuiz(){
  const s=state, it=s.items[s.i], q=it.q, dom=D[q.domain];
  const pct=Math.round((s.i)/s.items.length*100);
  let choices = it.order.map((key,idx)=>{
    const dispLetter='ABCD'[idx];
    let cls='choice';
    if(it.revealed){
      if(key===q.answer) cls+=' correct';
      else if(key===it.picked) cls+=' wrong';
    } else if(it.picked===key) cls+=' sel';
    let badge='';
    if(it.revealed && key===q.answer) badge='<span class="badge" style="color:var(--ok)">✓ CORRETA</span>';
    else if(it.revealed && key===it.picked) badge='<span class="badge" style="color:var(--bad)">✗ SUA RESPOSTA</span>';
    return `<div class="${cls}" onclick="pick('${key}')">
        <div class="k mono">${dispLetter}</div>
        <div class="t">${esc(q.options[key])}</div>${badge}
      </div>`;
  }).join('');
  let explBlock = it.revealed ? `<div class="expl"><b>Resposta correta: ${q.answer}.</b> ${esc(q.explanation)}</div>` : '';
  app().innerHTML = `
    <div class="row" style="margin-bottom:6px">
      <button class="btn ghost mono" onclick="quitQuiz()">← SAIR</button>
      <span class="muted mono" style="font-size:12px">${esc(s.label)}</span>
      <span class="sp"></span>
      <span class="mono" style="font-size:14px">Q ${s.i+1} / ${s.items.length}</span>
    </div>
    <div class="progress"><i style="width:${pct}%"></i></div>
    <div class="qtag"><span class="tag mono" style="background:${dom.color}">${dom.tag}</span>${q.difficulty==='hard'?' <span class="tag mono" style="background:#e0574b">HARD</span>':''}</div>
    <p class="qtext">${esc(q.q)}</p>
    ${choices}
    ${explBlock}
    <div class="foot">
      <span class="sp"></span>
      ${ s.i>0 ? '<button class="btn ghost mono" onclick="prevQ()">← ANTERIOR</button>':''}
      <button class="btn primary mono" id="nextBtn" onclick="nextQ()" ${it.picked?'':'disabled'}>${ s.i===s.items.length-1?'FINALIZAR':'PRÓXIMA →'}</button>
    </div>
  `;
}
function pick(key){
  const it=state.items[state.i];
  if(it.revealed) return;
  it.picked=key;
  if(opts.instant){ it.revealed=true; }
  renderQuiz();
}
function nextQ(){
  const it=state.items[state.i];
  if(!it.picked) return;
  it.revealed=true;
  if(state.i < state.items.length-1){ state.i++; renderQuiz(); }
  else finish();
}
function prevQ(){ if(state.i>0){state.i--; renderQuiz();} }
function quitQuiz(){ if(confirm('Sair do simulado? O progresso atual será descartado.')){ state=null; go('home'); } }

/* ---------- RESULT ---------- */
function computeScore(){
  const perDom={}; // {D1:{c,t}}
  state.items.forEach(it=>{
    const d=it.q.domain; perDom[d]=perDom[d]||{c:0,t:0};
    perDom[d].t++; if(it.picked===it.q.answer) perDom[d].c++;
  });
  let presentWeight=0, acc=0, totalC=0, totalT=0;
  Object.keys(perDom).forEach(d=>{ presentWeight+=D[d].weight; });
  Object.keys(perDom).forEach(d=>{
    const r=perDom[d].c/perDom[d].t;
    acc += r * (D[d].weight/presentWeight);
    totalC+=perDom[d].c; totalT+=perDom[d].t;
  });
  const scaled = Math.round(M.scaleMin + acc*(M.scaleMax-M.scaleMin));
  return { perDom, weightedPct:acc, scaled, pass:scaled>=M.passMark, totalC, totalT };
}
function finish(){
  const r=computeScore();
  pushHist({ date:new Date().toISOString(), label:state.label, scaled:r.scaled, pass:r.pass, correct:r.totalC, total:r.totalT });
  state._result=r;
  go('result');
}
function revCard(it,idx){
  const q=it.q, ok=it.picked===q.answer;
  const pickedTxt = it.picked? it.picked : '—';
  let optLines = ['A','B','C','D'].map(k=>{
    let c=''; if(k===q.answer)c='c'; else if(k===it.picked && !ok)c='x';
    const mark = k===q.answer?'✓':(k===it.picked?'✗':' ');
    return `<div class="opt ${c}">${mark} ${k}) ${esc(q.options[k])}</div>`;
  }).join('');
  return `<div class="rev" style="border-left:3px solid ${ok?'var(--ok)':'var(--bad)'}">
    <div class="row"><span class="tag mono" style="background:${D[q.domain].color}">${D[q.domain].tag}</span>${q.difficulty==='hard'?'<span class="tag mono" style="background:#e0574b">HARD</span>':''}
      <span class="sp"></span>
      <span class="mono" style="color:${ok?'var(--ok)':'var(--bad)'}">${ok?'✓ ACERTOU':'✗ ERROU'}</span></div>
    <div class="qh">${idx+1}. ${esc(q.q)}</div>
    ${optLines}
    <div class="expl"><b style="color:${ok?'var(--ok)':'var(--bad)'}">Sua resposta: ${pickedTxt} ${ok?'(correta)':'· Correta: '+q.answer}.</b> ${esc(q.explanation)}</div>
  </div>`;
}
function renderReview(){
  const s=state;
  const f = s._revFilter||'all';
  const tagged = s.items.map((it,idx)=>({it,idx,ok:it.picked===it.q.answer}));
  const wrong = tagged.filter(t=>!t.ok), right = tagged.filter(t=>t.ok);
  let list;
  if(f==='wrong') list=wrong;
  else if(f==='right') list=right;
  else list=wrong.concat(right); // erros primeiro
  let body;
  if(!list.length){ body = `<p class="lead">Nada para mostrar neste filtro.</p>`; }
  else if(f==='all'){
    body = (wrong.length? `<h3 class="mono" style="color:var(--bad);font-size:12px;letter-spacing:.1em;margin:18px 0 10px">❌ QUE VOCÊ ERROU (${wrong.length})</h3>`+wrong.map(t=>revCard(t.it,t.idx)).join(''):'')
         + (right.length? `<h3 class="mono" style="color:var(--ok);font-size:12px;letter-spacing:.1em;margin:22px 0 10px">✅ QUE VOCÊ ACERTOU (${right.length})</h3>`+right.map(t=>revCard(t.it,t.idx)).join(''):'');
  } else {
    body = list.map(t=>revCard(t.it,t.idx)).join('');
  }
  const seg=(key,label)=>`<div class="seg ${f===key?'on':''}" onclick="setRevFilter('${key}')">${label}</div>`;
  return `
    <div class="row" style="margin:6px 0 4px"><h3 class="mono" style="color:var(--mut);font-size:12px;letter-spacing:.1em;margin:0">GABARITO COMENTADO</h3></div>
    <div class="opts">${seg('all','Todas')}${seg('wrong','Só erros ('+wrong.length+')')}${seg('right','Só acertos ('+right.length+')')}</div>
    <div id="revBody">${body}</div>`;
}
function setRevFilter(f){ state._revFilter=f; document.getElementById('reviewWrap').innerHTML=renderReview(); }
function renderResult(){
  const s=state, r=s._result;
  let doms = Object.keys(r.perDom).map(d=>{
    const pd=r.perDom[d], pct=Math.round(pd.c/pd.t*100);
    return `<span class="tag mono" style="background:${D[d].color};justify-self:start">${D[d].tag}</span>
            <div class="bar"><i style="width:${pct}%;background:${D[d].color}"></i></div>
            <span class="mono">${pd.c}/${pd.t}</span>`;
  }).join('');
  const wrongN = s.items.filter(it=>it.picked!==it.q.answer).length;
  app().innerHTML = `
    <div class="row"><button class="btn ghost mono" onclick="go('home')">← HOME</button><span class="sp"></span><span class="muted mono" style="font-size:12px">${esc(s.label)}</span></div>
    <div class="card" style="margin:14px 0;text-align:center;padding:30px">
      <small class="k mono">NOTA FINAL · ESCALA ${M.scaleMin}–${M.scaleMax}</small>
      <div class="score-big" style="margin:12px 0;color:${r.pass?'var(--ok)':'var(--bad)'}">${r.scaled}</div>
      <span class="pill ${r.pass?'pass':'fail'}">${r.pass?'✅ APROVADO':'❌ REPROVADO'} · corte ${M.passMark}</span>
      <p class="muted" style="margin-top:14px">${r.totalC} de ${r.totalT} corretas · ${wrongN} erradas · ${Math.round(r.weightedPct*100)}% ponderado</p>
    </div>
    <div class="card" style="margin-bottom:18px">
      <small class="k mono">DESEMPENHO POR DOMÍNIO</small>
      <div class="dgrid" style="margin-top:14px">${doms}</div>
    </div>
    <div class="row" style="margin-bottom:8px">
      <button class="btn primary mono" onclick="retrySame()">REFAZER ESTE</button>
      ${wrongN? '<button class="btn mono" onclick="retryWrong()">TREINAR SÓ OS ERROS ('+wrongN+')</button>':''}
      <button class="btn mono" onclick="go('home')">NOVO SIMULADO</button>
    </div>
    <div id="reviewWrap">${renderReview()}</div>
  `;
  window.scrollTo(0,0);
}
function retryWrong(){ const list=state.items.filter(it=>it.picked!==it.q.answer).map(it=>it.q); if(!list.length)return; buildState(list, 'Revisão dos erros · '+list.length); }
function retrySame(){ const list=state.items.map(it=>it.q); const lbl=state.label; buildState(list,lbl); }

/* ---------- HISTORY ---------- */
function renderHistory(){
  const h=hist();
  let rows = h.length? h.map(x=>{
    const d=new Date(x.date);
    return `<div class="hrow"><span class="mono" style="color:${x.pass?'var(--ok)':'var(--bad)'};width:60px">${x.scaled}</span>
      <span>${esc(x.label)}</span><span class="sp"></span>
      <span class="muted">${x.correct}/${x.total}</span>
      <span class="muted mono" style="font-size:11px">${d.toLocaleDateString('pt-BR')} ${d.toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}</span></div>`;
  }).join('') : '<p class="lead">Nenhum simulado registrado ainda.</p>';
  app().innerHTML = `
    <div class="row"><button class="btn ghost mono" onclick="go('home')">← HOME</button>
      <span class="sp"></span>${h.length?'<button class="btn mono" onclick="clearHist()">LIMPAR HISTÓRICO</button>':''}</div>
    <h1 style="margin-top:14px">Histórico</h1>
    <p class="lead">Suas notas ficam salvas neste navegador (localStorage).</p>
    <div class="card hist">${rows}</div>
  `;
}
function clearHist(){ if(confirm('Apagar todo o histórico?')){ localStorage.removeItem(LS_HIST); renderHistory(); } }

renderHome();
</script>
</body>
</html>
'''

html = HTML.replace("__DATA__", json.dumps(payload, ensure_ascii=False))
with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
    f.write(html)
print("Wrote index.html (", len(html), "bytes )")
