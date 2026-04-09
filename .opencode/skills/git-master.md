---
name: git-master
description: MUST USE for ANY git operations. Atomic commits, rebase/squash, history search (blame, bisect, log -S). STRONGLY RECOMMENDED: Use with task(category='quick', load_skills=['git-master'], ...) to save context. Triggers: 'commit', 'rebase', 'squash', 'who wrote', 'when was X added', 'find the commit that'.
allowed-tools: Bash(git*)
---

# Git Master Skill

Expert-level Git operations for clean history and effective collaboration.

## Core Principles

1. **Atomic Commits** - One logical change per commit
2. **Clear Messages** - Explain WHY, not just WHAT
3. **Clean History** - Rebase/squash before merging
4. **Safety First** - Never force push to shared branches

## Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding/updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements
- `ci`: CI/CD changes
- `build`: Build system changes

Examples:
```
feat(auth): add OAuth2 login support

Implement Google and GitHub OAuth2 login flow using
passport.js. Includes user profile creation and token
refresh logic.

Closes #123
```

## Essential Commands

### Daily Workflow

```bash
# Check status
git status

# Stage changes
git add <file>                    # Stage specific file
git add -p                        # Interactive staging (patch mode)
git add .                         # Stage all changes

# Commit
git commit -m "feat: add feature" # Quick commit
git commit                        # Open editor for detailed message

# Push
git push origin <branch>          # Push to remote
git push -u origin <branch>       # Push and set upstream
```

### Branch Management

```bash
# Create and switch to new branch
git checkout -b feature/new-feature

# Switch branches
git checkout main
git switch feature/new-feature    # Modern syntax

# List branches
git branch                        # Local branches
git branch -r                     # Remote branches
git branch -a                     # All branches

# Delete branches
git branch -d feature/old-feature     # Delete merged branch
git branch -D feature/abandoned       # Force delete unmerged branch
git push origin --delete feature/old  # Delete remote branch
```

### History Investigation

```bash
# View log
git log --oneline -20             # Compact view, last 20 commits
git log --graph --decorate        # Visual branch graph
git log --all --graph --oneline   # Full graph

# Search history
git log -S "function_name"        # Find when function was added/removed
git log -p --follow -- <file>     # Track file changes across renames
git log --grep="fix bug"          # Search commit messages

# Blame
git blame <file>                  # Show line-by-line author
git blame -L 10,20 <file>         # Blame specific lines

# Bisect (find bug introduction)
git bisect start
git bisect bad HEAD               # Current version has bug
git bisect good v1.0.0            # Old version was good
git bisect run ./test.sh          # Automated bisect
```

### Stashing

```bash
git stash push -m "WIP: feature"  # Stash with message
git stash list                    # List stashes
git stash pop                     # Apply and remove latest
git stash apply stash@{1}         # Apply specific stash
git stash drop stash@{0}          # Delete specific stash
git stash clear                   # Remove all stashes
```

### Undoing Changes

```bash
# Unstage files
git restore --staged <file>       # Unstage specific file
git restore --staged .            # Unstage all

# Discard local changes
git restore <file>                # Discard changes in file
git checkout -- <file>            # Old syntax

# Amend last commit
git commit --amend                # Edit commit message
git commit --amend --no-edit      # Keep message, add changes

# Reset (DANGEROUS - use with caution)
git reset --soft HEAD~1           # Undo commit, keep changes staged
git reset --mixed HEAD~1          # Undo commit, unstage changes
git reset --hard HEAD~1           # UNDO COMMIT AND DISCARD CHANGES
```

## Advanced Operations

### Rebasing

```bash
# Basic rebase
git checkout feature-branch
git rebase main                   # Replay feature commits on main

# Interactive rebase
git rebase -i HEAD~5              # Last 5 commits
git rebase -i main                # Rebase onto main interactively

# Rebase actions in editor:
# p, pick = use commit
# r, reword = use commit, but edit message
# e, edit = use commit, but stop for amending
# s, squash = use commit, meld into previous
# f, fixup = like squash, but discard message
# d, drop = remove commit

# Abort rebase
git rebase --abort

# Continue after resolving conflicts
git rebase --continue
```

### Cherry-picking

```bash
# Apply specific commit to current branch
git cherry-pick <commit-hash>

# Cherry-pick without committing
git cherry-pick -n <commit-hash>

# Cherry-pick range
git cherry-pick <start>^..<end>
```

