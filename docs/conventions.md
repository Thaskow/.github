# Conventions

Règles communes à tous les repos actifs de `Thaskow` (et de `CStonx` quand elles s'appliquent). Elles valent pour les nouveaux commits : l'historique existant n'est jamais réécrit.

## Repos

- Slug en **kebab-case minuscule** : `nginx-reverse`, `uptime-kuma`, `observability`. Une marque garde son nom affiché dans le README (`CStonx`, `MemoVision`).
- Branche par défaut : **`main`**.
- Chaque repo actif a un README avec les sections utiles parmi : Rôle, Architecture, Prérequis, Installation, Déploiement, Configuration, Variables, Secrets, Persistance, Sauvegarde / restauration, Mise à jour, Dépendances, Sécurité, Développement, Rollback, Limitations. Une section sans objet n'est pas ajoutée.
- `.github/CODEOWNERS` décrit les zones de responsabilité, même à une seule personne.
- Repo dormant : archivé (lecture seule, réversible), jamais supprimé sans décision explicite.

## Branches et PR

```text
feat/…  fix/…  chore/…  docs/…  ci/…  refactor/…
```

- `main` est protégée par un ruleset sur les repos qui déploient : PR obligatoire (sans review externe imposée), check `validate` vert, conversations résolues, ni force push ni suppression. L'administrateur peut fusionner une PR sans attendre les checks (Release PR de Release Please, urgence).
- Fusion **squash** : le titre de la PR devient le commit sur `main`, il suit donc Conventional Commits.
- Branche supprimée après fusion.

## Commits : Conventional Commits

```text
feat: …       nouvelle fonctionnalité            → version mineure
fix: …        correction                         → version patch
docs: … ci: … chore: … refactor: … perf: … test: … build: …
feat!: …      ou pied de page BREAKING CHANGE:  → version majeure
```

Un scope est bienvenu quand il aide : `fix(backup): …`, `ci(deploy): …`. Messages en français, à l'impératif ou au constat, sans point final.

## Labels

`bug`, `feature`, `security`, `infra`, `dependencies`, `breaking-change`, `documentation`, `ci`, `maintenance` (+ `autorelease: *` créés par Release Please). Synchronisés avec `python scripts/sync-labels.py <repo>…` depuis [`labels.json`](../labels.json).

## Secrets et variables

Ce qui est sensible va dans les **secrets**, le reste dans les **variables**. Tout ce qui sert à la production est rangé dans l'environnement GitHub **`production`** (limité à la branche `main`), pas au niveau du repo.

| Nom | Type | Rôle |
| --- | --- | --- |
| `SERVER_HOST` | variable | adresse du VPS |
| `SERVER_USER` | variable | utilisateur SSH |
| `DEPLOY_PATH` | variable | dossier du service sur le serveur |
| `SSH_PRIVATE_KEY` | secret | clé de déploiement (tournée à chaque `python vps.py deploy`) |
| `SSH_KNOWN_HOSTS` | secret | empreintes du serveur ; jamais de `ssh-keyscan` en CI |
| `NTFY_URL` | secret | topic ntfy des notifications (facultatif) |
| `<SERVICE>_…` | secret | secrets propres au service, rendus dans le `.env` du serveur |

`Thaskow/vps` pose tous ces noms : un secret n'est jamais saisi à la main sauf s'il vient d'un tiers (token Discord, identifiants Reddit…). Les valeurs ne sont jamais affichées, ni dans les logs ni dans les issues.

## GitHub Actions

- Actions tierces épinglées par **SHA** avec la version en commentaire (`uses: actions/checkout@<sha> # v7.0.1`). Dependabot les met à jour.
- `permissions: contents: read` en tête de chaque workflow ; tout droit supplémentaire est déclaré sur le job qui en a besoin.
- Un déploiement ne tourne jamais en parallèle d'un autre sur le même service : `concurrency: deploy-<repo>`, sans annulation.
- Logique partagée dans ce repo :
  - [`deploy-compose.yml`](../.github/workflows/deploy-compose.yml) : déploiement `git` + `docker compose` sur le VPS, health check, retour automatique à la version précédente, notification ntfy ;
  - [`validate.yml`](../.github/workflows/validate.yml) : pre-commit, `docker compose config`, images figées, checks propres au repo ;
  - [`dependabot-auto-merge.yml`](../.github/workflows/dependabot-auto-merge.yml) : fusion automatique des patchs (jamais les images Docker) ;
  - actions composites [`ssh-setup`](../actions/ssh-setup/action.yml) et [`ntfy`](../actions/ntfy/action.yml) pour les workflows sur mesure.
- Les repos appellent ces workflows par SHA (`Thaskow/.github/.github/workflows/deploy-compose.yml@<sha> # v1.0.0`) ; une version de ce repo n'est jamais modifiée après publication.

## Contrat de déploiement (`deploy-compose.yml`)

1. Le serveur a un clone du repo dans `DEPLOY_PATH` (créé par `python vps.py deploy`, avec une deploy key en lecture seule).
2. `git fetch` puis `git reset --hard <commit>` et `git clean -fd` : **les fichiers ignorés sont conservés** (`.env`, `data/`, `backups/`…). Toute donnée écrite dans le dossier du repo doit donc être dans `.gitignore`.
3. Commandes `pre-deploy` du repo (génération, `nginx -t`…), `docker compose config`, `pull`, `up -d --wait`.
4. Tous les conteneurs doivent être `running` et `healthy` (si healthcheck), puis `health-url` doit répondre depuis Internet.
5. Sinon : retour automatique au commit précédent, workflow en échec, notification.

Rollback manuel : **Actions → Deploy → Run workflow**, `ref` = tag (`v1.4.3`) ou commit.

## Versions

| Type de repo | Release Please | Déploiement |
| --- | --- | --- |
| Application ou outil (`reddit`, `cstonx/*`, ce repo) | oui | `main`, version visible dans le résumé du déploiement |
| Config déclarative d'un service tiers (`ntfy`, `uptime-kuma`, `beszel`, `observability`, `nginx-reverse`, `authelia`, `homarr`) | non : la version est celle de l'image | `main` |
| Provisioning (`vps`) | non | manuel (`python vps.py deploy`) |

- SemVer, tags `vX.Y.Z` créés par la Release PR, **jamais déplacés ni recréés** : une correction = une nouvelle version.
- Images construites et publiées : tags `X.Y.Z`, `X.Y`, `X`, et `latest` seulement si sa sémantique est documentée. La production référence toujours une version complète.
- Images tierces : version figée (`postgres:18.6-alpine`), jamais `latest`.

## Dépendances

Dependabot partout (déjà en place sur CStonx, natif, sans application à installer) : GitHub Actions, images Docker, pip, npm, hooks pre-commit. Hebdomadaire, groupé, label `dependencies`.

- Patchs d'actions, pip, npm, pre-commit : fusion automatique quand la CI est verte.
- Mineures et majeures : review manuelle.
- **Images Docker : toujours en review manuelle**, notes de version et migrations lues avant de fusionner (Postgres, GlitchTip, nginx en priorité).

## Docker

- Image en version figée, `restart: unless-stopped`, rotation des logs (`json-file`, 10 Mo × 3), `security_opt: [no-new-privileges:true]`, `cap_drop: [ALL]` quand l'image le supporte, `mem_limit` et `pids_limit`.
- Un `healthcheck` par service quand l'image ne le fournit pas : c'est lui qui valide le déploiement.
- Ports publiés sur **`127.0.0.1` uniquement** ; nginx-reverse est le seul point d'entrée public (Docker contourne `ufw`).
- `name:` du projet compose figé dans le fichier : le nom des volumes ne dépend pas du dossier.
- Données persistantes : volume nommé, ou dossier ignoré par git dans le repo, déclaré dans `data` de `vps.json` pour la sauvegarde.

## Validation locale

```sh
pip install pre-commit
pre-commit install
```

Les mêmes hooks tournent en CI (`validate`) : espaces, fins de fichier, YAML, JSON, Ruff, ShellCheck, Gitleaks.
