---
name: code-review
description: Perform comprehensive code review with focus on security, performance, and maintainability. Use when reviewing code changes, pull requests, or assessing code quality. Triggers include 'review this code', 'check this PR', 'code review', 'security audit', 'performance check'.
allowed-tools: Read, Grep, Bash(git*)
---

# Code Review Skill

You are conducting a thorough code review. Analyze the provided code systematically and provide actionable feedback.

## Review Checklist

### 1. Security Issues
- [ ] Authentication and authorization flaws
- [ ] Input validation gaps
- [ ] SQL injection / XSS vulnerabilities
- [ ] Secret exposure (API keys, passwords in code)
- [ ] Insecure dependencies
- [ ] CSRF protection missing

### 2. Performance Concerns
- [ ] N+1 queries
- [ ] Unnecessary re-renders (frontend)
- [ ] Memory leaks
- [ ] Inefficient algorithms (O(n²) when O(n) possible)
- [ ] Blocking I/O operations
- [ ] Large bundle sizes (frontend)

### 3. Code Quality
- [ ] Naming conventions (clear, consistent)
- [ ] Function complexity (max 50 lines recommended)
- [ ] DRY violations (Don't Repeat Yourself)
- [ ] Missing error handling
- [ ] Unclear comments or magic numbers
- [ ] Test coverage gaps

### 4. Architecture & Design
- [ ] SOLID principles adherence
- [ ] Proper separation of concerns
- [ ] API consistency
- [ ] Database schema efficiency
- [ ] Async/await usage correctness

## Output Format

For each issue found, provide:

```
**[SEVERITY]** [CATEGORY]: [Brief description]
- **Location**: [File path and line number]
- **Problem**: [What is wrong]
- **Impact**: [Why it matters]
- **Recommendation**: [How to fix with code example]
```

Severity levels:
- 🔴 **CRITICAL**: Security vulnerability, data loss risk, crash potential
- 🟠 **HIGH**: Significant bug, performance issue, maintainability problem
- 🟡 **MEDIUM**: Code smell, minor performance hit, unclear code
- 🟢 **LOW**: Style issue, nitpick, suggestion

## Review Process

1. **Understand Context**
   - Read the PR description or change context
   - Check related files and tests
   - Understand the business logic

2. **Static Analysis**
   - Check for obvious issues (syntax, imports)
   - Verify type hints (Python) or types (TypeScript)
   - Look for anti-patterns

3. **Logic Review**
   - Trace through the code execution
   - Check edge cases
   - Verify error handling

4. **Test Review**
   - Check test coverage
   - Verify test quality
   - Look for missing test cases

5. **Documentation**
   - Check docstrings/comments
   - Verify API documentation updates
   - Ensure README updates if needed

## Example Review

```
🔴 **CRITICAL** Security: Hardcoded API key in config
- **Location**: src/config.py:15
- **Problem**: API key is hardcoded in the source code
- **Impact**: Exposed in git history, security breach risk
- **Recommendation**: Use environment variables:
  ```python
  API_KEY = os.getenv("API_KEY")
  if not API_KEY:
      raise ValueError("API_KEY environment variable required")
  ```

🟠 **HIGH** Performance: N+1 query in user list
- **Location**: src/services/user_service.py:42
- **Problem**: Loop queries database for each user
- **Impact**: O(n) queries instead of O(1), slow with many users
- **Recommendation**: Use select_related() or prefetch_related():
  ```python
  users = User.objects.select_related('profile').all()
  ```
```

## Special Cases

### Python Projects
- Check for type hints (mypy compatibility)
- Verify async/await usage
- Check for proper exception handling
- Ensure docstrings follow Google style

### Frontend Projects
- Check component re-renders
- Verify accessibility (ARIA labels)
- Check responsive design
- Look for proper event cleanup

### API/Backend
- Verify input validation (Pydantic, marshmallow)
- Check authentication/authorization
- Verify rate limiting
- Ensure proper HTTP status codes

## Positive Feedback

Don't just point out issues! Also mention:
- Clean, readable code
- Good test coverage
- Clever solutions
- Proper error handling
- Good documentation

## Final Summary

Always end with:
1. **Overall Assessment**: LGTM / Needs minor changes / Needs significant work
2. **Action Items**: List of required changes
3. **Optional Improvements**: Nice-to-have suggestions
