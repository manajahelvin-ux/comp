# 🔧 Fonctionnement local — neutralisation des dépendances externes

> Généré par `localize.py` le 2026-10-23 (branche `arena/95a74ebe-comp`).

## Objectif

Faire tourner les 131 LP **100 % en local** (formulaires, OTP SMS, CRM,
redirections, polices, iframes de contenu, vidéos, liens, `url()` CSS), **hors
ligne**, **responsive mobile/tablette/PC**, avec un design visuel inchangé,
avant import sur le serveur.

## Ce qui a été fait

| Phase | Action | Portée |
|---|---|---|
| **réparation** | `paritel-typ` et `securite-professionnels` : leur `script.js` d'export contenait **tout le bloc de scripts dupliqué** (~3400 lignes) → `SyntaxError` et JS entièrement mort ; reconstruits sur le modèle des sites frères sains (4288 lignes + shim) | 2 sites |
| `html` | Suppression des loaders **GTM/gtag**, iframes `<noscript>` GTM et `<link rel="prefetch">` externes | tous les `index.html` |
| `js` | Injection du **local-shim v2** en tête de `script.js` : interception `XMLHttpRequest`, `fetch`, `sendBeacon`, `Image`, injection dynamique `<script>`/`<link>` externes + stub **Turnstile** ; conservation de `dataLayer`/`gtag` en local ; redirection distante de `site/` neutralisée ; **formulaires** : l'export Webflow n'embarque pas le client de soumission → le handler d'échec (« Oops! Something went wrong… ») est remplacé par une **réussite simulée** (`.w-form-done`), `data-redirect` mappé vers les dossiers locaux (table `FORM_REDIRECTS`) | tous les `script.js` |
| `fonts` | Génération de `fonts-global.css` + copie des `.woff2` (**@fontsource**) : Poppins, Oswald, PT Serif… ne dépendent plus de `fonts.googleapis.com` | 130 sites |
| `embeds` | `<iframe>` de contenu → dossiers locaux ; 1 embed YouTube (`primagaz`) → placeholder SVG local ; `data-video-urls` (Webflow) → fichiers `videos/*.mp4` locaux | 13 sites |
| `links` | `<a href>` externes mappés vers les dossiers locaux correspondants ; coquilles `htpps://` corrigées ; **199 liens `<a>`** pointent vers des dossiers locaux, ancrages/queries conservés | tous les `index.html` |
| `cssfix` | `url("https://cdn.prod.website-files.com/…")` dans 2 `style.css` → fichier local `img/employe.png` (visuel identique) | 2 fichiers |
| `fixrefs` | Réparation des références cassées : 2 assets d'export manquants (picto + icône conso → placeholder SVG `lexus-lbx-2/img/conso-placeholder-local.svg`), vidéos `lbx~3` → `lbx-3` | 4 refs |
| — | Le shim est **actif uniquement en local** (`localhost`, `127.0.0.1`, `*.e2b.app`, `*.local`, `file://`, ou forçage `localStorage.localShim='1'`) : **le déploiement serveur n'est pas impacté**. | — |

**Inchangé** : design et mise en page (seules 2 `url()` CSS de fond ont été
localisées, visuel identique), images existantes, canonical/robots/sitemap
(`*.lp.comparateurpro.fr`), `<a href>` externes **informatifs sans dossier
local** (rgpd/edenred, bloctel, orias, cnil, comparateurpro.fr…), scripts
données (`data-*` stockant des URL métier non appelées).

## Résidus externes restants (visibles dans le HTML, sans blocage local)

| Hôte | Occurrences | Nature |
|---|---|---|
| `www.comparateurpro.fr` | 33 |
| `rgpd.myedenred.fr` | 18 |
| `www.w3.org` | 15 |
| `www.hellolead.pro` | 10 |
| `cnil.fr` | 7 |
| `www.hyundai.com` | 6 |
| `www.edenred.fr` | 5 |
| `www.nissan.fr` | 5 |
| `www.bloctel.gouv.fr` | 5 |
| `www.ubepro.fr` | 4 |
| `www.orias.fr` | 3 |
| `www.toyota.fr` | 3 |
| `mc.hellolead.pro` | 2 |
| `www.dacia.fr` | 2 |
| `lexus.essaiauto.fr` | 2 |
| `avtm-l.fr` | 2 |
| `www.avent-media.fr` | 2 |
| `www.ovhcloud.com` | 2 |
| `www.plugandtel.com` | 2 |
| `tools.google.com` | 2 |
| `devis.comparateurpro.fr` | 2 |
| `fbdgiff.r.bh.d.sendibt3.com` | 2 |
| `www.volvocars.com` | 2 |
| `script.google.com` | 1 |
| `www.ayvens.com` | 1 |
| `www.renault.fr` | 1 |
| `service-public.fr` | 1 |
| `groupe.intuis.fr` | 1 |
| `www.lexus.fr` | 1 |
| `orias.fr` | 1 |
| … et 6 autres hôtes (liens `<a>` légal/contact) | — |
| `*.lp.comparateurpro.fr` | 134 | canonical/robots/sitemap (SEO, non appelés par le navigateur) |

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
3. **Redirection `site/`** : pointe maintenant vers `../mentions-legales/`
   (relatif, cible locale) — repasser l'URL absolue prod
   (`https://www.comparateurpro.fr/mentions-legales`) si nécessaire.

## Test local

```bash
./tester-local.sh        # ou tester-local.bat sous Windows
# puis ouvrir http://localhost:8080/<nom-du-site>/
```

Console navigateur : les appels neutralisés sont loggués `[local-shim] …`.
