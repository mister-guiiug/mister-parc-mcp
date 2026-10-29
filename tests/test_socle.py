from __future__ import annotations

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from mister_parc import sources
from mister_parc.socle import sections

from .conftest import README, VERSION

pytestmark = pytest.mark.anyio


async def test_offre_range_les_modules_par_categorie(client: Client) -> None:
    r = (await client.call_tool("socle_offre")).data
    assert r["version"] == VERSION
    assert sum(len(m) for m in r["modules"].values()) == 8
    assert "pwa-doctor" in r["outils"]
    assert "pwa-ci.yml" in r["workflows"]


async def test_module_emporte_et_emporte_par(client: Client) -> None:
    r = (await client.call_tool("socle_module", {"nom": "eslint-base"})).data
    assert r["emporte"] == []
    assert r["emporte_par"] == ["eslint-react"]
    r = (await client.call_tool("socle_module", {"nom": "eslint-react"})).data
    assert r["emporte"] == ["eslint-base"]
    assert r["importe_par"] == ["mister-cim10", "pwa-starter-kit"]


async def test_module_inconnu(client: Client) -> None:
    with pytest.raises(ToolError, match="absent"):
        await client.call_tool("socle_module", {"nom": "react/use-magie"})


async def test_workflow_donne_la_ligne_uses_et_ses_appelants(client: Client) -> None:
    r = (await client.call_tool("socle_workflow", {"nom": "pwa-ci.yml"})).data
    assert r["uses"] == "uses: mister-guiiug/dev-pwa-config/.github/workflows/pwa-ci.yml@v6"
    assert r["defauts"]["run-tests"] == "true"
    cim10 = next(a for a in r["appele_par"] if a["depot"] == "mister-cim10")
    assert cim10["avec"]["run-e2e"] == "true"


async def test_doc_lit_la_version_publiee(client: Client, demandes: list[str]) -> None:
    r = (await client.call_tool("socle_doc", {"fichier": "CONFIG.md"})).data
    assert r["url"] == sources.url_doc_socle(VERSION, "CONFIG.md")
    assert "vars" in r["texte"]
    assert r["url"] in demandes


async def test_doc_refuse_un_fichier_hors_liste(client: Client) -> None:
    with pytest.raises(ToolError):
        await client.call_tool("socle_doc", {"fichier": "../../etc/passwd"})


async def test_chercher_trouve_noms_et_sections(client: Client) -> None:
    r = (await client.call_tool("socle_chercher", {"terme": "Prefetch"})).data
    assert r["sections_trouvees"] == 1
    assert r["sections"][0]["titre"] == "Préchargement des routes"
    r = (await client.call_tool("socle_chercher", {"terme": "eslint"})).data
    assert r["modules"] == ["eslint-base", "eslint-react"]
    assert r["sections"] == []


def test_sections_ignore_les_titres_dans_un_bloc_de_code() -> None:
    titres = [t for t, _ in sections(README)]
    assert titres == ["dev-pwa-config", "Stack cible", "Préchargement des routes", "Images"]
