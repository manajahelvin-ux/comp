# 🔧 Fonctionnement local — neutralisation des dépendances externes

> Généré par `localize.py` le 2026-10-23 (branche `arena/95a74ebe-comp`).

## Objectif

Faire tourner les 131 LP **en local** (formulaires, OTP SMS, CRM,
redirections, polices…) **sans toucher au design ni à `style.css`**, avant
import sur le serveur.

## Ce qui a été fait

| Phase | Action | Portée |
|---|---|---|
| **réparation** | `paritel-typ` et `securite-professionnels` : leur `script.js` d'export contenait **tout le bloc de scripts dupliqué** (~3400 lignes) → `SyntaxError` et JS entièrement mort ; reconstruits sur le modèle des sites frères sains (4288 lignes + shim) | 2 sites |
| `html` | Suppression des loaders **GTM/gtag**, iframes `<noscript>` GTM et `<link rel="prefetch">` externes | tous les `index.html` |
| `js` | Injection du **local-shim** en tête de `script.js` : interception `XMLHttpRequest`, `fetch`, `sendBeacon`, `Image`, injection dynamique `<script>`/`<link>` externes + stub **Turnstile** ; conservation de `dataLayer`/`gtag` en local ; redirection distante de `site/` neutralisée | tous les `script.js` |
| `fonts` | Génération de `fonts-global.css` + copie des `.woff2` (**@fontsource**) : Poppins, Oswald, PT Serif… ne dépendent plus de `fonts.googleapis.com` | 130 sites |
| — | Le shim est **actif uniquement en local** (`localhost`, `127.0.0.1`, `*.e2b.app`, `*.local`, `file://`, ou forçage `localStorage.localShim='1'`) : **le déploiement serveur n'est pas impacté**. | — |

**Inchangé (design/CSS)** : `style.css` (0 modification), images, polices déjà
locales, `<a href>` externes (légal/contact), iframes de contenu (YouTube,
embeds ubepro/comparateurpro), vidéos hotlinkées, canonical/robots/sitemap.

## Résidus externes connus (visibles dans le HTML, sans blocage local)

| Hôte | Occurrences | Nature |
|---|---|---|
| `www.hellolead.pro` | 188 |
| `www.comparateurpro.fr` | 45 |
| `rgpd.myedenred.fr` | 18 |
| `www.w3.org` | 15 |
| `contact.edenred.fr` | 9 |
| `www.ubepro.fr` | 9 |
| `uploads-ssl.webflow.com` | 8 |
| `www.hyundai.com` | 6 |
| `www.edenred.fr` | 5 |
| `www.nissan.fr` | 5 |
| `cnil.fr` | 4 |
| `www.bloctel.gouv.fr` | 4 |
| `www.orias.fr` | 3 |
| `www.toyota.fr` | 3 |
| `www.ubepro.com` | 2 |
| `mc.hellolead.pro` | 2 |
| `www.dacia.fr` | 2 |
| `lexus.essaiauto.fr` | 2 |
| `avtm-l.fr` | 2 |
| `www.avent-media.fr` | 2 |
| `www.ovhcloud.com` | 2 |
| `www.plugandtel.com` | 2 |
| `tools.google.com` | 2 |
| `devis.comparateurpro.fr` | 2 |
| `hellodevis.fr` | 2 |
| `fbdgiff.r.bh.d.sendibt3.com` | 2 |
| `www.volvocars.com` | 2 |
| `script.google.com` | 1 |
| `www.ayvens.com` | 1 |
| `www.renault.fr` | 1 |
| … et 10 autres hôtes (liens `<a>` légal/contact) | — |
| `*.lp.comparateurpro.fr` | 134 | canonical/robots/sitemap (SEO, non appelés par le navigateur) |

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
