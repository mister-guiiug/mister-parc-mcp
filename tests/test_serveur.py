"""Le serveur tel qu'un client MCP 2026-07-28 le voit : identité, liste, schémas."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator

from serveur import DUREE_CACHE_LISTES_S, mcp

pytestmark = pytest.mark.anyio

# L'ordre compte : la spécification 2026-07-28 demande une liste DÉTERMINISTE, pour
# que les clients et les caches de prompt des modèles la reprennent telle quelle.
OUTILS = [
    "parc_etat",
    "parc_a_faire",
    "parc_depots",
    "parc_depot",
    "parc_echecs",
    "parc_prs",
    "parc_alertes",
    "parc_sites",
    "parc_renovate",
    "parc_librairie",
    "parc_librairies_en_retard",
    "parc_chercher",
    "parc_tendances",
    "parc_journal",
    "socle_offre",
    "socle_module",
    "socle_workflow",
    "socle_usage",
    "socle_doc",
    "socle_chercher",
]

# Un appel valide par outil : de quoi faire parler chacun sur les données de test.
ARGUMENTS: dict[str, dict] = {
    "parc_depot": {"nom": "mister-cim10"},
    "parc_alertes": {"depot": "mister-cim10"},
    "parc_librairie": {"paquet": "lucide-react"},
    "parc_chercher": {"terme": "cim"},
    "socle_module": {"nom": "eslint-react"},
    "socle_workflow": {"nom": "pwa-ci.yml"},
    "socle_usage": {"depot": "mister-cim10"},
    "socle_doc": {"fichier": "README.md"},
    "socle_chercher": {"terme": "prefetch"},
}


async def test_les_outils_sont_ceux_annonces_dans_un_ordre_fixe(client: Client) -> None:
    assert [t.name for t in await client.list_tools()] == OUTILS


async def test_le_serveur_dit_sa_propre_version(client: Client) -> None:
    projet = tomllib.loads(Path("pyproject.toml").read_text("utf-8"))["project"]
    assert client.server_info is not None
    assert client.server_info.name == "mister-parc"
    assert client.server_info.version == projet["version"]


async def test_la_liste_annonce_sa_fraicheur(client: Client) -> None:
    liste = (await client.list_tools_mcp()).model_dump(by_alias=True)
    assert liste["ttlMs"] == DUREE_CACHE_LISTES_S * 1000
    assert liste["cacheScope"] == "private"


# Le serveur ne fait que lire. Un outil qui écrirait (fusionner une PR, lancer
# une campagne) contournerait la décision humaine que le parc exige.
async def test_chaque_outil_se_declare_en_lecture_seule(client: Client) -> None:
    for t in await client.list_tools():
        assert t.annotations is not None, t.name
        assert t.annotations.read_only_hint is True, t.name
        assert t.annotations.destructive_hint is not True, t.name


async def test_chaque_outil_a_un_titre_et_dit_ce_qu_il_rend(client: Client) -> None:
    for t in await client.list_tools():
        assert t.title, t.name
        assert t.description and len(t.description) > 40, t.name
        schema = t.output_schema or {}
        assert schema.get("properties"), f"{t.name} : outputSchema sans champs"


# LE CONTRAT. Un client 2026-07-28 peut valider `structuredContent` contre
# l'`outputSchema` annoncé : chaque réponse réelle doit donc s'y conformer.
async def test_chaque_reponse_respecte_son_output_schema(client: Client) -> None:
    for t in await client.list_tools():
        Draft202012Validator.check_schema(t.output_schema)
        r = await client.call_tool(t.name, ARGUMENTS.get(t.name, {}))
        erreurs = sorted(
            Draft202012Validator(t.output_schema).iter_errors(r.structured_content),
            key=lambda e: list(e.path),
        )
        assert not erreurs, f"{t.name} : {erreurs[0].message} à {list(erreurs[0].path)}"


def test_les_instructions_menent_aux_premiers_outils() -> None:
    assert "parc_etat" in mcp.instructions
    assert "socle_chercher" in mcp.instructions
