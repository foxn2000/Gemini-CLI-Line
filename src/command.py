import subprocess
import sys
import shutil
from pathlib import Path
from typing import Optional

def execute_command(command: str, workdir: Optional[str | Path] = None) -> str:
    """
    Execute a shell command and return its output.
    On Windows, it uses PowerShell. On other systems, it uses the default shell.

    Parameters
    ----------
    command : str
        The command to execute.
    workdir : str | pathlib.Path | None, optional
        Directory in which to run the command. If None, uses the caller's
        current working directory.

    Returns
    -------
    str
        The combined standard output and standard error from the command.
    """
    if not isinstance(command, str):
        raise ValueError("command must be a str")

    # Resolve and validate the working directory if supplied
    cwd: Optional[Path] = None
    if workdir is not None:
        cwd = Path(workdir).expanduser().resolve()
        if not cwd.is_dir():
            return f"Error: Directory '{cwd}' not found."

    # Determine the executable shell based on the operating system
    executable_shell: Optional[str] = None
    if sys.platform == "win32":
        # On Windows, prefer modern PowerShell (pwsh) if available, 
        # otherwise use the older powershell.exe.
        # shutil.which finds the path to the executable.
        executable_shell = shutil.which("pwsh") or shutil.which("powershell")
        if not executable_shell:
             return "Error: PowerShell is not installed or not in the system's PATH."


    try:
        # Use shell=True to interpret the command string.
        # On Windows, explicitly set the executable to PowerShell.
        # On other OSes, executable_shell remains None, so it uses the default shell (e.g., /bin/sh).
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd is not None else None,
            check=False,
            executable=executable_shell,
            # Explicitly set encoding to UTF-8 to prevent garbled text (mojibake),
            # as PowerShell often outputs in UTF-8.
            encoding='utf-8',
            errors='replace'  # Replace characters that cannot be decoded
        )
        
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()

        if stdout and stderr:
            return f"--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}"
        elif stdout:
            return stdout
        elif stderr:
            return stderr
        else:
            return "Command executed successfully with no output."

    except Exception as e:
        return f"An unexpected error occurred: {e}"