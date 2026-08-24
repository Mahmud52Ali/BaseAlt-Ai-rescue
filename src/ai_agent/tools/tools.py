import subprocess
from ai_agent.tools.util.validator import validate

MAX_COMMAND_OUTPUT = 4_000
MAX_COMMAND_OUTPUT_FOR_READ = 50_000

# stop process
def stop_processes(processes):
    for process in processes:
        if process.poll() is None:
            process.kill()

    for process in processes:
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass

# read by path
def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding = "utf-8", errors="replace") as f:
            content = f.read(MAX_COMMAND_OUTPUT_FOR_READ + 1)
            if len(content) > MAX_COMMAND_OUTPUT_FOR_READ:
                return (
                    f"OUTPUT_TO_LARGE: file exceeds {MAX_COMMAND_OUTPUT_FOR_READ} characters. "
                    "Use execute_cmd_r with grep, head or tail to read_only "
                )
            return content if content else "file is empty."
    except Exception as e:
        return f"file read error '{path}': {e}"

# execute read-only command
def execute_cmd_r(command: str) -> str:
    validation = validate(command)

    if not validation.allowed:
        return (
            "Security error: command rejected. "
            f"Reason: {validation.error}"
        )

    commands = validation.commands

    if not commands:
        return "Security error: validator returned no commands."

    processes = []
    previous_stdout = None

    try:
        for args in commands:
            process = subprocess.Popen(
                args,
                stdin=previous_stdout or subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            if previous_stdout is not None:
                previous_stdout.close()

            previous_stdout = process.stdout
            processes.append(process)

        output, _ = processes[-1].communicate(timeout=25)

        for process in processes[:-1]:
            process.wait(timeout=2)

        if not output:
            return "Command successfully completed, but output is empty."

        if len(output) > MAX_COMMAND_OUTPUT:
            return (
                f"OUTPUT_TOO_LARGE: command produced {len(output)} characters, "
                f"limit is {MAX_COMMAND_OUTPUT}. "
                "Retry with a narrower command using grep, head, tail, "
                "or journalctl filters such as -p, -u, -n, --since or --until."
            )

        return output
    except FileNotFoundError as error:
        return f"Error: command '{error.filename}' not found in system."

    except subprocess.TimeoutExpired:
        for process in processes:
            process.kill()

        for process in processes:
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass

        return "Error: command execution timeout."

    except Exception as error:
        for process in processes:
            if process.poll() is None:
                process.kill()

        return f"Error executing command: {error}"


# execute all command
def execute_cmd_wr(command: str) -> str:
    if not isinstance(command, str) or not command.strip():
        return "Error: command must be a non-empty string."

    try:
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=25,
        )
    except subprocess.TimeoutExpired:
        return "Error: command execution timeout."
    except Exception as error:
        return f"Error executing command: {error}"

    output = result.stdout or ""

    if len(output) > MAX_COMMAND_OUTPUT:
        return (
            f"OUTPUT_TOO_LARGE: command produced {len(output)} characters, "
            f"limit is {MAX_COMMAND_OUTPUT}."
        )

    if not output:
        return f"Command completed with exit code {result.returncode}. Output is empty."

    return f"Exit code: {result.returncode}\n{output}"

# Report submission tool
def submit_verification_report(complete: bool, results: list) -> dict:
    if not results:
        return {
            "ok": False,
            "error": "Results list cannot be empty.",
        }
    if not isinstance(complete, bool) or not isinstance(results, list):
        return {"ok": False, "error": "Invalid report format."}

    required = {"finding", "verdict", "boot_critical", "evidence"}
    for result in results:
        if not isinstance(result, dict) or not required.issubset(result):
            return {"ok": False, "error": "Invalid finding format."}
        if not isinstance(result["finding"], str) or not result["finding"].strip():
            return {"ok": False, "error": "Finding description is required."}
        if result["verdict"] not in {"CONFIRMED", "REFUTED", "UNKNOWN"}:
            return {"ok": False, "error": "Invalid verdict."}
        if result["boot_critical"] not in {"YES", "NO", "UNKNOWN"}:
            return {"ok": False, "error": "Invalid boot_critical value."}
        if result["verdict"] == "REFUTED" and result["boot_critical"] != "NO":
            return {"ok": False, "error": "A refuted finding cannot be boot-critical."}
        if not isinstance(result["evidence"], str) or not result["evidence"].strip():
            return {"ok": False, "error": "Evidence is required."}

    blockers = [
        dict(result) for result in results
        if result["verdict"] == "CONFIRMED"
        and result["boot_critical"] == "YES"
    ]
    uncertain = any(
        result["boot_critical"] == "UNKNOWN"
        or (result["verdict"] == "UNKNOWN" and result["boot_critical"] != "NO")
        for result in results
    )

    if blockers and complete:
        decision = "START_REPAIR_PLANNING"
    elif blockers and not complete:
        decision = "START_PARTIAL_REPAIR_PLANNING"
    elif not complete or uncertain:
        decision = "REPORT_INCONCLUSIVE"
    else:
        decision = "NO_BOOT_BLOCKERS"

    return {
        "ok": True,
        "decision": decision,
        "blocking_findings": blockers,
        "results": results,
    }

