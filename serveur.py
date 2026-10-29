"""Point d'entrée du serveur : `serveur.py:mcp` dans Horizon.

Deux familles d'outils, montées sous leur espace de noms : `parc_*` (le tableau
de bord) et `socle_*` (dev-pwa-config). Les monter ici, dans le code, tient
lieu de Remix, que Horizon réserve à son offre Enterprise.

Protocole MCP 2026-07-28, que parle la bibliothèque `mcp` (2.3.0 et suivantes) :
sans état, `server/discover`, `resultType` sur chaque résultat. Ce qui revient
au serveur est réglé ici : son identité (`serverInfo`, version comprise) et la
fraîcheur que ses listes annoncent (`ttlMs`, `cacheScope`, SEP-2549).

En local, sur stdio : `uv run fastmcp run serveur.py:mcp`.
"""

import tomllib
from pathlib import Path

from fastmcp import FastMCP

from mister_parc import parc, socle

# Une seule version, celle du projet : `serverInfo.version` disait celle de FastMCP.
_PROJET = tomllib.loads((Path(__file__).parent / "pyproject.toml").read_text("utf-8"))
VERSION: str = _PROJET["project"]["version"]

# La liste des outils ne change qu'à un déploiement : un client qui la garde une
# heure voit un outil neuf au plus une heure après la mise en production.
# `private`, parce que le serveur est derrière une authentification.
DUREE_CACHE_LISTES_S = 3600

INSTRUCTIONS = """\
L'état du parc mister-guiiug : une trentaine de dépôts publics, des PWA React pour \
la plupart, et leur socle commun dev-pwa-config.

Tout est en lecture seule, lu dans ce que le tableau de bord publie à chaque relevé \
(au mieux une fois par heure ; `genere` date chaque réponse). Commencer par \
`parc_etat`, puis `parc_a_faire` pour le détail d'une rubrique. `parc_chercher` \
retrouve un nom exact de dépôt ou de librairie.

Avant d'écrire dans une application un composant, un hook ou un workflow, appeler \
`socle_chercher` : le socle l'offre peut-être déjà.
"""

mcp = FastMCP(
    "mister-parc",
    instructions=INSTRUCTIONS,
    version=VERSION,
    website_url="https://github.com/mister-guiiug/mister-parc-mcp",
    cache_ttl=DUREE_CACHE_LISTES_S,
    cache_scope="private",
)
mcp.mount(parc.serveur, namespace="parc")
mcp.mount(socle.serveur, namespace="socle")

if __name__ == "__main__":
    mcp.run()
