from __future__ import annotations

import re

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from mister_parc import sources

from .conftest import donnees

pytestmark = pytest.mark.anyio


async def test_etat_resume_le_releve_sans_le_detail(client: Client) -> None:
    r = (await client.call_tool("parc_etat")).data
    D = donnees()
    assert r["genere"] == D["genere"]
    assert r["chiffres"]["depots"] == D["kpi"]["depots"]
    assert r["socle"]["version"] == "6.28.1"
    assert [x["cle"] for x in r["a_faire"]] == ["alertes", "scanning", "correctifs"]
    # Le titre est celui de la page, calculé par le relevé.
    assert r["a_faire"][0]["titre"].endswith("ont des alertes de vulnérabilité")
    assert "details" not in r["a_faire"][0]


async def test_a_faire_filtre_par_niveau_et_rend_le_detail(client: Client) -> None:
    r = (await client.call_tool("parc_a_faire", {"niveau": "entretien"})).data
    assert [x["cle"] for x in r["items"]] == ["correctifs"]
    detail = r["items"][0]["details"][0]
    assert detail["paquet"] == "lucide-react"
    assert detail["depots"], "chaque montée nomme ses dépôts"


async def test_a_faire_filtre_par_rubrique(client: Client) -> None:
    r = (await client.call_tool("parc_a_faire", {"rubrique": "scanning"})).data
    assert [x["cle"] for x in r["items"]] == ["scanning"]


async def test_a_faire_refuse_un_niveau_inconnu(client: Client) -> None:
    with pytest.raises(ToolError):
        await client.call_tool("parc_a_faire", {"niveau": "urgent"})


async def test_depots_une_ligne_par_depot_et_par_famille(client: Client) -> None:
    tous = (await client.call_tool("parc_depots")).data["depots"]
    assert len(tous) == 4
    pwa = (await client.call_tool("parc_depots", {"famille": "pwa"})).data["depots"]
    assert [x["nom"] for x in pwa] == ["mister-cim10"]
    assert pwa[0]["socle"] == "6.28.1"
    assert pwa[0]["site_en_ligne"] is True


async def test_depot_resserre_les_workflows(client: Client) -> None:
    r = (await client.call_tool("parc_depot", {"nom": "MISTER-CIM10"})).data["depot"]
    assert r["nom"] == "mister-cim10"
    assert r["workflows"], "le dépôt a des workflows"
    assert all("derniers" not in w for w in r["workflows"])
    assert {"nom", "etat", "url"} <= set(r["workflows"][0])


async def test_depot_inconnu_propose_des_noms_proches(client: Client) -> None:
    with pytest.raises(ToolError, match="mister-cim10"):
        await client.call_tool("parc_depot", {"nom": "mister-cim1"})


async def test_echecs(client: Client) -> None:
    r = (await client.call_tool("parc_echecs")).data
    assert [e["depot"] for e in r["echecs"]] == ["mister-cim10"]


async def test_librairie_et_son_retard(client: Client) -> None:
    lib = (await client.call_tool("parc_librairie", {"paquet": "lucide-react"})).data["librairie"]
    assert lib["enRetard"] == 1
    with pytest.raises(ToolError, match="absent"):
        await client.call_tool("parc_librairie", {"paquet": "leftpad"})


async def test_librairies_en_retard_seulement(client: Client) -> None:
    r = (await client.call_tool("parc_librairies_en_retard")).data["librairies"]
    assert {x["paquet"] for x in r} == {"lucide-react", "motion"}
    assert (await client.call_tool("parc_librairies_en_retard", {"ecosysteme": "cargo"})).data[
        "librairies"
    ] == []


async def test_tendances_et_journal_bornes(client: Client) -> None:
    h = (await client.call_tool("parc_tendances", {"jours": 2})).data["historique"]
    assert h == donnees()["historique"][-2:]
    j = (await client.call_tool("parc_journal", {"n": 1})).data["journal"]
    assert j == donnees()["journal"][:1]
    with pytest.raises(ToolError):
        await client.call_tool("parc_tendances", {"jours": 0})


async def test_un_seul_telechargement_par_fichier_dans_le_cache(
    client: Client, demandes: list[str]
) -> None:
    await client.call_tool("parc_depots")
    await client.call_tool("parc_echecs")
    assert demandes.count(sources.URL_DONNEES) == 1


async def test_fichier_non_publie_le_dit(
    client: Client, publie: dict[str, tuple[int, str]]
) -> None:
    del publie[sources.URL_A_FAIRE]
    with pytest.raises(ToolError, match=re.escape("a-faire.json : HTTP 404")):
        await client.call_tool("parc_a_faire")
