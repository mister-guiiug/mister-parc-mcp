"""Le réseau des tests : les fichiers publiés, servis depuis `tests/`.

`donnees.json` et `a-faire.json` sont le relevé du 29/10/2026, réduit à quatre
dépôts (un par famille) et à huit modules du socle ; l'échec de CI y est
inventé, le relevé n'en avait aucun. Les documents du socle sont écrits ici.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastmcp import Client

from mister_parc import sources
from serveur import mcp

ICI = Path(__file__).parent
VERSION = "6.28.1"

README = """\
# dev-pwa-config

## Stack cible

Node 22, Vite 8.

## Préchargement des routes

`react/use-prefetch` précharge une route au survol.

```md
# Pas un titre : un bloc de code
```

## Images

`stripImageMetadata` retire les métadonnées.
"""

CONFIG = """\
# Configuration

## Secrets ou variables

Ce que Vite copie dans le bundle va en `vars`.
"""

CONTRIBUTING = """\
# Contribuer

## Le socle promeut, il n'invente pas

Une chose entre quand plusieurs applications l'ont écrite.
"""


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def publie() -> dict[str, tuple[int, str]]:
    """URL publiée → (statut, corps). Un test peut en retirer ou en changer une."""
    doc = lambda f: sources.url_doc_socle(VERSION, f)  # noqa: E731
    return {
        sources.URL_DONNEES: (200, (ICI / "donnees.json").read_text(encoding="utf-8")),
        sources.URL_A_FAIRE: (200, (ICI / "a-faire.json").read_text(encoding="utf-8")),
        doc("README.md"): (200, README),
        doc("CONFIG.md"): (200, CONFIG),
        doc("CONTRIBUTING.md"): (200, CONTRIBUTING),
        doc("STRATEGIE.md"): (200, "# Stratégie\n"),
    }


@pytest.fixture
def demandes(publie: dict[str, tuple[int, str]], monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Branche le réseau simulé ; rend la liste des URL demandées, dans l'ordre."""
    vues: list[str] = []

    def repondre(requete: httpx.Request) -> httpx.Response:
        url = str(requete.url)
        vues.append(url)
        statut, corps = publie.get(url, (404, "introuvable"))
        return httpx.Response(statut, text=corps)

    monkeypatch.setattr(sources, "transport", httpx.MockTransport(repondre))
    sources.vider_cache()
    yield vues
    sources.vider_cache()


@pytest.fixture
async def client(demandes: list[str]) -> AsyncIterator[Client]:
    async with Client(mcp) as c:
        yield c


async def appeler(client: Client, outil: str, arguments: dict | None = None) -> dict:
    """La réponse structurée d'un outil, `structuredContent`, telle que le client la reçoit.

    `.data` ne convient plus : depuis que chaque outil annonce un `outputSchema`, FastMCP
    en fait des objets typés. Le contrat, c'est le JSON.
    """
    return (await client.call_tool(outil, arguments or {})).structured_content


def donnees() -> dict:
    return json.loads((ICI / "donnees.json").read_text(encoding="utf-8"))
