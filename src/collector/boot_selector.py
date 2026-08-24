import re
import subprocess


BOOT_LINE_RE = re.compile(r"^\s*(-?\d+)\s+([0-9a-fA-F]{32})\b")
RESCUE_UNIT = "alt-ai-rescue.service"


def run_journalctl(arguments, timeout=60):
    return subprocess.run(
        ["journalctl"] + arguments,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def parse_boot_list(output):
    boots = []
    for line in output.splitlines():
        match = BOOT_LINE_RE.match(line)
        if match:
            boots.append({
                "index": int(match.group(1)),
                "boot_id": match.group(2).lower(),
            })
    return boots


def list_boots(run=run_journalctl):
    try:
        process = run(["--list-boots", "--no-pager", "--quiet"])
    except (OSError, subprocess.TimeoutExpired) as error:
        return [], "journalctl --list-boots failed: %s" % error

    if process.returncode != 0:
        detail = process.stderr.strip() or "exit code %d" % process.returncode
        return [], "journalctl --list-boots failed: %s" % detail

    boots = parse_boot_list(process.stdout)
    if not boots:
        return [], "journalctl did not return any boot records"
    return boots, None


def is_rescue_boot(boot_id, run=run_journalctl):
    try:
        process = run([
            "-b", boot_id,
            "-u", RESCUE_UNIT,
            "-n", "1",
            "-o", "cat",
            "--no-pager",
            "--quiet",
        ])
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, "cannot classify boot %s: %s" % (boot_id, error)

    if process.returncode != 0:
        detail = process.stderr.strip() or "exit code %d" % process.returncode
        return False, "cannot classify boot %s: %s" % (boot_id, detail)
    return bool(process.stdout.strip()), None


def select_previous_system_boot(run=run_journalctl):
    boots, error = list_boots(run)
    if error:
        return None, [], error

    warnings = []
    candidates = sorted(
        (boot for boot in boots if boot["index"] < 0),
        key=lambda boot: boot["index"],
        reverse=True,
    )

    for boot in candidates:
        rescue, warning = is_rescue_boot(boot["boot_id"], run)
        if warning:
            warnings.append(warning)
        if not rescue:
            selected = dict(boot)
            selected["selection"] = "latest boot without ALT AI Rescue service"
            return selected, warnings, None

    return None, warnings, "no previous system boot was found"
