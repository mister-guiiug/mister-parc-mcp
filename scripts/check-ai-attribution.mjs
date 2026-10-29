#!/usr/bin/env node
/**
 * Refuse les signatures d'assistant IA dans les messages de commit et les
 * fichiers versionnés.
 *
 * POURQUOI. L'historique d'un dépôt sert à comprendre POURQUOI un changement a
 * eu lieu ; avec quel outil il a été tapé n'en fait pas partie, pas plus que le
 * nom d'un éditeur de texte. Et ces lignes se propagent : un agent qui lit
 * l'historique pour en imiter le style les reconduit. Ce dépôt n'en porte
 * aucune depuis son premier commit, et ce contrôle est là pour que cela dure.
 *
 * D'OÙ IL VIENT. La règle et ce script viennent de miss-contraction, qui les a
 * écrits le premier (scripts/check-ai-attribution.mjs) ; la règle vaut pour
 * tout le compte mister-guiiug. Cette copie reprend celle du dépôt .github,
 * elle-même celle de mister-guiiug.github.io ; elle n'a aucune dépendance npm :
 * ce dépôt est en Python et n'a pas de package.json.
 *
 * CE QUI EST REFUSÉ, ET CE QUI NE L'EST PAS. `Co-Authored-By` reste autorisé
 * pour une personne : c'est un attribut git légitime, et une vraie séance à
 * deux mérite d'être visible. Seules sont refusées les lignes qui nomment un
 * assistant connu ou son adresse de robot, et les mentions de génération.
 *
 * Usage :
 *   node scripts/check-ai-attribution.mjs --message <fichier>
 *   node scripts/check-ai-attribution.mjs --files <f1> <f2> …
 */

import { readFileSync } from 'node:fs';

/**
 * Chaque motif porte son explication : le message d'erreur doit apprendre
 * quelque chose, pas seulement interdire.
 */
export const PATTERNS = [
  {
    id: 'co-authored-ia',
    // L'ancre tolère les marqueurs de commentaire : `// Co-Authored-By: …` dans
    // un fichier est attrapé comme le trailer d'un message de commit.
    regex:
      /^[\s*/#>-]*co-authored-by:.*(claude|anthropic|copilot|chatgpt|openai|gemini|cursor|codeium|devin|noreply@anthropic\.com)/i,
    quoi: 'une ligne `Co-Authored-By` créditant un assistant IA',
  },
  {
    id: 'generated-with',
    regex:
      /(generated with|généré (avec|par)|created (with|by))\s*\[?\s*(claude|chatgpt|copilot|cursor|gemini)/i,
    quoi: 'une mention « generated with … »',
  },
  {
    id: 'robot',
    regex: /\u{1F916}/u,
    quoi: "l'émoji robot, qui accompagne ces signatures",
  },
  {
    id: 'claude-code-url',
    regex: /claude\.(ai|com)\/code/i,
    quoi: 'un lien promotionnel vers Claude Code',
  },
];

/**
 * Les fichiers qui ont le DROIT de citer ces motifs, parce qu'ils sont la
 * règle elle-même. Une liste de chemins, pas un marqueur en commentaire : rien
 * ne doit pouvoir s'exempter en s'ajoutant une ligne.
 */
export const EXEMPTS = [
  'scripts/check-ai-attribution.mjs',
  'test/check-ai-attribution.test.mjs',
  '.github/workflows/no-ai-attribution.yml',
  'AGENTS.md',
  'CLAUDE.md',
];

/** Le chemin est-il celui d'un fichier qui énonce la règle ? */
export function estExempt(chemin) {
  const normalise = chemin.replace(/\\/g, '/');
  return EXEMPTS.some(e => normalise === e || normalise.endsWith(`/${e}`));
}

/** Les motifs trouvés dans un texte, avec leur numéro de ligne. */
export function findAttribution(text) {
  const lignes = text.split(/\r?\n/);
  const trouves = [];
  for (const motif of PATTERNS) {
    for (const [i, ligne] of lignes.entries()) {
      if (motif.regex.test(ligne)) {
        trouves.push({ id: motif.id, quoi: motif.quoi, ligne: i + 1, texte: ligne.trim() });
        break; // une occurrence par motif suffit à refuser
      }
    }
  }
  return trouves;
}

const RAPPEL = `
  L'historique de ce dépôt explique POURQUOI un changement a eu lieu. Avec
  quel outil il a été écrit n'en fait pas partie, pas plus que le nom de
  l'éditeur de texte. Retirez la ligne et recommencez.

  \`Co-Authored-By\` reste bienvenu pour créditer une personne.`;

function main(argv) {
  const mode = argv[2];
  const cibles = argv.slice(3);
  let faute = false;

  if (mode === '--message') {
    const trouves = findAttribution(readFileSync(cibles[0], 'utf8'));
    if (trouves.length > 0) {
      faute = true;
      console.error('\n✗ Message de commit refusé.\n');
      for (const t of trouves) {
        console.error(`  ligne ${t.ligne} : ${t.quoi}`);
        console.error(`    ${t.texte}`);
      }
      console.error(RAPPEL);
    }
  } else if (mode === '--files') {
    for (const fichier of cibles) {
      if (estExempt(fichier)) continue;
      let contenu;
      try {
        contenu = readFileSync(fichier, 'utf8');
      } catch {
        continue; // fichier supprimé : rien à lire
      }
      const trouves = findAttribution(contenu);
      if (trouves.length > 0) {
        faute = true;
        console.error(`\n✗ ${fichier}`);
        for (const t of trouves) {
          console.error(`  ligne ${t.ligne} : ${t.quoi}`);
          console.error(`    ${t.texte}`);
        }
      }
    }
    if (faute) console.error(RAPPEL);
  } else {
    console.error('Usage : check-ai-attribution.mjs --message <fichier> | --files <fichiers…>');
    return 2;
  }
  return faute ? 1 : 0;
}

// N'exécute rien à l'import : le test importe `findAttribution`.
if (process.argv[1] && process.argv[1].replace(/\\/g, '/').endsWith('scripts/check-ai-attribution.mjs')) {
  process.exit(main(process.argv));
}
