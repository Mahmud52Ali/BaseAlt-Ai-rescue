import json

from .llm_client import query_llm
from .tools.tools import REPAIR_REPORT_TOOL_SCHEMA, REPAIR_TOOLS_SCHEMA, TOOL_MAP


def request_repair_report(messages):
    messages.append({
        "role": "user",
        "content": (
            "Submit the final repair result using submit_repair_report. "
            "State whether you believe the problem was repaired and summarize "
            "what happened."
        ),
    })

    last_error = "Repair report was not submitted."

    for attempt in range(2):
        print(
            f"\n--- [ОТЧЁТ] Попытка формирования отчёта о ремонте {attempt + 1}/2 ---"
        )
        message = query_llm(
            messages,
            tools=[REPAIR_REPORT_TOOL_SCHEMA],
            tool_choice="required",
        )
        messages.append(message)
        calls = message.get("tool_calls") or []

        if len(calls) != 1:
            last_error = "Expected one repair report tool call."
            messages.append({"role": "user", "content": last_error})
            continue

        call = calls[0]
        try:
            if call["function"]["name"] != "submit_repair_report":
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
            "content": f"Fix the repair report: {last_error}",
        })

    return {
        "ok": False,
        "decision": "REPAIR_REPORT_FAILED",
        "error": last_error,
    }


def run_repair(workflow_results: dict) -> dict | None:
    print("=== [ЭТАП 3] Запуск ремонта системы ===")

    system_prompt = (
        "You are a Linux recovery repair agent.\n"
        "The input contains confirmed boot-blocking problems and a proposed repair plan.\n"
        "Your task is to repair the current system using read_file and execute_cmd_wr.\n"
        "The diagnosis describes the goal; the proposed plan is guidance, not a mandatory checklist.\n"
        "Inspect the actual system state, execute suitable commands, observe their results, "
        "and adapt your approach whenever a command or assumption fails.\n"
        "A failed command is not the end of the repair: use its output to choose the next action.\n"
        "Continue until you believe the problem is repaired or no useful action remains.\n"
        "Verify the final system state when possible, then report your own conclusion.\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "Repair the confirmed problems using the proposed plan as guidance: "
                f"{json.dumps(workflow_results, ensure_ascii=False)}"
            ),
        },
    ]

    for step in range(1, 26):
        print(f"\n--- [Итерация {step}] Запрос к ИИ... ---")

        message = query_llm(messages, tools=REPAIR_TOOLS_SCHEMA)
        messages.append(message)
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            result = request_repair_report(messages)
            print("\n==================================================")
            print("        ИТОГОВЫЙ ОТЧЕТ О РЕМОНТЕ (ЭТАП 3)        ")
            print("==================================================")
            if result.get("ok"):
                print(result.get("decision"))
                print(result.get("summary"))
            else:
                print("Repair report error:", result.get("error"))
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
