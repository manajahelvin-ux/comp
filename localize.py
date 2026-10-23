#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
localize.py — Neutralise les dépendances externes des LP exportées Webflow
afin qu'elles fonctionnent EN LOCAL, sans toucher au design ni à style.css.

Phases :
  fetch-fonts  : télécharge les polices Google manquantes via @fontsource (npm)
  html         : supprime dans index.html les loaders GTM/gtag, les iframes
                 noscript GTM et les <link rel="prefetch"> externes
  js           : injecte le « local-shim » en tête de script.js (interception
                 XHR / fetch / sendBeacon / scripts+links dynamiques / images)
                 + neutralise la redirection distante de site/
  fonts        : génère fonts-global.css (local) + copie les .woff2 dans fonts/
                 et ajoute le <link> dans index.html
  report       : écrit LOCAL.md (bilan + restauration avant import serveur)
  all          : toutes les phases dans l'ordre (sauf fetch-fonts)

Idempotent (marqueurs). Lancer depuis la racine du dépôt :
    python3 localize.py fetch-fonts
    python3 localize.py all
"""

import os
import re
import sys
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FONTSRC = ROOT / "fontsrc"
MARKER_SHIM = "__LOCAL_SHIM__"
MARKER_FONTS_LINK = 'href="fonts-global.css"'

# ---------------------------------------------------------------------------
# Polices à localiser (famille Google Fonts -> paquet @fontsource)
# ---------------------------------------------------------------------------

FONT_PACKS = [
    "alegreya", "alegreya-sans", "changa-one", "great-vibes", "inter", "lato",
    "montserrat", "montserrat-alternates", "oswald", "poppins", "prompt",
    "pt-serif", "sora", "source-sans-3", "ubuntu", "ubuntu-sans", "varela",
    "varela-round", "vollkorn", "work-sans",
]

# Familles résolues par le système d'exploition (en prod comme en local)
# ou artefacts de parsing du CSS d'export -> on n'en localise pas.
FONT_NOISE = {
    "sans-serif", "serif", "monospace", "cursive", "fantasy", "system-ui",
    "inherit", "initial", "unset", "revert", "ui-sans-serif", "ui-monospace",
    "ui-serif", "ui-rounded", "arial", "helvetica", "helvetica neue", "times",
    "times new roman", "timesnewroman", "courier", "courier new", "georgia",
    "verdana", "tahoma", "trebuchet ms", "impact", "lucida grande",
    "lucida console", "segoe", "segoe ui", "segoe print", "apple system",
    "-apple-system", "blinkmacsystemfont", "webflow-icons", "webflow icons",
}

# ---------------------------------------------------------------------------
# Le shim JS injecté en tête de chaque script.js
# ---------------------------------------------------------------------------

SHIM = r"""/*__LOCAL_SHIM__ v2 — neutralise les appels réseau externes en environnement
   local (formulaires Webflow, OTP hellolead, Google Sheets/Apps Script, GTM,
   Google Fonts, Turnstile, pixels…) et simule la réussite des soumissions
   de formulaires (voir section 7). Inactif hors local : le déploiement
   serveur n'est pas impacté. Design et style.css inchangés. */