### Tags

```bash
# Create tag
git tag -a v1.0.0 -m "Version 1.0.0"
git tag v1.0.0                    # Lightweight tag

# Push tags
git push origin v1.0.0            # Push specific tag
git push origin --tags            # Push all tags

# Delete tag
git tag -d v1.0.0
git push origin --delete v1.0.0
```

### Submodules

```bash
# Add submodule
git submodule add <url> <path>

# Update submodules
git submodule update --init --recursive

# Pull with submodules
git pull --recurse-submodules
```

## Workflows

### Feature Branch Workflow

```bash
# 1. Start feature
git checkout -b feature/login main

# 2. Make commits
git add .
git commit -m "feat(auth): implement login form"
git commit -m "test(auth): add login tests"

# 3. Keep up to date
git fetch origin
git rebase origin/main

# 4. Push and create PR
git push -u origin feature/login

# 5. After PR approval, squash and merge via GitHub/GitLab
# OR manually:
git checkout main
git merge --squash feature/login
git commit -m "feat(auth): implement user login

Implement user login with email/password authentication.
Includes form validation, error handling, and unit tests.

Closes #456"
```

### Hotfix Workflow

```bash
# 1. Create hotfix from production
git checkout -b hotfix/critical-bug v1.2.0

# 2. Fix and commit
git commit -m "fix: resolve critical memory leak"

# 3. Tag release
git tag -a v1.2.1 -m "Hotfix v1.2.1"

# 4. Push
git push origin hotfix/critical-bug --tags

# 5. Merge to main AND backport to develop
```

## Best Practices

### Commit Guidelines

1. **Commit Early, Commit Often**
   - Small, logical commits are easier to review
   - Don't wait until feature is "complete"

2. **Write Good Messages**
   ```
   feat(api): add user authentication endpoint
   
   Implement JWT-based authentication for the REST API.
   Includes login, logout, and token refresh functionality.
   Passwords are hashed using bcrypt with salt rounds of 12.
   
   Security considerations:
   - Tokens expire after 24 hours
   - Rate limiting: 5 attempts per minute
   - CSRF protection enabled
   
   Closes #234
   ```

3. **Separate Concerns**
   - Don't mix feature code with refactoring
   - Don't mix bug fixes with style changes
   - One logical change per commit

### Branch Naming

```
feature/description        # New features
fix/description            # Bug fixes
docs/description           # Documentation
refactor/description       # Code refactoring
test/description           # Test additions
chore/description          # Maintenance
hotfix/description         # Production fixes
release/v1.2.0            # Release branches
```

### Before Committing

```bash
# Review your changes
git diff --cached          # See what's staged
git diff                   # See unstaged changes

# Check what you're committing
git status

# Run tests
pytest                     # Python
npm test                   # Node.js

# Check code quality
black --check .            # Python formatting
ruff check .               # Python linting
```

### Collaboration

```bash
# Before pushing
git fetch origin
git rebase origin/main     # Keep linear history

# If push is rejected
git pull --rebase origin/main
git push

# Clean up old branches
git branch --merged | xargs git branch -d
```

## Troubleshooting

### Merge Conflicts

```bash
# When conflict occurs:
# 1. Edit files to resolve conflicts
# 2. Mark as resolved
git add <resolved-file>

# 3. Continue operation
git rebase --continue
# OR
git merge --continue
```

### Recover Lost Work

```bash
# Find lost commits
git reflog

# Recover from reflog
git checkout <commit-hash>
git checkout -b recovered-branch

# Undo bad reset
git reflog
git reset --hard HEAD@{1}  # Go back one reflog entry
```

### Large Files

```bash
# Find large files in history
git rev-list --objects --all | \
  git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | \
  awk '/^blob/ {print $3" "$4}' | \
  sort -rn | \
  head -20

# Remove from history (DANGEROUS)
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch path/to/large-file' \
  --prune-empty --tag-name-filter cat -- --all
```

## Aliases (Recommended)

Add to `~/.gitconfig`:

```ini
[alias]
    st = status -sb
    co = checkout
    br = branch
    ci = commit
    lg = log --oneline --graph --decorate --all
    amend = commit --amend --no-edit
    unstage = restore --staged
    uncommit = reset --soft HEAD~1
    last = log -1 HEAD
    visual = !gitk
```
