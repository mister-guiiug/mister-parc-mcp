"""Le tableau de bord du parc, interrogeable.

Chaque outil lit `donnees.json` ou `a-faire.json` (voir `sources`) et rend une
vue resserrée : ce qu'il faut pour répondre, pas le modèle entier, qui pèse
près d'un demi-mégaoctet. La forme de chaque réponse est dans `sorties`.
"""

from __future__ import annotations

from difflib import get_close_matches
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from . import sources
from .sorties import (
    AFaire,
    Alertes,
    Depots,
    Echecs,
    Etat,
    FicheDepot,
    FicheLibrairie,
    Journal,
    LigneDepot,
    PullRequests,
    RechercheParc,
    Renovate,
    Retards,
    Sites,
    Tendances,
)

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


def resume_depot(d: dict[str, Any]) -> LigneDepot:
    return {
        "nom": d.get("nom", ""),
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
        "ruleset": (d.get("ruleset") or {}).get("etat"),
        "dernier_commit": (d.get("commit") or {}).get("date"),
    }


@serveur.tool(title="État du parc", annotations=LECTURE)
async def etat() -> Etat:
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
            {"cle": it["cle"], "niveau": it.get("niveau"), "titre": it["titre"], "n": it["n"]}
            for it in af.get("items", [])
        ],
        "changements": d.get("changements") or [],
    }


@serveur.tool(title="À faire, en détail", annotations=LECTURE)
async def a_faire(
    niveau: Annotated[
        Niveau | None, Field(description="Ne garder qu'un niveau de gravité.")
    ] = None,
    rubrique: Annotated[
        str | None,
        Field(description="Ne garder qu'une rubrique, par sa clé : rouges, prs, correctifs…"),
    ] = None,
) -> AFaire:
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


@serveur.tool(title="Les dépôts", annotations=LECTURE)
async def depots(
    famille: Annotated[
        Famille | None, Field(description="Ne garder qu'une famille de dépôts.")
    ] = None,
) -> Depots:
    """Les dépôts publics du compte, une ligne chacun : famille, CI (verts, rouges, en cours),
    alertes de vulnérabilité, alertes CodeQL, PR ouvertes, site en ligne, version du socle,
    état du ruleset, date du dernier commit.
    """
    d = await sources.donnees()
    lignes = [
        resume_depot(x)
        for x in d.get("depots") or []
        if famille is None or x.get("famille") == famille
    ]
    return {"genere": d.get("genere"), "depots": lignes}


@serveur.tool(title="Fiche d'un dépôt", annotations=LECTURE)
async def depot(
    nom: Annotated[str, Field(description="Nom du dépôt, par exemple mister-cim10.")],
) -> FicheDepot:
    """Tout ce que le relevé sait d'un dépôt : dernier commit, workflows et leur dernier état,
    PR ouvertes, alertes, CodeQL, ruleset, site et production, pile technique, usage du socle.
    """
    d = await sources.donnees()
    x = trouver(nom, d.get("depots") or [], "nom", "Dépôt")
    vue = {k: v for k, v in x.items() if k != "workflows"}
    vue["workflows"] = [{k: w.get(k) for k in CHAMPS_WORKFLOW} for w in x.get("workflows") or []]
    return {"genere": d.get("genere"), "depot": vue}


@serveur.tool(title="Échecs de CI", annotations=LECTURE)
async def echecs() -> Echecs:
    """Les workflows rouges sur la branche par défaut : dépôt, workflow, job et étape en échec,
    lien du run. Une liste vide veut dire que tout est vert.
    """
    d = await sources.donnees()
    return {"genere": d.get("genere"), "echecs": d.get("echecs") or []}