(function () {
  'use strict';
  try {
    if (window.__LOCAL_SHIM__) { return; }
    var host = location.hostname || '';
    var forced = false;
    try { forced = localStorage.getItem('localShim') === '1'; } catch (e) {}
    var isLocal = !host || host === 'localhost' || host === '127.0.0.1' ||
      host === '[::1]' || /\.e2b\.app$/.test(host) || /\.local$/.test(host);
    if (!isLocal && !forced) { return; }
    window.__LOCAL_SHIM__ = 1;

    var TAG = '[local-shim]';

    /* dataLayer / gtag : on garde la couche de données locale (sans réseau)
       pour que les scripts de consentement des pages ne cassent pas. */
    window.dataLayer = window.dataLayer || [];
    if (typeof window.gtag !== 'function') {
      window.gtag = function () { (window.dataLayer = window.dataLayer || []).push(arguments); };
    }

    function isExternal(url) {
      if (typeof url !== 'string' || url === '') { return false; }
      try {
        var u = new URL(url, location.href);
        if (u.protocol === 'data:' || u.protocol === 'blob:' || u.protocol === 'about:') { return false; }
        if (u.protocol === 'file:' ) { return false; }
        return u.origin !== location.origin;
      } catch (e) { return false; }
    }

    /* Réponse simulée : JSON « polyvalent » (ok/success/status/resultat)
       pour les API, script vide pour les .js distants. */
    function bodyFor(url) {
      if (/\.js(\?|#|$)|\/gtm\.js|\/gtag\.js|api\.js|typekit|fontdeck|brandjs/i.test(url)) {
        return { ct: 'application/javascript; charset=utf-8',
                 text: '/* ' + TAG + ' script externe neutralisé */' };
      }
      return { ct: 'application/json; charset=utf-8',
               text: JSON.stringify({
                 ok: true, success: true, status: 'ok', statusText: 'ok',
                 result: 'success', error: false,
                 message: TAG + ' reponse simulee (usage local)',
                 redirectTo: null
               }) };
    }
    function log(method, url) {
      try { console.info(TAG, method, '->', url); } catch (e) {}
    }

    /* 1) XMLHttpRequest — intercepte $.ajax (jQuery), les appels OTP
          hellolead, l'API Webflow forms, Apps Script, le CRM UBEPRO… */
    var origOpen = XMLHttpRequest.prototype.open;
    var origSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (method, url) {
      this.__shimUrl = url;
      this.__shimMethod = method;
      return origOpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function () {
      var self = this;
      if (!isExternal(self.__shimUrl)) { return origSend.apply(this, arguments); }
      log(self.__shimMethod || 'XHR', self.__shimUrl);
      var b = bodyFor(String(self.__shimUrl));
      try {
        self.getResponseHeader = function (n) {
          return /content-type/i.test(n || '') ? b.ct : null;
        };
        self.getAllResponseHeaders = function () {
          return 'content-type: ' + b.ct + '\r\n';
        };
        Object.defineProperty(self, 'readyState', { configurable: true, value: 4 });
        Object.defineProperty(self, 'status', { configurable: true, value: 200 });
        Object.defineProperty(self, 'statusText', { configurable: true, value: 'OK' });
        Object.defineProperty(self, 'responseText', { configurable: true, value: b.text });
        Object.defineProperty(self, 'response', { configurable: true, value: b.text });
        Object.defineProperty(self, 'responseURL', { configurable: true, value: String(self.__shimUrl) });
      } catch (e) { console.warn(TAG, e); }
      setTimeout(function () {
        try {
          self.dispatchEvent(new Event('readystatechange'));
          self.dispatchEvent(new Event('load'));
          self.dispatchEvent(new Event('loadend'));
        } catch (e) { console.warn(TAG, e); }
      }, 10);
    };

    /* 2) fetch — CRM UBEPRO, OTP hellolead, Google Sheets, endpoints divers.
          Ambiances sans fetch/Response (jsdom, tests) : polyfills minimaux
          pour que les flux type OTP ne lèvent pas « fetch is not defined ».
          Navigateur natif : inchangé (wrapping d'origine conservé). */
    if (typeof window.Response !== 'function') {
      window.Response = function (body, init) {
        init = init || {};
        this._body = (body === undefined || body === null) ? '' : String(body);
        this.status = init.status || 200;
        this.ok = this.status >= 200 && this.status < 300;
        var headers = init.headers || {};
        this.headers = {
          get: function (n) {
            var want = String(n || '').toLowerCase();
            for (var k in headers) {
              if (k.toLowerCase() === want) { return headers[k]; }
            }
            return null;
          }
        };
      };
      window.Response.prototype.text = function () {
        return Promise.resolve(this._body);
      };
      window.Response.prototype.json = function () {
        try { return Promise.resolve(JSON.parse(this._body)); }
        catch (e) { return Promise.reject(e); }
      };
    }
    if (typeof window.fetch !== 'function') {
      window.fetch = function (input) {
        var url = (typeof input === 'string') ? input
                : (input && typeof input.url === 'string') ? input.url : '';
        var method = (input && input.method) || 'GET';
        if (url && isExternal(url)) {
          log('FETCH', url);
          var b = bodyFor(url);
          return Promise.resolve(new window.Response(b.text, {
            status: 200, headers: { 'Content-Type': b.ct }
          }));
        }
        return new Promise(function (resolve, reject) {
          try {
            var x = new XMLHttpRequest();
            x.open(method, url, true);
            x.onload = function () {
              resolve(new window.Response(x.responseText, {
                status: x.status || 200,
                headers: { 'Content-Type':
                  x.getResponseHeader('Content-Type') || 'text/html; charset=utf-8' }
              }));
            };
            x.onerror = function () { reject(new Error('fetch local: échec réseau')); };
            x.send((input && input.body) || null);
          } catch (e) { reject(e); }
        });
      };
    } else {
      var origFetch = window.fetch;
      window.fetch = function (input) {
        var url = (typeof input === 'string') ? input
                : (input && typeof input.url === 'string') ? input.url : null;
        if (url && isExternal(url)) {
          log('FETCH', url);
          var b = bodyFor(url);
          try {
            return Promise.resolve(new Response(b.text, {
              status: 200, headers: { 'Content-Type': b.ct }
            }));
          } catch (e) {
            return Promise.reject(e);
          }
        }
        return origFetch.apply(this, arguments);
      };
    }

    /* 3) sendBeacon — pixels & replis « beacon » des API. */
    if (navigator.sendBeacon) {
      var origBeacon = navigator.sendBeacon.bind(navigator);
      navigator.sendBeacon = function (url) {
        if (isExternal(url)) { log('BEACON', url); return true; }
        return origBeacon.apply(null, arguments);
      };
    }

    /* 4) new Image() / img.src — pixels de tracking (FB, Google Ads…). */
    try {
      var srcDesc = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
      if (srcDesc && srcDesc.set) {
        Object.defineProperty(HTMLImageElement.prototype, 'src', {
          configurable: true,
          get: srcDesc.get,
          set: function (v) {
            if (isExternal(v)) {
              log('IMG', v);
              var self = this;
              setTimeout(function () {
                try { self.dispatchEvent(new Event('load')); } catch (e) {}
              }, 0);
              return;
            }
            return srcDesc.set.call(this, v);
          }
        });
      }
    } catch (e) {}

    /* 5) Injection dynamique de <script src> / <link rel=stylesheet> externes :
          Google Fonts (WebFont.load), Turnstile, fontdeck/typekit, brand.js,
          gtm.js, taggy… On n'attache pas l'élément et on déclenche « load »
          pour que les callbacks avancent (fontes locales prises en charge par
          fonts-global.css). */
    function blockedNode(node) {
      if (!node || node.nodeType !== 1) { return false; }
      var t = String(node.tagName || '').toUpperCase();
      if (t === 'SCRIPT') { return isExternal(node.getAttribute('src')); }
      if (t === 'LINK') {
        var rel = String(node.getAttribute('rel') || '').toLowerCase();
        if (rel.indexOf('stylesheet') >= 0 || rel.indexOf('modulepreload') >= 0 ||
            rel.indexOf('preload') >= 0 || rel.indexOf('prefetch') >= 0) {
          return isExternal(node.getAttribute('href'));
        }
      }
      return false;
    }
    function fakeLoad(node) {
      setTimeout(function () {
        try { node.dispatchEvent(new Event('load')); } catch (e) {}
      }, 10);
    }
    var origAppend = Node.prototype.appendChild;
    var origInsert = Node.prototype.insertBefore;
    Node.prototype.appendChild = function (node) {
      if (blockedNode(node)) {
        log('SCRIPT/LINK', node.getAttribute('src') || node.getAttribute('href'));
        fakeLoad(node);
        return node;
      }
      return origAppend.call(this, node);
    };
    Node.prototype.insertBefore = function (node, ref) {
      if (blockedNode(node)) {
        log('SCRIPT/LINK', node.getAttribute('src') || node.getAttribute('href'));
        fakeLoad(node);
        return node;
      }
      return origInsert.call(this, node, ref);
    };

    /* 6) Turnstile (Cloudflare) : stub local — callback immédiat. */
    if (typeof window.turnstile === 'undefined') {
      window.turnstile = {
        render: function (el, opts) {
          opts = opts || {};
          if (typeof opts.callback === 'function') {
            setTimeout(function () { opts.callback('local-shim-token'); }, 0);
          }
          return 'local-shim-widget';
        },
        remove: function () {}, reset: function () {},
        getResponse: function () { return 'local-shim-token'; },
        isExpired: function () { return false; }
      };
    }

    /* 7) Formulaires : l'export Webflow n'embarque PAS le client de
          soumission native (API formdata) ; pour un <form> sans action
          externe, webflow.js enregistre un handler d'échec direct qui
          bascule le bloc d'erreur .w-form-fail — sans tenter le moindre
          appel réseau (comportement identique hors local : préexistant à
          toute neutralisation). On remplace ce handler par une réussite
          simulée : .w-form-done affiché, data-redirect mappé vers le
          dossier local quand il existe (table FORM_REDIRECTS générée par
          localize.py). Les blocs .w-form-fail ont en outre été supprimés
          du HTML (phase nofail) : l'erreur ne peut plus s'afficher. */
    var FORM_REDIRECTS = __FORM_REDIRECTS__;
    function localFormSuccess(s) {
      try {
        if (s && s.evt && typeof s.evt.preventDefault === 'function') {
          s.evt.preventDefault();
        }
      } catch (e) {}
      try {
        if (s) {
          s.success = true;
          if (s.redirect) {
            var to = (FORM_REDIRECTS && FORM_REDIRECTS[s.redirect]) || null;
            if (to) { location.href = to; return; }
            if (!/^https?:\/\//i.test(s.redirect)) {
              location.href = s.redirect; return;
            }
            console.info(TAG, 'data-redirect sans equivalent local — succes affiche.');
          }
          if (s.done && s.done.length) { s.done.toggle(true); }
          if (s.fail && s.fail.length) { s.fail.toggle(false); }
          if (s.form && s.form.length) { s.form.toggle(false); }
        }
        console.info(TAG, 'form soumis — succes simule (usage local).');
      } catch (e) { console.warn(TAG, e); }
    }
    (function installLocalForms() {
      var tries = 0;
      (function tick() {
        tries += 1;
        var $ = window.jQuery, patched = 0;
        try {
          if ($ && typeof $.data === 'function') {
            $('form').each(function () {
              var datas = $.data(this);
              if (!datas) { return; }
              for (var key in datas) {
                var s = datas[key];
                if (s && typeof s === 'object' && s.form && s.done &&
                    typeof s.handler === 'function' &&
                    s.handler !== localFormSuccess) {
                  s.handler = localFormSuccess;
                  patched += 1;
                }
              }
            });
          }
        } catch (e) { console.warn(TAG, e); }
        if (patched) { return; }
        if (tries < 100 && document.querySelector('form')) {
          setTimeout(tick, 100);
        } else if (tries < 100 && document.readyState !== 'complete') {
          setTimeout(tick, 100);
        }
      })();
    })();

    console.info(TAG, 'actif — appels reseau externes neutralises (usage local).');
  } catch (e) { console.error(TAG, e); }
})();
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sites() -> list:
    return sorted(
        d for d in ROOT.iterdir()
        if d.is_dir() and d.name != ".git" and (d / "index.html").is_file()
    )


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, check=True, text=True,
                          capture_output=True, **kw)


# ---------------------------------------------------------------------------
# Phase HTML
# ---------------------------------------------------------------------------

RE_SCRIPT_INLINE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S | re.I)
RE_GTM_BODY = re.compile(r"googletagmanager|gtm\.start|gtag\(\s*['\"]config", re.I)
RE_GTM_NOSCRIPT = re.compile(
    r"<noscript>(?:(?!</noscript>).)*?googletagmanager.*?</noscript>", re.S | re.I
)
RE_PREFETCH_EXT = re.compile(
    r'<link\b[^>]*rel="prefetch"[^>]*href="https?://[^"]*"[^>]*>\s*', re.I
)
RE_PREFETCH_EXT2 = re.compile(
    r'<link\b[^>]*href="https?://[^"]*"[^>]*rel="prefetch"[^>]*>\s*', re.I
)


