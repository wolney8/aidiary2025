# Version Control & Code Hygiene Strategy

## Branching Strategy

### Main Branch Protection
- **main**: Always stable, working code only
- Never commit directly to main after establishing feature branches
- All features developed in separate branches and merged via tested commits

### Feature Branch Workflow

#### Branch Naming Convention
```
feature/milestone-X-description
hotfix/issue-description
release/vX.Y.Z
```

#### Examples:
- `feature/milestone-7-edit-entry`
- `feature/milestone-9-structured-diary`
- `feature/milestone-10-excel-import`
- `hotfix/search-infinite-loading`
- `release/v0.12.0`

### Development Workflow

#### 1. Starting New Feature
```bash
# Ensure main is clean and up to date
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/milestone-X-description

# Work on feature with regular commits
git add .
git commit -m "milestone-X: specific change description"
```

#### 2. Regular Documentation
- Update CHANGELOG.md with each significant change
- Create test-results-vX.Y.Z.md after each testing cycle
- Document any breaking changes or important decisions

#### 3. Pre-Merge Testing
```bash
# Test feature thoroughly
npm test  # Frontend tests
python -m pytest  # Backend tests

# Update documentation
# - CHANGELOG.md (Unreleased section)
# - test-results-vX.Y.Z.md
# - Any relevant docs/

# Final commit with test results
git add .
git commit -m "milestone-X: testing complete, ready for merge"
```

#### 4. Safe Merging
```bash
# Switch to main and ensure it's current
git checkout main
git pull origin main

# Merge feature (creates merge commit for easy rollback)
git merge --no-ff feature/milestone-X-description

# Test merged result
npm test && python -m pytest

# If tests pass, push to remote
git push origin main

# Clean up feature branch
git branch -d feature/milestone-X-description
```

#### 5. Rollback Strategy (if main breaks)
```bash
# Find the last working commit
git log --oneline

# Create rollback branch from last working state
git checkout -b rollback/to-vX.Y.Z [last-working-commit-hash]

# Make this the new main
git checkout main
git reset --hard rollback/to-vX.Y.Z
git push --force-with-lease origin main

# Document the rollback
echo "ROLLBACK: $(date)" >> ROLLBACK_LOG.md
echo "Reason: [description]" >> ROLLBACK_LOG.md
echo "Rolled back to: [commit-hash]" >> ROLLBACK_LOG.md
```

## Code Hygiene Requirements

### Before Every Commit
1. **Code Quality Checks**
   - No console.log statements in production code
   - No commented-out code blocks
   - Proper error handling
   - British English in all user-facing text

2. **Documentation Updates**
   - Update CHANGELOG.md with changes
   - Add/update JSDoc comments for new functions
   - Update PROJECT_PLAN.md if scope changes

3. **Testing Requirements**
   - All new code has corresponding tests
   - Existing tests still pass
   - Manual testing of changed functionality

### After Every Milestone
1. **Create Test Results Document**
   - File: `docs/tests/test-results-vX.Y.Z.md`
   - Include: test outcomes, known issues, performance notes
   - Add link to CHANGELOG.md

2. **Version Tagging**
   ```bash
   git tag -a vX.Y.Z -m "Milestone X: description"
   git push origin vX.Y.Z
   ```

3. **Documentation Review**
   - Ensure PROJECT_PLAN.md reflects current state
   - Update README.md if needed
   - Review and clean up any outdated docs

## Emergency Procedures

### If Main Branch Becomes Broken
1. **Immediate Response**
   - Stop all new development
   - Assess severity (build broken vs feature broken vs data corruption)
   - Create incident documentation

2. **Quick Fix (< 30 minutes)**
   ```bash
   git checkout -b hotfix/urgent-fix
   # Make minimal fix
   git commit -m "hotfix: urgent fix for [issue]"
   git checkout main
   git merge --no-ff hotfix/urgent-fix
   git push origin main
   ```

3. **Full Rollback (> 30 minutes to fix)**
   - Use rollback strategy above
   - Fix issue in separate feature branch
   - Merge when fully tested

### Recovery Process
1. Document what went wrong in LESSONS_LEARNED_vX.Y.Z.md
2. Update this strategy document if needed
3. Add prevention measures to pre-commit checklist

## File Organization

### Documentation Structure
```
docs/
  PROJECT_PLAN.md           # Master plan and milestones
  VERSION_CONTROL_STRATEGY.md  # This file
  LESSONS_LEARNED_vX.Y.Z.md    # Post-incident learning
  tests/
    test-results-vX.Y.Z.md     # Test outcomes per version
    user-test-results-vX.Y.Z.md # User acceptance testing
```

### Commit Message Format
```
milestone-X: brief description

Optional longer description explaining:
- What changed
- Why it changed  
- Any breaking changes
- Testing performed

Relates to: [issue/feature description]
```

## Branch Protection Rules

### Main Branch
- Require tests to pass before merge
- Require documentation updates
- No direct pushes (except emergency hotfixes)
- Require at least manual testing verification

### Feature Branches
- Regular commits with descriptive messages
- Include test results in final commit
- Update CHANGELOG.md before merge request
- Delete after successful merge

This strategy ensures we can always return to a working state while maintaining clear development progress and comprehensive documentation.