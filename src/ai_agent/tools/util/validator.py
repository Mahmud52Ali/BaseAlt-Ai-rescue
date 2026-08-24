from dataclasses import dataclass
import shlex


READ_ONLY_COMMANDS = {
    "cat",
    "grep",
    "head",
    "tail",
    "cut",
    "wc",
    "sort",
    "uniq",
    "ls",
    "stat",
    "file",
    "readlink",
    "findmnt",
    "df",
    "du",
    "lsblk",
    "blkid",
    "journalctl",
    "dmesg",
    "uname",
    "ps",
    "free",
    "uptime",
    "systemctl",
    "find",
}


@dataclass
class ValidationResult:
    allowed: bool
    error: str | None = None
    commands: list[list[str]] | None = None


def validate_arguments(command: str, args: list[str]) -> str | None:

    if command == "journalctl":
        for arg in args:
            if (
                arg.startswith("--vacuum-")
                or arg in {"--rotate", "--flush", "--sync"}
            ):
                return f"journalctl argument modifies logs: {arg}"

    if command == "systemctl":
        allowed = {
        "status",
        "show",
        "cat",
        "is-active",
        "is-failed",
        "is-enabled",
        "list-units",
        "list-unit-files",
        "list-dependencies",
        "get-default",
        }

        if not args:
            return " systemctl action is required"

        action = args[0]

        if action not in allowed:
            return f"systemctl action is not allowed: {action}. "


    if command == "find":
        forbidden = {
        "-delete",
        "-exec",
        "-execdir",
        "-ok",
        "-okdir",
        "-fprint",
        "-fprint0",
        "-fprintf",
        "-fls",
        }

        for arg in args:
            if arg in forbidden:
                return f"find option is not allowed: {arg}"


    if command == "dmesg":
        forbidden = {
            "-c",
            "-C",
            "--clear",
            "--read-clear",
            "--console-on",
            "--console-off",
        }

        for arg in args:
            if arg in forbidden:
                return f"dmesg argument modifies system state: {arg}"

    if command == "blkid":
        for arg in args:
            if arg in {"-g", "--garbage-collect"}:
                return f"blkid argument modifies cache: {arg}"

    return None


def validate(command: str) -> ValidationResult:
    if not isinstance(command, str):
        return ValidationResult(
            allowed=False,
            error="Command must be a string.",
        )

    command = command.strip()

    if not command:
        return ValidationResult(
            allowed=False,
            error="Command is empty.",
        )

    if "\x00" in command:
        return ValidationResult(
            allowed=False,
            error="Command contains a NUL byte.",
        )

    try:
        lexer = shlex.shlex(
            command,
            posix=True,
            punctuation_chars="|;&<>",
        )
        lexer.whitespace_split = True
        lexer.commenters = ""

        tokens = list(lexer)

    except ValueError as error:
        return ValidationResult(
            allowed=False,
            error=f"Invalid command syntax: {error}",
        )

    commands: list[list[str]] = [[]]

    for token in tokens:
        is_operator = (
            token
            and all(char in "|;&<>" for char in token)
        )

        if is_operator:
            if token != "|":
                return ValidationResult(
                    allowed=False,
                    error=f"Shell operator is forbidden: {token}",
                )

            if not commands[-1]:
                return ValidationResult(
                    allowed=False,
                    error="Empty command before pipe.",
                )

            commands.append([])
            continue

        commands[-1].append(token)

    if not commands[-1]:
        return ValidationResult(
            allowed=False,
            error="Empty command after pipe.",
        )

    for args in commands:
        executable = args[0]

        if "/" in executable:
            return ValidationResult(
                allowed=False,
                error=f"Executable paths are forbidden: {executable}",
            )

        if executable not in READ_ONLY_COMMANDS:
            return ValidationResult(
                allowed=False,
                error=f"Command is not allowed: {executable}",
            )

        argument_error = validate_arguments(
            executable,
            args[1:],
        )

        if argument_error:
            return ValidationResult(
                allowed=False,
                error=argument_error,
            )

    return ValidationResult(
        allowed=True,
        commands=commands,
    )