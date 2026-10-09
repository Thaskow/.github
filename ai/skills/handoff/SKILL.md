---
name: handoff
description: Écrit ou relit l'état court d'une tâche en cours (.git/ai-handoff.md) pour reprendre une session interrompue, compactée ou passée à un autre agent (Claude Code ↔ Codex). À utiliser avant un /clear au milieu d'une tâche, en fin de session sur une tâche inachevée, ou au début d'une reprise.
---

# Passage de relais

Fichier : `<git dir>/ai-handoff.md` (`git rev-parse --absolute-git-dir`). Il est dans `.git/`, donc jamais versionné, propre à chaque clone ou worktree, lisible par Claude Code comme par Codex.

## Écrire (fin de session ou avant `/clear`)

Remplace le fichier entier, 40 lignes au plus, sans copier de doc ni de diff :

```markdown
# <objectif en une phrase>
Mis à jour : <date ISO> · branche <nom> · dernier commit <sha court>
## État
<fait / en cours / bloqué, 1 à 3 lignes>
## Décisions
- <décision> — <raison>
## Fichiers touchés
- <chemin> — <quoi>
## Vérifications
- <commande> — <résultat>
## Reste à faire
1. <prochaine action concrète>
## Pièges
- <ce qui a coûté du temps et ne doit pas être redécouvert>
```

Une décision durable (architecture, contrat, convention) va aussi dans la doc du repo : le handoff n'en est pas la source.

## Reprendre

1. Lis le fichier, puis vérifie-le contre la réalité : `git status --short`, `git log --oneline -5`, branche courante. Le code fait foi : signale tout écart au lieu de suivre le fichier.
2. Reprends à « Reste à faire ». Ne relis pas les fichiers déjà listés sauf ceux que tu vas modifier.

## Expiration

Supprime le fichier quand la tâche est fusionnée ou abandonnée. S'il date de plus de 14 jours, considère-le comme un indice, pas comme un état.
