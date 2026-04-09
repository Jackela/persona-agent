---
name: browser-use
description: Automates browser interactions for web testing, form filling, screenshots, and data extraction. Use when the user needs to navigate websites, interact with web pages, fill forms, take screenshots, or extract information from web pages.
allowed-tools: Bash(browser-use:*)
---

# Browser Automation with browser-use CLI

The `browser-use` command provides fast, persistent browser automation. A background daemon keeps the browser open across commands, giving ~50ms latency per call.

## Prerequisites

```bash
# Ensure virtual environment is activated
source /mnt/d/Code/persona-agent/.venv/bin/activate

# Install browser-use if not already installed
pip install browser-use playwright

# Install browser binaries
playwright install chromium

# Verify installation
browser-use doctor
```

## Core Workflow

1. **Navigate**: `browser-use open <url>` — launches headless browser and opens page
2. **Inspect**: `browser-use state` — returns clickable elements with indices
3. **Interact**: use indices from state (`browser-use click 5`, `browser-use input 3 "text"`)
4. **Verify**: `browser-use state` or `browser-use screenshot` to confirm
5. **Repeat**: browser stays open between commands

If a command fails, run `browser-use close` first to clear any broken session, then retry.

To use the user's existing Chrome (preserves logins/cookies): run `browser-use connect` first.
To use a cloud browser instead: run `browser-use cloud connect` first.
After either, commands work the same way.

## Browser Modes

```bash
browser-use open <url>                         # Default: headless Chromium (no setup needed)
browser-use --headed open <url>                # Visible window (for debugging)
browser-use connect                            # Connect to user's Chrome (preserves logins/cookies)
browser-use cloud connect                      # Cloud browser (zero-config, requires API key)
browser-use --profile "Default" open <url>     # Real Chrome with specific profile
```

After `connect` or `cloud connect`, all subsequent commands go to that browser — no extra flags needed.

## Commands

```bash
# Navigation
browser-use open <url>                    # Navigate to URL
browser-use back                          # Go back in history
browser-use scroll down                   # Scroll down (--amount N for pixels)
browser-use scroll up                     # Scroll up
browser-use tab list                      # List all tabs
browser-use tab new [url]                 # Open a new tab (blank or with URL)
browser-use tab switch <index>            # Switch to tab by index
browser-use tab close <index> [index...]  # Close one or more tabs

# Page State — always run state first to get element indices
browser-use state                         # URL, title, clickable elements with indices
browser-use screenshot [path.png]         # Screenshot (base64 if no path, --full for full page)

# Interactions — use indices from state
browser-use click <index>                 # Click element by index
browser-use click <x> <y>                 # Click at pixel coordinates
browser-use type "text"                   # Type into focused element
browser-use input <index> "text"          # Click element, then type
browser-use keys "Enter"                  # Send keyboard keys (also "Control+a", etc.)
browser-use select <index> "option"       # Select dropdown option
browser-use upload <index> <path>         # Upload file to file input
browser-use hover <index>                 # Hover over element
browser-use dblclick <index>              # Double-click element
browser-use rightclick <index>            # Right-click element

# Data Extraction
browser-use eval "js code"                # Execute JavaScript, return result
browser-use get title                     # Page title
browser-use get html [--selector "h1"]    # Page HTML (or scoped to selector)
browser-use get text <index>              # Element text content
browser-use get value <index>             # Input/textarea value
browser-use get attributes <index>        # Element attributes
browser-use get bbox <index>              # Bounding box (x, y, width, height)

# Wait
browser-use wait selector "css"           # Wait for element (--state visible|hidden|attached|detached, --timeout ms)
browser-use wait text "text"              # Wait for text to appear

# Cookies
browser-use cookies get [--url <url>]     # Get cookies (optionally filtered)
browser-use cookies set <name> <value>    # Set cookie (--domain, --secure, --http-only, --same-site, --expires)
browser-use cookies clear [--url <url>]   # Clear cookies
browser-use cookies export <file>         # Export to JSON
browser-use cookies import <file>         # Import from JSON

# Session
browser-use close                         # Close browser and stop daemon
browser-use sessions                      # List active sessions
browser-use close --all                   # Close all sessions
```

