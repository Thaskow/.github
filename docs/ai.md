# Agents de code (Claude Code, Codex)

Configuration commune des agents de code pour les repos Thaskow et CStonx : instructions globales, sous-agents, skills, profils et outils déterministes. Objectif : le coût le plus bas par tâche **correctement terminée**, sans perte de qualité ni de sécurité.

## Contenu

| Source | Installé vers | Rôle |
| --- | --- | --- |
| [`ai/AGENTS.md`](../ai/AGENTS.md) | `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` | Règles globales : sécurité, coût, modes FAST/STANDARD/DEEP, contexte, vérification |
| `~/.ai-local.md` (hors repo, facultatif) | ajouté à la fin des deux fichiers ci-dessus | Spécificités de la machine (chemins, version de Node, outils absents) |
| [`ai/claude/agents/`](../ai/claude/agents/) | `~/.claude/agents/` | Sous-agents (tableau plus bas) |
| [`ai/skills/handoff/`](../ai/skills/handoff/SKILL.md) | `~/.claude/skills/`, `~/.codex/skills/` | `/handoff` : passation de session dans `<git dir>/ai-handoff.md` |
| [`ai/codex/*.config.toml`](../ai/codex/) | `~/.codex/` | Profils `codex -p standard` (effort `medium`) et `codex -p deep` (`xhigh`) |
| [`ai/claude/settings.json`](../ai/claude/settings.json) | fusionné dans `~/.claude/settings.json` | Compaction automatique à 250 000 tokens |
| [`tools/ai/`](../tools/ai/) | utilisé sur place | Outils déterministes (tableau plus bas) |

Dans les repos : `AGENTS.md` à la racine (lu par Codex et Copilot), `CLAUDE.md` réduit à `@AGENTS.md` (import pour Claude Code). Une seule source, pas de copie.

## Installer, mettre à jour, revenir en arrière

```sh
python tools/ai/install.py              # simulation : liste ce qui changerait
python tools/ai/install.py --apply      # écrit (copie .bak-<date> de chaque fichier remplacé)
python tools/ai/install.py --uninstall --apply   # restaure les dernières copies, retire les fichiers créés
```

Idempotent : un second `--apply` n'écrit rien. On modifie toujours la source dans ce repo, puis on relance `--apply` ; les fichiers installés portent un en-tête qui le rappelle. `{{TOOLS}}` dans les sources est remplacé par le chemin absolu de `tools/ai`.

Retour arrière côté repos : chaque changement d'instructions est un commit `docs:` isolé, annulable par `git revert`.

## Modes

Le risque choisit le mode, pas la taille du diff.

| Mode | Quand | Claude Code | Codex |
| --- | --- | --- | --- |
| FAST | lecture, question, petite modification sans risque | `/model sonnet` + `/effort low` | défaut (`low`) |
| STANDARD | fonctionnalité, correction, refactor courant | `opus`, effort `medium` (défaut) | `-p standard` |
| DEEP | sécurité, auth, droits, infra, migration, multi-repos, architecture | `opus` + `/effort high`, puis `security-reviewer` | `-p deep` |

Escalade : au plus deux essais identiques, puis on change d'approche ou de mode.

## Sous-agents

Chacun n'existe que parce qu'il coûte moins cher que la même tâche dans la session principale (contexte frais, modèle moins cher, sortie courte).

| Agent | Modèle | Usage | Pourquoi c'est rentable |
| --- | --- | --- | --- |
| `code-locator` | Haiku, effort bas, sans `CLAUDE.md` | trouver fichiers, symboles, appelants, impact d'un changement | les lectures restent hors du contexte principal, renvoie ≤ 25 lignes |
| `test-triage` | Haiku | lancer tests, lint, build et ne renvoyer que les échecs | une sortie de build passe de dizaines de milliers de caractères à quelques lignes |
| `i18n-translator` | Haiku | traduire les clés manquantes FR → EN | reçoit seulement les clés (`check_i18n.py --missing-only`), jamais les catalogues |
| `docs-maintainer` | Sonnet | mettre la doc à jour après un changement | tâche de rédaction, pas de raisonnement profond |
| `security-reviewer` | Opus, effort haut, lecture seule | revue avant de conclure une tâche DEEP | seul agent cher : un défaut de sécurité coûte plus que la revue |

Pas d'agent « inspecteur de dépendances » (couvert par `code-locator` et `npm ls`/`pip`), ni « résumeur de session » (compaction native + `/handoff`).

## Outils déterministes (`tools/ai/`)

