from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


CATEGORY_CATALOG: list[dict[str, str]] = [
    {"group": "Org", "label": "Exec changes", "path": "Org -> Exec Changes"},
    {
        "group": "Strategy",
        "label": "General news & strategy",
        "path": "Strategy & Miscellaneous News -> General News & Strategy",
    },
    {
        "group": "Strategy",
        "label": "Strategy",
        "path": "Strategy & Miscellaneous News -> Strategy",
    },
    {
        "group": "M&A",
        "label": "General news & strategy",
        "path": "M&A -> General News & Strategy",
    },
    {
        "group": "Investor Relations",
        "label": "Quarterly earnings",
        "path": "Investor Relations -> Quarterly Earnings",
    },
    {
        "group": "Investor Relations",
        "label": "Company materials",
        "path": "Investor Relations -> Company Materials",
    },
    {
        "group": "Investor Relations",
        "label": "News coverage",
        "path": "Investor Relations -> News Coverage",
    },
    {
        "group": "Content / Deals / Distribution",
        "label": "Film - Development",
        "path": "Content, Deals, Distribution -> Film -> Development",
    },
    {
        "group": "Content / Deals / Distribution",
        "label": "Film - Greenlights",
        "path": "Content, Deals, Distribution -> Film -> Greenlights",
    },
    {
        "group": "Content / Deals / Distribution",
        "label": "Film - Pickups",
        "path": "Content, Deals, Distribution -> Film -> Pickups",
    },
    {
        "group": "Content / Deals / Distribution",
        "label": "Film - Dating",
        "path": "Content, Deals, Distribution -> Film -> Dating",
    },
    {
        "group": "Content / Deals / Distribution",
        "label": "Film - Renewals",
        "path": "Content, Deals, Distribution -> Film -> Renewals",
    },
    {
        "group": "Content / Deals / Distribution",
        "label": "Film - Cancellations",
        "path": "Content, Deals, Distribution -> Film -> Cancellations",
    },
    {
        "group": "Content / Deals / Distribution",
        "label": "Film - General news & strategy",
        "path": "Content, Deals, Distribution -> Film -> General News & Strategy",
    },
    {
        "group": "Content / Deals / Distribution",
        "label": "TV - Development",
        "path": "Content, Deals, Distribution -> TV -> Development",
    },
    {
        "group": "Content / Deals / Distribution",
        "label": "TV - Greenlights",
        "path": "Content, Deals, Distribution -> TV -> Greenlights",
    },
    {
        "group": "Content / Deals / Distribution",
        "label": "TV - Pickups",
        "path": "Content, Deals, Distribution -> TV -> Pickups",
    },
    {
        "group": "Content / Deals / Distribution",
        "label": "TV - Dating",
        "path": "Content, Deals, Distribution -> TV -> Dating",
    },
    {
        "group": "Content / Deals / Distribution",
        "label": "TV - Renewals",
        "path": "Content, Deals, Distribution -> TV -> Renewals",
    },
    {
        "group": "Content / Deals / Distribution",
        "label": "TV - Cancellations",
        "path": "Content, Deals, Distribution -> TV -> Cancellations",
    },
    {
        "group": "Content / Deals / Distribution",
        "label": "TV - General news & strategy",
        "path": "Content, Deals, Distribution -> TV -> General News & Strategy",
    },
    {
        "group": "Content / Deals / Distribution",
        "label": "Sports - General news & strategy",
        "path": "Content, Deals, Distribution -> Sports -> General News & Strategy",
    },
    {
        "group": "Content / Deals / Distribution",
        "label": "Podcasts - General news & strategy",
        "path": "Content, Deals, Distribution -> Podcasts -> General News & Strategy",
    },
]


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def reviewer_allowed_roots() -> list[Path]:
    """
    File roots the reviewer is allowed to load JSON from.

    Default: repo root only.
    Extend via REVIEWER_ALLOWED_ROOTS (comma-separated absolute paths).
    """
    roots: list[Path] = [project_root()]
    extra = os.getenv("REVIEWER_ALLOWED_ROOTS", "")
    for item in extra.split(","):
        txt = item.strip()
        if not txt:
            continue
        try:
            roots.append(Path(txt).expanduser().resolve())
        except OSError:
            continue

    unique: list[Path] = []
    seen: set[str] = set()
    for r in roots:
        key = str(r)
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


