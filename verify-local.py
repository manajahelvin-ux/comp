#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify-local.py — Vérification d'erreur complète des 131 LP en local.

Contrôles :
  1. refs        : toutes les références locales (src/href/poster/videos/url())
                   pointent vers des fichiers existants
  2. external    : plus aucune dépendance externe bloquante dans le HTML/CSS
                   (GTM, iframe externe, prefetch, uploads-ssl, cdn.prod, script http)
  3. js-syntax   : `node --check` sur les 131 script.js
  4. responsive  : viewport, @media, pas de body min-width bloquant, iframes sans largeur fixe
  5. runtime     : chaque page exécutée dans jsdom — erreurs JS non interceptées
  6. http        : toutes les pages répondent 200 sur le serveur local

Usage :  python3 verify-local.py            (tous les contrôles)
         python3 verify-local.py refs       (un contrôle précis)
"""

import json
import os
import re
import subprocess
import sys
import threading
import functools
import http.server
import socketserver
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FORBIDDEN_HTML = [
    ("GTM/gtag loader", re.compile(r"googletagmanager|gtm\.start|gtag\(\s*['\"]config", re.I)),
    ("prefetch externe", re.compile(r'<link\b[^>]*rel="prefetch"[^>]*https?://', re.I)),
    ("iframe externe", re.compile(r'<iframe[^>]*\bsrc="https?://', re.I)),
    ("script externe", re.compile(r'<script[^>]*\bsrc="https?://', re.I)),
    ("uploads-ssl", re.compile(r"uploads-ssl\.webflow\.com", re.I)),
    ("lien htpps cassé", re.compile(r"htpps://", re.I)),
]


def sites():
    return sorted(
        d for d in ROOT.iterdir()
        if d.is_dir() and d.name not in (".git", ".verify", "fontsrc")
        and (d / "index.html").is_file()
    )


# ---------------------------------------------------------------- 1. refs
def check_refs():
    pats = [
        re.compile(r'<script[^>]*\bsrc="([^"]+)"'),
        re.compile(r'<link[^>]*\bhref="([^"]+)"'),
        re.compile(r'<img[^>]*\bsrc="([^"]+)"'),
        re.compile(r'<source[^>]*\bsrc="([^"]+)"'),
        re.compile(r'<a[^>]*\bhref="([^"]+)"'),
        re.compile(r'data-poster-url="([^"]+)"'),
    ]
    missing = []
    for d in sites():
        s = (d / "index.html").read_text(encoding="utf-8", errors="replace")
        refs = set()
        for p in pats:
            refs.update(p.findall(s))
        for m in re.finditer(r'data-video-urls="([^"]+)"', s):
            refs.update(x.strip() for x in m.group(1).split(","))
        for r in refs:
            if re.match(r"^(https?:|mailto:|tel:|#|javascript:|data:)", r):
                continue
            if r.startswith("../"):
                path = os.path.normpath(str(d / r))
            elif r.startswith("/"):
                path = str(ROOT / r.lstrip("/"))
            else:
                path = str(d / r)
            path = path.split("#")[0].split("?")[0]
            if path.endswith("/"):
                path = path + "index.html"
            if not os.path.exists(path):
                missing.append(f"{d.name}: {r}")
        # fonts-global.css -> woff2
        fg = d / "fonts-global.css"
        if fg.is_file():
            for u in re.findall(r"url\((?:'|\")?fonts/([^)'\"]+)", fg.read_text(encoding="utf-8")):
                if not (d / "fonts" / u).is_file():
                    missing.append(f"{d.name}: fonts/{u}")
    return missing


# ------------------------------------------------------------- 2. external
def check_external():
    hits = []
    for d in sites():
        s = (d / "index.html").read_text(encoding="utf-8", errors="replace")
        for name, pat in FORBIDDEN_HTML:
            if pat.search(s):
                hits.append(f"{d.name}: {name}")
        css = (d / "style.css").read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'url\((["\']?)(https?://[^)"\']+)\1\)', css):
            hits.append(f"{d.name}: style.css url externe {m.group(2)[:60]}")
    return hits


# ----------------------------------------------------------- 3. js-syntax
def check_js_syntax():
    fails = []
    for d in sites():
        r = subprocess.run(["node", "--check", str(d / "script.js")],
                           capture_output=True, text=True)
        if r.returncode != 0:
            first = (r.stderr or "").strip().splitlines()
            fails.append(f"{d.name}: {first[0] if first else 'syntax error'}")
    return fails


# ---------------------------------------------------------- 4. responsive
def check_responsive():
    issues = []
    for d in sites():
        s = (d / "index.html").read_text(encoding="utf-8", errors="replace")
        m = re.search(r'<meta\b[^>]*name="viewport"[^>]*>', s, re.I)
        if not m or "width=device-width" not in m.group(0):
            issues.append(f"{d.name}: viewport absent/incomplet")
        if re.search(r"user-scalable=no|maximum-scale=1\b", s):
            issues.append(f"{d.name}: zoom bloqué")
        if re.search(r'<iframe[^>]*\bwidth="\d+"', s):
            issues.append(f"{d.name}: iframe largeur fixe")
        css = (d / "style.css").read_text(encoding="utf-8", errors="replace")
        if not re.search(r"@media", css):
            issues.append(f"{d.name}: aucun @media (non responsive)")
        for m in re.finditer(r"(?:^|\})\s*([^{}]*\bbody\b[^{}]*)\{([^}]*)\}", css, re.M):
            mw = re.search(r"min-width:\s*(\d+)px", m.group(2))
            if mw and int(mw.group(1)) > 480:
                issues.append(f"{d.name}: body min-width {mw.group(1)}px")
    return issues


# ------------------------------------------------------------- 5. runtime
JSDOM_CHECK = r"""
const fs = require('fs'), path = require('path');
const { JSDOM, VirtualConsole } = require(path.join(process.argv[2], 'node_modules', 'jsdom'));
const root = process.argv[3];

