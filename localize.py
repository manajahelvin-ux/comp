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

SHIM = r"""/*__LOCAL_SHIM__ v1 — neutralise les appels réseau externes en environnement
   local (formulaires Webflow, OTP hellolead, Google Sheets/Apps Script, GTM,
   Google Fonts, Turnstile, pixels…). Inactif hors local : le déploiement
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

    /* 2) fetch — CRM UBEPRO, Google Sheets, endpoints divers. */
    if (typeof window.fetch === 'function') {
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

SITE_REDIRECTS = [
    ('window.location.href = "https://www.comparateurpro.fr/mentions-legales";',
     'window.location.href = "mentions-legales/";'),
    # depuis /site/, il faut remonter d'un cran pour atteindre /mentions-legales/
    ('window.location.href = "mentions-legales/";',
     'window.location.href = "../mentions-legales/";'),
]


def phase_js(verbose=True):
    n_shim = n_redir = 0
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
            s = SHIM + "\n" + s
            n_shim += 1
            changed = True
        if changed:
            f.write_text(s, encoding="utf-8")
    if verbose:
        print(f"[js] shim injecté : {n_shim} script.js | redirections neutralisées : {n_redir}")
    return n_shim, n_redir


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

Faire tourner les {len(sites())} LP **en local** (formulaires, OTP SMS, CRM,
redirections, polices…) **sans toucher au design ni à `style.css`**, avant
import sur le serveur.

## Ce qui a été fait

| Phase | Action | Portée |
|---|---|---|
| **réparation** | `paritel-typ` et `securite-professionnels` : leur `script.js` d'export contenait **tout le bloc de scripts dupliqué** (~3400 lignes) → `SyntaxError` et JS entièrement mort ; reconstruits sur le modèle des sites frères sains (4288 lignes + shim) | 2 sites |
| `html` | Suppression des loaders **GTM/gtag**, iframes `<noscript>` GTM et `<link rel="prefetch">` externes | tous les `index.html` |
| `js` | Injection du **local-shim** en tête de `script.js` : interception `XMLHttpRequest`, `fetch`, `sendBeacon`, `Image`, injection dynamique `<script>`/`<link>` externes + stub **Turnstile** ; conservation de `dataLayer`/`gtag` en local ; redirection distante de `site/` neutralisée | tous les `script.js` |
| `fonts` | Génération de `fonts-global.css` + copie des `.woff2` (**@fontsource**) : Poppins, Oswald, PT Serif… ne dépendent plus de `fonts.googleapis.com` | {n_fonts} sites |
| — | Le shim est **actif uniquement en local** (`localhost`, `127.0.0.1`, `*.e2b.app`, `*.local`, `file://`, ou forçage `localStorage.localShim='1'`) : **le déploiement serveur n'est pas impacté**. | — |

**Inchangé (design/CSS)** : `style.css` (0 modification), images, polices déjà
locales, `<a href>` externes (légal/contact), iframes de contenu (YouTube,
embeds ubepro/comparateurpro), vidéos hotlinkées, canonical/robots/sitemap.

## Résidus externes connus (visibles dans le HTML, sans blocage local)

| Hôte | Occurrences | Nature |
|---|---|---|
{rows}

- `uploads-ssl.webflow.com` (4 sites : canal, lexus-lbx-2, nissan-juke, volvo) :
  vidéos hotlinkées → **nécessitent internet** (à ré-exporter depuis Webflow).
- `url("https://cdn.prod.website-files.com/…")` dans `style.css` de
  `typ-formulaires-securite-thank-you-page` et `typ-formulaires-typ-secu-form`
  (image de fond, **CSS inchangé volontairement** → fond coloré à la place si
  hors ligne).

## Restaurer AVANT l'import serveur

1. **GTM** : réintégrer les loaders supprimés (34 pages concernées) :
   - `GTM-WMVZJKS` (33 pages) et `GTM-53SH7D7F` (27 pages), plus les
     `<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=…">`.
   - Les blocs *Consent Mode* (déjà présents dans le HTML) sont conservés.
2. **Shim** : rien à faire — inactif hors local (vérifier le hostname cible ;
   pour le forcer en local : `localStorage.setItem('localShim','1')`).
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

def main():
    args = sys.argv[1:] or ["all"]
    cmd = args[0]
    if cmd in ("fetch-fonts", "all", "html", "js", "fonts", "report"):
        if cmd in ("fetch-fonts", "all"):
            phase_fetch_fonts()
        if cmd in ("html", "all"):
            phase_html()
        if cmd in ("js", "all"):
            phase_js()
        if cmd in ("fonts", "all"):
            phase_fonts()
        if cmd in ("report", "all"):
            phase_report()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
