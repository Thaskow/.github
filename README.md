# .github

Conventions, workflows réutilisables et modèles communs aux repos de [Thaskow](https://github.com/Thaskow).

## Rôle

- **Conventions** d'ingénierie : [docs/conventions.md](docs/conventions.md) (nommage, branches, commits, secrets, déploiement, versions, Docker).
- **Modèles par défaut** pour les repos qui n'ont pas les leurs : [PR](PULL_REQUEST_TEMPLATE.md), [issues](ISSUE_TEMPLATE/) (bug, fonctionnalité, changement d'infra), [CONTRIBUTING](CONTRIBUTING.md), [SECURITY](SECURITY.md).
- **Workflows réutilisables** et actions composites, appelés par les repos de services.
- **Labels** communs : [labels.json](labels.json).

L'architecture du serveur et les ADR sont dans le repo privé `Thaskow/vps` (`docs/`), source de vérité de l'infrastructure. Ce repo est public pour que les modèles s'appliquent et que les repos de l'organisation `CStonx` puissent l'appeler : il ne contient ni secret, ni adresse, ni chemin du serveur.

## Workflows réutilisables

### `deploy-compose.yml`

Déploie un repo `docker compose` déjà cloné sur le VPS, depuis l'environnement `production` du repo appelant.

```yaml
name: Deploy

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      ref:
        description: Commit ou tag à déployer (rollback)
        default: ''

permissions:
  contents: read

jobs:
  deploy:
    uses: Thaskow/.github/.github/workflows/deploy-compose.yml@<sha> # v1.0.0
    secrets: inherit
    with:
      ref: ${{ inputs.ref }}
      health-url: https://service.thaskow.fr/health
```

| Entrée | Défaut | Rôle |
| --- | --- | --- |
| `ref` | commit déclencheur | commit, tag ou branche à déployer |
| `pre-deploy` | — | commandes serveur avant `up` (ex. `python3 nginx-conf.py` puis `nginx -t`) |
| `post-deploy` | — | commandes serveur après un déploiement réussi (ex. timer systemd) |
| `env-file` | — | modèle du `.env` : `${SECRET}` obligatoire, `${VAR:-défaut}` facultatif (32 noms distincts au plus ; seuls les secrets cités sont lus) |
| `build` | `false` | `up --build` pour les images construites sur le serveur |
| `force-recreate` | `false` | `up --force-recreate` |
| `wait-timeout` | `180` | délai pour que les conteneurs soient sains |
| `health-url`, `health-expect` | — | URL publique vérifiée après le déploiement (et texte attendu) |
| `environment-url` | — | lien affiché sur l'environnement |

Attendu dans l'environnement `production` de l'appelant : variables `SERVER_HOST`, `SERVER_USER`, `DEPLOY_PATH` ; secrets `SSH_PRIVATE_KEY`, `SSH_KNOWN_HOSTS`, `NTFY_URL` (facultatif). `python vps.py deploy` les pose.

Déroulé : `git reset --hard` sur le commit voulu (les fichiers ignorés sont conservés), `pre-deploy`, `docker compose config`, `pull`, `up -d --wait`, contrôle que tous les conteneurs sont `running`/`healthy`, `health-url`. En cas d'échec, **retour automatique au commit précédent**. Notification ntfy : succès (priorité basse), échec ou retour arrière (priorité haute). La version déployée (`git describe`) est dans le résumé du job.

### `validate.yml`

Check `validate` des PR : `pre-commit run --all-files`, `docker compose config` (avec `compose-env` factice si le fichier exige des variables), refus des images sans version figée, puis les commandes `run` du repo.

### `dependabot-auto-merge.yml`

Active la fusion automatique des PR Dependabot de **patch** pour les écosystèmes listés (actions, pip, npm, pre-commit). Les images Docker et les versions mineures/majeures restent en review manuelle.

## Actions composites

- `actions/ssh-setup` : clé et empreintes du serveur, refuse de continuer si un secret manque.
- `actions/ntfy` : notification avec titre UTF-8, ignorée sans URL.

```yaml
- uses: Thaskow/.github/actions/ssh-setup@<sha> # v1.0.0
  with:
    private-key: ${{ secrets.SSH_PRIVATE_KEY }}
    known-hosts: ${{ secrets.SSH_KNOWN_HOSTS }}
    host: ${{ vars.SERVER_HOST }}
    user: ${{ vars.SERVER_USER }}
- run: ssh "$SERVER" uptime
```

## Versions

Release Please (`release.yml`) : chaque fusion sur `main` met à jour une Release PR ; la fusionner crée le tag `vX.Y.Z` et la release. Les appelants référencent le SHA du tag, que Dependabot met à jour. Un tag publié n'est jamais déplacé.

Un changement de contrat (entrée renommée, comportement par défaut modifié) est un `feat!:` → version majeure.

## Développement

```sh
pip install pre-commit && pre-commit install
python scripts/sync-labels.py Thaskow/<repo>   # aligne les labels d'un repo
```

## Réglages GitHub déclarés

[`repos.json`](repos.json) liste les repos et leur rôle ; [`scripts/apply-settings.py`](scripts/apply-settings.py) les rend conformes (idempotent, simulation par défaut) :

```sh
python scripts/apply-settings.py            # affiche ce qui changerait
python scripts/apply-settings.py --apply    # applique
python scripts/apply-settings.py --apply --only Thaskow/ntfy
```

- renommages en kebab-case (GitHub redirige les anciennes URL) et branche par défaut `master` → `main` ;
- fusion **squash uniquement** (titre de la PR = commit), branche supprimée après fusion, auto-merge autorisé, wiki désactivé ;
- alertes et correctifs de sécurité Dependabot ; secret scanning + push protection sur les repos publics ;
- permissions Actions : `GITHUB_TOKEN` en lecture, création/approbation de PR par Actions **interdite** sauf `release_please: true` (Release Please ouvre sa PR avec `GITHUB_TOKEN`) ;
- épinglage des actions par SHA obligatoire (`sha_pinning_required`) sur les repos actifs, désactivable par repo avec `"sha_pinning_required": false` ;
- rétention des artefacts et logs : 30 jours (les sauvegardes fixent la leur) ;
- labels de [`labels.json`](labels.json) ;
- **ruleset `main`** sur les repos actifs : PR obligatoire (sans review imposée), check `validate / validate`, conversations résolues, ni suppression ni force push ; l'administrateur peut fusionner une PR sans attendre les checks (Release PR, urgence), jamais pousser directement.

Les repos de l'organisation `CStonx` (privés, offre gratuite) ne peuvent pas avoir de ruleset : seules les alertes de sécurité leur sont appliquées. Les environnements `production` et leurs secrets sont posés par `python vps.py deploy` (repo `vps`).

La CI valide les workflows avec `actionlint`.
