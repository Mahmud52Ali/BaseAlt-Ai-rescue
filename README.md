# ALT AI Rescue

ALT AI Rescue adds a recovery boot mode to ALT Workstation. The agent can use
the bundled local llama.cpp model or an OpenAI-compatible chat/completions API.

## Packages

- `alt-ai-rescue-core` installs the console recovery environment and API client.
  It does not require llama.cpp or download model weights.
- `alt-ai-rescue-local` depends on `alt-ai-rescue-core` and adds the llama.cpp
  service and local model installer.
- `alt-ai-rescue` depends on `alt-ai-rescue-local` and keeps the usual full
  installation available under the original package name.

Install the desired RPM with `apt-get install <path-to-rpm>`. The full package
requires the ALT Linux package that provides `/usr/bin/llama-server`.

## Model configuration

Edit `/etc/alt-ai-rescue/model.conf` as root. It is the only user model
configuration file and is preserved across RPM upgrades. The package installs
it with mode `0600` because it can contain an API key.

The core package starts with `local = false`. On a fresh installation,
`alt-ai-rescue-local` changes it to `true` only if the configuration is still
untouched. Package upgrades leave the selected model unchanged. Removing
`alt-ai-rescue-local` sets `local = false` because llama.cpp is no longer
available. The local service uses the generic API model ID
`alt-ai-rescue-local`, independent of the GGUF file's name. The `url`, `model`,
and `api_key` fields are used only when `local = false`.

For an API-only installation, fill in the full chat/completions endpoint and
model ID. For example, [Gemini's OpenAI-compatible
endpoint](https://ai.google.dev/gemini-api/docs/openai) can be configured as follows:

```ini
[model]
local = false
url = https://generativelanguage.googleapis.com/v1beta/openai/chat/completions
model = <Gemini model ID supported by your API account>
api_key = <your API key>
timeout_seconds = 60
```

The same fields work with other services that implement the OpenAI-compatible
chat/completions request and tool-call response format. `api_key` may be empty
for an endpoint that does not require a bearer token. The current agent sends
system findings and tool output to the selected API, so use a service you trust.

When recovery mode starts, ALT AI Rescue starts llama.cpp only if `local = true`.
Changing the config while in recovery starts or stops that service after the
file is saved. If an AI recovery run is in progress, the change takes effect
after that run ends. You can apply a change manually with
`systemctl start alt-ai-rescue-model-sync.service`.

## Build and checks

Build on ALT Linux after placing `alt-ai-rescue-1.0.tar.xz` in the RPM SOURCES
directory:

```sh
rpmbuild -ba packaging/alt-ai-rescue.spec
```

Check Python and shell syntax with:

```sh
python3 -m compileall -q src
sh -n src/alt-ai-rescue-menu src/alt-ai-rescue-ai src/model_controller/install-model grub/42_alt_ai_rescue
```