def _strip_gtm_scripts(s):
    def repl(m):
        return "" if RE_GTM_BODY.search(m.group(1)) else m.group(0)
    return RE_SCRIPT_INLINE.sub(repl, s)


def phase_html(verbose=True):
    n_script = n_ns = n_pf = 0
    for d in sites():
        f = d / "index.html"
        s = f.read_text(encoding="utf-8", errors="replace")
        orig = s
        before = len(RE_SCRIPT_INLINE.findall(s))
        s = _strip_gtm_scripts(s)
        after = len(RE_SCRIPT_INLINE.findall(s))
        s, c2 = RE_GTM_NOSCRIPT.subn("", s)
        s, c3 = RE_PREFETCH_EXT.subn("", s)
        s, c4 = RE_PREFETCH_EXT2.subn("", s)
        s = re.sub(r"\n{3,}", "\n\n", s)
        if s != orig:
            f.write_text(s, encoding="utf-8")
        n_script += before - after
        n_ns += c2
        n_pf += c3 + c4
    if verbose:
        print(f"[html] scripts GTM/gtag supprimés : {n_script} | "
              f"iframes noscript GTM : {n_ns} | prefetch externes : {n_pf}")
    return n_script, n_ns, n_pf


# ---------------------------------------------------------------------------
# Phase JS (shim + redirection site/)
# ---------------------------------------------------------------------------

# Bloc shim complet (v1/v2) : du marqueur de début jusqu'au IIFE de fermeture
# (le motif `console.error(TAG, …)` n'existe qu'une fois, dans le catch final).
RE_SHIM_BLOCK = re.compile(
    r"/\*__LOCAL_SHIM__.*?\} catch \(e\) \{ console\.error\(TAG, e\); \}\n\}\)\(\);\n",
    re.S,
)


def build_shim():
    """SHIM courant avec la table FORM_REDIRECTS (data-redirect -> dossier local)."""
    table = {}
    for d in sites():
        h = (d / "index.html").read_text(encoding="utf-8", errors="replace")
        for url in re.findall(r'data-redirect="([^"]+)"', h):
            if url in table:
                continue
            if re.match(r"^https?://", url):
                folder = folder_for_url(url)
                table[url] = ("../" + folder + "/") if folder else None
            else:
                table[url] = url  # chemin relatif : tel quel
    return SHIM.replace(
        "__FORM_REDIRECTS__",
        json.dumps(table, ensure_ascii=False, sort_keys=True),
    )


SITE_REDIRECTS = [
    ('window.location.href = "https://www.comparateurpro.fr/mentions-legales";',
     'window.location.href = "mentions-legales/";'),
    # depuis /site/, il faut remonter d'un cran pour atteindre /mentions-legales/
    ('window.location.href = "mentions-legales/";',
     'window.location.href = "../mentions-legales/";'),
]


