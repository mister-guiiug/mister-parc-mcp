# AGENTS.md : mister-parc-mcp

Serveur MCP en Python (FastMCP 4, uv), hébergé sur Prefect Horizon. **Pas une PWA** : les
configs partagées du socle ne s'y appliquent pas. Les règles du compte, si : aucune
signature d'assistant (contrôlée ici par `.github/workflows/no-ai-attribution.yml`), une
branche et une PR pour tout changement, `main` protégé par le ruleset.

## Trois règles propres à ce dépôt

1. **Lire, ne pas recalculer.** Le serveur lit `donnees.json` et `a-faire.json` (publiés par
   parc-dashboard) et la documentation du socle. S'il faut un chiffre que ces fichiers n'ont
   pas, il s'ajoute à la publication de parc-dashboard, en JavaScript, à côté de la règle qui
   le calcule. Le refaire ici en Python mettrait la même règle à deux endroits.
2. **Lecture seule.** Aucun outil n'écrit, et `tests/test_serveur.py` exige `readOnlyHint`
   sur chacun. Un outil qui fusionnerait une PR contournerait la décision du propriétaire.
3. **Les noms des jobs sont des contextes exigés** : `Lint, tests et inspection` (ci.yml) et
   `Commits et fichiers sans signature d'assistant` (no-ai-attribution.yml). Les renommer
   gèle toutes les PR, tant que `CHECKS` de `scripts/apply-rulesets.mjs` (dans
   dev-pwa-config) n'est pas mis à jour.

## Vérifier avant une PR

```bash
uv run ruff check && uv run ruff format --check && uv run pytest && uv run fastmcp inspect serveur.py:mcp
```

Le point d'entrée `serveur.py` est à la racine, et le paquet `mister_parc/` à côté : Horizon
charge le fichier en ajoutant son dossier au chemin d'import, sans installer le projet.
