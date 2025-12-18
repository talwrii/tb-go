"""Command-line interface for tb-go."""

import sys
from typing import List, Optional

from .parser import TracebackParser, TracebackLocation
from .clipboard import read_clipboard, ClipboardError
from .selector import FzfSelector, FzfNotFoundError
from .vim_opener import VimOpener, VimNotFoundError
from .runner import CommandRunner


class Colors:
    """ANSI color codes."""
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'  # No Color


def print_colored(text: str, color: str) -> None:
    """Print text with color."""
    print(f"{color}{text}{Colors.NC}")


def select_location(locations: List[TracebackLocation]) -> Optional[TracebackLocation]:
    """
    Select a location using fzf or fall back to last location.
    
    Args:
        locations: List of traceback locations
        
    Returns:
        Selected location or None
    """
    try:
        selector = FzfSelector()
        return selector.select(locations)
    except FzfNotFoundError:
        print_colored("fzf not found, opening last location...", Colors.YELLOW)
        # Return last location (most recent error)
        return locations[-1] if locations else None


def main() -> int:
    """Main entry point for tb-go CLI."""
    
    # Determine mode based on arguments
    if len(sys.argv) == 1:
        # Mode 1: Read from clipboard
        print_colored("Reading traceback from clipboard...", Colors.BLUE)
        try:
            text = read_clipboard()
        except ClipboardError as e:
            print_colored(f"Error: {e}", Colors.RED)
            print("\nUsage: tb-go [command args...]")
            print("  With no args: reads from clipboard")
            print("  With args: runs command and captures stderr")
            return 1
    else:
        # Mode 2: Run command
        command = sys.argv[1:]
        print_colored(f"Running: {' '.join(command)}", Colors.BLUE)
        print()
        
        runner = CommandRunner()
        text, exit_code = runner.run(command)
        
        print()
        if exit_code == 0:
            print_colored("Command succeeded (exit code 0)", Colors.GREEN)
            print("No errors to navigate to.")
            return 0
        else:
            print_colored(f"Command failed (exit code {exit_code})", Colors.YELLOW)
    
    # Parse traceback
    parser = TracebackParser()
    
    if not parser.has_traceback(text):
        print_colored("No traceback found in output", Colors.RED)
        return 1
    
    locations = parser.parse(text)
    
    if not locations:
        print_colored("No traceback locations found", Colors.RED)
        return 1
    
    print_colored(f"Found {len(locations)} traceback location(s)", Colors.GREEN)
    print()
    
    # Select location
    selected = select_location(locations)
    
    if not selected:
        print_colored("Cancelled", Colors.YELLOW)
        return 0
    
    # Open in vim
    print()
    print_colored(f"Opening: {selected.filepath} at line {selected.line}", Colors.GREEN)
    
    try:
        opener = VimOpener()
        opener.open(selected)
    except VimNotFoundError as e:
        print_colored(f"Error: {e}", Colors.RED)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())