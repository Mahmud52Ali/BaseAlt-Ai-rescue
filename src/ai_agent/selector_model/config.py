import configparser
from urllib.parse import urlsplit


CONFIG_PATH = "/etc/alt-ai-rescue/model.conf"
LOCAL_URL = "http://127.0.0.1:8080/v1/chat/completions"
LOCAL_MODEL_ID = "alt-ai-rescue-local"
LOCAL_HEALTH_URL = "http://127.0.0.1:8080/health"


class ConfigError(ValueError):
    pass


def read_config(path=CONFIG_PATH):
    parser = configparser.ConfigParser(interpolation=None)

    try:
        with open(path, "r", encoding="utf-8") as config_file:
            parser.read_file(config_file)
    except OSError as error:
        raise ConfigError(f"Cannot read {path}: {error.strerror}") from error
    except UnicodeError as error:
        raise ConfigError(f"Invalid UTF-8 in {path}") from error
    except configparser.Error as error:
        raise ConfigError(f"Invalid syntax in {path}") from error

    if not parser.has_section("model"):
        raise ConfigError(f"Missing [model] section in {path}")

    return parser


def read_local_flag(path=CONFIG_PATH):
    parser = read_config(path)

    try:
        return parser.getboolean("model", "local")
    except (configparser.Error, ValueError) as error:
        raise ConfigError(f"Invalid local flag in {path}: use true or false") from error


def load_settings(path=CONFIG_PATH):
    parser = read_config(path)

    try:
        local = parser.getboolean("model", "local")
        timeout = parser.getint("model", "timeout_seconds", fallback=60)
    except (configparser.Error, ValueError) as error:
        raise ConfigError(f"Invalid local or timeout_seconds in {path}") from error

    if timeout <= 0:
        raise ConfigError("timeout_seconds must be greater than zero")

    if local:
        return {
            "local": True,
            "url": LOCAL_URL,
            "model": LOCAL_MODEL_ID,
            "api_key": "",
            "timeout_seconds": timeout,
        }

    url = parser.get("model", "url", fallback="").strip()
    model = parser.get("model", "model", fallback="").strip()
    api_key = parser.get("model", "api_key", fallback="").strip()

    try:
        parsed_url = urlsplit(url)
        host = parsed_url.hostname
        _ = parsed_url.port  # Checking the port also catches malformed values.
    except ValueError as error:
        raise ConfigError("Invalid API URL in model.conf") from error
    if parsed_url.scheme not in {"http", "https"} or not host:
        raise ConfigError("Set a full http(s) chat/completions URL in model.conf")
    if parsed_url.username or parsed_url.password or parsed_url.fragment:
        raise ConfigError("API URL must not contain credentials or a fragment")
    if not model:
        raise ConfigError("Set model in model.conf when local = false")

    return {
        "local": False,
        "url": url,
        "model": model,
        "api_key": api_key,
        "timeout_seconds": timeout,
    }


if __name__ == "__main__":
    try:
        settings = load_settings()
    except ConfigError as error:
        print(f"Model configuration: {error}")
    else:
        if settings["local"]:
            print("Model: local llama.cpp")
        else:
            print(f"Model: {settings['model']} (API)")
