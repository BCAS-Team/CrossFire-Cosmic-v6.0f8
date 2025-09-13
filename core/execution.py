import subprocess
import threading
import sys
import time
from dataclasses import dataclass
from typing import List, Union, Optional

from .logger import LOG, cprint


@dataclass
class RunResult:
    ok: bool
    code: int
    out: str
    err: str


def _show_progress_dots(process):
    """Show progress dots while a process is running."""
    spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    i = 0
    while process.poll() is None:
        if process.poll() is not None:
            return
        sys.stdout.write(f"\r{spinner_chars[i % len(spinner_chars)]} Working...")
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1
    sys.stdout.write("\r" + " " * 20 + "\r")  # Clear the line


def run_command(cmd: Union[List[str], str], timeout=300, retries=1, show_progress=False, shell=False, cwd=None) -> RunResult:
    """Execute a command with proper error handling and progress tracking."""
    
    cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
    if LOG.verbose:
        cprint(f"Running: {cmd_str}", "INFO")
    
    for attempt in range(retries + 1):
        if attempt > 0:
            cprint(f"Retry attempt {attempt}/{retries}", "WARNING")
            time.sleep(2)
        
        try:
            # Start the process
            if shell:
                process = subprocess.Popen(
                    cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, cwd=cwd, bufsize=1, universal_newlines=True
                )
            else:
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, cwd=cwd, bufsize=1, universal_newlines=True
                )
            
            if show_progress and not LOG.json_mode:
                # Show progress dots for long-running commands
                progress_thread = threading.Thread(target=_show_progress_dots, args=(process,))
                progress_thread.daemon = True
                progress_thread.start()
            
            # Wait for completion
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                return RunResult(False, -1, stdout, f"Command timed out after {timeout} seconds")
            
            result = RunResult(
                ok=(process.returncode == 0),
                code=process.returncode,
                out=stdout,
                err=stderr
            )
            
            if LOG.verbose and not result.ok:
                cprint(f"Command failed with exit code {result.code}", "ERROR")
                if result.err:
                    cprint(f"Error output: {result.err[:500]}", "ERROR")
            
            return result
            
        except Exception as e:
            if attempt == retries:
                return RunResult(False, -1, "", f"Exception: {str(e)}")
            time.sleep(1)
    
    return RunResult(False, -1, "", "All retry attempts failed")