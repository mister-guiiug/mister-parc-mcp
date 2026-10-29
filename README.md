# mister-parc-mcp

Serveur [MCP](https://modelcontextprotocol.io) en **lecture seule** sur l'état du parc
`mister-guiiug` : le [tableau de bord](https://mister-guiiug.github.io/parc-dashboard/) et
le socle [`dev-pwa-config`](https://github.com/mister-guiiug/dev-pwa-config). Écrit avec
[FastMCP](https://gofastmcp.com) 4, hébergé sur [Prefect Horizon](https://horizon.prefect.io).

Il répond, depuis n'importe quel client MCP, à « qu'est-ce qui est à faire sur le parc ? »
sans qu'on recopie le tableau de bord, et à « le socle a-t-il déjà ceci ? » avant qu'un
agent ne le réécrive dans une application.

## Les outils

| Outil | Ce qu'il rend |
|---|---|
| `parc_etat` | chiffres clés du dernier relevé, version du socle, rubriques « À faire », ce qui a bougé |
| `parc_a_faire` | la liste « À faire » avec son détail, filtrable par niveau ou par rubrique |
| `parc_depots` | une ligne par dépôt : CI, alertes, CodeQL, PR, site, version du socle |
| `parc_depot` | tout ce que le relevé sait d'un dépôt |
| `parc_echecs` | les workflows rouges sur la branche par défaut, avec job et étape |
| `parc_librairie` | une librairie : ses versions, et quel dépôt est sur laquelle |
| `parc_librairies_en_retard` | les librairies en retard sur l'amont, les plus en retard d'abord |
| `parc_tendances` | l'historique quotidien : taux de vert, rouges, alertes |
| `parc_journal` | les dernières transitions vues par le relevé |
| `socle_offre` | modules par catégorie, outils et workflows réutilisables du socle |
| `socle_module` | un module : ce qu'il emporte, ce qui l'emporte, qui l'importe |
| `socle_workflow` | un workflow réutilisable : la ligne `uses:`, ses défauts, qui l'appelle et avec quoi |
| `socle_doc` | README, CONFIG, CONTRIBUTING ou STRATEGIE du socle, à la version publiée |
| `socle_chercher` | un terme dans les noms du socle et les sections de sa documentation |

Chaque outil se déclare en lecture seule (`readOnlyHint`), et un test l'exige.

## D'où viennent les réponses

Le serveur **lit ce que le parc publie déjà, et ne recalcule rien** :

- `donnees.json` et `a-faire.json`, que le tableau de bord publie à chaque relevé, au mieux
  toutes les heures ([parc-dashboard#57](https://github.com/mister-guiiug/parc-dashboard/pull/57)).
  La liste « À faire » sort de la fonction même de la page (`aFairePublie`) : la règle
  n'existe qu'en un endroit. Chaque réponse porte `genere`, la date du relevé.
- la documentation du socle sous l'étiquette de sa version publiée (`v6.28.1`…), lue sur
  `raw.githubusercontent.com`.

Tout est public : le serveur n'a **aucun jeton** et aucune variable d'environnement.

## Se connecter

Le serveur déployé est derrière l'authentification de Horizon : seuls les membres de
l'organisation Horizon s'y connectent, par une connexion OAuth que le client ouvre lui-même.

```bash
claude mcp add --transport http mister-parc https://<nom-du-serveur>.fastmcp.app/mcp
```

En local, sans Horizon, sur stdio :

```bash
claude mcp add mister-parc-local -- uv run --directory <chemin du dépôt> fastmcp run serveur.py:mcp
```

## Déployer sur Horizon

Dans [horizon.prefect.io](https://horizon.prefect.io), créer un serveur depuis ce dépôt :

| Réglage | Valeur |
|---|---|
| Point d'entrée | `serveur.py:mcp` |
| Dépendances | `pyproject.toml` |
| Python | 3.12, le défaut de Horizon (`.python-version`) |
| Authentification | activée (le défaut) |
| Variables | aucune |

Chaque push sur `main` redéploie ; chaque PR a son déploiement d'aperçu.

**Les limites de Horizon qui comptent ici** : 170 secondes par requête, 6 Mo par réponse,
1 Go de mémoire, disque effacé entre deux requêtes, pas de tâche de fond. `donnees.json`
pèse environ 470 Ko ; chaque instance le garde cinq minutes en mémoire. Rendre le serveur
public (sans authentification) demande le plan Developer de Horizon.

## Développer

```bash
uv sync
uv run pytest
uv run ruff check
uv run ruff format --check
uv run fastmcp inspect serveur.py:mcp
```

Les tests ne touchent pas le réseau : `tests/conftest.py` sert un relevé réel réduit à
quatre dépôts. `tests/engendrer-donnees.mjs` le régénère, avec le code du tableau de bord.

## Ce qu'il ne fait pas, exprès

- **Écrire.** Ni fusion, ni campagne, ni commentaire : dans ce parc, une fusion attend la
  décision du propriétaire.
- **Recalculer.** Un chiffre qui manque s'ajoute à la publication du tableau de bord, pas ici.
- **Les dépôts privés.** Le relevé publié ne les contient pas.

## Licence

[MIT](LICENSE)
