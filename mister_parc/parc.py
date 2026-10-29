"""Le tableau de bord du parc, interrogeable.

Chaque outil lit `donnees.json` ou `a-faire.json` (voir `sources`) et rend une
vue resserrée : ce qu'il faut pour répondre, pas le modèle entier, qui pèse
près d'un demi-mégaoctet.
"""

from __future__ import annotations

from difflib import get_close_matches
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from . import sources

serveur = FastMCP("parc")

LECTURE = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=True)

Niveau = Literal["critique", "attention", "decision", "entretien"]
Famille = Literal["pwa", "desktop", "socle", "autre"]

# Les chiffres que `etat` rend. Le relevé en compte une cinquantaine ; ceux-ci
# répondent à « est-ce que tout va bien ? ».
CHIFFRES = (
    "depots",
    "verts",
    "rouges",
    "taux",
    "prOuvertes",
    "sites",
    "sitesEnLigne",
    "alertes",
    "alertesGraves",
    "scanning",
    "scanningGraves",
    "depotsSansRuleset",
    "socleEnRetard",
    "dormantes",
)

# Chaque workflow porte l'historique de ses derniers runs : 11 Ko sur un seul
# dépôt. Le dernier état suffit, et son lien mène au reste.
CHAMPS_WORKFLOW = ("nom", "fichier", "reutilisable", "etat", "conclusion", "date", "url")


def trouver(nom: str, elements: list[dict[str, Any]], cle: str, quoi: str) -> dict[str, Any]:
    """L'élément nommé, sans égard à la casse ; sinon une erreur qui propose des noms proches."""
    for e in elements:
        if str(e.get(cle, "")).lower() == nom.lower():
            return e
    noms = [str(e.get(cle)) for e in elements]
    proches = get_close_matches(nom, noms, n=5, cutoff=0.5)
    suite = f" Noms proches : {', '.join(proches)}." if proches else ""
    raise ToolError(f"{quoi} « {nom} » absent du dernier relevé.{suite}")


def version_du_socle(depot: dict[str, Any]) -> str | None:
    for brique in depot.get("pile") or []:
        if brique.get("nom") == "pile.socle":
            return brique.get("version")
    return None


def resume_depot(d: dict[str, Any]) -> dict[str, Any]:
    return {
        "nom": d.get("nom"),
        "famille": d.get("famille"),
        "role": d.get("role"),
        "description": d.get("description"),
        "url": d.get("url"),
        "ci": d.get("compte"),
        "alertes": (d.get("alertes") or {}).get("total"),
        "codeql": (d.get("scanning") or {}).get("total"),
        "prs_ouvertes": len(d.get("prs") or []),
        "site_en_ligne": (d.get("pages") or {}).get("ok"),
        "socle": version_du_socle(d),
        "dernier_commit": (d.get("commit") or {}).get("date"),
    }


@serveur.tool(annotations=LECTURE)
async def etat() -> dict[str, Any]:
    """L'état du parc en une réponse : chiffres clés du dernier relevé, version du socle,
    rubriques « À faire » (sans leur détail) et ce qui a bougé depuis la photo du jour.

    À appeler en premier. `genere` date le relevé : il passe au mieux toutes les heures.
    Le détail d'une rubrique s'obtient par `a_faire`.
    """
    d = await sources.donnees()
    af = await sources.a_faire()
    kpi = d.get("kpi") or {}
    return {
        "genere": d.get("genere"),
        "page": sources.PAGE,
        "chiffres": {k: kpi[k] for k in CHIFFRES if k in kpi},
        "socle": {
            "version": (d.get("socleOffre") or {}).get("version"),
            "amont": kpi.get("socleAmont"),
            "a_publier": d.get("socleAPublier"),
        },
        "a_faire": [
            {k: it.get(k) for k in ("cle", "niveau", "titre", "n")} for it in af.get("items", [])
        ],
        "changements": d.get("changements") or [],
    }


@serveur.tool(annotations=LECTURE)
async def a_faire(
    niveau: Annotated[
        Niveau | None, Field(description="Ne garder qu'un niveau de gravité.")
    ] = None,
    rubrique: Annotated[
        str | None,
        Field(description="Ne garder qu'une rubrique, par sa clé : rouges, prs, correctifs…"),
    ] = None,
) -> dict[str, Any]:
    """La liste « À faire » du tableau de bord, avec le détail de chaque rubrique :
    dépôts concernés, PR à relire, montées de librairies (paquet, cible, dépôts et versions).

    C'est la liste que la page affiche, calculée par le relevé ; rien n'est recalculé ici.
    Niveaux, du plus urgent au moins urgent : critique, attention, decision, entretien.
    """
    af = await sources.a_faire()
    items = [
        it
        for it in af.get("items", [])
        if (niveau is None or it.get("niveau") == niveau)
        and (rubrique is None or it.get("cle") == rubrique)
    ]
    return {"genere": af.get("genere"), "page": sources.PAGE, "items": items}


