"""Le socle dev-pwa-config, pour un agent qui s'apprête à écrire.

Le socle promeut, il n'invente pas : avant d'écrire un hook, un composant ou un
workflow dans une application, il faut savoir s'il existe déjà. `use-prefetch`
a été réécrit dix fois dans le parc faute de cette question. Ces outils y
répondent depuis ce que le tableau de bord mesure (`socleOffre`, l'usage par
dépôt) et depuis la documentation de la version publiée.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from . import sources
from .parc import LECTURE, trouver

serveur = FastMCP("socle")

Document = Literal["README.md", "CONFIG.md", "CONTRIBUTING.md", "STRATEGIE.md"]

# Ce que `chercher` parcourt. STRATEGIE.md raconte le pourquoi du découpage, pas
# ce que le socle offre : il y ajouterait surtout du bruit.
DOCUMENTS_CHERCHES: tuple[Document, ...] = ("README.md", "CONFIG.md", "CONTRIBUTING.md")
MAX_SECTIONS = 8
MAX_CARACTERES_SECTION = 4000

_TITRE = re.compile(r"#{1,6} ")


def sections(texte: str) -> list[tuple[str, str]]:
    """Le texte Markdown découpé à chaque titre, hors blocs de code."""
    out: list[tuple[str, str]] = []
    titre, lignes, dans_code = "", [], False
    for ligne in texte.splitlines():
        if ligne.lstrip().startswith("```"):
            dans_code = not dans_code
        if not dans_code and _TITRE.match(ligne):
            out.append((titre, "\n".join(lignes).strip()))
            titre, lignes = ligne.lstrip("#").strip(), []
        else:
            lignes.append(ligne)
    out.append((titre, "\n".join(lignes).strip()))
    return [(t, c) for t, c in out if t or c]


async def _offre() -> tuple[dict[str, Any], dict[str, Any]]:
    d = await sources.donnees()
    return d, d.get("socleOffre") or {}


async def _document(version: str, fichier: str) -> tuple[str, str]:
    url = sources.url_doc_socle(version, fichier)
    return url, await sources.texte_publie(url)


@serveur.tool(annotations=LECTURE)
async def offre() -> dict[str, Any]:
    """Ce que la dernière version publiée du socle offre : ses modules rangés par catégorie
    (composants, crochets React, configs Vite, outillage…), ses outils en ligne de commande
    et ses workflows réutilisables.
    """
    _, o = await _offre()
    par_categorie: dict[str, list[str]] = {}
    categories = o.get("categories") or {}
    for m in o.get("modules") or []:
        par_categorie.setdefault(categories.get(m, "autre"), []).append(m)
    return {
        "version": o.get("version"),
        "modules": par_categorie,
        "outils": o.get("outils") or [],
        "workflows": o.get("workflows") or [],
    }


@serveur.tool(annotations=LECTURE)
async def module(
    nom: Annotated[
        str, Field(description="Nom du module, tel que l'importe une app : react/i18n, analytics…")
    ],
) -> dict[str, Any]:
    """Un module du socle : sa catégorie, les modules qu'il emporte avec lui, ceux qui
    l'emportent, et les dépôts qui l'importent directement.
    """
    d, o = await _offre()
    modules = [{"nom": m} for m in o.get("modules") or []]
    nom = trouver(nom, modules, "nom", "Module du socle")["nom"]
    graphe = (o.get("graphe") or {}).get("modules") or {}
    return {
        "version": o.get("version"),
        "nom": nom,
        "categorie": (o.get("categories") or {}).get(nom),
        "emporte": graphe.get(nom, []),
        "emporte_par": sorted(m for m, deps in graphe.items() if nom in deps),
        "importe_par": sorted(
            x["nom"]
            for x in d.get("depots") or []
            if nom in ((x.get("usageSocle") or {}).get("modules") or [])
        ),
    }


@serveur.tool(annotations=LECTURE)
async def workflow(
    nom: Annotated[str, Field(description="Fichier du workflow réutilisable : pwa-ci.yml…")],
) -> dict[str, Any]:
    """Un workflow réutilisable du socle : la ligne `uses:` à écrire (étiquette majeure
    roulante), ses entrées par défaut quand le relevé les connaît, les outils qu'il lance,
    et les dépôts qui l'appellent, avec les entrées qu'ils lui passent.
    """
    d, o = await _offre()
    fichiers = [{"nom": w} for w in o.get("workflows") or []]
    nom = trouver(nom, fichiers, "nom", "Workflow du socle")["nom"]
    majeure = str(o.get("version") or "").split(".")[0]
    ci = (o.get("ci") or {}).get(nom) or {}
    appels = [
        {"depot": x["nom"], "avec": a.get("avec") or {}}
        for x in d.get("depots") or []
        for a in (x.get("usageSocle") or {}).get("appels") or []
        if a.get("workflow") == nom
    ]
    return {
        "version": o.get("version"),
        "nom": nom,
        "uses": f"uses: {sources.COMPTE}/dev-pwa-config/.github/workflows/{nom}@v{majeure}",
        "defauts": ci.get("defauts"),
        "outils": ci.get("outils"),
        "appele_par": sorted(appels, key=lambda a: a["depot"]),
    }


@serveur.tool(annotations=LECTURE)
async def doc(
    fichier: Annotated[Document, Field(description="Le document du socle à lire.")],
) -> dict[str, Any]:
    """Un document du socle, en entier, à la version publiée : README.md (l'API et la stack
    cible), CONFIG.md (secrets et variables), CONTRIBUTING.md (ce qui entre au socle),
    STRATEGIE.md (le découpage en trois couches). README.md dépasse 100 Ko : pour une question
    précise, `chercher` coûte moins.
    """
    _, o = await _offre()
    version = str(o.get("version"))
    url, texte = await _document(version, fichier)
    return {"version": version, "fichier": fichier, "url": url, "texte": texte}


@serveur.tool(annotations=LECTURE)
async def chercher(
    terme: Annotated[
        str,
        Field(min_length=2, description="Ce que l'on cherche : prefetch, CSP, Supabase, QR…"),
    ],
) -> dict[str, Any]:
    """Le socle a-t-il déjà ceci ? Cherche le terme, sans égard à la casse, dans les noms des
    modules, outils et workflows, puis dans les sections de README.md, CONFIG.md et
    CONTRIBUTING.md. À appeler AVANT d'écrire dans une app ce qui pourrait y être.
    """
    _, o = await _offre()
    version = str(o.get("version"))
    t = terme.lower()
    trouve = {
        "modules": [m for m in o.get("modules") or [] if t in m.lower()],
        "outils": [x for x in o.get("outils") or [] if t in x.lower()],
        "workflows": [w for w in o.get("workflows") or [] if t in w.lower()],
    }
    extraits: list[dict[str, Any]] = []
    total = 0
    for fichier in DOCUMENTS_CHERCHES:
        url, texte = await _document(version, fichier)
        for titre, corps in sections(texte):
            if t not in titre.lower() and t not in corps.lower():
                continue
            total += 1
            if len(extraits) < MAX_SECTIONS:
                extraits.append(
                    {
                        "fichier": fichier,
                        "titre": titre,
                        "texte": corps[:MAX_CARACTERES_SECTION],
                        "tronque": len(corps) > MAX_CARACTERES_SECTION,
                        "url": url,
                    }
                )
    return {
        "version": version,
        "terme": terme,
        **trouve,
        "sections": extraits,
        "sections_trouvees": total,
    }