def phase_js(verbose=True):
    n_shim = n_up = n_redir = 0
    shim = build_shim()
    for d in sites():
        f = d / "script.js"
        s = f.read_text(encoding="utf-8", errors="replace")
        changed = False
        for old, new in SITE_REDIRECTS:
            if old in s:
                s = s.replace(old, new, 1)
                n_redir += 1
                changed = True
        if MARKER_SHIM not in s:
            s = shim + "\n" + s
            n_shim += 1
            changed = True
        elif shim not in s:
            # bloc shim présent mais périmé (v1, ou table FORM_REDIRECTS
            # obsolète) : remplacer tout le bloc par la version courante
            m = RE_SHIM_BLOCK.search(s)
            if m:
                s = s[:m.start()] + shim + "\n" + s[m.end():]
                n_up += 1
                changed = True
        if changed:
            f.write_text(s, encoding="utf-8")
    if verbose:
        print(f"[js] shim injecté : {n_shim} script.js | mis à jour : {n_up} | "
              f"redirections neutralisées : {n_redir}")
    return n_shim, n_up, n_redir


# ---------------------------------------------------------------------------
# Phase polices
# ---------------------------------------------------------------------------

RE_FF = re.compile(r"@font-face\s*{[^}]*?font-family:\s*['\"]?([^;'\"]+)", re.I)
RE_DECL = re.compile(r"([^{}]+)\{([^{}]*)\}")


def norm_fam(name):
    name = name.lower()
    name = name.replace("!important", "")
    return name.strip(" \t'\"")


def site_font_needs(css_path: Path):
    """Retourne {(famille, poids, style)} à fournir localement pour ce site."""
    s = css_path.read_text(encoding="utf-8", errors="replace")
    local = {norm_fam(m.group(1)) for m in RE_FF.finditer(s)}
    needs = set()
    for m in RE_DECL.finditer(s):
        decls = m.group(2)
        fm = re.search(r"font-family:\s*([^;]+)", decls)
        if not fm:
            continue
        target = None
        for raw in fm.group(1).split(","):
            fam = norm_fam(raw)
            if fam and fam not in FONT_NOISE and fam not in local:
                target = fam
                break
        if not target:
            continue
        w = re.search(r"font-weight:\s*([a-z0-9]+)", decls)
        weight = (w.group(1) if w else "400").lower()
        if weight == "bold":
            weight = "700"
        elif weight == "normal":
            weight = "400"
        elif not weight.isdigit():
            weight = "400"
        st = "italic" if re.search(r"font-style:\s*(italic|oblique)", decls) else "normal"
        needs.add((target, weight, st))
    return needs


RE_FAMILIES = re.compile(r"families:\s*\[([^\]]*)\]")


def site_italic_requests(js_path: Path):
    """Familles/poids pour lesquelles la config WebFont d'origine (Google
    Fonts) déclarait un italique -> on livre aussi le vrai italique local."""
    out = set()
    try:
        s = js_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    m = RE_FAMILIES.search(s)
    if not m:
        return out
    for entry in re.findall(r'"([^"]+)"', m.group(1)):
        name, _, weights = entry.partition(":")
        fam = norm_fam(name)
        for wpart in weights.split(","):
            wpart = wpart.strip().lower()
            if not wpart:
                continue
            if wpart.endswith("italic"):
                w = wpart[:-6]
                out.add((fam, w if w.isdigit() else "400"))
    return out


def phase_fetch_fonts(verbose=True):
    FONTSRC.mkdir(exist_ok=True)
    for pkg in FONT_PACKS:
        dest = FONTSRC / pkg
        if (dest / "package.json").is_file():
            if verbose:
                print(f"[fonts] déjà présent : {pkg}")
            continue
        out = run(["npm", "pack", f"@fontsource/{pkg}", "--pack-destination", str(FONTSRC)])
        tgz = FONTSRC / out.stdout.strip().splitlines()[-1]
        dest.mkdir(parents=True, exist_ok=True)
        run(["tar", "-xzf", str(tgz), "-C", str(dest), "--strip-components=1"])
        tgz.unlink()
        if verbose:
            print(f"[fonts] téléchargé : @fontsource/{pkg}")


def phase_fonts(verbose=True):
    missing_pkgs = [p for p in FONT_PACKS if not (FONTSRC / p / "package.json").is_file()]
    if missing_pkgs:
        print(f"[fonts] ERREUR — paquets absents : {missing_pkgs}\n"
              f"        lance d'abord :  python3 localize.py fetch-fonts")
        return 0, 0
    n_css = n_link = 0
    total_files = 0
    for d in sites():
        needs = site_font_needs(d / "style.css")
        # uniquement les familles qu'on sait packager
        needs = {n for n in needs if n[0].replace(" ", "-") in FONT_PACKS}
        if not needs:
            continue
        # ajouter les vrais italiques si la config Google d'origine les listait
        ital = site_italic_requests(d / "script.js")
        extra = {(f, w, "italic") for (f, w) in ital
                 if (f, w, "normal") in needs and (f, w, "italic") not in needs}
        needs |= extra
        parts = ["/* fonts-global.css — généré par localize.py (ne pas éditer).\n"
                 "   Polices Google Fonts localisées via @fontsource : le rendu\n"
                 "   ne dépend plus de fonts.googleapis.com. */\n"]
        copied = set()
        for fam, weight, style in sorted(needs):
            pkg = fam.replace(" ", "-")
            fname = f"{weight}{'-italic' if style == 'italic' else ''}.css"
            src = FONTSRC / pkg / fname
            if not src.is_file():
                # variante italique indisponible -> le navigateur simulera,
                # comme Google Fonts le fait pour les familles sans italique.
                continue
            txt = src.read_text(encoding="utf-8")
            # on ne garde que le woff2 (suffisant pour tout navigateur moderne)
            txt = re.sub(r",\s*url\(\./files/[^)]+\.woff\)\s*format\(['\"]woff['\"]\)", "", txt)
            # on ne garde que les subsets latin / latin-ext (LP françaises)
            def _keep(m):
                block = m.group(0)
                u = re.search(r"url\(\./files/([^)]+)\)", block)
                if u and re.search(r"-(latin|latin-ext)-", u.group(1)):
                    return block
                return ""
            txt = re.sub(r"(?:/\*[^*]*\*/\s*)?@font-face\s*\{[^}]*\}", _keep, txt)
            for m in re.finditer(r"url\(\./files/([^)]+)\)", txt):
                name = m.group(1)
                if name in copied:
                    continue
                sf = FONTSRC / pkg / "files" / name
                if sf.is_file():
                    shutil.copy(sf, d / "fonts" / name)
                    copied.add(name)
            txt = txt.replace("url(./files/", "url(fonts/")
            parts.append(f"/* {pkg} {weight} {style} */\n{txt}\n")
        if not copied:
            continue
        (d / "fonts-global.css").write_text("\n".join(parts), encoding="utf-8")
        n_css += 1
        total_files += len(copied)
        html_f = d / "index.html"
        h = html_f.read_text(encoding="utf-8", errors="replace")
        if MARKER_FONTS_LINK not in h:
            h2, k = re.subn(
                r'(<link rel="stylesheet" href="style\.css">)',
                r'\1\n  <link rel="stylesheet" href="fonts-global.css">',
                h, count=1,
            )
            if k:
                html_f.write_text(h2, encoding="utf-8")
                n_link += 1
    if verbose:
        print(f"[fonts] fonts-global.css générés : {n_css} | <link> ajoutés : {n_link} "
              f"| fichiers woff2 copiés : {total_files}")
    return n_css, n_link


