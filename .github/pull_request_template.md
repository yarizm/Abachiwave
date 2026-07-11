## Summary

Describe the user-visible or engineering outcome of this change.

## Validation

- [ ] `uv run ruff check .`
- [ ] `uv run mypy`
- [ ] `uv run pytest`
- [ ] `npm run lint`
- [ ] `npm run typecheck`
- [ ] `npm test`
- [ ] `npm run build`
- [ ] `npm run test:e2e`
- [ ] Integration smoke completed, or the reason it was not run is documented.
- [ ] Python/Node dependency audits and secret scan pass.

## Change Review

- [ ] API changes and compatibility impact are documented.
- [ ] Database migrations include upgrade, downgrade, and existing-data considerations.
- [ ] New environment variables are added to `.env.example` and documentation.
- [ ] Worker, storage, and cancellation behavior have been considered where applicable.
- [ ] Logs and fixtures do not contain credentials or private creative content.

## Rollback

Describe how to revert the code, migration, and stored objects safely.
