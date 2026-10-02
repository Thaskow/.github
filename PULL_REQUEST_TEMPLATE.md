## Résumé

<!-- Quoi et pourquoi, en deux ou trois lignes. Titre de la PR au format Conventional Commits : feat(scope): … -->

## Type de changement

- [ ] feat
- [ ] fix
- [ ] docs
- [ ] ci
- [ ] chore
- [ ] refactor
- [ ] perf / test / build
- [ ] **breaking change** (`feat!:` ou `BREAKING CHANGE:`)

## Validation

- [ ] CI verte (pre-commit, `docker compose config`, tests du repo)
- [ ] Config validée localement si besoin (`nginx -t`, `python vps.py plan`…)
- [ ] Pas de secret ajouté (valeurs dans les secrets GitHub ou le coffre `vault.enc`)
- [ ] Impact prod vérifié
- [ ] Rollback possible

## Impact production

<!-- Services redémarrés, coupure éventuelle, données touchées. « Aucun » si rien n'est déployé. -->

## Migration nécessaire

<!-- Actions manuelles avant/après merge (secrets, variables, python vps.py deploy…). « Aucune » sinon. -->

## Rollback

<!-- Par défaut : Run workflow « Deploy » avec ref = commit ou tag précédent. -->
