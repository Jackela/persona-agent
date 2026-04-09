"""Output formatters for consistent CLI formatting.

This module provides centralized formatting utilities for CLI output,
enabling consistent styling and easier testing through dependency injection.
"""

from typing import Any

from rich.console import Console
from rich.table import Table


class OutputFormatter:
    """Formatter for consistent CLI output.

    Provides methods for common output patterns including tables, errors,
    success messages, info messages, and warnings. Supports dependency
    injection of a Console instance for testing purposes.

    Example:
        >>> formatter = OutputFormatter()
        >>> formatter.print_success("Operation completed!")
        >>> formatter.print_table(
        ...     headers=["Name", "Value"],
        ...     rows=["Alice", "Bob"], ["1", "2"]
        ... )
    """

    def __init__(self, console: Console | None = None) -> None:
        """Initialize the formatter.

        Args:
            console: Optional Console instance. If not provided, a new
                Console instance will be created. Pass a mock Console
                for testing.
        """
        self._console = console if console is not None else Console()

    @property
    def console(self) -> Console:
        """Get the underlying console instance."""
        return self._console

    def print_table(
        self,
        headers: list[str],
        rows: list[list[Any]],
        title: str | None = None,
        show_header: bool = True,
    ) -> None:
        """Print a formatted table.

        Args:
            headers: List of column headers.
            rows: List of row data, where each row is a list of values.
            title: Optional table title displayed above the table.
            show_header: Whether to display the header row.
        """
        table = Table(show_header=show_header, header_style="bold")

        for header in headers:
            table.add_column(header)

        for row in rows:
            table.add_row(*[str(cell) for cell in row])

        if title:
            self._console.print(f"\n[bold]{title}[/bold]\n")

        self._console.print(table)

        if title:
            self._console.print()

    def print_error(self, message: str) -> None:
        """Print an error message.

        Args:
            message: The error message to display.
        """
        self._console.print(f"[red]Error: {message}[/red]")

    def print_success(self, message: str) -> None:
        """Print a success message.

        Args:
            message: The success message to display.
        """
        self._console.print(f"[green]{message}[/green]")

    def print_info(self, message: str) -> None:
        """Print an informational message.

        Args:
            message: The info message to display.
        """
        self._console.print(f"[cyan]{message}[/cyan]")

    def print_warning(self, message: str) -> None:
        """Print a warning message.

        Args:
            message: The warning message to display.
        """
        self._console.print(f"[yellow]Warning: {message}[/yellow]")

    def print_bold(self, message: str) -> None:
        """Print a bold message.

        Args:
            message: The message to display in bold.
        """
        self._console.print(f"[bold]{message}[/bold]")

    def print_dim(self, message: str) -> None:
        """Print a dim/subtle message.

        Args:
            message: The message to display in dim style.
        """
        self._console.print(f"[dim]{message}[/dim]")