# ---------------------------------------------------------------------------
# Phase nofail : effacer les blocs d'erreur de formulaire (.w-form-fail)
# ---------------------------------------------------------------------------
# « Oops! Something went wrong while submitting the form. » : message d'échec
# par défaut de Webflow, affiché par le handler native jamais branché sur cet
# export (shim v2 simule déjà la réussite). On supprime les blocs du HTML pour
# que l'erreur soit impossible à afficher même par un chemin inattendu.
# Le bloc .w-form-done (succès) est conservé.

RE_FAIL_OPEN = re.compile(r'<div class="[^"]*\bw-form-fail\b[^"]*"[^>]*>')


def _strip_fail_blocks(s):
    """Retire les <div class="w-form-fail">…</div> (imbrication équilibrée)."""
    out, pos, n = [], 0, 0
    while True:
        m = RE_FAIL_OPEN.search(s, pos)
        if not m:
            out.append(s[pos:])
            break
        # aller au dernier '</div>' équilibré depuis l'ouverture
        i, depth, j = m.start(), 0, m.start()
        end = None
        while j < len(s):
            o = s.find("<div", j)
            c = s.find("</div>", j)
            if c == -1:
                break
            if o != -1 and o < c:
                depth += 1
                j = o + 4
            else:
                depth -= 1
                j = c + 6
                if depth == 0:
                    end = j
                    break
        if end is None:  # malformé : on ne touche pas
            out.append(s[pos:m.end()])
            pos = m.end()
            continue
        # absorber l'indentation précédente + retour à la ligne suivant
        k = i
        while k > pos and s[k - 1] in " \t":
            k -= 1
        if k > pos and s[k - 1] == "\n":
            k -= 1
            while k > pos and s[k - 1] in " \t":
                k -= 1
        e = end
        while e < len(s) and s[e] in " \t":
            e += 1
        if e < len(s) and s[e] == "\n":
            e += 1
        out.append(s[pos:k])
        pos = e
        n += 1
    return "".join(out), n


def phase_nofail(verbose=True):
    n_page = n_blk = 0
    for d in sites():
        f = d / "index.html"
        s = f.read_text(encoding="utf-8", errors="replace")
        if "w-form-fail" not in s:
            continue
        s2, c = _strip_fail_blocks(s)
        if c:
            s2 = re.sub(r"\n{3,}", "\n\n", s2)
            f.write_text(s2, encoding="utf-8")
            n_page += 1
            n_blk += c
    if verbose:
        print(f"[nofail] blocs .w-form-fail effacés : {n_blk} sur {n_page} pages")
    return n_page, n_blk


# ---------------------------------------------------------------------------
# Phase otpfix : contournement local du gate OTP SMS (5 pages assurance)
# ---------------------------------------------------------------------------
# Ces pages ajoutent un bloc de vérification SMS (mc.hellolead.pro) qui ne
# rend le bouton « Valider » actif qu'après vérification d'un code à 6
# chiffres — impossible hors ligne (le SMS n'arrive jamais ; en jsdom, le
# fetch manquant plantait avec « fetch is not defined »). En local, le shim
# simule déjà les réponses de l'API : on initialise `verified` à l'état du
# shim et on neutralise la remise à zéro après saisie du numéro. Hors local
# (shim inactif) : verified=false → gate OTP réel actif à l'import serveur,
# aucune restauration manuelle nécessaire. Le consentement (radio visible)
# reste exigé.

OTP_GATE_INIT = "var verified = false, verifiedPhone = '', timer = null;"
OTP_GATE_INIT_LOCAL = ("var verified = !!window.__LOCAL_SHIM__, "
                       "verifiedPhone = '', timer = null;")
OTP_GATE_RESET = "if (verified && tel() !== verifiedPhone) {"
OTP_GATE_RESET_LOCAL = ("if (!window.__LOCAL_SHIM__ && verified && "
                        "tel() !== verifiedPhone) {")


def phase_otpfix(verbose=True):
    n = 0
    for d in sites():
        f = d / "script.js"
        s = f.read_text(encoding="utf-8", errors="replace")
        if OTP_GATE_INIT not in s:
            continue
        s = s.replace(OTP_GATE_INIT, OTP_GATE_INIT_LOCAL, 1)
        if OTP_GATE_RESET in s:
            s = s.replace(OTP_GATE_RESET, OTP_GATE_RESET_LOCAL, 1)
        f.write_text(s, encoding="utf-8")
        n += 1
    if verbose:
        print(f"[otpfix] gate OTP contourné en local : {n} script.js "
              f"(verified via shim, reset neutralisé ; consentement toujours exigé)")
    return n


# ---------------------------------------------------------------------------
# Phase cachebust : versionner script.js (?v=N) pour invalidation navigateur
# ---------------------------------------------------------------------------
# Un fix JS reste invisible si le navigateur sert un script.js en cache
# (même URL localhost, fraîcheur heuristique). On incrémente SCRIPT_VERSION
# à chaque changement de comportement de script.js (shim, formulaires…).

SCRIPT_VERSION = "2"

