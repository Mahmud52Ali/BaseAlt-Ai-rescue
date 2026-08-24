import json

from .llm_client import query_llm
from .tools.tools import REPORT_TOOL_SCHEMA, TOOL_MAP, TOOLS_SCHEMA


def request_verification_report(messages):
    messages.append({
        "role": "user",
        "content": (
            "Submit your final analysis using submit_verification_report. "
            "Set complete=false if any finding was not checked."
        ),
    })

    last_error = "Report was not submitted."

    for n in range(2):
        print(
            f"\n--- [ОТЧЁТ] Попытка формирования отчёта {n + 1}/2 ---"
        )
        message = query_llm(
            messages,
            tools=[REPORT_TOOL_SCHEMA],
            tool_choice="required",
        )
        messages.append(message)
        calls = message.get("tool_calls") or []

        if len(calls) != 1:
            last_error = "Expected one report tool call."
            messages.append({"role": "user", "content": last_error})
            continue

        call = calls[0]
        try:
            if call["function"]["name"] != "submit_verification_report":
                raise KeyError("Unexpected tool name.")
            arguments = json.loads(call["function"]["arguments"])
            result = TOOL_MAP[call["function"]["name"]](**arguments)
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            result = {"ok": False, "error": str(error)}

        messages.append({
            "role": "tool",
            "tool_call_id": call["id"],
            "name": call["function"]["name"],
            "content": json.dumps(result, ensure_ascii=False),
        })

        if result.get("ok"):
            return result

        last_error = result["error"]
        messages.append({
            "role": "user",
            "content": f"Fix the report: {last_error}",
        })

    return {
        "ok": False,
        "decision": "REPORT_FAILED",
        "error": last_error,
    }


def run_diagnosis(findings_path: str = "findings.json"):
    print("=== [ЭТАП 1] Запуск проверки первичного отчета ===")

    system_prompt = (
    "You are a Linux recovery verification agent.\n"
    "Your task is to verify every finding listed in the findings file.\n"
    "Use that file only as the list of problems to verify.\n"
    "Do not search for new problems and do not propose repairs.\n"
    "\n"
    "Use target_boot.boot_id from the findings file when examining logs.\n"
    "Historical boot logs must be accessed using journalctl -b BOOT_ID.\n"
    "Never search /var/log for a file containing the boot ID.\n"
    "Never use /var/log/boot.log.\n"
    "Never use old files from /var/log/alt-ai-rescue/cases.\n"
    "Do not request the entire journal. Filter it by unit, priority, "
    "message pattern, or number of records.\n"
    "\n"
    "Use commands such as:\n"
    "journalctl -b BOOT_ID -u UNIT -n 50 --no-pager -o cat\n"
    "journalctl -b BOOT_ID -p err -n 100 --no-pager -o cat\n"
    "journalctl -b BOOT_ID --grep=PATTERN -n 50 --no-pager -o cat\n"
    "\n"
    "Use read_file for relevant configuration files such as /etc/fstab.\n"
    "Use execute_cmd_r only for read-only verification commands.\n"
    "Do not use shell redirections such as 2>&1.\n"
    "Never repeat an identical tool call or command.\n"
    "\n"
    "If a command fails or returns empty output, do not repeat it.\n"
    "Try one different verification method.\n"
    "If evidence is still unavailable, mark the finding UNKNOWN and continue.\n"
    "\n"
    "If a finding has count greater than 1, it represents repeated occurrences "
    "of the same error pattern. Verify the pattern once.\n"
    "\n"
    "For every input finding return exactly one result.\n"
    "Set verdict to CONFIRMED, REFUTED, or UNKNOWN.\n"
    "Set boot_critical to YES, NO, or UNKNOWN.\n"
    "Evidence must contain the exact command or file examined, the relevant "
    "observed output, and an explanation of what it proves.\n"
    "Do not finish until every input finding has a result.\n"
)

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Read {findings_path} and verify every finding. "
                "Use the available tools as needed. Return a final verdict for each finding."
            ),
        },
    ]

    for step in range(1, 26):
        print(f"\n--- [Итерация {step}] Запрос к ИИ... ---")

        message = query_llm(messages, tools=TOOLS_SCHEMA)
        messages.append(message)
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            result = request_verification_report(messages)
            print("\n==================================================")
            print("        ИТОГОВЫЙ ВЕРДИКТ ПРОВЕРКИ (ЭТАП 1)        ")
            print("==================================================")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return result

        for call in tool_calls:
            call_id = call["id"]
            function_name = call["function"]["name"]

            try:
                arguments = json.loads(call["function"]["arguments"])
            except json.JSONDecodeError:
                arguments = {}

            print(f"[ИИ ВЫЗЫВАЕТ]: {function_name}({arguments})")

            if function_name in TOOL_MAP:
                output = TOOL_MAP[function_name](**arguments)
            else:
                output = f"Ошибка: Функция {function_name} не найдена."

            print(f"[ОТВЕТ ИНСТРУМЕНТА]: {str(output)[:120].strip()}...")
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "name": function_name,
                "content": str(output),
            })

    print("[!] Превышен лимит итераций.")
    return None