class FakeResponse {
  constructor(body, init) {
    init = init || {};
    this._body = String(body == null ? '' : body);
    this.status = init.status || 200;
    this.ok = this.status >= 200 && this.status < 300;
    const h = (init.headers) || {};
    this.headers = { get: (k) => {
      for (const key of Object.keys(h)) if (key.toLowerCase() === String(k).toLowerCase()) return h[key];
      return null;
    }};
  }
  text() { return Promise.resolve(this._body); }
  json() { return Promise.resolve(JSON.parse(this._body)); }
}

const IGNORE = /Not implemented|Could not parse CSS|Error: Not applicable/;
(async () => {
  const dirs = fs.readdirSync(root).filter(d =>
    d !== '.git' && d !== '.verify' && d !== 'fontsrc' &&
    fs.existsSync(path.join(root, d, 'index.html')));
  const bad = [];
  for (const site of dirs) {
    const errs = [];
    const vc = new VirtualConsole();
    vc.on('jsdomError', (e) => {
      const m = String((e && e.message) || e);
      if (IGNORE.test(m)) return;
      const detail = (e && e.detail && String(e.detail.message || e.detail)) || '';
      if (IGNORE.test(detail)) return;
      errs.push(m.split('\n')[0] + (detail ? ' | ' + detail.split('\n')[0] : ''));
    });
    vc.on('error', (...a) => {
      const m = a.map(String).join(' ');
      if (IGNORE.test(m)) return;
      errs.push('console.error: ' + m.slice(0, 220));
    });
    const html = fs.readFileSync(path.join(root, site, 'index.html'), 'utf8');
    const dom = new JSDOM(html, {
      url: 'http://localhost:8080/' + site + '/',
      runScripts: 'outside-only',
      pretendToBeVisual: true,
      virtualConsole: vc,
    });
    const w = dom.window;
    w.Response = FakeResponse;
    if (typeof w.matchMedia !== 'function') {
      w.matchMedia = function (q) {
        return {
          matches: false, media: String(q), onchange: null,
          addListener() {}, removeListener() {},
          addEventListener() {}, removeEventListener() {},
          dispatchEvent() { return false; },
        };
      };
    }
    // canvas: jsdom n'implémente pas getContext -> on stub (les vrais
    // navigateurs ont un canvas natif ; sinon chunk1 s'arrête à tort)
    try {
      const makeCtx = () => {
        const o = {
          measureText: () => ({ width: 0 }),
          getImageData: () => ({ data: new Uint8ClampedArray(4), width: 1, height: 1 }),
          createImageData: () => ({ data: new Uint8ClampedArray(4), width: 1, height: 1 }),
          createLinearGradient: () => ({ addColorStop() {} }),
          createRadialGradient: () => ({ addColorStop() {} }),
          createPattern: () => null,
          getContext: () => null,
          canvas: { width: 300, height: 150 },
        };
        return new Proxy(o, {
          get: (t, p) => (p in t ? t[p]
            : (typeof p === 'string' ? function () { return undefined; } : undefined)),
          set: (t, p, v) => { t[p] = v; return true; },
        });
      };
      w.HTMLCanvasElement.prototype.getContext = function () { return makeCtx(); };
    } catch (e) {}
    w.fetch = (input) => {
      try {
        const url = (typeof input === 'string') ? input : input.url;
        const u = new URL(url, 'http://localhost:8080/' + site + '/');
        if (u.origin !== 'http://localhost:8080') return Promise.resolve(new FakeResponse('{}'));
        const p = path.join(root, decodeURIComponent(u.pathname));
        if (fs.existsSync(p) && fs.statSync(p).isFile()) {
          return Promise.resolve(new FakeResponse(fs.readFileSync(p, 'utf8')));
        }
        return Promise.resolve(new FakeResponse('', { status: 404 }));
      } catch (e) { return Promise.reject(e); }
    };
    w.addEventListener('error', (ev) => {
      if (ev && ev.message && !IGNORE.test(ev.message)) errs.push('window.error: ' + ev.message);
    });
    try {
      w.eval(fs.readFileSync(path.join(root, site, 'script.js'), 'utf8'));
    } catch (e) {
      errs.push('eval: ' + ((e && e.message) || e));
    }
    await new Promise((r) => setTimeout(r, 500));
    try { w.close(); } catch (e) {}
    const uniq = [...new Set(errs)];
    if (uniq.length) bad.push({ site, errs: uniq.slice(0, 6) });
  }
  console.log(JSON.stringify({ total: dirs.length, failed: bad.length, bad }));
})().catch((e) => { console.error(e); process.exit(1); });
"""


def check_runtime():
    check_file = ROOT / ".verify" / "jsdom-check.js"
    check_file.write_text(JSDOM_CHECK, encoding="utf-8")
    r = subprocess.run(
        ["node", str(check_file), str(ROOT / ".verify"), str(ROOT)],
        capture_output=True, text=True, cwd=str(ROOT), timeout=900,
    )
    if r.returncode != 0:
        return [f"jsdom harness failed: {r.stderr[:400]}"]
    out = r.stdout.strip().splitlines()[-1]
    data = json.loads(out)
    fails = []
    for b in data["bad"]:
        fails.append(f"{b['site']}: " + " || ".join(b["errs"])[:400])
    return fails, data


# --------------------------------------------------------------- 6. http
def check_http(port=8077):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))

    class QuietHandler(handler.func):
        def log_message(self, *a):  # silence des accès
            pass

    class Srv(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True
        def handle_error(self, request, client_address):
            pass  # clients qui ferment tôt : non bloquant

    httpd = Srv(("0.0.0.0", port),
                 functools.partial(QuietHandler, directory=str(ROOT)))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    fails = []
    try:
        for d in sites():
            for sub in ("", "style.css", "script.js", "fonts-global.css"):
                url = f"http://127.0.0.1:{port}/{d.name}/" + sub
                if sub and not (d / sub).is_file():
                    continue
                try:
                    with urllib.request.urlopen(url, timeout=10) as resp:
                        if resp.status != 200:
                            fails.append(f"{url} -> {resp.status}")
                except Exception as e:
                    fails.append(f"{url} -> {e}")
    finally:
        httpd.shutdown()
    return fails


# ---------------------------------------------------------------------------
def main():
    args = sys.argv[1:] or ["refs", "external", "js-syntax", "responsive", "runtime", "http"]
    only = set(args)
    summary = []

    def run(name, fn, expected_ok):
        if name not in only:
            return None
        res = fn()
        if name == "runtime":
            if isinstance(res, list):
                fails = res
                note = "harness jsdom en échec"
            else:
                fails, data = res
                note = f"{data['total']} pages exécutées, {data['failed']} en erreur"
        else:
            fails = res
            note = f"{len(fails)} problème(s)"
        status = "OK " if not fails else "FAIL"
        summary.append((name, status, note, fails))
        print(f"[{status}] {name:12s} {note}")
        for f in fails[:40]:
            print(f"        - {f}")
        if len(fails) > 40:
            print(f"        … +{len(fails) - 40} autres")
        return fails

    run("refs", check_refs, True)
    run("external", check_external, True)
    run("js-syntax", check_js_syntax, True)
    run("responsive", check_responsive, True)
    run("runtime", check_runtime, True)
    run("http", check_http, True)

    print("\n=== SYNTHÈSE ===")
    ok = True
    for name, status, note, fails in summary:
        print(f"  {status}  {name:12s} {note}")
        if fails:
            ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
