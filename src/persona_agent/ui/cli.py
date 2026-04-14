"""CLI interface for persona-agent using Service Layer architecture."""

import asyncio
import logging
import sys

import click
from rich.console import Console
from rich.panel import Panel

from persona_agent.services import (
    CharacterNotFoundError,
    CharacterService,
    ChatPersonaNotFoundError,
    ChatService,
    ChatServiceError,
    ChatSessionNotFoundError,
    SessionService,
)
from persona_agent.ui.formatters import OutputFormatter
from persona_agent.utils.exceptions import PersonaAgentError

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
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
    default="ollama",
    type=click.Choice(["ollama", "openai", "anthropic", "local"]),
    help="LLM provider",
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
def chat(persona: str | None, provider: str, model: str | None, session: str | None) -> None:
    """Start an interactive chat session."""
    asyncio.run(_chat_async(persona, provider, model, session))


async def _chat_async(
    persona: str | None,
    provider: str,
    model: str | None,
    session: str | None,
) -> None:
    """Async chat implementation using ChatService."""
    formatter = OutputFormatter(console)

    async with ChatService(llm_provider=provider, llm_model=model) as chat_service:
        try:
            # Get or create session
            if session:
                # Resume existing session
                try:
                    session_info = await chat_service.get_session_info(session)
                    current_session_id = session
                    # Use session's persona if none specified
                    if not persona:
                        persona = session_info.get("persona_name")
                except ChatSessionNotFoundError:
                    formatter.print_error(f"Session '{session}' not found.")
                    return
                except ChatServiceError as e:
                    logger.error(f"Failed to get session info: {e}")
                    formatter.print_error(f"Failed to retrieve session: {e}")
                    return
            else:
                # Create new session
                try:
                    current_session_id = await chat_service.create_new_session(persona_name=persona)
                except ChatPersonaNotFoundError:
                    formatter.print_error(f"Persona '{persona}' not found.")
                    return
                except ChatServiceError as e:
                    logger.error(f"Failed to create session: {e}")
                    formatter.print_error(f"Failed to create session: {e}")
                    return

            # Validate we have a persona
            if not persona:
                # Try to get default from character service
                character_service = CharacterService()
                available = character_service.list_characters()
                if available:
                    persona = available[0]
                else:
                    formatter.print_error("No characters found. Please create one first.")
                    return

            # Get character info for display
            character_service = CharacterService()
            try:
                char = character_service.get_character(persona)
            except CharacterNotFoundError:
                formatter.print_error(f"Character '{persona}' not found.")
                return
            except Exception as e:
                logger.error(f"Failed to load character '{persona}': {e}")
                formatter.print_error(f"Failed to load character: {e}")
                return

            # Display welcome
            console.print(
                Panel.fit(
                    f"[bold]{char.name}[/bold]\n{char.relationship or 'Your companion'}",
                    title="Persona-Agent",
                    border_style="blue",
                )
            )

            formatter.print_dim("\nType 'exit' or press Ctrl+C to quit.\n")

            # Chat loop
            while True:
                try:
                    user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()

                    if not user_input:
                        continue

                    if user_input.lower() in ["exit", "quit", "bye"]:
                        formatter.print_dim("\nGoodbye!")
                        break

                    # Send message and get response
                    with console.status("[dim]Thinking...[/dim]", spinner="dots"):
                        response = await chat_service.send_message(
                            session_id=current_session_id,
                            message=user_input,
                        )

                    # Display response
                    console.print(f"[bold magenta]{char.name}:[/bold magenta] ", end="")
                    console.print(response)
                    console.print()

                except KeyboardInterrupt:
                    formatter.print_dim("\n\nGoodbye!")
                    break
                except PersonaAgentError as e:
                    logger.error(f"Chat error: {e}")
                    formatter.print_error(f"\n{e.message}\n")
                except Exception as e:
                    logger.exception(f"Unexpected error in chat loop: {e}")
                    formatter.print_error("\nAn unexpected error occurred. Please try again.\n")

        except ChatSessionNotFoundError:
            formatter.print_error("Session not found.")
        except ChatPersonaNotFoundError:
            formatter.print_error("Persona not found.")
        except ChatServiceError as e:
            logger.error(f"Chat service error: {e}")
            formatter.print_error(f"Chat service error: {e}")
        except Exception as e:
            logger.exception(f"Unexpected chat error: {e}")
            formatter.print_error(f"An unexpected error occurred: {e}")