def _resolve_under_root(candidate: Path, root: Path) -> Path:
    if candidate.is_absolute():
        return candidate.resolve()
    return (root / candidate).resolve()


def resolve_article_json_path(path: str) -> Path:
    if not path or not str(path).strip():
        raise ValueError("path is required.")

    raw = Path(str(path)).expanduser()
    allowed = reviewer_allowed_roots()
    resolved: Path | None = None
    for root in allowed:
        try:
            candidate = _resolve_under_root(raw, root)
        except OSError:
            continue
        if candidate.is_relative_to(root):
            resolved = candidate
            break

    if resolved is None:
        allowed_txt = ", ".join(str(p) for p in allowed)
        raise ValueError(f"path must be within one of: {allowed_txt}")

    if resolved.suffix.lower() != ".json":
        raise ValueError("only .json files are supported for reviewer loads.")
    if not resolved.exists():
        raise ValueError(f"file not found: {resolved}")
    if not resolved.is_file():
        raise ValueError(f"not a file: {resolved}")

    return resolved


def load_article_payload_from_path(path: str) -> dict[str, Any]:
    resolved = resolve_article_json_path(path)
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {resolved.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("article JSON must be a single object (not a list).")
    return data


def list_sample_articles() -> list[dict[str, str]]:
    root = project_root()
    samples_dir = root / "data" / "samples"
    if not samples_dir.exists():
        return []

    items: list[dict[str, str]] = []
    for path in sorted(samples_dir.rglob("*.json")):
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        rel_txt = str(rel).replace("\\", "/")
        items.append({"path": rel_txt, "name": path.stem, "group": path.parent.name})
    return items


def _json_for_script_tag(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def render_reviewer_page(*, samples: list[dict[str, str]]) -> str:
    bootstrap = {
        "samples": samples,
        "catalog": CATEGORY_CATALOG,
        "allowed_roots": [str(p) for p in reviewer_allowed_roots()],
    }
    bootstrap_json = _json_for_script_tag(bootstrap)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Coverage Review Desk</title>
  <style>
    :root {{
      --paper: #0f1218;
      --paper2: #141a23;
      --ink: #f4f0e6;
      --muted: rgba(244, 240, 230, 0.72);
      --stroke: rgba(244, 240, 230, 0.16);
      --accent: #ff4d2e;
      --accent2: #22c55e;
      --shadow: rgba(0, 0, 0, 0.55);
      --radius: 18px;
      --mono: "Cascadia Mono", "Consolas", "Courier New", monospace;
      --serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ height: 100%; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: var(--serif);
      background:
        radial-gradient(
          1100px 520px at 16% 16%,
          rgba(255, 77, 46, 0.10),
          transparent 62%
        ),
        radial-gradient(
          900px 460px at 86% 18%,
          rgba(34, 197, 94, 0.08),
          transparent 58%
        ),
        linear-gradient(180deg, var(--paper), var(--paper2));
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        repeating-linear-gradient(
          0deg,
          rgba(255,255,255,0.020),
          rgba(255,255,255,0.020) 1px,
          transparent 1px,
          transparent 5px
        ),
        repeating-linear-gradient(
          90deg,
          rgba(0,0,0,0.22),
          rgba(0,0,0,0.22) 1px,
          transparent 1px,
          transparent 6px
        );
      opacity: 0.20;
      mix-blend-mode: overlay;
    }}
    code {{ font-family: var(--mono); }}
    .wrap {{ max-width: 1280px; margin: 0 auto; padding: 26px 16px 44px; }}
    .mast {{ display: grid; grid-template-columns: 1fr auto; gap: 14px; align-items: end; }}
    .mast h1 {{ margin: 0; font-size: 42px; line-height: 1.02; }}
    .mast p {{ margin: 8px 0 0; color: var(--muted); max-width: 78ch; font-size: 15px; }}
    .badge {{
      display: inline-flex; align-items: center; gap: 10px;
      border: 1px solid var(--stroke); border-radius: 999px;
      padding: 10px 14px; background: rgba(12, 14, 19, 0.55);
      box-shadow: 0 18px 60px var(--shadow); font-size: 12px; color: var(--muted);
      white-space: nowrap;
    }}
    .dot {{
      width: 9px; height: 9px; border-radius: 50%;
      background: radial-gradient(circle at 35% 35%, #fff, var(--accent));
      box-shadow: 0 0 0 3px rgba(255, 77, 46, 0.18);
    }}
    .grid {{ display: grid; grid-template-columns: 0.92fr 1.08fr; gap: 16px; margin-top: 16px; }}
    @media (max-width: 980px) {{ .grid {{ grid-template-columns: 1fr; }} }}
    .panel {{
      border: 1px solid var(--stroke); border-radius: var(--radius);
      background: rgba(11, 13, 18, 0.58);
      box-shadow: 0 28px 70px rgba(0,0,0,0.35);
      overflow: clip; position: relative;
    }}
    .panel::after {{
      content: ""; position: absolute; inset: 0; pointer-events: none;
      background: radial-gradient(820px 280px at 14% 0%, rgba(255, 77, 46, 0.08), transparent 62%);
      opacity: 0.75;
    }}
    .panel > * {{ position: relative; z-index: 1; }}
    .head {{
      padding: 16px 18px; border-bottom: 1px solid var(--stroke);
      background: linear-gradient(180deg, rgba(255,255,255,0.06), transparent);
      display: flex; justify-content: space-between; gap: 10px; align-items: baseline;
    }}
    .head h2 {{
      margin: 0; font-size: 16px; letter-spacing: 0.6px; text-transform: uppercase;
      color: rgba(244, 240, 230, 0.88);
    }}
    .hint {{ color: var(--muted); font-size: 12px; max-width: 64ch; }}
    .body {{ padding: 16px 18px 18px; }}
    label {{ display:block; font-size: 12px; color: var(--muted); margin-bottom: 6px; }}
    .row {{ display:grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }}
    @media (max-width: 540px) {{ .row {{ grid-template-columns: 1fr; }} }}
    input[type="text"], textarea, select {{
      width: 100%; border: 1px solid var(--stroke); border-radius: 12px;
      padding: 11px 12px; background: rgba(10, 12, 16, 0.60); color: var(--ink);
      outline: none; font-family: var(--serif);
      transition: border-color 120ms ease, box-shadow 120ms ease;
    }}
    textarea {{
      min-height: 150px;
      font-family: var(--mono);
      font-size: 12px;
      line-height: 1.45;
      resize: vertical;
    }}
    input[type="text"]:focus, textarea:focus, select:focus {{
      border-color: rgba(255, 77, 46, 0.65); box-shadow: 0 0 0 4px rgba(255, 77, 46, 0.14);
    }}
    .btnrow {{ display:flex; gap: 10px; align-items:center; flex-wrap: wrap; margin-top: 10px; }}
    button {{
      appearance: none; border: none; border-radius: 14px; cursor: pointer;
      padding: 12px 14px; color: #0b0d12; font-weight: 750;
      background: linear-gradient(135deg, rgba(255, 77, 46, 1), rgba(255, 161, 61, 1));
      box-shadow: 0 14px 34px rgba(255, 77, 46, 0.18);
      transition: transform 120ms ease, filter 120ms ease;
    }}
    button:hover {{ transform: translateY(-1px); filter: saturate(1.08); }}
    button:active {{ transform: translateY(0px); }}
    .ghost {{
      background: rgba(10, 12, 16, 0.50); color: var(--ink);
      border: 1px solid var(--stroke); box-shadow: none; font-weight: 650;
    }}
    .ghost:hover {{ border-color: rgba(244, 240, 230, 0.30); }}
    .status {{
      margin-left:auto;
      font-size: 12px;
      color: var(--muted);
      display:inline-flex;
      gap: 10px;
      align-items:center;
    }}
    .spin {{
      width: 14px; height: 14px; border-radius: 50%;
      border: 2px solid rgba(244, 240, 230, 0.22); border-top-color: rgba(244, 240, 230, 0.82);
      animation: spin 780ms linear infinite; display:none;
    }}
    .busy .spin {{ display:inline-block; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    .chips {{
      display:grid;
      grid-template-columns: repeat(2, minmax(0,1fr));
      gap: 10px;
      margin-top: 10px;
    }}
    @media (max-width: 540px) {{ .chips {{ grid-template-columns: 1fr; }} }}
    .chip {{
      text-align:left; border: 1px solid var(--stroke); background: rgba(10, 12, 16, 0.52);
      border-radius: 14px; padding: 12px 12px; cursor: pointer; color: var(--ink);
      transition: transform 120ms ease, border-color 120ms ease, background 120ms ease;
    }}
    .chip:hover {{
      transform: translateY(-1px);
      border-color: rgba(244,240,230,0.30);
      background: rgba(10, 12, 16, 0.66);
    }}
    .chip .k {{ font-size: 12px; color: var(--muted); margin-bottom: 2px; }}
    .chip .v {{
      font-family: var(--mono);
      font-size: 12px;
      color: rgba(244, 240, 230, 0.92);
      line-height: 1.25;
    }}
    .kvgrid {{ display:grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }}
    @media (max-width: 540px) {{ .kvgrid {{ grid-template-columns: 1fr; }} }}
    .kv {{
      border: 1px solid var(--stroke);
      border-radius: 14px;
      padding: 12px 12px;
      background: rgba(10, 12, 16, 0.52);
    }}
    .kv .k {{
      font-size: 11px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.7px;
      margin-bottom: 6px;
    }}
    .kv .v {{
      font-family: var(--mono);
      font-size: 12px;
      color: rgba(244, 240, 230, 0.92);
      overflow-wrap:anywhere;
    }}
    pre {{
      margin: 0; border: 1px solid var(--stroke); border-radius: 14px;
      padding: 14px 14px; background: rgba(8, 10, 14, 0.70);
      font-family: var(--mono); font-size: 12px; line-height: 1.45;
      overflow:auto; max-height: 54vh;
    }}
    .note {{ font-size: 12px; color: var(--muted); line-height: 1.35; margin-top: 10px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="mast">
      <div>
        <h1>Coverage Review Desk</h1>
        <p>
          Pick a category override and rerun the pipeline without touching the JSON file.
          Your last override is remembered locally per path.
        </p>
      </div>
      <div class="badge" title="This page runs locally inside the FastAPI server">
        <span class="dot"></span>
        <span>Local reviewer</span>
      </div>
    </div>

    <div class="grid">
      <section class="panel">
        <div class="head">
          <h2>Input</h2>
          <div class="hint">
            Load a JSON file, or paste a JSON object with <code>title</code>, <code>source</code>,
            <code>url</code>, <code>content</code>, <code>published_at</code>.
          </div>
        </div>
        <div class="body">
          <div class="row">
            <div>
              <label for="sample">Sample fixture</label>
              <select id="sample"></select>
            </div>
            <div>
              <label for="path">Path</label>
              <input id="path" type="text" placeholder="data/samples/debug/variety_....json" />
            </div>
          </div>
          <div class="btnrow">
            <button class="ghost" id="loadBtn" type="button">Load JSON</button>
            <button class="ghost" id="clearBtn" type="button">Clear</button>
            <div class="status" id="status">
              <span class="spin"></span>
              <span id="statusText">Ready</span>
            </div>
          </div>

          <label for="payload" style="margin-top: 12px;">Payload (JSON)</label>
          <textarea
            id="payload"
            spellcheck="false"
            placeholder='{{"title":"...","source":"...","url":"...","content":"...","published_at":"YYYY-MM-DD"}}'
          ></textarea>

          <div class="row" style="margin-top: 12px;">
            <div>
              <label for="filter">Find category</label>
              <input id="filter" type="text" placeholder="e.g., TV, Earnings, Exec..." />
            </div>
            <div>
              <label for="overrideCategory">Override (full path)</label>
              <input
                id="overrideCategory"
                type="text"
                placeholder="Strategy & Miscellaneous News -> General News & Strategy"
              />
            </div>
          </div>

          <div class="chips" id="chips"></div>

          <details style="margin-top: 12px;">
            <summary style="cursor:pointer; color: var(--muted);">Advanced overrides</summary>
            <div class="row" style="margin-top: 10px;">
              <div>
                <label for="overrideCompany">Override company (optional)</label>
                <input id="overrideCompany" type="text" placeholder="Netflix" />
              </div>
              <div>
                <label for="overrideQuarter">Override quarter (optional)</label>
                <input id="overrideQuarter" type="text" placeholder="2025 Q4" />
              </div>
            </div>
            <label
              style="display:flex; gap: 10px; align-items:center; margin-top: 8px; cursor:pointer;"
            >
              <input id="allowDuplicate" type="checkbox" />
              <span style="color: var(--muted); font-size: 12px;">Allow duplicate ingest</span>
            </label>
            <div class="note">
              Allow-duplicate is intended for manual reroutes: it forces a new ingest record even
              when the URL already exists for that company/quarter.
            </div>
          </details>

          <div class="btnrow" style="margin-top: 12px;">
            <button id="runBtn" type="button">Run (override)</button>
            <button class="ghost" id="runDefaultBtn" type="button">Run (no override)</button>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="head">
          <h2>Result</h2>
          <div class="hint">
            Markdown is returned from the pipeline. Copy/paste into docs or compare outputs.
          </div>
        </div>
        <div class="body">
          <div class="kvgrid">
            <div class="kv">
              <div class="k">Status</div>
              <div class="v" id="resultStatus">—</div>
            </div>
            <div class="kv">
              <div class="k">Prompt</div>
              <div class="v" id="resultPrompt">—</div>
            </div>
            <div class="kv">
              <div class="k">Stored path</div>
              <div class="v" id="resultStored">—</div>
            </div>
            <div class="kv">
              <div class="k">Duplicate of</div>
              <div class="v" id="resultDuplicate">—</div>
            </div>
          </div>
          <pre id="markdown">(no output yet)</pre>
          <div class="btnrow" style="margin-top: 12px;">
            <button class="ghost" id="copyBtn" type="button">Copy markdown</button>
            <button class="ghost" id="copyJsonBtn" type="button">Copy response JSON</button>
          </div>
          <pre id="rawJson" style="margin-top: 12px;">(response JSON will appear here)</pre>
        </div>
      </section>
    </div>
  </div>

  <script id="reviewer-bootstrap" type="application/json">{bootstrap_json}</script>
  <script>
    const bootstrap = JSON.parse(
      document.getElementById("reviewer-bootstrap").textContent
    );
    const el = (id) => document.getElementById(id);
    const statusEl = el("status");
    const statusText = el("statusText");

    function setStatus(text, busy=false) {{
      statusText.textContent = text;
      statusEl.classList.toggle("busy", busy);
    }}

    function safeJsonParse(text) {{
      const t = (text || "").trim();
      if (!t) throw new Error("Payload is empty.");
      try {{ return JSON.parse(t); }} catch (e) {{
        throw new Error("Invalid JSON payload: " + e.message);
      }}
    }}

    function storeKey(path) {{
      const p = (path || "").trim();
      if (!p) return null;
      return "reviewerOverride::" + p;
    }}
    function loadOverride(path) {{
      const k = storeKey(path);
      if (!k) return null;
      try {{ return localStorage.getItem(k); }} catch {{ return null; }}
    }}
    function saveOverride(path, value) {{
      const k = storeKey(path);
      if (!k) return;
      try {{
        if (!value) localStorage.removeItem(k);
        else localStorage.setItem(k, value);
      }} catch {{}}
    }}

    function renderSamples() {{
      const select = el("sample");
      select.innerHTML = "";
      const opt0 = document.createElement("option");
      opt0.value = "";
      opt0.textContent = "— choose a sample —";
      select.appendChild(opt0);
      for (const s of (bootstrap.samples || [])) {{
        const opt = document.createElement("option");
        opt.value = s.path;
        opt.textContent = `[${{s.group}}] ${{s.name}}`;
        select.appendChild(opt);
      }}
      select.addEventListener("change", () => {{
        const p = select.value;
        if (p) el("path").value = p;
        const saved = loadOverride(p);
        if (saved) el("overrideCategory").value = saved;
      }});
    }}

    function renderChips() {{
      const root = el("chips");
      root.innerHTML = "";
      const catalog = bootstrap.catalog || [];
      const filter = (el("filter").value || "").trim().toLowerCase();
      const shown = catalog.filter((c) => {{
        if (!filter) return true;
        const hay = `${{c.group}} ${{c.label}} ${{c.path}}`.toLowerCase();
        return hay.includes(filter);
      }});
      for (const c of shown) {{
        const b = document.createElement("button");
        b.type = "button";
        b.className = "chip";
        b.innerHTML =
          `<div class="k">${{c.group}} · ${{c.label}}</div>` +
          `<div class="v">${{c.path}}</div>`;
        b.addEventListener("click", () => {{
          el("overrideCategory").value = c.path;
          saveOverride(el("path").value, c.path);
        }});
        root.appendChild(b);
      }}
    }}
    el("filter").addEventListener("input", renderChips);
    el("overrideCategory").addEventListener("input", () => {{
      saveOverride(el("path").value, (el("overrideCategory").value || "").trim());
    }});

    async function postJson(url, body) {{
      const resp = await fetch(url, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(body),
      }});
      const text = await resp.text();
      let data;
      try {{ data = JSON.parse(text); }} catch {{
        throw new Error(`HTTP ${{resp.status}}: ${{text}}`);
      }}
      if (!resp.ok) {{
        const detail = data.detail || data.message || JSON.stringify(data);
        throw new Error(`HTTP ${{resp.status}}: ${{detail}}`);
      }}
      return data;
    }}

    async function loadJson() {{
      const p = el("path").value.trim();
      const payloadText = el("payload").value.trim();
      if (!p && !payloadText) {{
        setStatus("Provide a path or paste JSON.", false);
        return;
      }}
      setStatus("Loading…", true);
      try {{
        let data;
        if (payloadText) {{
          data = await postJson("/review/api/load", {{ payload: safeJsonParse(payloadText) }});
        }} else {{
          data = await postJson("/review/api/load", {{ path: p }});
        }}
        if (data.payload) el("payload").value = JSON.stringify(data.payload, null, 2);
        const saved = loadOverride(p);
        if (saved) el("overrideCategory").value = saved;
        setStatus("Loaded.", false);
      }} catch (e) {{
        setStatus(e.message, false);
      }}
    }}

    async function runPipeline(withOverride) {{
      const p = el("path").value.trim();
      const override = (el("overrideCategory").value || "").trim();
      const overrideCompany = (el("overrideCompany").value || "").trim() || null;
      const overrideQuarter = (el("overrideQuarter").value || "").trim() || null;
      const allowDuplicate = !!el("allowDuplicate").checked;

      let payload = null;
      try {{
        payload = safeJsonParse(el("payload").value);
      }} catch (e) {{
        if (!p) {{
          setStatus(e.message, false);
          return;
        }}
      }}
      if (withOverride && !override) {{
        setStatus("Pick an override category (or use Run (no override)).", false);
        return;
      }}

      setStatus("Running…", true);
      try {{
        const body = {{
          allow_duplicate_ingest: allowDuplicate,
          override_company: overrideCompany,
          override_quarter: overrideQuarter,
        }};
        if (payload) body.payload = payload;
        else body.path = p;
        if (withOverride) body.override_category = override;

        if (withOverride) saveOverride(p, override);
        const data = await postJson("/review/api/run", body);

        el("resultStatus").textContent = data.status || "—";
        el("resultPrompt").textContent = data.prompt_name || "—";
        el("resultStored").textContent = data.stored_path || "—";
        el("resultDuplicate").textContent = data.duplicate_of || "—";
        el("markdown").textContent = data.markdown || "(no markdown in response)";
        el("rawJson").textContent = JSON.stringify(data, null, 2);
        setStatus("Done.", false);
      }} catch (e) {{
        el("rawJson").textContent = e.message;
        setStatus(e.message, false);
      }}
    }}

    el("loadBtn").addEventListener("click", loadJson);
    el("clearBtn").addEventListener("click", () => {{
      el("path").value = "";
      el("payload").value = "";
      el("overrideCategory").value = "";
      el("overrideCompany").value = "";
      el("overrideQuarter").value = "";
      el("allowDuplicate").checked = false;
      el("markdown").textContent = "(no output yet)";
      el("rawJson").textContent = "(response JSON will appear here)";
      el("resultStatus").textContent = "—";
      el("resultPrompt").textContent = "—";
      el("resultStored").textContent = "—";
      el("resultDuplicate").textContent = "—";
      setStatus("Cleared.", false);
    }});
    el("runBtn").addEventListener("click", () => runPipeline(true));
    el("runDefaultBtn").addEventListener("click", () => runPipeline(false));

    el("copyBtn").addEventListener("click", async () => {{
      try {{
        await navigator.clipboard.writeText(el("markdown").textContent || "");
        setStatus("Copied markdown.", false);
      }} catch {{
        setStatus("Copy failed (browser permissions).", false);
      }}
    }});
    el("copyJsonBtn").addEventListener("click", async () => {{
      try {{
        await navigator.clipboard.writeText(el("rawJson").textContent || "");
        setStatus("Copied JSON.", false);
      }} catch {{
        setStatus("Copy failed (browser permissions).", false);
      }}
    }});

    renderSamples();
    renderChips();
    setStatus("Ready. Allowed roots: " + (bootstrap.allowed_roots || []).join(" | "), false);
  </script>
</body>
</html>
"""
