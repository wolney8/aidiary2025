# docs/tests/README.md
# Test Results Documentation

## Purpose
Track test results and issues after each iteration.

## Process
1. After each AI iteration, commit with: `vX.Y.Z / working|not-working / see test file`
2. Create `test-results-vX.Y.Z.md` documenting:
   - What was tested
   - Commands run
   - Any failures
   - Screenshots/notes
   - Expected fixes for next iteration

## Test Commands

### Backend Tests
```bash
cd server
source venv/bin/activate
pytest -v
```

### Frontend Tests
```bash
cd client
npm test
npm run e2e  # If Playwright configured
```

## Checklist for Each Test Run
- [ ] Backend starts without errors
- [ ] Frontend compiles and serves
- [ ] Auth flow works (register → login → JWT)
- [ ] Daily entry CRUD operations
- [ ] Dream entry CRUD operations
- [ ] AI analysis returns expected fields
- [ ] UI matches wireframes
- [ ] Database schema unchanged