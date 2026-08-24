"""Extract compact error candidates from one historical system journal."""

import json
import re
import subprocess


MAX_FINDINGS = 40
MAX_MESSAGE_CHARS = 500
WARNING_PATTERN = re.compile(
    r"\b(?:BUG|fail(?:ed|ure)?|fatal|error|invalid|panic|oops|timeout|timed\s+out|"
    r"dependency|emergency|corrupt(?:ed|ion)?|read[- ]only|segfault|"
    r"out\s+of\s+memory|oom(?:-kill)?|watchdog|lockup|hung\s+task|"
    r"unable|cannot|denied|refused|unreachable|not\s+found)\b|"
    r"\bI/O\s+error\b|\bno\s+such\s+file\b",
    re.IGNORECASE,
)
BOOT_PATTERN = re.compile(
    r"failed to mount|dependency failed|timed out waiting for (?:device|mount)|"
    r"emergency mode|local-fs\.target|fstab|fsck|filesystem|read[- ]only|"
    r"I/O error|no space left|out of memory|failed to start|"
    r"target .*failed|\.mount\b|\.device\b|cryptsetup|LUKS|UUID=|/dev/",
    re.IGNORECASE,
)
LOGIN_PATTERN = re.compile(
    r"display-manager|gdm|sddm|lightdm|xdm|greeter|login|pam|"
    r"xorg|xwayland|wayland|graphical\.target",
    re.IGNORECASE,
)
FATAL_PATTERN = re.compile(
    r"segfault|core dump|out of memory|oom(?:-kill)?|fatal|crash",
    re.IGNORECASE,
)
KNOWN_NOISE_PATTERN = re.compile(
    r"org\.freedesktop\.portal|dconf-WARNING|"
    r"could(?:n't| not) list homed users|org\.freedesktop\.home1.*ServiceUnknown",
    re.IGNORECASE,
)
UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
MESSAGE_MASKS = (
    (UUID_PATTERN, "<UUID>"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}\S*"), "<TIME>"),
    (re.compile(r"\b(?:pid|ppid|tid|process)\s*[=:]?\s*\d+\b", re.I), "<PROCESS>"),
    (re.compile(r"(?<=\[)\d+(?=\])"), "<NUM>"),
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), "<HEX>"),
    (re.compile(r"\b[0-9a-fA-F]{12,}\b"), "<HEX>"),
    (re.compile(r"\b\d+(?:\.\d+)?\s*(?:us|ms|sec|secs|seconds|minutes)\b", re.I), "<DURATION>"),
    (re.compile(r"\b\d{4,}\b"), "<NUM>"),
)
PRIORITY_NAMES = {
    0: "emerg",
    1: "alert",
    2: "crit",
    3: "err",
    4: "warning",
    5: "notice",
    6: "info",
    7: "debug",
}


