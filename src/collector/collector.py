import json
import os
import sys
from datetime import datetime

from boot_selector import select_previous_system_boot
from journal_scanner import scan_boot


DEFAULT_OUTPUT_DIR = "/var/log/alt-ai-rescue"
RUNTIME_OUTPUT_DIR = "/run/alt-ai-rescue"


def output_directories():
    override = os.environ.get("ALT_AI_RESCUE_LOG_DIR")
    return [override] if override else [DEFAULT_OUTPUT_DIR, RUNTIME_OUTPUT_DIR]


def diagnostic_finding(message, source):
    return {
        "message": message,
        "source": source,
        "priority": None,
        "priority_name": "diagnostic",
        "count": 1,
    }


def build_findings():
    boot, warnings, selection_error = select_previous_system_boot()
    limitations = list(warnings)
    stats = {}

    if selection_error:
        limitations.append(selection_error)
        findings = [diagnostic_finding(
            "Previous system boot could not be selected: %s" % selection_error,
            "journalctl --list-boots",
        )]
    else:
        findings, stats, scan_error = scan_boot(boot["boot_id"])
        if scan_error:
            limitations.append(scan_error)
            findings = [diagnostic_finding(
                "Previous system boot journal could not be read: %s" % scan_error,
                "journalctl -b %s" % boot["boot_id"],
            )]
        else:
            if stats.get("invalid_json_lines"):
                limitations.append(
                    "%d journal records were not valid JSON"
                    % stats["invalid_json_lines"]
                )
            if not findings:
                findings = [diagnostic_finding(
                    "No error candidates were found in the previous system boot journal.",
                    "journalctl -b %s" % boot["boot_id"],
                )]

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "collection_status": "partial" if limitations else "complete",
        "target_boot": boot,
        "limitations": limitations,
        "scan": stats,
        "findings": findings,
    }


def write_findings(result):
    failures = []
    for directory in output_directories():
        path = os.path.join(directory, "findings-latest.json")
        temporary = path + ".tmp"
        try:
            os.makedirs(directory, mode=0o700, exist_ok=True)
            os.chmod(directory, 0o700)
            with open(temporary, "w", encoding="utf-8") as stream:
                json.dump(result, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
            return path, failures
        except OSError as error:
            failures.append("%s: %s" % (directory, error))
            try:
                os.unlink(temporary)
            except OSError:
                pass
    return None, failures


def main():
    os.umask(0o077)
    result = build_findings()
    path, failures = write_findings(result)
    if path is None:
        print("Cannot write findings: %s" % "; ".join(failures), file=sys.stderr)
        return 1

    print("Previous system boot:", end=" ")
    if result["target_boot"]:
        print("%s (%s)" % (
            result["target_boot"]["index"],
            result["target_boot"]["boot_id"],
        ))
    else:
        print("unavailable")
    print("Error candidates: %d" % len(result["findings"]))
    print("Findings written to: %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