@serveur.tool(title="Pull requests ouvertes", annotations=LECTURE)
async def prs(
    robots: Annotated[
        bool, Field(description="Garder aussi les PR ouvertes par un robot (Renovate…).")
    ] = True,
) -> PullRequests:
    """Les pull requests ouvertes sur tout le compte, les plus anciennes d'abord : dépôt,
    numéro, titre, branche, auteur, brouillon ou non, et l'état de leur CI.

    Dans ce parc, une PR ne se fusionne que sur la décision du propriétaire : cet outil
    les liste, il ne fusionne rien.
    """
    d = await sources.donnees()
    lignes = [
        {
            "depot": x.get("nom", ""),
            "num": p.get("num"),
            "titre": p.get("titre", ""),
            "brouillon": bool(p.get("brouillon")),
            "branche": p.get("branche"),
            "date": p.get("date"),
            "auteur": p.get("auteur"),
            "robot": bool(p.get("robot")),
            "url": p.get("url", ""),
            "ci": p.get("ci"),
        }
        for x in d.get("depots") or []
        for p in x.get("prs") or []
        if robots or not p.get("robot")
    ]
    lignes.sort(key=lambda p: str(p["date"] or ""))
    return {"genere": d.get("genere"), "prs": lignes}


@serveur.tool(title="Alertes de sécurité", annotations=LECTURE)
async def alertes(
    depot: Annotated[
        str | None, Field(description="Un seul dépôt ; sinon tous ceux qui ont des alertes.")
    ] = None,
) -> Alertes:
    """Les alertes ouvertes, dépôt par dépôt : vulnérabilités Dependabot (avec leurs
    identifiants CVE ou GHSA, et combien touchent la production) et alertes CodeQL (avec la
    règle en cause). Sans `depot`, seuls les dépôts qui ont au moins une alerte.
    """
    d = await sources.donnees()
    kpi = d.get("kpi") or {}
    tous = d.get("depots") or []
    choisis = [trouver(depot, tous, "nom", "Dépôt")] if depot else tous
    lignes = []
    for x in choisis:
        a = x.get("alertes") or {}
        s = x.get("scanning") or {}
        if not depot and not (a.get("total") or s.get("total")):
            continue
        lignes.append(
            {
                "depot": x.get("nom", ""),
                "dependabot": a.get("total") or 0,
                "dependabot_graves": a.get("graves") or 0,
                "dependabot_production": a.get("production") or 0,
                "dependabot_ids": list(a.get("ids") or []),
                "codeql": s.get("total") or 0,
                "codeql_graves": s.get("graves") or 0,
                "codeql_regles": list(s.get("ids") or []),
            }
        )
    lignes.sort(key=lambda x: (-(x["dependabot_graves"] + x["codeql_graves"]), x["depot"]))
    return {
        "genere": d.get("genere"),
        "lisibles": {
            "dependabot": bool(kpi.get("alertesLisibles")),
            "codeql": bool(kpi.get("scanningLisible")),
        },
        "depots": lignes,
    }


@serveur.tool(title="Sites en ligne", annotations=LECTURE)
async def sites(
    en_panne: Annotated[
        bool,
        Field(description="Ne garder que les sites injoignables ou en retard sur main."),
    ] = False,
) -> Sites:
    """Les sites GitHub Pages du parc : répondent-ils (code HTTP, temps de réponse, titre),
    la production est-elle à jour face à `main`, et sert-elle des morceaux fugaces ou des URL
    mortes.
    """
    d = await sources.donnees()
    lignes = []
    for x in d.get("depots") or []:
        p = x.get("pages") or {}
        if not p.get("url"):
            continue
        prod = x.get("prod") or {}
        ligne = {
            "depot": x.get("nom", ""),
            "url": p["url"],
            "en_ligne": p.get("ok"),
            "code": p.get("code"),
            "ms": p.get("ms"),
            "titre": p.get("titre"),
            "production": prod.get("etat"),
            "retard": prod.get("retard"),
            "fugaces": list(prod.get("fugaces") or []),
            "mortes": list(prod.get("mortes") or []),
        }
        casse = ligne["en_ligne"] is False or ligne["production"] == "retard" or ligne["mortes"]
        if not en_panne or casse:
            lignes.append(ligne)
    return {"genere": d.get("genere"), "sites": lignes}