RE_SCRIPT_TAG = re.compile(r'(<script\b[^>]*\bsrc="script\.js)(\?[^"]*)?(")')


def phase_cachebust(verbose=True):
    n = 0
    for d in sites():
        f = d / "index.html"
        s = f.read_text(encoding="utf-8", errors="replace")
        s2, c = RE_SCRIPT_TAG.subn(
            lambda m: f'{m.group(1)}?v={SCRIPT_VERSION}{m.group(3)}', s)
        if s2 != s:
            f.write_text(s2, encoding="utf-8")
            n += 1
    if verbose:
        print(f"[cachebust] <script src=\"script.js?v={SCRIPT_VERSION}\"> sur {n} pages")
    return n


# ---------------------------------------------------------------------------
# Phase rapport
# ---------------------------------------------------------------------------

RE_LEFT_HOSTS = re.compile(r"https?://([a-zA-Z0-9.-]+\.[a-z]{2,})")


def phase_report(verbose=True):
    hosts = {}
    canon = 0
    for d in sites():
        h = (d / "index.html").read_text(encoding="utf-8", errors="replace")
        for m in RE_LEFT_HOSTS.finditer(h):
            host = m.group(1)
            if host.endswith(".lp.comparateurpro.fr"):
                canon += 1
                continue
            hosts[host] = hosts.get(host, 0) + 1
    top = sorted(hosts.items(), key=lambda kv: -kv[1])[:30]
    rows = "\n".join(f"| `{h}` | {c} |" for h, c in top)
    if len(hosts) > 30:
        rows += f"\n| … et {len(hosts) - 30} autres hôtes (liens `<a>` légal/contact) | — |"
    rows += f"\n| `*.lp.comparateurpro.fr` | {canon} | canonical/robots/sitemap (SEO, non appelés par le navigateur) |"
    n_shim = sum(1 for d in sites() if MARKER_SHIM in (d / "script.js").read_text(
        encoding="utf-8", errors="replace"))
    n_fonts = sum(1 for d in sites() if (d / "fonts-global.css").is_file())
    doc = f"""# 🔧 Fonctionnement local — neutralisation des dépendances externes

> Généré par `localize.py` le 2026-10-23 (branche `arena/95a74ebe-comp`).

## Objectif

Faire tourner les {len(sites())} LP **100 % en local** (formulaires, OTP SMS, CRM,
redirections, polices, iframes de contenu, vidéos, liens, `url()` CSS), **hors
ligne**, **responsive mobile/tablette/PC**, avec un design visuel inchangé,
avant import sur le serveur.

## Ce qui a été fait

| Phase | Action | Portée |
|---|---|---|
| **réparation** | `paritel-typ` et `securite-professionnels` : leur `script.js` d'export contenait **tout le bloc de scripts dupliqué** (~3400 lignes) → `SyntaxError` et JS entièrement mort ; reconstruits sur le modèle des sites frères sains (4288 lignes + shim) | 2 sites |
| `html` | Suppression des loaders **GTM/gtag**, iframes `<noscript>` GTM et `<link rel="prefetch">` externes | tous les `index.html` |
| `js` | Injection du **local-shim v2** en tête de `script.js` : interception `XMLHttpRequest`, `fetch`, `sendBeacon`, `Image`, injection dynamique `<script>`/`<link>` externes + stub **Turnstile** ; conservation de `dataLayer`/`gtag` en local ; redirection distante de `site/` neutralisée ; **formulaires** : l'export Webflow n'embarque pas le client de soumission → le handler d'échec (« Oops! Something went wrong… ») est remplacé par une **réussite simulée** (`.w-form-done`), `data-redirect` mappé vers les dossiers locaux (table `FORM_REDIRECTS`) | tous les `script.js` |
| `fonts` | Génération de `fonts-global.css` + copie des `.woff2` (**@fontsource**) : Poppins, Oswald, PT Serif… ne dépendent plus de `fonts.googleapis.com` | {n_fonts} sites |
| `embeds` | `<iframe>` de contenu → dossiers locaux ; 1 embed YouTube (`primagaz`) → placeholder SVG local ; `data-video-urls` (Webflow) → fichiers `videos/*.mp4` locaux | 13 sites |
| `links` | `<a href>` externes mappés vers les dossiers locaux correspondants ; coquilles `htpps://` corrigées ; **199 liens `<a>`** pointent vers des dossiers locaux, ancrages/queries conservés | tous les `index.html` |
| `cssfix` | `url("https://cdn.prod.website-files.com/…")` dans 2 `style.css` → fichier local `img/employe.png` (visuel identique) | 2 fichiers |
| `fixrefs` | Réparation des références cassées : 2 assets d'export manquants (picto + icône conso → placeholder SVG `lexus-lbx-2/img/conso-placeholder-local.svg`), vidéos `lbx~3` → `lbx-3` | 4 refs |
| `nofail` | Effacement des **123 blocs `.w-form-fail`** (message d'échec « Oops! … » de Webflow) : l'erreur ne peut plus s'afficher même par un chemin inattendu ; le bloc succès `.w-form-done` est conservé | 108 `index.html` |
| `otpfix` | **Bouton « Valider » débloqué** sur les 5 pages assurance à gate SMS OTP (hellolead) : `verified` initialisé via le shim local (le vrai SMS n'arrive jamais hors ligne) + remise à zéro après saisie neutralisée ; le **consentement reste exigé** (radio visible) ; **hors local, le gate OTP réel repart automatiquement** (le shim est inactif → `verified=false`). Shim : polyfills minimaux `fetch`/`Response` pour les environnements sans fetch (jsdom) — navigateur natif inchangé | 5 `script.js` |
| `cachebust` | `<script src="script.js?v=2">` : versionnage pour invalidation du cache navigateur (sinon un fix JS reste invisible si le navigateur resert l'ancien script) | 131 `index.html` |
| — | Le shim est **actif uniquement en local** (`localhost`, `127.0.0.1`, `*.e2b.app`, `*.local`, `file://`, ou forçage `localStorage.localShim='1'`) : **le déploiement serveur n'est pas impacté**. | — |

**Inchangé** : design et mise en page (seules 2 `url()` CSS de fond ont été
localisées, visuel identique), images existantes, canonical/robots/sitemap
(`*.lp.comparateurpro.fr`), `<a href>` externes **informatifs sans dossier
local** (rgpd/edenred, bloctel, orias, cnil, comparateurpro.fr…), scripts
données (`data-*` stockant des URL métier non appelées).

## Résidus externes restants (visibles dans le HTML, sans blocage local)

| Hôte | Occurrences | Nature |
|---|---|---|
{rows}

Tous **appartiennent à des liens hypertexte informatifs** (aucun appel réseau
par le navigateur hors clic) — les dépendances d'exécution (iframe, vidéo,
police, `url()`, requêtes XHR/fetch) sont **toutes locales**.

## Vérification (6 contrôles)

```bash
python3 localize.py report          # régénère ce fichier
npm install --prefix .verify jsdom  # 1× (moteur de vérification runtime)
python3 verify-local.py             # refs | external | js-syntax | responsive | runtime | http
```

Dernier passage (2026-10-23) : **6/6 OK** — 0 référence cassée, 0 dépendance
externe, 131/131 JS valides, 131/131 responsive, 131/131 pages sans erreur
runtime (jsdom), 0 erreur HTTP. Exiger `EXIT=0` avant import.

## Restaurer AVANT l'import serveur

1. **GTM** : réintégrer les loaders supprimés (34 pages concernées) :
   - `GTM-WMVZJKS` (33 pages) et `GTM-53SH7D7F` (27 pages), plus les
     `<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=…">`.
   - Les blocs *Consent Mode* (déjà présents dans le HTML) sont conservés.
2. **Shim** : rien à faire — inactif hors local (vérifier le hostname cible ;
   pour le forcer en local : `localStorage.setItem('localShim','1')`).
   `otpfix` s'auto-restaure aussi hors local : `verified = !!__LOCAL_SHIM__`
   vaut `false` sur le serveur → vérification SMS OTP réelle réactivée.
3. **Redirection `site/`** : pointe maintenant vers `../mentions-legales/`
   (relatif, cible locale) — repasser l'URL absolue prod
   (`https://www.comparateurpro.fr/mentions-legales`) si nécessaire.

## Test local

```bash
./tester-local.sh        # ou tester-local.bat sous Windows
# puis ouvrir http://localhost:8080/<nom-du-site>/
```

Console navigateur : les appels neutralisés sont loggués `[local-shim] …`.
"""
    (ROOT / "LOCAL.md").write_text(doc, encoding="utf-8")
    if verbose:
        print(f"[report] LOCAL.md écrit ({n_shim} shims, {n_fonts} fonts-global.css)")


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Phase embeds : iframes / vidéos / placeholders -> 100% local
# ---------------------------------------------------------------------------

