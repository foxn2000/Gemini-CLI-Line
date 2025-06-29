import subprocess
from pathlib import Path
from typing import Optional, Final

def run_gemini(prompt: str, workdir: Optional[str | Path] = None) -> str:
    """
    Execute `gemini -p '{prompt}' -yolo` and return its standard output.

    Parameters
    ----------
    prompt : str
        Natural-language prompt passed after the -p flag.
    workdir : str | pathlib.Path | None, optional
        Directory in which to run the command. If None, uses the caller's
        current working directory.

    Returns
    -------
    str
        Standard output produced by the Gemini CLI.

    Raises
    ------
    ValueError
        If *prompt* is not a string.
    FileNotFoundError
        If 'gemini' executable is absent or *workdir* is invalid.
    RuntimeError
        If the command exits with non-zero status or another OS error occurs.
    """
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a str")

    # Resolve and validate the working directory if supplied
    cwd: Optional[Path] = None
    if workdir is not None:
        cwd = Path(workdir).expanduser().resolve()
        if not cwd.is_dir():
            raise FileNotFoundError(f"workdir '{cwd}' is not an existing directory")

    # Build the argument list; using list form prevents shell injection
    CMD: Final[list[str]] = ["gemini", "-p", prompt, "-y"]

    try:
        completed = subprocess.run(
            CMD,
            capture_output=True,  # capture stdout/stderr
            text=True,            # decode bytes → str
            cwd=str(cwd) if cwd is not None else None,
            check=False           # manual error handling
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "Executable 'gemini' not found. Is Gemini CLI installed?"
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"OS error while running gemini: {exc}") from exc

    if completed.returncode != 0:
        raise RuntimeError(
            f"gemini exited with status {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )

    return completed.stdout