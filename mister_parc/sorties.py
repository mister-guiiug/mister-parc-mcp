"""La forme de chaque réponse, d'où FastMCP tire l'`outputSchema` de chaque outil.

Sans elles, chaque outil annonçait `{"type": "object"}` : un client ne savait rien
de ce qu'il allait recevoir, et ne pouvait pas valider `structuredContent`. Les
champs repris tels quels du relevé (le détail d'une rubrique, la fiche entière
d'un dépôt) restent des objets libres : leur forme est celle de parc-dashboard,
et la recopier ici la ferait vieillir à deux endroits.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from pydantic import Field

Date = Annotated[str | None, Field(description="Date ISO 8601, en UTC.")]
Genere = Annotated[str | None, Field(description="Date du relevé qui fonde la réponse (ISO 8601).")]
Libre = dict[str, Any]

# ── parc ─────────────────────────────────────────────────────────────────────


class Chiffres(TypedDict, total=False):
    """Les chiffres clés du relevé. Une clé que le relevé n'a pas mesurée est absente."""

    depots: int
    verts: int
    rouges: int
    taux: Annotated[int, Field(description="Part des workflows verts, en pour cent.")]
    prOuvertes: int
    sites: int
    sitesEnLigne: int
    alertes: Annotated[int, Field(description="Alertes de vulnérabilité (Dependabot) ouvertes.")]
    alertesGraves: int
    scanning: Annotated[int, Field(description="Alertes CodeQL (sécurité et qualité) ouvertes.")]
    scanningGraves: int
    depotsSansRuleset: int
    socleEnRetard: Annotated[int, Field(description="Dépôts en retard sur le socle publié.")]
    dormantes: Annotated[int, Field(description="Librairies sans publication depuis un an.")]


class EtatSocle(TypedDict):
    version: Annotated[str | None, Field(description="Dernière version publiée du socle.")]
    amont: str | None
    a_publier: Annotated[
        Libre | None, Field(description="Version coupée sur main et pas encore publiée.")
    ]


class Rubrique(TypedDict):
    cle: Annotated[str, Field(description="Clé de la rubrique : rouges, prs, correctifs…")]
    niveau: Annotated[str | None, Field(description="critique, attention, decision ou entretien.")]
    titre: Annotated[str, Field(description="Le titre que la page affiche.")]
    n: int


class RubriqueDetaillee(Rubrique):
    details: Annotated[list[Libre], Field(description="Les entrées de la rubrique, du relevé.")]


class Etat(TypedDict):
    genere: Genere
    page: str
    chiffres: Chiffres
    socle: EtatSocle
    a_faire: list[Rubrique]
    changements: Annotated[
        list[Libre], Field(description="Ce qui a bougé depuis la photo du jour.")
    ]


class AFaire(TypedDict):
    genere: Genere
    page: str
    items: list[RubriqueDetaillee]


class LigneDepot(TypedDict):
    nom: str
    famille: Annotated[str | None, Field(description="pwa, desktop, socle ou autre.")]
    role: str | None
    description: str | None
    url: str | None
    ci: Annotated[
        dict[str, int] | None, Field(description="Workflows par état : vert, rouge, encours…")
    ]
    alertes: int | None
    codeql: int | None
    prs_ouvertes: int
    site_en_ligne: bool | None
    socle: Annotated[str | None, Field(description="Version du socle que le dépôt verrouille.")]
    ruleset: Annotated[str | None, Field(description="actif, absent, disabled ou faible.")]
    dernier_commit: Date


class Depots(TypedDict):
    genere: Genere
    depots: list[LigneDepot]


class FicheDepot(TypedDict):
    genere: Genere
    depot: Annotated[Libre, Field(description="La fiche du relevé, workflows résumés.")]


class Echecs(TypedDict):
    genere: Genere
    echecs: list[Libre]


class FicheLibrairie(TypedDict):
    genere: Genere
    librairie: Libre


class LigneRetard(TypedDict):
    paquet: str
    ecosysteme: str | None
    plus_recente: str | None
    publiee_le: Date
    depots_en_retard: int | None
    depots: int | None


class Retards(TypedDict):
    genere: Genere
    librairies: list[LigneRetard]


class Tendances(TypedDict):
    historique: Annotated[
        list[Libre], Field(description="Un point par jour, le plus ancien d'abord.")
    ]


class Journal(TypedDict):
    journal: Annotated[list[Libre], Field(description="Les transitions, la plus récente d'abord.")]


class PullRequest(TypedDict):
    depot: str
    num: int
    titre: str
    brouillon: bool
    branche: str | None
    date: Date
    auteur: str | None
    robot: Annotated[bool, Field(description="Ouverte par un robot (Renovate, Dependabot…).")]
    url: str
    ci: Annotated[str | None, Field(description="vert, rouge, encours, ou null sans CI lue.")]


class PullRequests(TypedDict):
    genere: Genere
    prs: list[PullRequest]