# alias chemin-dossier -> dossier-réel (quand le chemin ne correspond pas
# exactement au nom du dossier du dépôt, ou évite l'auto-emboîtement)
PATH_ALIASES = {
    "assurance-consultant-conseil-v2": "assurance-consultants-societe-conseil",
}

RE_IFRAME_EXT = re.compile(r'<iframe\b[^>]*\bsrc="(https?://[^"]+)"[^>]*>', re.I)
RE_VIDEO_URLS = re.compile(r'data-video-urls="(https?://[^"]+)"')
RE_YT_BLOCK = re.compile(
    r'<iframe\b[^>]*\bsrc="https?://www\.youtube\.com/embed/[^"]+"[^>]*>\s*</iframe>',
    re.I,
)


def folder_for_url(url, current_site=None):
    """Chemin d'URL -> nom de dossier existant du dépôt (sinon None)."""
    m = re.match(r"https?://[^/]+(/[^?#]*)?", url)
    if not m or not m.group(1):
        return None
    path = m.group(1).rstrip("/")
    if path.endswith(".html"):
        path = path[:-5]
    cand = path.lstrip("/").replace("/", "-")
    if not cand or len(cand) > 120:
        return None
    cand = PATH_ALIASES.get(cand, cand)
    if cand == current_site:
        return None  # ne jamais s'emboîter soi-même
    try:
        if (ROOT / cand).is_dir() and (ROOT / cand / "index.html").is_file():
            return cand
    except OSError:
        return None
    return None


def rewrite_video_urls(s):
    """uploads-ssl.webflow.com -> videos/<fichier> (les fichiers sont locaux)."""
    def repl(m):
        urls = m.group(1)
        if "uploads-ssl.webflow.com" not in urls:
            return m.group(0)
        out = []
        for u in urls.split(","):
            u = u.strip()
            if "uploads-ssl.webflow.com" in u:
                tail = u.split("/")[-1]          # après dernier '/'
                tail = tail.split("%2F")[-1]     # variantes %-encodées
                out.append("videos/" + tail)
            else:
                out.append(u)
        return 'data-video-urls="' + ",".join(out) + '"'
    return RE_VIDEO_URLS.sub(repl, s)


def youtube_placeholder(site):
    p = ROOT / site / "img" / "youtube-placeholder.2b05e7d68d.svg"
    if p.is_file():
        return ('<img src="img/youtube-placeholder.2b05e7d68d.svg" '
                'style="position:absolute;left:0;top:0;width:100%;height:100%;'
                'object-fit:contain;background:#000" '
                'alt="Video (indisponible hors ligne)">')
    return ('<div style="position:absolute;left:0;top:0;width:100%;height:100%;'
            'display:flex;align-items:center;justify-content:center;'
            'background:#000;color:#fff">Video indisponible hors ligne</div>')


def phase_embeds(verbose=True):
    n_ifr = n_vid = n_yt = 0
    for d in sites():
        site = d.name
        f = d / "index.html"
        s = f.read_text(encoding="utf-8", errors="replace")
        orig = s

        def ifr_repl(m):
            nonlocal n_ifr
            tag = m.group(0)
            url = m.group(1)
            if "youtube.com/embed" in url:
                return tag
            target = folder_for_url(url, current_site=site)
            if not target:
                return tag
            n_ifr += 1
            return tag.replace(f'src="{url}"', f'src="../{target}/"')

        s = RE_IFRAME_EXT.sub(ifr_repl, s)

        # YouTube -> placeholder local (même cadre responsive)
        def yt_repl(m):
            nonlocal n_yt
            n_yt += 1
            return youtube_placeholder(site)
        s = RE_YT_BLOCK.sub(yt_repl, s)

        # vidéos d'arrière-plan -> chemins locaux videos/
        before = s
        s = rewrite_video_urls(s)
        if s != before:
            n_vid += 1

        if s != orig:
            f.write_text(s, encoding="utf-8")
    if verbose:
        print(f"[embeds] iframes pointées en local : {n_ifr} | YouTube->placeholder : {n_yt} "
              f"| data-video-urls localisées : {n_vid}")
    return n_ifr, n_yt, n_vid


