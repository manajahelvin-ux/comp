# Diagnostic des sites — 2026-10-22

Dossier : `sites` — 12 sites — 11 réparation(s) appliquée(s)

| Site | Réparations appliquées | Alertes restantes | État |
|---|---|---|---|
| `acces-internet-et-telephonie-pro` | patch Formly null applique [FORMLY] | — | ✔ |
| `accueil` | patch Formly null applique [FORMLY] | — | ✔ |
| `assurance-agriculteur` | patch Formly null applique [FORMLY] | — | ✔ |
| `assurance-assurance-professionnelle-iard-cookie` | patch Formly null applique [FORMLY] | — | ✔ |
| `assurance-commerce` | patch Formly null applique [FORMLY] | — | ✔ |
| `assurance-consultants-societe-conseil` | patch Formly null applique [FORMLY] | — | ✔ |
| `assurance-estheticienne-institut-beaute` | patch Formly null applique [FORMLY] | — | ✔ |
| `assurance-estheticiennes-institut-beaute` | — | — | ✔ |
| `assurance-estheticiennes-instituts-beaute` | patch Formly null applique [FORMLY] | — | ✔ |
| `assurance-marchandise` | patch Formly null applique [FORMLY] | — | ✔ |
| `assurance-multirisques` | patch Formly null applique [FORMLY] | — | ✔ |
| `assurance-tns` | patch Formly null applique [FORMLY] | — | ✔ |

## Détails par site

### `acces-internet-et-telephonie-pro`
- banniere cookies: non; GTM: absent; description: oui; H1: 1
- Réparations : patch Formly null applique [FORMLY]
- Alertes : aucune

### `accueil`
- banniere cookies: non; GTM: absent; description: oui; H1: 0
- Réparations : patch Formly null applique [FORMLY]
- Alertes : aucune

### `assurance-agriculteur`
- banniere cookies: oui; GTM: GTM-53SH7D7F; description: oui; H1: 1
- Réparations : patch Formly null applique [FORMLY]
- Alertes : aucune

### `assurance-assurance-professionnelle-iard-cookie`
- banniere cookies: oui; GTM: GTM-53SH7D7F; description: oui; H1: 0
- Réparations : patch Formly null applique [FORMLY]
- Alertes : aucune

### `assurance-commerce`
- banniere cookies: non; GTM: GTM-WMVZJKS; description: oui; H1: 0
- Réparations : patch Formly null applique [FORMLY]
- Alertes : aucune

### `assurance-consultants-societe-conseil`
- banniere cookies: oui; GTM: GTM-53SH7D7F; description: oui; H1: 0
- Réparations : patch Formly null applique [FORMLY]
- Alertes : aucune

### `assurance-estheticienne-institut-beaute`
- banniere cookies: oui; GTM: GTM-53SH7D7F; description: oui; H1: 0
- Réparations : patch Formly null applique [FORMLY]
- Alertes : aucune

### `assurance-estheticiennes-institut-beaute`
- banniere cookies: non; GTM: GTM-53SH7D7F; description: oui; H1: 1
- Réparations : aucune
- Alertes : aucune

### `assurance-estheticiennes-instituts-beaute`
- banniere cookies: non; GTM: absent; description: oui; H1: 0
- Réparations : patch Formly null applique [FORMLY]
- Alertes : aucune

### `assurance-marchandise`
- banniere cookies: non; GTM: GTM-WMVZJKS; description: oui; H1: 0
- Réparations : patch Formly null applique [FORMLY]
- Alertes : aucune

### `assurance-multirisques`
- banniere cookies: non; GTM: GTM-53SH7D7F; description: oui; H1: 0
- Réparations : patch Formly null applique [FORMLY]
- Alertes : aucune

### `assurance-tns`
- banniere cookies: oui; GTM: GTM-53SH7D7F; description: oui; H1: 1
- Réparations : patch Formly null applique [FORMLY]
- Alertes : aucune

## Comment tester correctement

Les formulaires et la bannière nécessitent un serveur HTTP local
(pas d'ouverture en double-clic file://) :

```bash
cd sites
python -m http.server 8080
```

Puis ouvrir http://localhost:8080/nom-du-site/ dans le navigateur.