@cli.group()
def plan() -> None:
    """Manage execution plans."""
    pass


@plan.command("create")
@click.argument("goal")
@click.option(
    "--execute/--no-execute",
    default=True,
    help="Execute the plan immediately",
)
def plan_create(goal: str, execute: bool) -> None:
    """Create a new plan for a goal."""
    asyncio.run(_plan_create_async(goal, execute))


async def _plan_create_async(goal: str, execute: bool) -> None:
    """Async implementation of plan create."""
    from persona_agent.core.agent_engine import AgentEngine
    from persona_agent.core.planning import PlanExecutor, PlanningEngine
    from persona_agent.utils.llm_client import LLMClient

    formatter = OutputFormatter(console)

    try:
        # Initialize engine
        llm_client = LLMClient(provider="ollama")
        agent_engine = AgentEngine(llm_client=llm_client)

        # Create plan
        planning_engine = PlanningEngine(agent_engine)
        plan = await planning_engine.create_plan(goal)

        formatter.print_success(f"Created plan: {plan.id}")
        formatter.print_info(f"Goal: {plan.goal}")
        formatter.print_info(f"Tasks: {len(plan.tasks)}")

        for task_id in plan.get_task_order():
            task = plan.tasks[task_id]
            deps = f" (depends on: {', '.join(task.dependencies)})" if task.dependencies else ""
            console.print(f"  • {task_id}: {task.description}{deps}")

        if execute:
            formatter.print_info("\nExecuting plan...")
            plan_executor = PlanExecutor(agent_engine)

            def on_progress(plan_id: str, task_id: str, pct: int) -> None:
                console.print(f"  Progress: {pct}% (task: {task_id})")

            results = await plan_executor.execute_plan(plan, on_progress=on_progress)

            if results["status"] == "completed":
                formatter.print_success("\nPlan completed successfully!")
            else:
                formatter.print_error(f"\nPlan failed. Status: {results['status']}")

    except Exception as e:
        logger.error(f"Plan creation failed: {e}")
        formatter.print_error(f"Failed to create plan: {e}")


@plan.command("status")
@click.argument("plan_id")
def plan_status(plan_id: str) -> None:
    """Show the status of a plan."""
    console.print(f"Plan status: {plan_id}")
    console.print("[dim]Not yet implemented[/dim]")


@cli.group()
def config() -> None:
    """Manage configuration."""
    pass


@config.command("list")
def list_characters() -> None:
    """List available characters using CharacterService."""
    formatter = OutputFormatter(console)

    try:
        character_service = CharacterService()
        characters = character_service.list_characters()

        if not characters:
            formatter.print_warning("No characters found.")
            return

        formatter.print_table(
            headers=["Character"],
            rows=[[char] for char in characters],
            title="Available Characters",
        )
    except Exception as e:
        logger.error(f"Error listing characters: {e}")
        formatter.print_error(f"Error listing characters: {e}")


@config.command("show")
@click.argument("character")
def show_character(character: str) -> None:
    """Show character details using CharacterService."""
    formatter = OutputFormatter(console)

    try:
        character_service = CharacterService()

        # Validate character exists
        if not character_service.character_exists(character):
            formatter.print_error(f"Character '{character}' not found.")
            return

        profile = character_service.get_character(character)
        console.print(
            Panel.fit(
                profile.to_prompt_context(),
                title=profile.name,
                border_style="green",
            )
        )
    except Exception as e:
        logger.error(f"Error loading character '{character}': {e}")
        formatter.print_error(f"Error loading character: {e}")


@cli.group()
def session() -> None:
    """Manage chat sessions."""
    pass


@session.command("list")
@click.option(
    "--limit",
    "-l",
    default=20,
    type=int,
    help="Maximum number of sessions to show",
)
def list_sessions(limit: int) -> None:
    """List recent chat sessions using SessionService."""
    formatter = OutputFormatter(console)

    async def _list() -> None:
        try:
            async with SessionService() as service:
                sessions = await service.list_sessions(limit=limit)

                if not sessions:
                    formatter.print_warning("No sessions found.")
                    return

                # Format for table display
                rows = []
                for s in sessions:
                    last_str = (
                        s["last_activity"].strftime("%Y-%m-%d %H:%M")
                        if hasattr(s["last_activity"], "strftime")
                        else str(s["last_activity"])
                    )
                    rows.append([s["session_id"], str(s["message_count"]), last_str])

                formatter.print_table(
                    headers=["Session ID", "Messages", "Last Activity"],
                    rows=rows,
                    title=f"Recent Sessions (last {len(sessions)})",
                )
        except Exception as e:
            logger.error(f"Error reading sessions: {e}")
            formatter.print_error(f"Error reading sessions: {e}")

    asyncio.run(_list())


