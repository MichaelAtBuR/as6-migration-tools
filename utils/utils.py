# Utilities to call in multiple files
import concurrent.futures
import hashlib
import json
import os
import sys
from pathlib import Path

from CTkMessagebox import CTkMessagebox


class ConsoleColors:
    RESET = "\x1b[0m"  # Reset all formatting
    MANDATORY = "\x1b[1;31m"  # Set style to bold, red foreground.
    WARNING = "\x1b[1;33m"  # Set style to bold, yellow foreground.
    INFO = "\x1b[92m"  # Set style to light green foreground.


def get_build_number():
    try:
        version_file = Path(__file__).resolve().parent.parent / "version.txt"
        return version_file.read_text(encoding="utf-8").strip()
    except Exception:
        return "?"


def log(message, log_file=None, when="", severity=""):
    if when != "":
        message = f"[{when}] {message}"
    if severity != "":
        # Color highlighting based on severity level
        if severity.upper() == "MANDATORY" or severity.upper() == "ERROR":
            colored_severity = (
                f"{ConsoleColors.MANDATORY}[{severity}]{ConsoleColors.RESET}"
            )
        elif severity.upper() == "WARNING":
            colored_severity = (
                f"{ConsoleColors.WARNING}[{severity}]{ConsoleColors.RESET}"
            )
        elif severity.upper() == "INFO":
            colored_severity = f"{ConsoleColors.INFO}[{severity}]{ConsoleColors.RESET}"
        else:
            colored_severity = f"[{severity}]"

        # For console with color
        console_message = f"{colored_severity} {message}"
        # For file without color
        file_message = f"[{severity}] {message}"
    else:
        console_message = message
        file_message = message

    # Print to console with colors (with newline at start)
    print(
        f"\n{console_message}",
        file=(sys.stderr if severity.upper() == "ERROR" else sys.stdout),
    )
    if log_file:
        log_file.write(file_message + "\n")  # Write to file without colors
        log_file.flush()  # Ensure data is written immediately


def get_and_check_project_file(project_path):
    project_path = Path(project_path)
    if not project_path.exists():
        log(
            f"The provided project path does not exist: '{project_path}'"
            "\nEnsure the path is correct and the project folder exists."
            "\nIf the path contains spaces, make sure to wrap it in quotes, like this:"
            f'\n   python {os.path.basename(sys.argv[0])} "C:\\path\\to\\your\\project"',
            severity="ERROR",
        )
        sys.exit(1)

    # Check if .apj file exists in the provided path
    apj_file = next(project_path.glob("*.apj"), None)
    if not apj_file:
        log(
            f"No .apj file found in the provided path: {project_path}"
            "\nPlease specify a valid Automation Studio project path.",
            severity="ERROR",
        )
        sys.exit(1)

    return os.path.basename(apj_file)


def calculate_file_hash(file_path):
    """
    Calculates the hash (MD5) of a file for comparison purposes.
    """
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(4096):
            md5.update(chunk)
    return md5.hexdigest()


def ask_user(message, default="y", parent=None, extra_note=""):
    """
    Ask the user a yes/no question. Uses terminal input if no GUI context.
    """
    if parent is not None:
        cleaned_msg = (
            message.replace("(y/n)", "")
            .replace("[y]", "")
            .replace("[n]", "")
            .strip(": ")
            .strip()
        )
        result = ask_user_gui(cleaned_msg, extra_note=extra_note)
        choice = "y" if result else "n"
        log(f"{message} (User selected: '{choice}')", severity="INFO")
        return choice

    # Fallback to terminal
    try:
        if sys.stdin and sys.stdin.isatty():
            return input(message).strip().lower()
    except Exception as e:
        log(f"ask_user fallback triggered due to: {e}", severity="DEBUG")
    log(f"{message} (Automatically using default: '{default}')", severity="INFO")
    return default


def ask_user_gui(message: str, extra_note: str = "") -> bool:
    """
    Display a Yes/No confirmation popup using customtkinter.
    An optional extra_note can be provided for additional info.
    """
    final_message = f"{extra_note}\n\n" if extra_note else ""
    final_message += message
    msg = CTkMessagebox(
        title="Question",
        message=final_message,
        icon="question",
        option_1="Yes",
        option_2="No",
        width=460,
        wraplength=390,
    )
    response = msg.get()
    return response == "Yes"


def scan_files_parallel(root_dir, extensions, process_functions, *args):
    """
    Scans files in a directory tree in parallel for specific content.

    Args:
        root_dir (Path): The root directory to search in.
        extensions (list): File extensions to include.
        process_functions (callable or list): The function to apply on each file.
        *args: Additional arguments to pass to the process_function.

    Returns:
        dict or list: Aggregated results from all scanned files.
    """
    single_function_mode = not isinstance(process_functions, list)
    if single_function_mode:
        process_functions = [process_functions]

    results = {func.__name__: [] for func in process_functions}

    file_paths = [
        str(path)
        for ext in extensions
        for path in root_dir.rglob(f"*{ext}")
        if path.is_file()
    ]

    def process_file(path):
        file_results = {}
        for func in process_functions:
            file_results[func.__name__] = func(path, *args)
        return file_results

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(process_file, path): path for path in file_paths}
        for future in concurrent.futures.as_completed(futures):
            func_results = future.result()
            for func_name, result in func_results.items():
                results[func_name].extend(result)

    if single_function_mode:
        # Flatten results if only one function was used
        return results[process_functions[0].__name__]
    else:
        return results


def load_discontinuation_info(filename):
    try:
        root_path = Path(__file__).resolve().parent.parent
        discontinuation_dir = root_path / "discontinuations"
        file_path = discontinuation_dir / f"{filename}.json"
        with file_path.open("r", encoding="utf-8") as json_file:
            return json.load(json_file)
    except Exception as e:
        log(f"Error loading JSON file '{filename}': {e}", severity="ERROR")
        return {}