class LisibiliteAlertes(TypedDict):
    dependabot: Annotated[bool, Field(description="Le relevé a pu lire les alertes Dependabot.")]
    codeql: Annotated[bool, Field(description="Le relevé a pu lire les alertes CodeQL.")]


class LigneAlertes(TypedDict):
    depot: str
    dependabot: int
    dependabot_graves: int
    dependabot_production: Annotated[
        int, Field(description="Alertes sur une dépendance de production, pas de développement.")
    ]
    dependabot_ids: Annotated[list[str], Field(description="Identifiants d'avis : CVE, GHSA.")]
    codeql: int
    codeql_graves: int
    codeql_regles: Annotated[
        list[str], Field(description="Règles CodeQL en cause, telles que le relevé les liste.")
    ]


class Alertes(TypedDict):
    genere: Genere
    lisibles: LisibiliteAlertes
    depots: list[LigneAlertes]


class Site(TypedDict):
    depot: str
    url: str
    en_ligne: bool | None
    code: Annotated[int | None, Field(description="Code HTTP de la page d'accueil.")]
    ms: Annotated[int | None, Field(description="Temps de réponse mesuré, en millisecondes.")]
    titre: str | None
    production: Annotated[
        str | None, Field(description="aJour, retard ou inconnu : ce qui tourne face à main.")
    ]
    retard: Any
    fugaces: Annotated[list[Any], Field(description="Morceaux hors précache, sans empreinte.")]
    mortes: Annotated[list[Any], Field(description="URL de production qui ne répondent plus.")]


class Sites(TypedDict):
    genere: Genere
    sites: list[Site]


class MiseRenovate(TypedDict):
    titre: str
    majeure: bool


class LigneRenovate(TypedDict):
    depot: str
    en_attente: int
    majeures: int
    mises: list[MiseRenovate]
    introuvables: Annotated[
        list[str], Field(description="Paquets que Renovate ne sait pas résoudre.")
    ]
    tableau: Annotated[str | None, Field(description="Le « Dependency Dashboard » du dépôt.")]


class Renovate(TypedDict):
    genere: Genere
    depots: list[LigneRenovate]


class DepotTrouve(TypedDict):
    nom: str
    famille: str | None
    description: str | None
    url: str | None


class LibrairieTrouvee(TypedDict):
    paquet: str
    ecosysteme: str | None
    depots: int | None


class RechercheParc(TypedDict):
    genere: Genere
    terme: str
    depots: list[DepotTrouve]
    librairies: list[LibrairieTrouvee]


# ── socle ────────────────────────────────────────────────────────────────────


class Offre(TypedDict):
    version: str | None
    modules: Annotated[dict[str, list[str]], Field(description="Les modules, par catégorie.")]
    outils: Annotated[list[str], Field(description="Outils en ligne de commande : pwa-doctor…")]
    workflows: Annotated[list[str], Field(description="Workflows réutilisables : pwa-ci.yml…")]
    pairs: Annotated[
        list[str], Field(description="Dépendances pairs que le socle attend des apps.")
    ]


class Module(TypedDict):
    version: str | None
    nom: str
    categorie: str | None
    emporte: Annotated[list[str], Field(description="Modules qu'il emporte, transitivement.")]
    emporte_par: list[str]
    importe_par: Annotated[list[str], Field(description="Dépôts qui l'importent directement.")]


class Appel(TypedDict):
    depot: str
    avec: Annotated[Libre, Field(description="Les entrées `with:` que le dépôt lui passe.")]


class Workflow(TypedDict):
    version: str | None
    nom: str
    uses: Annotated[str, Field(description="La ligne à écrire dans un workflow appelant.")]
    defauts: Annotated[Libre | None, Field(description="Entrées et leur valeur par défaut.")]
    outils: list[Libre] | None
    appele_par: list[Appel]


class DocumentSocle(TypedDict):
    version: str
    fichier: str
    url: str
    texte: str


class Section(TypedDict):
    fichier: str
    titre: str
    texte: str
    tronque: bool
    url: str


class RechercheSocle(TypedDict):
    version: str
    terme: str
    modules: list[str]
    outils: list[str]
    workflows: list[str]
    sections: list[Section]
    sections_trouvees: int


class AppelWorkflow(TypedDict):
    workflow: str
    avec: Libre


class Usage(TypedDict):
    genere: Genere
    depot: str
    socle: Annotated[str | None, Field(description="Version du socle que le dépôt verrouille.")]
    modules: Annotated[list[str], Field(description="Modules importés directement.")]
    outils: Annotated[list[str], Field(description="Outils appelés par ses scripts.")]
    outils_ci: Annotated[list[str], Field(description="Outils que la CI partagée lance pour lui.")]
    workflows: list[str]
    appels: list[AppelWorkflow]
    mesure_incomplete: Annotated[
        bool, Field(description="Le relevé n'a pas pu lire tout le code du dépôt.")
    ]