def submit_planning_report(complete: bool, steps: list) -> dict:
    if not isinstance(complete, bool) or not isinstance(steps, list):
        return {"ok": False, "error": "Invalid report format."}

    required = {"step", "action", "evidence"}
    for step in steps:
        if not isinstance(step, dict) or not required.issubset(step):
            return {"ok": False, "error": "Invalid step format."}
        if not isinstance(step["step"], int) or step["step"] < 1:
            return {"ok": False, "error": "Step number must be a positive integer."}
        if not isinstance(step["action"], str) or not step["action"].strip():
            return {"ok": False, "error": "Action description is required."}
        if not isinstance(step["evidence"], str) or not step["evidence"].strip():
            return {"ok": False, "error": "Evidence is required."}
    if not steps:
        return {"ok": False, "error": "Steps list cannot be empty."}
    return {
        "ok": True,
        "decision": "PLANNING_COMPLETE" if complete else "PLANNING_INCOMPLETE",
        "steps": steps,
    }

def submit_repair_report(repaired: bool, summary: str) -> dict:
    if not isinstance(repaired, bool) or not isinstance(summary, str):
        return {"ok": False, "error": "Invalid report format."}
    if not summary.strip():
        return {"ok": False, "error": "Repair summary is required."}

    return {
        "ok": True,
        "decision": "REPAIR_COMPLETE" if repaired else "REPAIR_FAILED",
        "summary": summary,
    }

TOOL_MAP = {
    "read_file": read_file,
    "execute_cmd_r": execute_cmd_r,
    "execute_cmd_wr": execute_cmd_wr,
    "submit_verification_report": submit_verification_report,
    "submit_planning_report": submit_planning_report,
    "submit_repair_report": submit_repair_report,
}

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Прочитать содержимое файла в Linux (например: /etc/fstab, /var/log/syslog, findings.json).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Абсолютный или относительный путь к файлу"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_cmd_r",
            "description": (
                "Execute an allowed read-only Linux command. "
                "Shell operators and redirections such as >, 2>, ||, && and ; "
                "are not supported. Stderr is returned automatically. "
                "Prefer filtered journalctl commands."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Команда для выполнения"}
                },
                "required": ["command"]
            }
        }
    }
]

REPAIR_TOOLS_SCHEMA = [
    TOOLS_SCHEMA[0],
    {
        "type": "function",
        "function": {
            "name": "execute_cmd_wr",
            "description": (
                "Execute an unrestricted Linux shell command. "
                "Pipes, redirections, command chains, and commands that modify "
                "the system are allowed. Stderr and the exit code are returned."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute",
                    }
                },
                "required": ["command"],
            },
        },
    },
]

REPORT_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "submit_verification_report",
        "description": "Submit the final verification report.",
        "parameters": {
            "type": "object",
            "properties": {
                "complete": {
                    "type": "boolean",
                    "description": "True only if every finding was checked.",
                },
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "finding": {"type": "string"},
                            "verdict": {
                                "type": "string",
                                "enum": ["CONFIRMED", "REFUTED", "UNKNOWN"],
                            },
                            "boot_critical": {
                                "type": "string",
                                "enum": ["YES", "NO", "UNKNOWN"],
                            },
                            "evidence": {"type": "string"},
                        },
                        "required": [
                            "finding", "verdict", "boot_critical", "evidence"
                        ],
                    },
                },
            },
            "required": ["complete", "results"],
        },
    },
}

PLAN_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "submit_planning_report",
        "description": (
    "True if the repair plan covers every confirmed problem "
    "and is ready for execution."
),
        "parameters": {
            "type": "object",
            "properties": {
                "complete": {
                    "type": "boolean",
                    "description": (
                "True if the repair plan covers every confirmed problem "
                "and is ready for execution."
            ),
                },
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step": {"type": "integer"},
                            "action": {"type": "string"},
                            "evidence": {"type": "string"},
                        },
                        "required": ["step", "action", "evidence"],
                    },
                },
            },
            "required": ["complete", "steps"],
        },
    },
}

REPAIR_REPORT_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "submit_repair_report",
        "description": "Submit the final repair execution report.",
        "parameters": {
            "type": "object",
            "properties": {
                "repaired": {
                    "type": "boolean",
                    "description": (
                        "True if you believe the reported problem was repaired, "
                        "otherwise false."
                    ),
                },
                "summary": {
                    "type": "string",
                    "description": (
                        "Describe what was done, any adaptations or failures, "
                        "and the final observed system state."
                    ),
                },
            },
            "required": ["repaired", "summary"],
        },
    },
}
