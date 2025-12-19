#!/usr/bin/env python3
"""tb-go: Navigate to traceback locations from the command line.

A single-file module for parsing Python tracebacks and opening them in vim.
"""
import sys
import re
import subprocess
import argparse
from typing import List, Optional, Tuple
from dataclasses import dataclass

# Global debug flag
DEBUG = False

def debug_print(msg: str) -> None:
    """Print debug message if debug mode is enabled."""
    if DEBUG:
        print(f"[DEBUG] {msg}", file=sys.stderr)

# ============================================================================
# Data Models
# ============================================================================

@dataclass
class TracebackLocation:
    """Represents a single location in a traceback."""
    filepath: str
    line: int
    function: str
    code: str
    
    def __str__(self) -> str:
        """Format for display in fzf."""
        func_part = f" in {self.function}" if self.function else ""
        return f"{self.filepath}:{self.line}{func_part}: {self.code.strip()}"

# ============================================================================
# Parser
# ============================================================================

class TracebackParser:
    """Parse Python tracebacks to extract file locations."""
    
    # Pattern matches: File "/path/to/file.py", line 123, in function_name
    # Or: File "/path/to/file.py", line 123 (for syntax errors)
    TRACEBACK_PATTERN = re.compile(
        r'^\s*File "([^"]+)", line (\d+)(?:, in (.+))?$',
        re.MULTILINE
    )
    
    def has_traceback(self, text: str) -> bool:
        """Check if text contains a traceback."""
        return 'Traceback (most recent call last)' in text or bool(self.TRACEBACK_PATTERN.search(text))
    
    def parse(self, text: str) -> List[TracebackLocation]:
        """Parse traceback text and extract locations.
        
        Args:
            text: Text containing a Python traceback
            
        Returns:
            List of TracebackLocation objects
        """
        locations = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            match = self.TRACEBACK_PATTERN.match(line)
            if match:
                filepath = match.group(1)
                line_num = int(match.group(2))
                function = match.group(3) if match.group(3) else "<module>"
                
                # Try to get the code line (usually the next line)
                code = ""
                if i + 1 < len(lines):
                    code = lines[i + 1].strip()
                
                locations.append(TracebackLocation(
                    filepath=filepath,
                    line=line_num,
                    function=function,
                    code=code
                ))
        
        return locations

# ============================================================================
# Clipboard
# ============================================================================

class ClipboardError(Exception):
    """Raised when clipboard operations fail."""
    pass

def read_clipboard() -> str:
    """Read text from system clipboard.
    
    Returns:
        Clipboard contents as string
        
    Raises:
        ClipboardError: If clipboard cannot be read
    """
    # Try xclip first (common on Linux)
    debug_print("Attempting to read clipboard with xclip...")
    try:
        result = subprocess.run(
            ['xclip', '-selection', 'clipboard', '-o'],
            capture_output=True,
            text=True,
            check=True
        )
        debug_print(f"xclip succeeded, got {len(result.stdout)} chars")
        return result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        debug_print(f"xclip failed: {e}")
    
    # Try xsel as fallback
    debug_print("Attempting to read clipboard with xsel...")
    try:
        result = subprocess.run(
            ['xsel', '--clipboard', '--output'],
            capture_output=True,
            text=True,
            check=True
        )
        debug_print(f"xsel succeeded, got {len(result.stdout)} chars")
        return result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        debug_print(f"xsel failed: {e}")
    
    # Try pbpaste on macOS
    debug_print("Attempting to read clipboard with pbpaste...")
    try:
        result = subprocess.run(
            ['pbpaste'],
            capture_output=True,
            text=True,
            check=True
        )
        debug_print(f"pbpaste succeeded, got {len(result.stdout)} chars")
        return result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        debug_print(f"pbpaste failed: {e}")
    
    raise ClipboardError(
        "Could not read clipboard. Please install xclip, xsel, or use macOS."
    )

# ============================================================================
# Selector (fzf)
# ============================================================================

class FzfNotFoundError(Exception):
    """Raised when fzf is not installed."""
    pass

