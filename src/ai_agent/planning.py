import json

from .llm_client import query_llm
from .tools.tools import TOOL_MAP, TOOLS_SCHEMA, PLAN_TOOL_SCHEMA

def request_verification_plan(messages):
    messages.append({
        "role": "user",
        "content": (
            "Submit the final repair plan using submit_planning_report. "
            "Set complete=true if the plan covers every confirmed problem and is ready "
            "for execution. Complete does not mean that the repair steps were already executed."
        ),
    })

    last_error = "Plan was not submitted."

    for n in range(2):
        print(
            f"\n--- [ОТЧЁТ] Попытка формирования плана {n + 1}/2 ---"
        )
        message = query_llm(
            messages,
            tools=[PLAN_TOOL_SCHEMA],
            tool_choice="required",
        )
        messages.append(message)
        calls = message.get("tool_calls") or []

        if len(calls) != 1:
            last_error = "Expected one planning tool call."
            messages.append({"role": "user", "content": last_error})
            continue

        call = calls[0]
        try:
            if call["function"]["name"] != "submit_planning_report":
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
            "content": f"Fix the plan: {last_error}",
        })

    return {
        "ok": False,
        "decision": "PLAN_FAILED",
        "error": last_error,
    }

def run_planning(diagnosis_result : dict ) -> dict:

    system_prompt = (
        "You are an AI agent responsible for planning repairs based on "
        "diagnosis results. Use the provided tools to assist in your planning."
        "When you have enough evidence to create a complete repair plan, "
        "stop calling tools and return a short final response. "
        "Do not continue inspecting unrelated system state. "
        "The orchestrator will then request the structured planning report."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Diagnosis result: {json.dumps(diagnosis_result, ensure_ascii=False)}"
            ),
        },
    ]

    for step in range(1,26):
        print(f"\n--- [Итерация {step}] Запрос к ИИ... ---")

        message = query_llm(messages, tools=TOOLS_SCHEMA)
        messages.append(message)
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            result = request_verification_plan(messages)
            print("\n==================================================")
            print("        ИТОГОВЫЙ ПЛАН ЛЕЧЕНИЯ (ЭТАП 2)        ")
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

    
