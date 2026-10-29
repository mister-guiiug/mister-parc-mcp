"""Ce que le serveur lit, et rien d'autre : des fichiers déjà publiés.

Le tableau de bord publie son modèle à chaque relevé (parc-dashboard,
`donnees.json` et `a-faire.json`) ; le socle publie sa documentation à chaque
version, sous l'étiquette `v<version>`. Le serveur ne recalcule rien de ce
qu'ils calculent : il lit, filtre et résume. Une règle écrite deux fois, une
en JavaScript et une en Python, vieillirait d'un côté sans que rien le dise.

Aucun jeton : tout ce qui est lu ici est public.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from fastmcp.exceptions import ToolError

COMPTE = "mister-guiiug"
PAGE = f"https://{COMPTE}.github.io/parc-dashboard/"
URL_DONNEES = PAGE + "donnees.json"
URL_A_FAIRE = PAGE + "a-faire.json"
BRUT_SOCLE = f"https://raw.githubusercontent.com/{COMPTE}/dev-pwa-config"

# Le relevé passe au mieux une fois par heure : relire plus souvent n'apprend
# rien. Le cache ne vit que dans une instance, et Horizon peut servir deux
# requêtes par deux instances : c'est une économie, pas une garantie.
DUREE_CACHE_S = 300.0
DELAI_S = 20.0

# Remplacé par un `httpx.MockTransport` dans les tests.
transport: httpx.AsyncBaseTransport | None = None

_cache: dict[str, tuple[float, Any]] = {}


def vider_cache() -> None:
    _cache.clear()


async def _telecharger(url: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=transport,
        timeout=DELAI_S,
        follow_redirects=True,
        headers={"User-Agent": "mister-parc-mcp"},
    ) as client:
        try:
            reponse = await client.get(url)
        except httpx.HTTPError as e:
            raise ToolError(f"{url} injoignable ({e.__class__.__name__}).") from e
    if reponse.status_code != 200:
        raise ToolError(f"{url} : HTTP {reponse.status_code}.")
    return reponse


async def _en_cache(url: str, lire: Callable[[str], Awaitable[Any]]) -> Any:
    maintenant = time.monotonic()
    vu = _cache.get(url)
    if vu is not None and maintenant - vu[0] < DUREE_CACHE_S:
        return vu[1]
    valeur = await lire(url)
    _cache[url] = (maintenant, valeur)
    return valeur


async def json_publie(url: str) -> Any:
    async def lire(u: str) -> Any:
        reponse = await _telecharger(u)
        try:
            return reponse.json()
        except ValueError as e:
            raise ToolError(f"{u} : la réponse n'est pas du JSON.") from e

    return await _en_cache(url, lire)


async def texte_publie(url: str) -> str:
    async def lire(u: str) -> str:
        return (await _telecharger(u)).text

    return await _en_cache(url, lire)


async def donnees() -> dict[str, Any]:
    """Le modèle que porte la page du tableau de bord."""
    return await json_publie(URL_DONNEES)


async def a_faire() -> dict[str, Any]:
    """La liste « À faire » de la page, telle que la page la dresse."""
    return await json_publie(URL_A_FAIRE)


def url_doc_socle(version: str, fichier: str) -> str:
    return f"{BRUT_SOCLE}/v{version}/{fichier}"
