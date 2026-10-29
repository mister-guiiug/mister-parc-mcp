// Engendre tests/donnees.json et tests/a-faire.json depuis un relevé réel,
// réduit à quatre dépôts (un par famille) et à huit modules du socle.
//
// En JavaScript, et c'est voulu : `a-faire.json` doit sortir de `aFairePublie`,
// la fonction même du tableau de bord, pas d'une imitation en Python.
//
// Usage, depuis la racine du dépôt, une copie de parc-dashboard à côté :
//   curl -o donnees.json https://mister-guiiug.github.io/parc-dashboard/donnees.json
//   node tests/engendrer-donnees.mjs donnees.json tests \
//     ../parc-dashboard/scripts/pilotage.mjs ../parc-dashboard/scripts/libelles.mjs
// Les tests nomment des dépôts, des librairies et des modules du relevé : après
// une régénération, relancer `uv run pytest` et relire ce qui a bougé.
import { readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const [source, sortie, pilotage, libelles] = process.argv.slice(2)
const { aFairePublie } = await import(pathToFileURL(pilotage))
const { traducteur } = await import(pathToFileURL(libelles))
const D = JSON.parse(readFileSync(source, 'utf8'))

const GARDES = ['mister-cim10', 'mister-claude-skills', 'mister-commitia', 'pwa-starter-kit']
const MODULES = ['analytics', 'components.css', 'eslint-base', 'eslint-react', 'react/app-header', 'react/i18n', 'tsconfig-app', 'tsconfig-app-react']

const depots = D.depots
  .filter((d) => GARDES.includes(d.nom))
  .map((d) => ({
    ...d,
    workflows: (d.workflows || []).map((w) => ({ ...w, derniers: (w.derniers || []).slice(0, 1) })),
    usageSocle: d.usageSocle && { ...d.usageSocle, modules: (d.usageSocle.modules || []).filter((m) => MODULES.includes(m)), fichiers: [] },
  }))
const gardeLib = (l) => l.enRetard > 0 || l.paquet === 'Node.js' || l.paquet === D.socle
const libs = D.libs.filter(gardeLib).map((l) => ({
  ...l,
  versions: l.versions.map((v) => ({ ...v, depots: v.depots.filter((x) => GARDES.includes(x.depot)).slice(0, 2) })),
}))
const o = D.socleOffre
const socleOffre = {
  ...o,
  modules: o.modules.filter((m) => MODULES.includes(m)),
  categories: Object.fromEntries(Object.entries(o.categories).filter(([m]) => MODULES.includes(m))),
  graphe: {
    ...o.graphe,
    modules: Object.fromEntries(
      Object.entries(o.graphe.modules)
        .filter(([m]) => MODULES.includes(m))
        .map(([m, deps]) => [m, deps.filter((x) => MODULES.includes(x))]),
    ),
  },
}
// Le relevé du 29/10 n'avait aucun échec : un échec inventé, à la forme du relevé.
const echecs = [
  {
    depot: 'mister-cim10',
    famille: 'pwa',
    workflow: 'CI',
    date: '2026-10-29T17:00:00Z',
    jours: 0,
    conclusion: 'failure',
    branche: 'main',
    url: 'https://github.com/mister-guiiug/mister-cim10/actions/runs/1',
    jobs: ['quality / tests'],
    etape: 'Run npm test',
    demarrage: false,
  },
]

const reduit = {
  ...D,
  depots,
  libs,
  echecs,
  socleOffre,
  activite: D.activite.filter((a) => GARDES.includes(a.depot)),
  historique: D.historique.slice(-5),
  journal: D.journal.slice(0, 5),
}
writeFileSync(join(sortie, 'donnees.json'), JSON.stringify(reduit, null, 1) + '\n')
writeFileSync(join(sortie, 'a-faire.json'), JSON.stringify(aFairePublie(reduit, traducteur('fr')), null, 1) + '\n')
console.log(`donnees.json : ${depots.length} dépôts, ${libs.length} librairies, ${socleOffre.modules.length} modules`)
console.log(`a-faire.json : ${aFairePublie(reduit, traducteur('fr')).items.map((i) => i.cle).join(', ')}`)
