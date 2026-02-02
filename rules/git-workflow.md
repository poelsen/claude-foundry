# Git Workflow

## Branch Strategy

- Feature Branch Workflow (short-lived feature branches)
- Rebase only (no merge commits), fast-forward merges
- Squash unnecessary commits before merge

## Branch Protection

Protected branches: `master`, `release/*`

- Never push directly — always use feature/bugfix branches + PR
- Never force push
- Require at least one review before merge
- CI must pass before merge

## Branch Naming

```
feature/<initials>_<issue>_<description>  # e.g., feature/rudm_foo-111_rocket
bugfix/<initials>_<description>           # e.g., bugfix/rudm_flat_tire
release/<major>_<minor>_<patch>           # e.g., release/1_0_x
devel/<initials>_<description>            # long-term development
```

Rules:
- Prepend developer initials
- Use hyphen/underscore as separators
- Keep names short for long-lived branches
- Delete feature/bugfix branches after merge

## Commit Message Format

```
[ISSUE-ID] <type>: <subject>

<optional body - wrap at 72 chars>
```

- ISSUE-ID is optional (omit when no issue tracker or early dev)
- Subject: 50 chars target, 70 max
- Types: feat, fix, refactor, docs, test, chore, perf, ci
- Imperative mood, capitalized, no trailing period
- Body can use past tense when describing completed changes
- End with AI attribution: `AI: Claude Opus 4.5` (or current model)
- See `rule-library/platform/github.md` for issue linking (`Closes #N`)

### Example

```
FOO-123 feat: Add rocket propulsion system

Implement new propulsion module with configurable thrust.
- Add ThrustController class
- Update flight dynamics
```

## Pull Requests

When creating PRs:
1. Analyze full commit history (not just latest commit)
2. Use `git diff [base-branch]...HEAD` to see all changes
3. Draft comprehensive summary
4. Include test plan

## Release & Hotfix Flow

1. Release: create tag on master
2. Hotfix needed: create release branch from tag
3. Create bugfix branch from release branch
4. Apply fix, rebase to release branch
5. Create new release tag
6. Cherry-pick/rebase fix back to master
