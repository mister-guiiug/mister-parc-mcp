from __future__ import annotations

import pytest
from fastmcp import Client

from serveur import mcp

pytestmark = pytest.mark.anyio

OUTILS = {
    "parc_etat",
    "parc_a_faire",
    "parc_depots",
    "parc_depot",
    "parc_echecs",
    "parc_librairie",
    "parc_librairies_en_retard",
    "parc_tendances",
    "parc_journal",
    "socle_offre",
    "socle_module",
    "socle_workflow",
    "socle_doc",
    "socle_chercher",
}


async def test_les_outils_sont_ceux_annonces(client: Client) -> None:
    assert {t.name for t in await client.list_tools()} == OUTILS


# Le serveur ne fait que lire. Un outil qui écrirait (fusionner une PR, lancer
# une campagne) contournerait la décision humaine que le parc exige.
async def test_chaque_outil_se_declare_en_lecture_seule(client: Client) -> None:
    for t in await client.list_tools():
        assert t.annotations is not None, t.name
        assert t.annotations.read_only_hint is True, t.name
        assert t.annotations.destructive_hint is not True, t.name


async def test_chaque_outil_dit_ce_qu_il_rend(client: Client) -> None:
    for t in await client.list_tools():
        assert t.description and len(t.description) > 40, t.name


def test_les_instructions_menent_aux_premiers_outils() -> None:
    assert "parc_etat" in mcp.instructions
    assert "socle_chercher" in mcp.instructions
