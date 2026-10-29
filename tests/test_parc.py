from __future__ import annotations

import re

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from mister_parc import sources

from .conftest import appeler, donnees

pytestmark = pytest.mark.anyio


async def test_etat_resume_le_releve_sans_le_detail(client: Client) -> None:
    r = await appeler(client, "parc_etat")
    D = donnees()
    assert r["genere"] == D["genere"]
    assert r["chiffres"]["depots"] == D["kpi"]["depots"]
    assert r["socle"]["version"] == "6.28.1"
    assert [x["cle"] for x in r["a_faire"]] == [
        "alertes",
        "scanning",
        "prs",
        "correctifs",
        "renovate",
    ]
    # Le titre est celui de la page, calculé par le relevé.
    assert r["a_faire"][0]["titre"].endswith("ont des alertes de vulnérabilité")
    assert "details" not in r["a_faire"][0]


async def test_a_faire_filtre_par_niveau_et_rend_le_detail(client: Client) -> None:
    r = await appeler(client, "parc_a_faire", {"niveau": "entretien"})
    assert [x["cle"] for x in r["items"]] == ["correctifs", "renovate"]
    detail = r["items"][0]["details"][0]
    assert detail["paquet"] == "lucide-react"
    assert detail["depots"], "chaque montée nomme ses dépôts"


async def test_a_faire_filtre_par_rubrique(client: Client) -> None:
    r = await appeler(client, "parc_a_faire", {"rubrique": "scanning"})
    assert [x["cle"] for x in r["items"]] == ["scanning"]


async def test_a_faire_refuse_un_niveau_inconnu(client: Client) -> None:
    with pytest.raises(ToolError):
        await client.call_tool("parc_a_faire", {"niveau": "urgent"})


async def test_depots_une_ligne_par_depot_et_par_famille(client: Client) -> None:
    tous = (await appeler(client, "parc_depots"))["depots"]
    assert len(tous) == 4
    pwa = (await appeler(client, "parc_depots", {"famille": "pwa"}))["depots"]
    assert [x["nom"] for x in pwa] == ["mister-cim10"]
    assert pwa[0]["socle"] == "6.28.1"
    assert pwa[0]["site_en_ligne"] is True
    assert pwa[0]["ruleset"] == "actif"
    assert pwa[0]["prs_ouvertes"] == 1


async def test_depot_resserre_les_workflows(client: Client) -> None:
    r = (await appeler(client, "parc_depot", {"nom": "MISTER-CIM10"}))["depot"]
    assert r["nom"] == "mister-cim10"
    assert r["workflows"], "le dépôt a des workflows"
    assert all("derniers" not in w for w in r["workflows"])
    assert {"nom", "etat", "url"} <= set(r["workflows"][0])


async def test_depot_inconnu_propose_des_noms_proches(client: Client) -> None:
    with pytest.raises(ToolError, match="mister-cim10"):
        await client.call_tool("parc_depot", {"nom": "mister-cim1"})


async def test_echecs(client: Client) -> None:
    r = await appeler(client, "parc_echecs")
    assert [e["depot"] for e in r["echecs"]] == ["mister-cim10"]


async def test_prs_de_tout_le_compte(client: Client) -> None:
    r = (await appeler(client, "parc_prs"))["prs"]
    assert [(p["depot"], p["num"], p["ci"]) for p in r] == [("mister-cim10", 158, "vert")]
    assert r[0]["url"].endswith("/pull/158")
    # Une PR humaine reste quand on écarte les robots.
    assert len((await appeler(client, "parc_prs", {"robots": False}))["prs"]) == 1


async def test_alertes_les_plus_graves_d_abord(client: Client) -> None:
    r = await appeler(client, "parc_alertes")
    assert r["lisibles"] == {"dependabot": True, "codeql": True}
    assert [x["depot"] for x in r["depots"]] == [
        "mister-commitia",
        "mister-cim10",
        "pwa-starter-kit",
    ]
    cim10 = r["depots"][1]
    assert cim10["dependabot_ids"] == ["CVE-2026-93753"]
    assert cim10["codeql_regles"] == ["js/clear-text-storage-of-sensitive-data"]


async def test_alertes_d_un_depot_meme_sans_alerte(client: Client) -> None:
    r = await appeler(client, "parc_alertes", {"depot": "mister-claude-skills"})
    assert [(x["depot"], x["dependabot"], x["codeql"]) for x in r["depots"]] == [
        ("mister-claude-skills", 0, 0)
    ]


async def test_sites_et_production(client: Client) -> None:
    r = (await appeler(client, "parc_sites"))["sites"]
    assert [s["depot"] for s in r] == ["mister-cim10", "pwa-starter-kit"]
    assert r[0]["en_ligne"] is True
    assert r[0]["production"] == "aJour"
    assert (await appeler(client, "parc_sites", {"en_panne": True}))["sites"] == []


async def test_renovate_en_attente(client: Client) -> None:
    r = (await appeler(client, "parc_renovate"))["depots"]
    assert [(x["depot"], x["en_attente"], x["majeures"]) for x in r] == [("mister-commitia", 2, 1)]
    assert [m["majeure"] for m in r[0]["mises"]] == [False, True]


async def test_chercher_dans_les_noms_et_les_descriptions(client: Client) -> None:
    r = await appeler(client, "parc_chercher", {"terme": "CIM"})
    assert [x["nom"] for x in r["depots"]] == ["mister-cim10"]
    r = await appeler(client, "parc_chercher", {"terme": "lucide"})
    assert [x["paquet"] for x in r["librairies"]] == ["lucide-react"]
    with pytest.raises(ToolError):
        await client.call_tool("parc_chercher", {"terme": "x"})


async def test_librairie_et_son_retard(client: Client) -> None:
    lib = (await appeler(client, "parc_librairie", {"paquet": "lucide-react"}))["librairie"]
    assert lib["enRetard"] == 1
    with pytest.raises(ToolError, match="absent"):
        await client.call_tool("parc_librairie", {"paquet": "leftpad"})


async def test_librairies_en_retard_seulement(client: Client) -> None:
    r = (await appeler(client, "parc_librairies_en_retard"))["librairies"]
    assert {x["paquet"] for x in r} == {"lucide-react", "motion"}
    vide = await appeler(client, "parc_librairies_en_retard", {"ecosysteme": "cargo"})
    assert vide["librairies"] == []


async def test_tendances_et_journal_bornes(client: Client) -> None:
    h = (await appeler(client, "parc_tendances", {"jours": 2}))["historique"]
    assert h == donnees()["historique"][-2:]
    j = (await appeler(client, "parc_journal", {"n": 1}))["journal"]
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
