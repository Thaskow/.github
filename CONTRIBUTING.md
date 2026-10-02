# Contribuer

1. Une branche par changement : `feat/…`, `fix/…`, `chore/…`, `docs/…`, `ci/…`, `refactor/…`.
2. `pre-commit install` une fois par clone : les mêmes vérifications tournent en CI.
3. Commits et titre de PR en [Conventional Commits](https://www.conventionalcommits.org/fr/) (`feat:`, `fix:`, `feat!:` pour un changement cassant).
4. PR vers `main` avec le modèle rempli (impact production, migration, rollback). Fusion en squash une fois `validate` vert.
5. Jamais de secret dans le code : secrets de l'environnement GitHub `production`, ou coffre `vault.enc` du repo `vps`.

Détails : [docs/conventions.md](https://github.com/Thaskow/.github/blob/main/docs/conventions.md).
