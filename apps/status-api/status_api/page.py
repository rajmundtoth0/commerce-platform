"""The internal status page — a single self-contained HTML document.

Intentionally boring: server-served static HTML + a little vanilla JS that calls
GET /status and renders cards. No build step, no framework, no graphs.
"""

from __future__ import annotations

STATUS_PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Internal Status</title>
<style>
  :root { color-scheme: light dark; }
  body { font: 15px/1.5 system-ui, sans-serif; margin: 0; background: #f5f6f8; color: #1c1e21; }
  header { padding: 20px 24px; border-bottom: 1px solid #e2e4e8; background: #fff; }
  h1 { margin: 0; font-size: 18px; }
  main { max-width: 920px; margin: 0 auto; padding: 24px; }
  h2 { font-size: 14px; text-transform: uppercase; letter-spacing: .04em; color: #6b7280; margin: 28px 0 10px; }
  .overall { padding: 16px 20px; border-radius: 10px; font-weight: 600; font-size: 17px; background: #fff; border: 1px solid #e2e4e8; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
  .card { background: #fff; border: 1px solid #e2e4e8; border-radius: 10px; padding: 14px 16px; }
  .card h3 { margin: 0 0 6px; font-size: 15px; }
  .muted { color: #6b7280; font-size: 13px; }
  .pill { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 12px; font-weight: 600; }
  .dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:6px; vertical-align:middle; }
  .operational { color:#0a7d33; } .operational-bg { background:#e6f4ea; color:#0a7d33; }
  .degraded, .maintenance { color:#9a6b00; } .degraded-bg { background:#fdf2d8; color:#9a6b00; }
  .partial_outage { color:#b25a00; } .partial_outage-bg { background:#fde3cc; color:#b25a00; }
  .down, .major_outage, .critical { color:#b3261e; } .major_outage-bg { background:#faddd8; color:#b3261e; }
  .unknown { color:#6b7280; } .unknown-bg { background:#eceef1; color:#6b7280; }
  .empty { color:#6b7280; font-style: italic; }
  .row { display:flex; justify-content:space-between; gap:10px; }
  time { color:#6b7280; font-size:12px; }
</style>
</head>
<body>
<header><h1>Internal Status</h1></header>
<main id="app"><p class="muted">Loading…</p></main>
<script>
const STATUS_CLASS = s => (s||"unknown").replace(/[^a-z_]/g,"");
const fmt = t => t ? new Date(t).toLocaleString() : "—";
const cap = s => (s||"").replace(/_/g," ").replace(/\\b\\w/g, c => c.toUpperCase());

function pill(s){ const c = STATUS_CLASS(s); return `<span class="pill ${c}-bg">${cap(s)}</span>`; }

function componentCard(c){
  return `<div class="card">
    <h3>${c.name}</h3>
    <div><span class="dot ${STATUS_CLASS(c.status)}" style="background:currentColor"></span>${pill(c.status)}</div>
    <p class="muted">Last checked: <time>${fmt(c.last_checked_at)}</time></p>
    ${c.last_error ? `<p class="muted">${c.last_error}</p>` : ""}
  </div>`;
}

function incidentCard(i){
  return `<div class="card">
    <div class="row"><h3>${i.title}</h3>${pill(i.status)}</div>
    <p class="muted">Severity: ${cap(i.severity)} · Area: ${cap(i.area)} · Cause: ${cap(i.cause)}</p>
    ${i.affected_components?.length ? `<p class="muted">Affected: ${i.affected_components.join(", ")}</p>` : ""}
    <p class="muted">Started: <time>${fmt(i.started_at)}</time>${i.resolved_at ? ` · Resolved: <time>${fmt(i.resolved_at)}</time>` : ""}</p>
    ${i.summary ? `<p>${i.summary}</p>` : ""}
    ${i.resolution ? `<p class="muted"><b>Resolution:</b> ${i.resolution}</p>` : ""}
    ${i.follow_up ? `<p class="muted"><b>Follow-up:</b> ${i.follow_up}</p>` : ""}
  </div>`;
}

function maintenanceCard(m){
  return `<div class="card">
    <div class="row"><h3>${m.title}</h3>${pill(m.status)}</div>
    ${m.affected_components?.length ? `<p class="muted">Affected: ${m.affected_components.join(", ")}</p>` : ""}
    <p class="muted">Window: <time>${fmt(m.scheduled_start_at)}</time> – <time>${fmt(m.scheduled_end_at)}</time></p>
    ${m.summary ? `<p>${m.summary}</p>` : ""}
  </div>`;
}

function section(title, items, render){
  const body = items.length ? `<div class="grid">${items.map(render).join("")}</div>`
                            : `<p class="empty">None.</p>`;
  return `<h2>${title}</h2>${body}`;
}

async function load(){
  const app = document.getElementById("app");
  try {
    const r = await fetch("status", {headers:{accept:"application/json"}});
    const d = await r.json();
    app.innerHTML =
      `<div class="overall"><span class="dot ${STATUS_CLASS(d.overall_status)}" style="background:currentColor"></span>
        Overall: ${pill(d.overall_status)} <time>· updated ${fmt(d.updated_at)}</time></div>`
      + section("Components", d.components||[], componentCard)
      + section("Active incidents", d.active_incidents||[], incidentCard)
      + section("Recent incidents", d.recent_incidents||[], incidentCard)
      + section("Planned maintenance", d.planned_maintenance||[], maintenanceCard);
  } catch (e) {
    app.innerHTML = `<p class="empty">Could not load status.</p>`;
  }
}
load();
setInterval(load, 15000);
</script>
</body>
</html>
"""
