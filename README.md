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
| `parc_depots` | une ligne par dépôt : CI, alertes, CodeQL, PR, site, version du socle, ruleset |
| `parc_depot` | tout ce que le relevé sait d'un dépôt |
| `parc_echecs` | les workflows rouges sur la branche par défaut, avec job et étape |
| `parc_prs` | les PR ouvertes sur tout le compte, avec l'état de leur CI |
| `parc_alertes` | les alertes Dependabot (CVE, GHSA, part en production) et CodeQL (règles), par dépôt |
| `parc_sites` | les sites en ligne : code HTTP, temps de réponse, production face à `main`, URL mortes |
| `parc_renovate` | ce que Renovate attend dans chaque dépôt, et ce qu'il ne sait pas résoudre |
| `parc_librairie` | une librairie : ses versions, et quel dépôt est sur laquelle |
| `parc_librairies_en_retard` | les librairies en retard sur l'amont, les plus en retard d'abord |
| `parc_chercher` | un nom exact de dépôt ou de librairie, à partir d'un bout de nom ou de description |
| `parc_tendances` | l'historique quotidien : taux de vert, rouges, alertes |
| `parc_journal` | les dernières transitions vues par le relevé |
| `socle_offre` | modules par catégorie, outils, workflows réutilisables et dépendances pairs du socle |
| `socle_module` | un module : ce qu'il emporte, ce qui l'emporte, qui l'importe |
| `socle_workflow` | un workflow réutilisable : la ligne `uses:`, ses défauts, qui l'appelle et avec quoi |
| `socle_usage` | ce qu'un dépôt prend au socle : version, modules, outils, workflows et leurs entrées |
| `socle_doc` | README, CONFIG, CONTRIBUTING ou STRATEGIE du socle, à la version publiée |
| `socle_chercher` | un terme dans les noms du socle et les sections de sa documentation |

Chaque outil se déclare en lecture seule (`readOnlyHint`), porte un titre lisible et annonce
la forme de sa réponse (`outputSchema`, tiré de `mister_parc/sorties.py`). Les tests exigent
les trois, et valident chaque réponse réelle contre le schéma qu'elle annonce.

## Protocole

Le serveur parle MCP **2026-07-28**, par la bibliothèque `mcp` 2.3 et FastMCP 4 : sans état,
`server/discover`, `resultType` sur chaque résultat. Ce qui revient au serveur lui-même :

- son identité : `serverInfo` porte son nom et **sa** version, celle de `pyproject.toml` ;
- la fraîcheur de ses listes (SEP-2549) : `ttlMs` d'une heure et `cacheScope` `private`.
  Derrière Horizon, la liste arrive pourtant avec `ttlMs` 0 : c'est la passerelle qui la
  réécrit (constaté le 29/10 : 3 600 000 en HTTP local, 0 par `fastmcp.app`) ;
- une liste d'outils dans un ordre fixe, que les clients peuvent garder en cache ;
- des schémas JSON Schema 2020-12 en entrée comme en sortie.

FastMCP annonce encore la capacité `logging`, dépréciée par cette version (SEP-2577) : le
serveur ne journalise rien par MCP, ses journaux vont sur la sortie d'erreur, que Horizon
recueille.

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

Le serveur est en ligne à **`https://mister-parc-mcp.fastmcp.app/mcp`**, derrière
l'authentification de Horizon : seuls les membres de l'organisation Horizon `mister-guiiug`
s'y connectent, par une connexion OAuth que le client ouvre lui-même. Sans authentification,
le gateway répond 401.

```bash
claude mcp add --transport http mister-parc https://mister-parc-mcp.fastmcp.app/mcp
```

Un client sans connexion interactive (un script, une CI) passe une clé d'API Horizon
(`fmcp_…`) comme jeton porteur.

En local, sans Horizon, sur stdio :

```bash
claude mcp add mister-parc-local -- uv run --directory <chemin du dépôt> fastmcp run serveur.py:mcp
```

## Déployer sur Horizon

Le projet Horizon `mister-parc-mcp` (organisation `mister-guiiug`) a été créé le 29/10/2026
par l'API de Horizon. Sa source est la branche `main` de ce dépôt, lue par l'application
GitHub de Horizon, qui n'a accès qu'à ce dépôt. Ses réglages :

| Réglage | Valeur |
|---|---|
| Point d'entrée | `serveur.py:mcp` |
| Dépendances | `pyproject.toml` |
| Python | 3.14, lue dans `.python-version` : la plus récente que Horizon accepte (3.11 à 3.14) |
| Authentification | activée (le défaut) |
| Variables | aucune |

**Chaque push sur `main` redéploie la production** : la cible `production` suit `main`.
**Chaque PR a son déploiement d'aperçu**, derrière la même authentification. Un retour en
arrière se fait depuis le tableau de bord de Horizon, ou par l'API (`rollback` d'un
déploiement précédent), pendant trente jours.

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