@session.command("info")
@click.argument("session_id")
def session_info(session_id: str) -> None:
    """Show detailed information about a session using SessionService."""
    formatter = OutputFormatter(console)

    async def _info() -> None:
        try:
            async with SessionService() as service:
                if not await service.session_exists(session_id):
                    formatter.print_warning(f"Session '{session_id}' not found.")
                    return

                info = await service.get_session_info(session_id)

                # Display session info
                console.print(f"\n[bold]Session:[/bold] [cyan]{session_id}[/cyan]\n")
                console.print(f"  Total messages: {info['message_count']}")

                if hasattr(info["first_activity"], "strftime"):
                    first_str = info["first_activity"].strftime("%Y-%m-%d %H:%M:%S")
                    last_str = info["last_activity"].strftime("%Y-%m-%d %H:%M:%S")
                else:
                    first_str = str(info["first_activity"])
                    last_str = str(info["last_activity"])

                console.print(f"  Started: {first_str}")
                console.print(f"  Last activity: {last_str}")

                # Display recent messages
                recent = info.get("recent_messages", [])
                if recent:
                    console.print("\n[bold]Recent messages:[/bold]\n")
                    for msg in recent:
                        if isinstance(msg, dict):
                            time_str = msg.get("timestamp", "")
                            if hasattr(time_str, "strftime"):
                                time_str = time_str.strftime("%H:%M:%S")
                            user_msg = msg.get("user_message", "")[:50]
                            console.print(f"  [dim]{time_str}[/dim] You: {user_msg}...")

                console.print()
        except Exception as e:
            logger.error(f"Error reading session info: {e}")
            formatter.print_error(f"Error reading session info: {e}")

    asyncio.run(_info())


@session.command("delete")
@click.argument("session_id")
@click.confirmation_option(prompt="Are you sure you want to delete this session?")
def delete_session(session_id: str) -> None:
    """Delete a session and all its messages using SessionService."""
    formatter = OutputFormatter(console)

    async def _delete() -> None:
        try:
            async with SessionService() as service:
                if not await service.session_exists(session_id):
                    formatter.print_warning(f"Session '{session_id}' not found.")
                    return

                await service.delete_session(session_id)
                formatter.print_success(f"Deleted session '{session_id}'.")
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            formatter.print_error(f"Error deleting session: {e}")

    asyncio.run(_delete())


@config.command("validate")
@click.option(
    "--dir",
    "-d",
    default="config",
    help="Configuration directory to validate",
)
def validate_config_cmd(dir: str) -> None:
    """Validate configuration files."""
    from persona_agent.config.validator import ConfigValidator

    validator = ConfigValidator(dir)
    is_valid = validator.validate_all()
    validator.print_report()

    if not is_valid:
        sys.exit(1)


@cli.group()
def skill() -> None:
    """Manage skills and skill evolution."""
    pass


@skill.command("list")
def skill_list() -> None:
    """List all registered skills."""
    from persona_agent.skills.registry import get_registry

    registry = get_registry()

    skills = registry.list_skills()

    if not skills:
        console.print("[dim]No skills registered.[/dim]")
        return

    console.print("\n[bold]Registered Skills:[/bold]\n")
    for skill_info in skills:
        status = "[green]●[/green]" if skill_info["enabled"] else "[red]●[/red]"
        loaded = "[green]loaded[/green]" if skill_info["loaded"] else "[dim]not loaded[/dim]"
        console.print(f"  {status} {skill_info['name']} [dim]({loaded})[/dim]")
        console.print(f"     {skill_info['description']}")
        console.print()


@skill.group()
def evolution() -> None:
    """Manage skill evolution."""
    pass