def run_journalctl(arguments, timeout=90):
    return subprocess.run(
        ["journalctl"] + arguments,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def decode_message(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        try:
            return bytes(value).decode("utf-8", errors="replace")
        except (TypeError, ValueError):
            return str(value)
    return str(value or "")


def normalize_message(message):
    return " ".join(message.split())[:MAX_MESSAGE_CHARS]


def message_template(message):
    template = message
    for pattern, replacement in MESSAGE_MASKS:
        template = pattern.sub(replacement, template)
    return template


def record_source(record):
    return str(
        record.get("UNIT")
        or record.get("_SYSTEMD_UNIT")
        or record.get("_SYSTEMD_USER_UNIT")
        or record.get("SYSLOG_IDENTIFIER")
        or record.get("_COMM")
        or record.get("_TRANSPORT")
        or "journal"
    )


def out_of_scope(record):
    """Kernel and initramfs diagnostics are outside this recovery layer."""
    if record.get("_TRANSPORT") == "kernel":
        return True
    for field in ("UNIT", "_SYSTEMD_UNIT", "SYSLOG_IDENTIFIER", "_COMM"):
        value = str(record.get(field) or "").lower()
        if value.startswith("initrd") or value.startswith("dracut"):
            return True
    return False


def user_scope(record, source):
    if record.get("_SYSTEMD_USER_UNIT"):
        return True
    source = source.lower()
    return source.startswith(("session-", "user@", "user-runtime-dir@", "app-"))


def relevant_record(record, priority, source, message):
    if KNOWN_NOISE_PATTERN.search(message):
        return False
    if user_scope(record, source):
        return bool(
            FATAL_PATTERN.search(message)
            or (LOGIN_PATTERN.search("%s %s" % (source, message))
                and WARNING_PATTERN.search(message))
        )
    return priority <= 3 or bool(WARNING_PATTERN.search(message))


def finding_score(finding):
    priority = finding["priority"]
    score = max(0, 7 - priority) * 100
    text = "%s %s" % (finding["source"], finding["message"])
    if BOOT_PATTERN.search(text):
        score += 500
    if FATAL_PATTERN.search(text):
        score += 300
    if LOGIN_PATTERN.search(text) and WARNING_PATTERN.search(text):
        score += 250
    return score + min(finding["count"], 50)


def finding_sort_key(finding):
    return (
        -finding_score(finding),
        finding["priority"],
        -finding["count"],
        finding["source"],
        finding["message"],
    )


def select_findings(findings, limit=MAX_FINDINGS):
    ordered = sorted(findings, key=finding_sort_key)
    if limit is None or len(ordered) <= limit:
        return ordered

    selected = [finding for finding in ordered if finding["priority"] <= 2]
    if len(selected) >= limit:
        return selected

    selected_ids = {id(finding) for finding in selected}
    for finding in ordered:
        if len(selected) >= limit:
            break
        if id(finding) not in selected_ids:
            selected.append(finding)
            selected_ids.add(id(finding))

    return sorted(selected, key=finding_sort_key)


def parse_records(output):
    records = []
    invalid_lines = 0
    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            invalid_lines += 1
            continue
        if isinstance(record, dict):
            records.append(record)
        else:
            invalid_lines += 1
    return records, invalid_lines


def aggregate_findings(records):
    findings = {}
    matched_records = 0

    for record in records:
        if out_of_scope(record):
            continue
        try:
            priority = int(record.get("PRIORITY", 4))
        except (TypeError, ValueError):
            priority = 4

        message = normalize_message(decode_message(record.get("MESSAGE")))
        if not message:
            continue
        source = record_source(record)
        if not relevant_record(record, priority, source, message):
            continue

        matched_records += 1
        resources = tuple(sorted(set(UUID_PATTERN.findall(message))))
        key = (source, message_template(message), resources)
        if key not in findings:
            findings[key] = {
                "message": message,
                "source": source,
                "priority": priority,
                "priority_name": PRIORITY_NAMES.get(priority, "unknown"),
                "count": 0,
            }
        elif priority < findings[key]["priority"]:
            findings[key]["priority"] = priority
            findings[key]["priority_name"] = PRIORITY_NAMES.get(
                priority, "unknown"
            )
        findings[key]["count"] += 1

    return list(findings.values()), matched_records


def extract_findings(records):
    findings, _matched_records = aggregate_findings(records)
    return select_findings(findings)


def scan_boot(boot_id, run=run_journalctl):
    try:
        process = run([
            "-b", boot_id,
            "-o", "json",
            "--no-pager",
            "--quiet",
        ])
    except (OSError, subprocess.TimeoutExpired) as error:
        return [], {}, "journal scan failed: %s" % error

    if process.returncode != 0:
        detail = process.stderr.strip() or "exit code %d" % process.returncode
        return [], {}, "journal scan failed: %s" % detail

    records, invalid_lines = parse_records(process.stdout)
    templates, matched_records = aggregate_findings(records)
    findings = select_findings(templates)
    stats = {
        "journal_records": len(records),
        "matched_records": matched_records,
        "templates_total": len(templates),
        "error_candidates": len(findings),
        "truncated_findings": max(0, len(templates) - len(findings)),
        "invalid_json_lines": invalid_lines,
    }
    return findings, stats, None
