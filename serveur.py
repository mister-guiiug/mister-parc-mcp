"""Point d'entrée du serveur : `serveur.py:mcp` dans Horizon.

Deux familles d'outils, montées sous leur espace de noms : `parc_*` (le tableau
de bord) et `socle_*` (dev-pwa-config). Les monter ici, dans le code, tient
lieu de Remix, que Horizon réserve à son offre Enterprise.

En local, sur stdio : `uv run fastmcp run serveur.py:mcp`.
"""

from fastmcp import FastMCP

from mister_parc import parc, socle

INSTRUCTIONS = """\
L'état du parc mister-guiiug : une trentaine de dépôts publics, des PWA React pour
la plupart, et leur socle commun dev-pwa-config.

Tout est en lecture seule, lu dans ce que le tableau de bord publie à chaque relevé
(au mieux une fois par heure ; `genere` date chaque réponse). Commencer par
`parc_etat`, puis `parc_a_faire` pour le détail d'une rubrique.

Avant d'écrire dans une application un composant, un hook ou un workflow, appeler
`socle_chercher` : le socle l'offre peut-être déjà.
"""

mcp = FastMCP("mister-parc", instructions=INSTRUCTIONS)
mcp.mount(parc.serveur, namespace="parc")
mcp.mount(socle.serveur, namespace="socle")

if __name__ == "__main__":
    mcp.run()
