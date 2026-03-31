"""CLI interface for persona-agent."""

import asyncio
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from persona_agent.config.loader import ConfigLoader
from persona_agent.core.agent_engine import AgentEngine
from persona_agent.core.memory_store import MemoryStore
from persona_agent.core.persona_manager import PersonaManager
from persona_agent.utils.llm_client import LLMClient

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Persona-Agent: A local role-playing AI agent."""
    pass


@cli.command()
@click.option(
    "--persona",
    "-p",
    help="Character to use",
)
@click.option(
    "--provider",
    default="openai",
    help="LLM provider (openai, anthropic, local)",
)
@click.option(
    "--model",
    help="Model name",
)
@click.option(
    "--session",
    "-s",
    help="Session ID to resume",
)
def chat(persona: str | None, provider: str, model: str | None, session: str | None):
    """Start an interactive chat session."""
    asyncio.run(_chat_async(persona, provider, model, session))


async def _chat_async(
    persona: str | None,
    provider: str,
    model: str | None,
    session: str | None,
):
    """Async chat implementation."""
    # Initialize components
    config_loader = ConfigLoader()

    # Load character
    if not persona:
        available = config_loader.list_characters()
        if available:
            persona = available[0]
        else:
            console.print("[red]No characters found. Please create one first.[/red]")
            return

    try:
        persona_manager = PersonaManager(config_loader, persona)
    except FileNotFoundError:
        console.print(f"[red]Character '{persona}' not found.[/red]")
        return

    # Initialize LLM client
    try:
        llm_client = LLMClient(provider=provider, model=model)
    except ValueError as e:
        console.print(f"[red]Failed to initialize LLM client: {e}[/red]")
        return

    # Initialize memory
    memory_store = MemoryStore()

    # Create agent engine
    agent = AgentEngine(
        persona_manager=persona_manager,
        memory_store=memory_store,
        llm_client=llm_client,
        session_id=session,
    )

    # Display welcome
    char = persona_manager.get_character()
    if char:
        console.print(
            Panel.fit(
                f"[bold]{char.name}[/bold]\n{char.relationship or 'Your companion'}",
                title="Persona-Agent",
                border_style="blue",
            )
        )

    console.print("\n[dim]Type 'exit' or press Ctrl+C to quit.[/dim]\n")

    # Chat loop
    while True:
        try:
            user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit", "bye"]:
                console.print("\n[dim]Goodbye![/dim]")
                break

            # Generate response
            with console.status("[dim]Thinking...[/dim]", spinner="dots"):
                response = await agent.chat(user_input)

            # Display response
            char_name = char.name if char else "Assistant"
            console.print(f"[bold magenta]{char_name}:[/bold magenta] ", end="")
            console.print(response)
            console.print()

        except KeyboardInterrupt:
            console.print("\n\n[dim]Goodbye![/dim]")
            break
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]\n")


@cli.group()
def config():
    """Manage configuration."""
    pass


@config.command("list")
def list_characters():
    """List available characters."""
    loader = ConfigLoader()
    characters = loader.list_characters()

    if not characters:
        console.print("[yellow]No characters found.[/yellow]")
        return

    console.print("\n[bold]Available Characters:[/bold]")
    for char in characters:
        console.print(f"  • {char}")
    console.print()


@config.command("show")
@click.argument("character")
def show_character(character: str):
    """Show character details."""
    loader = ConfigLoader()

    try:
        profile = loader.load_character(character)
        console.print(
            Panel.fit(
                profile.to_prompt_context(),
                title=profile.name,
                border_style="green",
            )
        )
    except FileNotFoundError:
        console.print(f"[red]Character '{character}' not found.[/red]")


@cli.group()
def session():
    """Manage chat sessions."""
    pass


@session.command("list")
@click.option(
    "--limit",
    "-l",
    default=20,
    help="Maximum number of sessions to show",
)
def list_sessions(limit: int):
    """List recent chat sessions."""
    from pathlib import Path

    db_path = Path("memory/persona_agent.db")
    if not db_path.exists():
        console.print("[yellow]No memory database found.[/yellow]")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            """
            SELECT session_id, COUNT(*) as message_count,
                   MAX(timestamp) as last_activity
            FROM conversations
            GROUP BY session_id
            ORDER BY last_activity DESC
            LIMIT ?
            """,
            (limit,),
        )
        sessions = cursor.fetchall()
        conn.close()

        if not sessions:
            console.print("[yellow]No sessions found.[/yellow]")
            return

        console.print(f"\n[bold]Recent Sessions (last {len(sessions)}):[/bold]\n")

        for session_id, count, last_time in sessions:
            last_str = datetime.fromtimestamp(last_time).strftime("%Y-%m-%d %H:%M")
            console.print(f"  [cyan]{session_id}[/cyan] - {count} messages (last: {last_str})")

        console.print()

    except Exception as e:
        console.print(f"[red]Error reading sessions: {e}[/red]")


@session.command("info")
@click.argument("session_id")
def session_info(session_id: str):
    """Show detailed information about a session."""
    from pathlib import Path

    db_path = Path("memory/persona_agent.db")
    if not db_path.exists():
        console.print("[yellow]No memory database found.[/yellow]")
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Get message count
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM conversations WHERE session_id = ?",
            (session_id,),
        )
        count = cursor.fetchone()["count"]

        if count == 0:
            console.print(f"[yellow]Session '{session_id}' not found.[/yellow]")
            conn.close()
            return

        # Get first and last message times
        cursor = conn.execute(
            """
            SELECT MIN(timestamp) as first_time, MAX(timestamp) as last_time
            FROM conversations WHERE session_id = ?
            """,
            (session_id,),
        )
        times = cursor.fetchone()

        # Get recent messages
        cursor = conn.execute(
            """
            SELECT user_message, assistant_message, timestamp
            FROM conversations WHERE session_id = ?
            ORDER BY timestamp DESC LIMIT 5
            """,
            (session_id,),
        )
        recent = cursor.fetchall()

        conn.close()

        # Display info
        console.print(f"\n[bold]Session:[/bold] [cyan]{session_id}[/cyan]\n")
        console.print(f"  Total messages: {count}")
        console.print(
            f"  Started: {datetime.fromtimestamp(times['first_time']).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        console.print(
            f"  Last activity: {datetime.fromtimestamp(times['last_time']).strftime('%Y-%m-%d %H:%M:%S')}"
        )

        console.print("\n[bold]Recent messages:[/bold]\n")
        for row in reversed(recent):
            time_str = datetime.fromtimestamp(row["timestamp"]).strftime("%H:%M:%S")
            console.print(f"  [dim]{time_str}[/dim] You: {row['user_message'][:50]}...")

        console.print()

    except Exception as e:
        console.print(f"[red]Error reading session info: {e}[/red]")


@session.command("delete")
@click.argument("session_id")
@click.confirmation_option(prompt="Are you sure you want to delete this session?")
def delete_session(session_id: str):
    """Delete a session and all its messages."""
    from pathlib import Path

    db_path = Path("memory/persona_agent.db")
    if not db_path.exists():
        console.print("[yellow]No memory database found.[/yellow]")
        return

    try:
        conn = sqlite3.connect(db_path)

        # Delete conversations
        cursor = conn.execute(
            "DELETE FROM conversations WHERE session_id = ?",
            (session_id,),
        )
        deleted = cursor.rowcount

        # Delete summaries
        conn.execute(
            "DELETE FROM memory_summaries WHERE session_id = ?",
            (session_id,),
        )

        conn.commit()
        conn.close()

        if deleted > 0:
            console.print(
                f"[green]Deleted session '{session_id}' ({deleted} messages removed).[/green]"
            )
        else:
            console.print(f"[yellow]Session '{session_id}' not found.[/yellow]")

    except Exception as e:
        console.print(f"[red]Error deleting session: {e}[/red]")


@config.command("validate")
@click.option(
    "--dir",
    "-d",
    default="config",
    help="Configuration directory to validate",
)
def validate_config_cmd(dir: str):
    """Validate configuration files."""
    from persona_agent.config.validator import ConfigValidator

    validator = ConfigValidator(dir)
    is_valid = validator.validate_all()
    validator.print_report()

    if not is_valid:
        sys.exit(1)


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