@evolution.command("status")
@click.argument("skill_name", required=False)
def evolution_status(skill_name: str | None) -> None:
    """Show evolution status for skills."""
    from persona_agent.skills.evolution import SkillEvolutionTracker

    formatter = OutputFormatter(console)
    tracker = SkillEvolutionTracker()

    if skill_name:
        metrics = tracker.get_metrics(skill_name)
        if not metrics:
            formatter.print_warning(f"No metrics for skill '{skill_name}'")
            return

        console.print(f"\n[bold]Skill:[/bold] {skill_name}\n")
        console.print(f"  Total executions: {metrics.total_executions}")
        console.print(f"  Success rate: {metrics.success_rate:.1%}")
        console.print(f"  Avg execution time: {metrics.average_execution_time_ms:.0f}ms")

        if metrics.needs_improvement:
            console.print("\n  [yellow]⚠ This skill needs improvement[/yellow]")
            rec_mode = tracker.get_recommended_mode(skill_name)
            if rec_mode:
                console.print(f"  [dim]Recommended mode: {rec_mode}[/dim]")
    else:
        stats = tracker.get_statistics()
        console.print("\n[bold]Evolution Statistics:[/bold]\n")
        console.print(f"  Skills tracked: {stats['total_skills_tracked']}")
        console.print(f"  Need evolution: {stats['skills_needing_evolution']}")
        console.print(f"  Overall success rate: {stats['overall_success_rate']:.1%}")


@evolution.command("propose")
@click.argument("skill_name")
@click.option(
    "--mode",
    type=click.Choice(["fix", "derived"]),
    default="fix",
    help="Evolution mode",
)
def evolution_propose(skill_name: str, mode: str) -> None:
    """Generate an evolution proposal for a skill."""
    console.print(f"[dim]Generating {mode} proposal for {skill_name}...[/dim]")
    console.print("[yellow]Not yet implemented[/yellow]")


@evolution.command("list")
def evolution_list() -> None:
    """List pending evolution proposals."""
    console.print("[dim]Listing evolution proposals...[/dim]")
    console.print("[yellow]Not yet implemented[/yellow]")


@cli.group()
def memory() -> None:
    """Manage memory and compaction."""
    pass


@memory.command("compact")
@click.option(
    "--older-than-days",
    "-d",
    type=int,
    default=7,
    help="Only compact memories older than this many days",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be compacted without doing it",
)
def memory_compact(older_than_days: int, dry_run: bool) -> None:
    """Compact old memories to save space."""
    from persona_agent.core.hierarchical_memory import HierarchicalMemory
    from persona_agent.core.memory import MemoryCompactor

    formatter = OutputFormatter(console)

    async def _compact() -> None:
        try:
            # Initialize memory system
            hierarchical = HierarchicalMemory()
            compactor = MemoryCompactor(hierarchical.episodic)

            memory_count = len(hierarchical.episodic._episodes)
            console.print(f"\nCurrent memory count: {memory_count}")
            console.print(f"Compaction threshold: {older_than_days} days\n")

            if dry_run:
                console.print("[dim]Dry run mode - no changes will be made[/dim]")
                return

            result = await compactor.compact_memories(older_than_days=older_than_days)

            if result.compacted_count > 0:
                formatter.print_success(
                    f"Compacted {result.compacted_count} memories into "
                    f"{result.summaries_created} summaries"
                )
                console.print(f"  Estimated bytes saved: {result.bytes_saved}")
                console.print(f"  Compaction ratio: {result.compaction_ratio:.1%}")
            else:
                console.print("[dim]No memories needed compaction.[/dim]")

        except Exception as e:
            logger.error(f"Compaction failed: {e}")
            formatter.print_error(f"Compaction failed: {e}")

    asyncio.run(_compact())


@memory.command("stats")
def memory_stats() -> None:
    """Show memory statistics."""
    from persona_agent.core.hierarchical_memory import HierarchicalMemory

    formatter = OutputFormatter(console)

    try:
        hierarchical = HierarchicalMemory()
        stats = hierarchical.get_stats()

        console.print("\n[bold]Memory Statistics:[/bold]\n")
        console.print(f"  Working memory: {stats['working']['exchanges']} exchanges")
        console.print(f"  Episodic memory: {stats['episodic']['total_episodes']} episodes")
        console.print(f"  Semantic memory: {stats['semantic']['entities']} entities")
        console.print(f"    Facts: {stats['semantic']['facts']}")
        console.print(f"    Relations: {stats['semantic']['relations']}")
        console.print()

    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}")
        formatter.print_error(f"Failed to get memory stats: {e}")


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", "-p", default=8080, type=int, help="Port to listen on")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
def web(host: str, port: int, reload: bool) -> None:
    """Launch the Persona Agent web UI."""
    import uvicorn

    console.print(f"[bold green]Starting Persona Agent Web UI at http://{host}:{port}[/bold green]")
    uvicorn.run("persona_agent.ui.web.server:app", host=host, port=port, reload=reload)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