@serveur.tool(title="Renovate en attente", annotations=LECTURE)
async def renovate() -> Renovate:
    """Ce que Renovate attend dans chaque dépôt, lu dans son « Dependency Dashboard » : les
    mises à jour en attente (majeures signalées) et les paquets qu'il ne sait pas résoudre.
    Avant de monter une librairie à la main, vérifier ici qu'une PR Renovate ne la couvre pas.
    """
    d = await sources.donnees()
    lignes = [
        {
            "depot": x.get("nom", ""),
            "en_attente": r.get("enAttente") or 0,
            "majeures": r.get("majeures") or 0,
            "mises": [
                {"titre": m.get("titre", ""), "majeure": bool(m.get("majeure"))}
                for m in r.get("mises") or []
            ],
            "introuvables": list(r.get("introuvables") or []),
            "tableau": r.get("issue"),
        }
        for x in d.get("depots") or []
        if (r := x.get("renovate")) and (r.get("enAttente") or r.get("introuvables"))
    ]
    return {"genere": d.get("genere"), "depots": lignes}


@serveur.tool(title="Librairie", annotations=LECTURE)
async def librairie(
    paquet: Annotated[
        str, Field(description="Nom exact du paquet, par exemple lucide-react ou Node.js.")
    ],
) -> FicheLibrairie:
    """Une librairie du parc : ses versions, quels dépôts sont sur laquelle, la dernière version
    publiée en amont et le retard.
    """
    d = await sources.donnees()
    lib = trouver(paquet, d.get("libs") or [], "paquet", "Librairie")
    return {"genere": d.get("genere"), "librairie": lib}


@serveur.tool(title="Librairies en retard", annotations=LECTURE)
async def librairies_en_retard(
    ecosysteme: Annotated[
        str | None, Field(description="npm, cargo, nuget, node… Toutes si absent.")
    ] = None,
) -> Retards:
    """Les librairies dont au moins un dépôt est en retard sur l'amont, les plus en retard
    d'abord. Pour le détail par dépôt, appeler `librairie`.
    """
    d = await sources.donnees()
    lignes = [
        {
            "paquet": lib.get("paquet", ""),
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


@serveur.tool(title="Chercher dans le parc", annotations=LECTURE)
async def chercher(
    terme: Annotated[
        str, Field(min_length=2, description="Un bout de nom ou de description : cim, sentry…")
    ],
) -> RechercheParc:
    """Les dépôts dont le nom ou la description contient le terme, et les librairies dont le
    nom le contient, sans égard à la casse. Pour retrouver un nom exact avant d'appeler
    `depot` ou `librairie`.
    """
    d = await sources.donnees()
    t = terme.lower()
    trouves = [
        {
            "nom": x.get("nom", ""),
            "famille": x.get("famille"),
            "description": x.get("description"),
            "url": x.get("url"),
        }
        for x in d.get("depots") or []
        if t in str(x.get("nom", "")).lower() or t in str(x.get("description") or "").lower()
    ]
    libs = [
        {
            "paquet": lib.get("paquet", ""),
            "ecosysteme": lib.get("ecosysteme"),
            "depots": lib.get("nbDepots"),
        }
        for lib in d.get("libs") or []
        if t in str(lib.get("paquet", "")).lower()
    ]
    return {"genere": d.get("genere"), "terme": terme, "depots": trouves, "librairies": libs}


@serveur.tool(title="Tendances", annotations=LECTURE)
async def tendances(
    jours: Annotated[int, Field(ge=1, le=400, description="Nombre de points, un par jour.")] = 30,
) -> Tendances:
    """L'historique quotidien du parc, du plus ancien au plus récent : taux de vert, rouges,
    alertes, socle en retard. Un jour sans changement n'a pas de point.
    """
    d = await sources.donnees()
    return {"historique": (d.get("historique") or [])[-jours:]}


@serveur.tool(title="Journal des transitions", annotations=LECTURE)
async def journal(
    n: Annotated[int, Field(ge=1, le=60, description="Nombre de transitions.")] = 20,
) -> Journal:
    """Les dernières transitions vues par le relevé, la plus récente d'abord : CI passée au
    rouge ou au vert, nouvelle version en amont, alertes qui montent ou descendent.
    """
    d = await sources.donnees()
    return {"journal": (d.get("journal") or [])[:n]}
