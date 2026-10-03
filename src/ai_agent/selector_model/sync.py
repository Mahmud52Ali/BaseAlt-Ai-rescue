import fcntl
import os
import subprocess
import sys
import time
import urllib.request

from .config import ConfigError, LOCAL_HEALTH_URL, read_local_flag


LLAMA_SERVICE = "alt-ai-rescue-llama.service"
LOCK_PATH = "/run/alt-ai-rescue/model.lock"


class ModelSyncError(RuntimeError):
    pass


def acquire_model_lock():
    os.makedirs(os.path.dirname(LOCK_PATH), mode=0o700, exist_ok=True)
    lock_file = open(LOCK_PATH, "a", encoding="utf-8")
    fcntl.flock(lock_file, fcntl.LOCK_EX)
    return lock_file


def service_state():
    result = subprocess.run(
        ["systemctl", "show", "--property=ActiveState", "--value", LLAMA_SERVICE],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ModelSyncError("Cannot query the llama.cpp service state")
    return result.stdout.strip()


def sync_model(local):
    state = service_state()

    if local and state != "active":
        action = "start"
    elif not local and state not in {"inactive", "failed"}:
        action = "stop"
    else:
        return

    result = subprocess.run(
        ["systemctl", action, LLAMA_SERVICE],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ModelSyncError(
            f"Cannot {action} llama.cpp. Check: systemctl status {LLAMA_SERVICE}"
        )

    active = service_state() == "active"
    if active != local:
        raise ModelSyncError(
            f"llama.cpp did not {action}. Check: systemctl status {LLAMA_SERVICE}"
        )


def wait_for_local_model():
    deadline = time.monotonic() + 300

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(LOCAL_HEALTH_URL, timeout=2) as response:
                if 200 <= response.status < 300:
                    return
        except OSError:
            pass
        time.sleep(1)

    raise ModelSyncError(
        f"llama.cpp did not become ready. Check: systemctl status {LLAMA_SERVICE}"
    )


def reconcile():
    with acquire_model_lock():
        for _ in range(5):
            local = read_local_flag()
            sync_model(local)
            if read_local_flag() == local:
                return
        raise ModelSyncError("Model configuration kept changing; retry synchronization")


def main():
    try:
        reconcile()
    except (ConfigError, ModelSyncError, OSError) as error:
        print(f"alt-ai-rescue: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