class FzfSelector:
    """Select from traceback locations using fzf."""
    
    def select(self, locations: List[TracebackLocation]) -> Optional[TracebackLocation]:
        """Present locations to user via fzf and return selection.
        
        Args:
            locations: List of traceback locations
            
        Returns:
            Selected location or None if cancelled
            
        Raises:
            FzfNotFoundError: If fzf is not installed
        """
        # Check if fzf is available
        debug_print("Checking for fzf...")
        try:
            subprocess.run(['fzf', '--version'], capture_output=True, check=True)
            debug_print("fzf found")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            debug_print(f"fzf not found: {e}")
            raise FzfNotFoundError("fzf not found. Please install fzf.")
        
        # Format locations for fzf
        items = [str(loc) for loc in locations]
        input_text = '\n'.join(items)
        debug_print(f"Presenting {len(items)} items to fzf")
        if DEBUG:
            debug_print(f"Items to show:")
            for item in items:
                debug_print(f"  {item}")
        
        # Run fzf
        # fzf needs: list items via stdin, keyboard from /dev/tty, UI drawn on /dev/tty
        try:
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                f.write(input_text)
                temp_file = f.name
            
            debug_print(f"Wrote {len(input_text)} bytes to temp file: {temp_file}")
            
            try:
                # The proper way: use setsid or script to give fzf a controlling terminal
                # Simpler: just exec fzf properly with bash
                # Read list from file, connect fzf fully to /dev/tty for interaction
                
                # Use shell command but properly escape the temp file path
                import shlex
                cmd = f'fzf --height=40% --reverse --prompt="Select traceback location: " < {shlex.quote(temp_file)}'
                
                # Key: run with stdin AND stdout/stderr all connected to /dev/tty
                # except we capture stdout for the result
                with open('/dev/tty', 'r') as tty_in, open('/dev/tty', 'w') as tty_err:
                    result = subprocess.run(
                        cmd,
                        shell=True,
                        stdin=tty_in,  # keyboard from terminal
                        stdout=subprocess.PIPE,  # capture selection
                        stderr=tty_err,  # UI to terminal
                        text=True,
                        check=False
                    )
            finally:
                os.unlink(temp_file)
            
            result_code = result.returncode
            stdout = result.stdout
            
            debug_print(f"fzf exited with code {result_code}")
            
            if result_code != 0:
                # User cancelled
                debug_print("User cancelled fzf selection")
                return None
            
            # Find which location was selected
            selected_text = stdout.strip()
            debug_print(f"User selected: {selected_text}")
            for loc in locations:
                if str(loc) == selected_text:
                    return loc
            
            debug_print("Warning: Selected text didn't match any location")
            return None
            
        except Exception as e:
            debug_print(f"fzf error: {e}")
            raise FzfNotFoundError(f"Error running fzf: {e}")

# ============================================================================
# Vim Opener
# ============================================================================

class VimNotFoundError(Exception):
    """Raised when vim is not installed."""
    pass

class VimOpener:
    """Open files in vim at specific line numbers."""
    
    def open(self, location: TracebackLocation) -> None:
        """Open a file in vim at the specified line.
        
        Args:
            location: Traceback location to open
            
        Raises:
            VimNotFoundError: If vim is not installed
        """
        # Check if vim is available
        debug_print("Checking for vim...")
        try:
            subprocess.run(['vim', '--version'], capture_output=True, check=True)
            debug_print("vim found")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            debug_print(f"vim not found: {e}")
            raise VimNotFoundError("vim not found. Please install vim.")
        
        # Open vim at the specific line
        # Using +{line} to jump to line number
        debug_print(f"Opening vim: vim +{location.line} {location.filepath}")
        try:
            import os
            import shlex
            # Use os.system instead of subprocess for proper terminal handling
            cmd = f"vim +{location.line} {shlex.quote(location.filepath)}"
            os.system(cmd)
            debug_print("vim closed")
            # Explicitly reset terminal
            os.system('reset')
        except Exception as e:
            debug_print(f"vim error: {e}")
            raise VimNotFoundError(f"Error opening vim: {e}")

