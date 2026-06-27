# Testing And Validation

## Confirmed commands

### Backend

```bash
cd server
source venv/bin/activate
pytest
```

### Frontend

```bash
cd client
npm test
npm run lint
npm run build
npm run test:e2e:smoke
```

## Run selection

- Backend route or service changes:
  run `cd server && pytest`
- Frontend component or service changes:
  run at least the relevant frontend tests; consider `npm run build` for route or template changes
- Cross-cutting changes:
  run both backend and frontend checks that are available

## Validation reminders

- Check route imports carefully because source drift already exists.
- Treat backend startup behaviour as part of validation when touching app initialisation.
- When a command cannot be run reliably, report that clearly in the final summary.