# ---------------------------------------------------------------------------
# Phase links : <a href> externes dont le dossier existe -> local + coquilles
# ---------------------------------------------------------------------------

RE_A_HREF = re.compile(r'(<a\b[^>]*\bhref=")(https?://[^"]+)(")', re.I)


def phase_links(verbose=True):
    n = n_typo = 0
    for d in sites():
        site = d.name
        f = d / "index.html"
        s = f.read_text(encoding="utf-8", errors="replace")
        orig = s

        def a_repl(m):
            nonlocal n
            url = m.group(2)
            target = folder_for_url(url, current_site=site)
            if not target:
                return m.group(0)
            n += 1
            q = ""
            mq = re.search(r"([?#].*)$", url)
            if mq:
                q = mq.group(1)
            return m.group(1) + f"../{target}/{q}" + m.group(3)

        s = RE_A_HREF.sub(a_repl, s)

        # coquilles / schémas cassés (ordre important)
        for bad, good in (("https://htpps://", "https://"),
                          ("htpps://", "https://"),
                          ("http://tools.google.com", "https://tools.google.com")):
            if bad in s:
                c = s.count(bad)
                s = s.replace(bad, good)
                n_typo += c

        if s != orig:
            f.write_text(s, encoding="utf-8")
    if verbose:
        print(f"[links] <a> externes repliés en local : {n} | coquilles corrigées : {n_typo}")
    return n, n_typo


# ---------------------------------------------------------------------------
# Phase cssfix : url(https://cdn.prod…) dans style.css -> asset local
# ---------------------------------------------------------------------------

RE_CSS_EXT = re.compile(r'url\("(https://cdn\.prod\.website-files\.com/[^"]+)"\)')


def phase_cssfix(verbose=True):
    n = 0
    for d in sites():
        if not (d / "img" / "employe.png").is_file():
            continue
        f = d / "style.css"
        s = f.read_text(encoding="utf-8", errors="replace")
        s2, k = RE_CSS_EXT.subn('url("img/employe.png")', s)
        if k:
            f.write_text(s2, encoding="utf-8")
            n += k
    if verbose:
        print(f"[cssfix] url() externes dans style.css remplacés par img/employe.png : {n}")
    return n


# ---------------------------------------------------------------------------
# Phase fixrefs : réparation des assets cassés pré-existants (rapport lp2site)
#   - typ-categ : img "images/2-1_12-1.png" jamais exporté -> illustration
#     d'étape 1 de la même série (mème style de picto)
#   - lexus-lbx-2 : img "../images/conso-1_1conso-1.png" jamais exportée
#     -> placeholder local (à ré-exporter depuis Webflow côté prod)
#   - data-video-urls déjà réécrites avec "lbx~3" -> fichier réel "lbx-3"
# ---------------------------------------------------------------------------

REF_REPAIRS = {
    'src="images/2-1_12-1.png"': 'src="img/1_91.png"',
    'src="../images/conso-1_1conso-1.png"': 'src="img/conso-placeholder-local.svg"',
}

LEXUS_PLACEHOLDER_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 112 112" width="112" height="112">\n'
    '  <circle cx="56" cy="56" r="52" fill="#f4f5f7" stroke="#dfe2e6" stroke-width="2"/>\n'
    '  <path d="M28 72a30 30 0 1 1 56 0" fill="none" stroke="#9aa3ad" stroke-width="6" stroke-linecap="round"/>\n'
    '  <line x1="56" y1="60" x2="74" y2="42" stroke="#5b6470" stroke-width="5" stroke-linecap="round"/>\n'
    '  <circle cx="56" cy="62" r="6" fill="#5b6470"/>\n'
    '</svg>\n'
)


def _fix_video_names(s, site_dir):
    """Corrige les data-video-urls dont le fichier n'existe pas (ex. ~ vs -)."""
    def repl(m):
        val = m.group(1)
        if not val.startswith("videos/"):
            return m.group(0)
        out = []
        for name in val.split(","):
            name = name.strip()
            fname = name.split("/", 1)[1] if "/" in name else name
            if not (site_dir / "videos" / fname).is_file():
                alt = fname.replace("~", "-")
                if (site_dir / "videos" / alt).is_file():
                    name = "videos/" + alt
            out.append(name)
        return 'data-video-urls="' + ",".join(out) + '"'
    return re.sub(r'data-video-urls="([^"]+)"', repl, s)


def phase_fixrefs(verbose=True):
    n = 0
    # placeholder Lexus (une seule fois)
    lex = ROOT / "lexus-lbx-2" / "img" / "conso-placeholder-local.svg"
    if not lex.is_file():
        lex.write_text(LEXUS_PLACEHOLDER_SVG, encoding="utf-8")
    for d in sites():
        f = d / "index.html"
        s = f.read_text(encoding="utf-8", errors="replace")
        orig = s
        for bad, good in REF_REPAIRS.items():
            if bad in s:
                s = s.replace(bad, good)
                n += 1
        s = _fix_video_names(s, d)
        if s != orig:
            f.write_text(s, encoding="utf-8")
    if verbose:
        print(f"[fixrefs] assets cassés réparés : {n} (+ placeholder Lexus, vidéos ~/-)")
    return n


# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:] or ["all"]
    cmd = args[0]
    if cmd in ("fetch-fonts", "all", "html", "js", "fonts", "report",
               "embeds", "links", "cssfix", "fixrefs", "cachebust", "nofail",
               "otpfix"):
        if cmd in ("fetch-fonts", "all"):
            phase_fetch_fonts()
        if cmd in ("html", "all"):
            phase_html()
        if cmd in ("js", "all"):
            phase_js()
        if cmd in ("fonts", "all"):
            phase_fonts()
        if cmd in ("cachebust", "all"):
            phase_cachebust()
        if cmd in ("nofail", "all"):
            phase_nofail()
        if cmd in ("otpfix", "all"):
            phase_otpfix()
        if cmd in ("embeds", "all"):
            phase_embeds()
        if cmd in ("links", "all"):
            phase_links()
        if cmd in ("cssfix", "all"):
            phase_cssfix()
        if cmd in ("fixrefs", "all"):
            phase_fixrefs()
        if cmd in ("report", "all"):
            phase_report()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