## Command Chaining

Commands can be chained with `&&`. The browser persists via the daemon, so chaining is safe and efficient.

```bash
# Chain open + snapshot in one call (open already waits for page load)
browser-use open https://example.com && browser-use state

# Chain multiple interactions
browser-use input 5 "user@example.com" && browser-use input 6 "password" && browser-use click 7

# Navigate and capture
browser-use open https://example.com && browser-use screenshot
```

Chain when you don't need intermediate output. Run separately when you need to parse the output first.

## Common Workflows

### Testing a Web Application

```bash
# Start local dev server first (in another terminal)
# npm run dev  # or python -m http.server 8000

# Test the application
browser-use open http://localhost:3000
browser-use state                           # Get element indices
browser-use click 3                         # Click element at index 3
browser-use screenshot result.png           # Take screenshot for verification
browser-use close
```

### Form Submission Testing

```bash
browser-use open https://example.com/signup
browser-use state                           # Get form element indices
# Based on state output:
browser-use input 2 "test@example.com"      # Fill email
browser-use input 3 "password123"           # Fill password
browser-use click 5                         # Click submit button
browser-use wait text "Success"             # Wait for success message
browser-use screenshot success.png
browser-use close
```

### Authenticated Browsing

When a task requires an authenticated site (Gmail, GitHub, internal tools), use Chrome profiles:

```bash
browser-use profile list                           # Check available profiles
# Ask the user which profile to use, then:
browser-use --profile "Default" open https://github.com  # Already logged in
```

### Exposing Local Dev Servers

```bash
browser-use tunnel 3000                            # → https://abc.trycloudflare.com
browser-use open https://abc.trycloudflare.com     # Browse the tunnel
```

## Multiple Browsers

For subagent workflows or running multiple browsers in parallel, use `--session NAME`. Each session gets its own browser.

```bash
browser-use --session agent1 open site-a.com
browser-use --session agent2 open site-b.com
```

## Configuration

```bash
browser-use config list                            # Show all config values
browser-use config set cloud_connect_proxy jp      # Set a value
browser-use config get cloud_connect_timeout       # Get a value
browser-use doctor                                 # Shows config + diagnostics
browser-use setup                                  # Interactive post-install setup
```

Config stored in `~/.browser-use/config.json`.

## Global Options

| Option | Description |
|--------|-------------|
| `--headed` | Show browser window |
| `--profile [NAME]` | Use real Chrome (bare `--profile` uses "Default") |
| `--cdp-url <url>` | Connect via CDP URL (`http://` or `ws://`) |
| `--session NAME` | Target a named session (default: "default") |
| `--json` | Output as JSON |
| `--mcp` | Run as MCP server via stdin/stdout |

## Tips

1. **Always run `state` first** to see available elements and their indices
2. **Use `--headed` for debugging** to see what the browser is doing
3. **Sessions persist** — browser stays open between commands
4. **CLI aliases**: `bu`, `browser`, and `browseruse` all work
5. **If commands fail**, run `browser-use close` first, then retry

## Troubleshooting

- **Browser won't start?** `browser-use close` then `browser-use --headed open <url>`
- **Element not found?** `browser-use scroll down` then `browser-use state`
- **Run diagnostics:** `browser-use doctor`

## Cleanup

```bash
browser-use close                         # Close browser session
browser-use tunnel stop --all             # Stop tunnels (if any)
```

## Python API (Advanced)

For programmatic control from Python:

```python
from browser_use import Agent, Browser, ChatBrowserUse
import asyncio

async def test_website():
    browser = Browser()
    agent = Agent(
        task="Test the login form on http://localhost:3000",
        llm=ChatBrowserUse(),
        browser=browser,
    )
    result = await agent.run()
    return result

# Run the test
result = asyncio.run(test_website())
```