@serveur.tool(annotations=LECTURE)
async def depots(
    famille: Annotated[
        Famille | None, Field(description="Ne garder qu'une famille de dépôts.")
    ] = None,
) -> dict[str, Any]:
    """Les dépôts publics du compte, une ligne chacun : famille, CI (verts, rouges, en cours),
    alertes de vulnérabilité, alertes CodeQL, PR ouvertes, site en ligne, version du socle,
    date du dernier commit.
    """
    d = await sources.donnees()
    lignes = [
        resume_depot(x)
        for x in d.get("depots") or []
        if famille is None or x.get("famille") == famille
    ]
    return {"genere": d.get("genere"), "depots": lignes}


@serveur.tool(annotations=LECTURE)
async def depot(
    nom: Annotated[str, Field(description="Nom du dépôt, par exemple mister-cim10.")],
) -> dict[str, Any]:
    """Tout ce que le relevé sait d'un dépôt : dernier commit, workflows et leur dernier état,
    PR ouvertes, alertes, CodeQL, ruleset, site et production, pile technique, usage du socle.
    """
    d = await sources.donnees()
    x = trouver(nom, d.get("depots") or [], "nom", "Dépôt")
    vue = {k: v for k, v in x.items() if k != "workflows"}
    vue["workflows"] = [{k: w.get(k) for k in CHAMPS_WORKFLOW} for w in x.get("workflows") or []]
    return {"genere": d.get("genere"), "depot": vue}


@serveur.tool(annotations=LECTURE)
async def echecs() -> dict[str, Any]:
    """Les workflows rouges sur la branche par défaut : dépôt, workflow, job et étape en échec,
    lien du run. Une liste vide veut dire que tout est vert.
    """
    d = await sources.donnees()
    return {"genere": d.get("genere"), "echecs": d.get("echecs") or []}


@serveur.tool(annotations=LECTURE)
async def librairie(
    paquet: Annotated[
        str, Field(description="Nom exact du paquet, par exemple lucide-react ou Node.js.")
    ],
) -> dict[str, Any]:
    """Une librairie du parc : ses versions, quels dépôts sont sur laquelle, la dernière version
    publiée en amont et le retard.
    """
    d = await sources.donnees()
    lib = trouver(paquet, d.get("libs") or [], "paquet", "Librairie")
    return {"genere": d.get("genere"), "librairie": lib}


@serveur.tool(annotations=LECTURE)
async def librairies_en_retard(
    ecosysteme: Annotated[
        str | None, Field(description="npm, cargo, nuget, node… Toutes si absent.")
    ] = None,
) -> dict[str, Any]:
    """Les librairies dont au moins un dépôt est en retard sur l'amont, les plus en retard
    d'abord. Pour le détail par dépôt, appeler `librairie`.
    """
    d = await sources.donnees()
    lignes = [
        {
            "paquet": lib.get("paquet"),
            "ecosysteme": lib.get("ecosysteme"),
            "plus_recente": lib.get("plusRecente"),
            "publiee_le": lib.get("publieLe"),
            "depots_en_retard": lib.get("enRetard"),
            "depots": lib.get("nbDepots"),
        }
        for lib in d.get("libs") or []
        if (lib.get("enRetard") or 0) > 0
        and (ecosysteme is None or lib.get("ecosysteme") == ecosysteme)
    ]
    lignes.sort(key=lambda x: (-(x["depots_en_retard"] or 0), str(x["paquet"])))
    return {"genere": d.get("genere"), "librairies": lignes}


@serveur.tool(annotations=LECTURE)
async def tendances(
    jours: Annotated[int, Field(ge=1, le=400, description="Nombre de points, un par jour.")] = 30,
) -> dict[str, Any]:
    """L'historique quotidien du parc, du plus ancien au plus récent : taux de vert, rouges,
    alertes, socle en retard. Un jour sans changement n'a pas de point.
    """
    d = await sources.donnees()
    return {"historique": (d.get("historique") or [])[-jours:]}


@serveur.tool(annotations=LECTURE)
async def journal(
    n: Annotated[int, Field(ge=1, le=60, description="Nombre de transitions.")] = 20,
) -> dict[str, Any]:
    """Les dernières transitions vues par le relevé, la plus récente d'abord : CI passée au
    rouge ou au vert, nouvelle version en amont, alertes qui montent ou descendent.
    """
    d = await sources.donnees()
    return {"journal": (d.get("journal") or [])[:n]}