# ============================================================================
# Command Runner
# ============================================================================

class CommandRunner:
    """Run commands and capture their output."""
    
    def run(self, command: List[str]) -> Tuple[str, int]:
        """Run a command and capture stderr.
        
        Args:
            command: Command and arguments as list
            
        Returns:
            Tuple of (stderr output, exit code)
        """
        debug_print(f"Running command: {command}")
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False
            )
            
            # Combine stdout and stderr for traceback parsing
            # (some programs print tracebacks to stdout)
            output = result.stdout + result.stderr
            debug_print(f"Command finished with exit code {result.returncode}")
            debug_print(f"Output length: {len(output)} chars")
            
            return output, result.returncode
            
        except Exception as e:
            debug_print(f"Command execution failed: {e}")
            return str(e), 1

# ============================================================================
# CLI Interface
# ============================================================================

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
    global DEBUG
    
    # Parse arguments
    parser = argparse.ArgumentParser(
        description='Navigate to Python traceback locations',
        epilog='With no command: reads traceback from clipboard or stdin. With command: runs it and captures output.'
    )
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('command', nargs='*', help='Command to run (optional)')
    
    args = parser.parse_args()
    DEBUG = args.debug
    
    debug_print("tb-go starting...")
    debug_print(f"Arguments: {sys.argv}")
    
    # Check if stdin is piped (not a tty)
    stdin_is_piped = not sys.stdin.isatty()
    debug_print(f"stdin is {'piped' if stdin_is_piped else 'a tty'}")
    
    # Determine mode based on arguments and stdin
    if not args.command:
        if stdin_is_piped:
            # Mode 1a: Read from stdin (piped)
            debug_print("Mode: Reading from stdin (piped)")
            print_colored("Reading traceback from stdin...", Colors.BLUE)
            text = sys.stdin.read()
            debug_print(f"Read {len(text)} characters from stdin")
        else:
            # Mode 1b: Read from clipboard
            debug_print("Mode: Reading from clipboard")
            print_colored("Reading traceback from clipboard...", Colors.BLUE)
            try:
                text = read_clipboard()
                debug_print(f"Read {len(text)} characters from clipboard")
            except ClipboardError as e:
                print_colored(f"Error: {e}", Colors.RED)
                print("\nUsage: tb-go [--debug] [command args...]")
                print("  With no command: reads from stdin (if piped) or clipboard")
                print("  With command: runs it and captures stderr")
                return 1
    else:
        # Mode 2: Run command
        command = args.command
        debug_print(f"Mode: Running command {command}")
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
    debug_print("Parsing traceback...")
    parser_obj = TracebackParser()
    
    if not parser_obj.has_traceback(text):
        print_colored("No traceback found in output", Colors.RED)
        debug_print(f"Text content: {text[:500]}...")
        return 1
    
    debug_print("Traceback detected, extracting locations...")
    locations = parser_obj.parse(text)
    
    if not locations:
        print_colored("No traceback locations found", Colors.RED)
        debug_print(f"Text content: {text[:500]}...")
        return 1
    
    debug_print(f"Extracted {len(locations)} locations")
    for i, loc in enumerate(locations):
        debug_print(f"  {i+1}. {loc.filepath}:{loc.line} in {loc.function}")
    
    print_colored(f"Found {len(locations)} traceback location(s)", Colors.GREEN)
    print()
    
    # Select location
    debug_print("Selecting location...")
    selected = select_location(locations)
    
    if not selected:
        print_colored("Cancelled", Colors.YELLOW)
        return 0
    
    debug_print(f"Selected: {selected.filepath}:{selected.line}")
    
    # Open in vim
    print()
    print_colored(f"Opening: {selected.filepath} at line {selected.line}", Colors.GREEN)
    
    try:
        opener = VimOpener()
        opener.open(selected)
    except VimNotFoundError as e:
        print_colored(f"Error: {e}", Colors.RED)
        return 1
    
    debug_print("Done!")
    return 0

if __name__ == "__main__":
    sys.exit(main())