| Outil | Rôle |
| --- | --- |
| `quiet.py <commande>` | lance une commande verbeuse, garde le log complet dans `.git/ai-logs/`, n'affiche que le code de sortie, les erreurs avec leur contexte et une fin dédoublonnée. Seulement pour les commandes verbeuses : sur une commande déjà courte, il ajoute ~100 caractères |
| `check_i18n.py <dossier>` | compare les catalogues à la référence `fr` (clés manquantes, en trop, paramètres, valeurs vides) ; `--missing-only en` sort le JSON minimal à traduire. Code 1 au moindre écart |
| `measure_context.py <repo>…` | fichiers d'instructions chargés au démarrage par Claude Code et Codex (imports `@` suivis), taille estimée en tokens |
| `usage_report.py` | coût réel des sessions locales (`~/.claude/projects`, sessions Codex) : requêtes par modèle, outils, taille du contexte, sessions les plus chères |
| `simulate_compaction.py` | rejoue la croissance du contexte des sessions mesurées avec un plafond de compaction |
| `install.py` | voir plus haut |

## Mesures (octobre 2026)

**Mesuré** = lu dans les journaux de session ou sur disque. **Simulé** = rejoué par `simulate_compaction.py` à partir de ces journaux. **Estimé** = tokens calculés à 3,6 caractères par token. Coût = équivalent API au prix public, quelle que soit l'offre utilisée.

Point de départ (mesuré, 13 sessions Claude Code, ~1 550 requêtes) :

- les **lectures de cache** font 63 % du coût, les écritures de cache 20 %, la sortie 18 % ; les entrées non cachées sont négligeables ;
- les 2 sessions les plus longues font 69 % du coût : jusqu'à 495 requêtes dans une même session, avec un contexte moyen de ~415 000 tokens par requête (fenêtre de 1 M, compaction vers ~967 000) ;
- contexte au premier message : médiane ~38 000 tokens ; les fichiers d'instructions n'en sont qu'une petite part ;
- 99 % des requêtes sur Opus, 6 requêtes de sous-agents sur ~1 550.

Le levier principal est donc la **longueur des sessions**, pas la taille des fichiers d'instructions.

| Optimisation | Effet | Nature |
| --- | --- | --- |
| Compaction à 250 000 tokens | −32 % (plafond 300 k) à −37 % (200 k) sur les sessions mesurées | simulé |
| `AGENTS.md` du site : tableau d'architecture déplacé dans `docs/architecture.md` | 52,7 Ko → 14,2 Ko (−73 %) ; repasse sous la limite de 32 Kio de Codex, qui tronquait le fichier et **perdait toutes les règles** | mesuré (octets) |
| `quiet.py` sur un build Nuxt | 76 800 → 1 100 caractères renvoyés au modèle | mesuré |
| Session ouverte dans le repo plutôt que dans `~`, une tâche par session, `/clear` | non chiffré séparément ; c'est ce qui a produit les sessions de 495 requêtes | règle |
| Opus → Sonnet comme modèle par défaut | −19 % seulement (les lectures de cache coûtent pareil) pour une qualité moindre | estimé, **rejeté** |

À remesurer après deux semaines d'usage : `python tools/ai/usage_report.py` et comparer coût par session, requêtes par session et part des lectures de cache.

## Décisions écartées

- **Index vectoriel / serveur MCP de recherche** : `rg` et les sous-agents suffisent à cette taille de code ; un index de plus serait à maintenir et désynchronisable.
- **`AGENTS.md` par module** : Codex ne lit que la chaîne racine → dossier courant ; un fichier de module ne serait pas vu depuis la racine. On préfère une carte des domaines dans l'`AGENTS.md` racine et une doc par domaine.
- **Compaction Codex** (`model_auto_compact_token_limit`) laissée par défaut : pas assez de sessions Codex mesurées pour la régler.
- **`service_tier = "fast"` de Codex** laissé tel quel : choix de latence, à revoir si le coût Codex devient significatif.
- **Supprimer des règles pour gagner de la place** : une règle ne part que si un contrôle exécutable (test, lint, CI) la couvre.

## Maintenance

- `AGENTS.md` d'un repo : viser < 16 Kio, jamais au-delà de 32 Kio (vérifier avec `measure_context.py`). Le détail va dans `docs/`, l'`AGENTS.md` garde les règles, les invariants et une carte qui pointe vers les docs.
- Un changement de contrat entre repos (protocole app ↔ site, passerelle Discord) se reporte des deux côtés dans le même lot.
- Nouveau sous-agent ou skill : seulement si sa tâche revient souvent et qu'il renvoie nettement moins qu'il ne lit. Sinon, une ligne dans `ai/AGENTS.md` suffit.
- Les noms de modèles et prix de `usage_report.py` (`PRICES`) se mettent à jour à chaque nouvelle génération de modèles.

## Nouveau repo

1. `AGENTS.md` : contexte en 3 lignes, stack, carte des domaines, règles, commandes, conventions.
2. `CLAUDE.md` contenant seulement `@AGENTS.md`.
3. Commandes de vérification exécutables (lint, tests, typecheck) citées dans `AGENTS.md`, pour que l'agent vérifie sans deviner.
4. Pas de secret, d'adresse ni de chemin de serveur dans un repo public.
