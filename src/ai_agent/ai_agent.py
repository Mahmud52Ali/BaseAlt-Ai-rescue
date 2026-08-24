from .diagnosis import run_diagnosis
from .planning import run_planning
from .repair import run_repair


def confirm_partial_planning() -> bool:
    print(
        "Найдена критическая ошибка, но диагностический отчет неполный.\n"
        "Можно составить частичный план только для уже подтвержденных ошибок."
    )
    answer = input("Начать частичное планирование? (y/n): ").strip().lower()
    return answer == "y"


def confirm_repair() -> bool:
    print(
        "План лечения готов. Следующий этап будет чинить систему "
    )
    answer = input("Начать починку? (y/n): ").strip().lower()
    return answer == "y"


def run_planning_phase(blocking_findings: list) -> dict | None:
    result = run_planning(blocking_findings)

    if result is None:
        print("[!] Limits iterations exceeded during planning phase.")
        return None

    if result.get("ok") is False:
        print("Planning error:", result.get("error"))
    elif result.get("decision") == "PLANNING_COMPLETE":
        print("Planning result:", result.get("steps"))
    elif result.get("decision") == "PLANNING_INCOMPLETE":
        print("Planning is incomplete:", result.get("steps"))
    else:
        print("Unknown planning decision:", result.get("decision"))

    return result


def run_AI(findings_path: str = "findings.json") -> dict | None:
    diagnosis_result = run_diagnosis(findings_path)

    if diagnosis_result is None:
        print("[!] Limits iterations exceeded during diagnosis phase.")
        return None

    if not diagnosis_result.get("ok"):
        print("Report error:", diagnosis_result.get("error"))
        return None

    decision = diagnosis_result.get("decision")

    if decision == "REPORT_INCONCLUSIVE":
        print("Report is inconclusive. Some findings could not be verified.")
        return None

    if decision == "NO_BOOT_BLOCKERS":
        print("No boot-critical findings were confirmed.")
        return None

    if decision == "START_PARTIAL_REPAIR_PLANNING":
        if not confirm_partial_planning():
            print("Partial planning was cancelled.")
            return None
    elif decision != "START_REPAIR_PLANNING":
        print("Unknown diagnosis decision:", decision)
        return None

    blocking_findings = diagnosis_result.get("blocking_findings", [])
    planning_result = run_planning_phase(blocking_findings)

    if (
        planning_result is None
        or planning_result.get("decision") != "PLANNING_COMPLETE"
    ):
        return None

    repair_input = {
        "blocking_findings": blocking_findings,
        "steps": planning_result["steps"],
    }

    if not confirm_repair():
        print("Repair was cancelled.")
        return None

    return run_repair(repair_input)


if __name__ == "__main__":
    run_AI("findings-latest.json")
