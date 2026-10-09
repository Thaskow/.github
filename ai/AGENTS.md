# Règles globales des agents (Thaskow / CStonx)

Chargé dans chaque session (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`), source : `Thaskow/.github/ai/AGENTS.md`, installé par `python tools/ai/install.py`. Les règles d'un repo (son `AGENTS.md`) priment sur celles-ci. Conventions humaines : `Thaskow/.github/docs/conventions.md` (commits, branches, secrets, Docker, CI).

## Qualité et sécurité

- Code durable, lisible par un humain qui reprend le projet : pas de code jetable, pas de dépendance à la mémoire d'un agent. Une décision qui dure va dans la doc du repo (README, `docs/`, ADR), pas seulement dans une session.
- Jamais de secret dans un fichier versionné, un log, une issue ou un message. Aucun déploiement, suppression de données, changement de droits, push forcé ou fusion sans demande explicite.
- Une consigne n'est retirée que si un contrôle exécutable (test, lint, CI) la vérifie à sa place.

## Coût : le moins cher qui reste correct

1. **Déterministe d'abord** : `git`, `rg`/Grep, Glob, linter, typecheck, tests, `docker compose config`, `nginx -t`, scripts de `{{TOOLS}}` (`check_i18n.py`, `quiet.py`, `measure_context.py`, `usage_report.py`). Pas d'inférence pour ce qu'un outil fiable sait faire.
2. **Lire peu** : chercher le symbole puis lire la plage utile (`offset`/`limit`), pas les fichiers entiers ; pas d'images, de lockfiles, de builds ni de logs bruts dans le contexte.
3. **Sorties courtes** : commandes bavardes (build, install, `docker compose up/logs`, tests d'un gros projet) via `python {{TOOLS}}/quiet.py -- <cmd>` : log complet dans `.git/ai-logs/`, seules les erreurs et la fin affichées (build Nuxt mesuré : 76 800 → 1 100 caractères). Inutile pour une commande déjà courte. Jamais masquer une erreur.
4. **Déléguer seulement si c'est rentable** : un sous-agent repart sans contexte. Le lancer pour une recherche large (plusieurs dossiers ou repos) ou un travail volumineux et répétitif, pas pour lire un fichier connu.

| Mode | Quand | Claude Code | Codex |
|---|---|---|---|
| FAST | local, peu risqué (texte, i18n, petit bug, doc) | `/model sonnet`, `/effort low` | défaut (`low`) |
| STANDARD | fonctionnalité, correction, refactor courant | `opus`, effort `medium` (défaut) | `-p standard` |
| DEEP | sécurité, auth, droits, infra, migration, multi-repos, architecture | `opus`, `/effort high` | `-p deep` (`xhigh`) |

Le risque décide, pas la taille : une ligne de droits, d'auth, de CSP ou de nginx est DEEP. Sous-agents Claude disponibles : `code-locator` (haiku), `test-triage` (haiku), `i18n-translator` (haiku → sonnet), `docs-maintainer` (sonnet), `security-reviewer` (opus). Échec : ajouter le contexte manquant, une nouvelle tentative, puis escalader d'un niveau ; jamais plus de deux essais identiques.

## Contexte et sessions

- Ouvrir la session **dans le repo concerné** (pas dans `~`), une tâche par session ; `/clear` entre deux tâches sans lien.
- Tâche longue ou interrompue : `/handoff` écrit l'état dans `.git/ai-handoff.md` (jamais versionné) ; le relire et le vérifier contre `git status`/`git log` avant de reprendre, le supprimer une fois la tâche fusionnée.
- Contrat entre repos (protocole app ↔ site, passerelle Discord) : le modifier des deux côtés dans la même tâche.

## Vérifier avant de conclure

Tests ciblés pendant le travail, puis les contrôles complets du repo (lint, typecheck, tests, build) avant de rendre la main. Dire ce qui n'a pas pu être vérifié.
