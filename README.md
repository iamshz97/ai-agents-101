# AI Agents 101

Hands-on mini labs for learning how to assemble production-grade AI agents with the [`openai-agents`](https://github.com/openai/openai-agents-python) SDK. Each script in this repository is a standalone chapter that introduces one new concept—starting with a single assistant and ending with multi-agent orchestration that talks to external tools.

## Prerequisites

- Python **3.11+**
- macOS, Linux, or Windows with PowerShell
- API access for the models you plan to call (OpenAI, Anthropic, etc.)
- (Optional) [`uv`](https://github.com/astral-sh/uv) for faster installs

## Installation

```bash
# Open in VS Code (optional)
# cmd/ctrl+shift+p → “Dev Containers: Reopen in Container”

# Using uv (recommended)
uv sync

# ...or plain pip
python -m venv .venv
.venv\Scripts\activate  # or source .venv/bin/activate
pip install -e .
```

The `pyproject.toml` already pins everything you need, including `openai-agents`, FastAPI, Scalar for docs, and the optional LiteLLM adapter.

## Environment Setup

All examples load a `.env` file via `python-dotenv`. Create one at the repo root before running anything:

```dotenv
# Core model providers
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-your-anthropic-key

# Google Calendar MCP connector (Chapter 02 & 03)
GOOGLE_CALENDAR_AUTHORIZATION=Bearer <token from Scalar workspace>

# Vector store used by FileSearchTool from Open AI (replace with your store id)
VECTOR_STORE_ID=vs_691f69d8c1d481918f716c9bdc82e4a0
```

Tips:

- The `VECTOR_STORE_ID` above matches the demo configuration but you should replace it with an ID from your own  OpenAI Vector Store workspace.
- The Google Calendar example expects an MCP server named `google_calendar` with connector ID `connector_googlecalendar`. Generate the authorization token with [Google oauth playground](https://developers.google.com/oauthplayground/).
- If you run Anthropic or Azure OpenAI via LiteLLM, update `01-agent-with-tools.py` to pass the correct `model` string.

### VS Code Dev Container workflow

If you prefer a fully reproducible environment, install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) for VS Code, open this repository, then run “Dev Containers: Reopen in Container” from the command palette. The container inherits your local git credentials and mounts the workspace so you can use the included tooling (`uv`, `python-dotenv`, etc.) without touching your host machine.

## Chapter Guide

| Chapter | File | Key Concepts | Run Command |
| :--- | :--- | :--- | :--- |
| 01 | `01-basic-agent.py` | Basic Agent, Runner | `uv run python 01-basic-agent.py` |
| 01 | `01-agent-with-tools.py` | Function Tools, LiteLLM | `uv run python 01-agent-with-tools.py` |
| 01 | `01-agent-structured-output.py` | Structured Output, WebSearch | `uv run python 01-agent-structured-output.py` |
| 02 | `02-agent-mcp-calendar.py` | MCP Tool (Google Calendar) | `uv run python 02-agent-mcp-calendar.py` |
| 02 | `02-agent-rag-leave-policy.py` | RAG (File Search) | `uv run python 02-agent-rag-leave-policy.py` |
| 02 | `02-agent-with-memory.py` | Long-term Memory (SQLite) | `uv run python 02-agent-with-memory.py` |
| 03 | `03-parallel-agents.py` | Parallel Orchestration | `uv run python 03-parallel-agents.py` |
| 03 | `03-sequential-agents.py` | Sequential Orchestration | `uv run python 03-sequential-agents.py` |

> 💡 Prefer `python` over `uv run` if you are using a plain virtual environment.

## Getting Started

1. Pick a chapter from the table above.
2. Ensure the required environment variables are set for that chapter (e.g., Calendar token for MCP demos).
3. Run the script with `uv run python <file>.py`. Many chapters use `run_demo_loop`, so you will see an interactive REPL where you can ask follow-up questions.
4. Change the prompt, instructions, or tool list and re-run to observe how the agent behaves.

Fast iteration tips:

- Enable tracing via `agents.trace` to visualize graph execution: wrap sections in `with trace("label"):` as seen in `03-parallel-agents.py`.
- Try swapping models (OpenAI, Anthropic, Groq via LiteLLM) to compare outputs.
- Customize the `FileSearchTool` by pointing it to your own documents.

## Project Structure

```
ai-agents-101/
├── 01-*.py        # Chapter 1: single-agent fundamentals
├── 02-*.py        # Chapter 2: external data + memory
├── 03-*.py        # Chapter 3: multi-agent orchestration
├── pyproject.toml # Dependencies + project metadata
├── uv.lock        # Reproducible env for uv users
└── README.md      # You are here
```

Each script is intentionally compact (<100 lines) so you can copy/paste the patterns into your own projects without wading through framework boilerplate.

## Learning Path & Next Steps

Follow this sequence to build your understanding:

1. **Basic Foundations**
   - `01-basic-agent.py`: Run your first agent loop.
   - `01-agent-with-tools.py`: Give the agent a Python function (tool) to call.
   - `01-agent-structured-output.py`: Force the agent to return structured data (Pydantic) instead of just text.

2. **Advanced Capabilities**
   - `02-agent-mcp-calendar.py`: Connect to external services like Google Calendar using the Model Context Protocol (MCP).
   - `02-agent-rag-leave-policy.py`: Add knowledge retrieval (RAG) so the agent can answer based on documents.
   - `02-agent-with-memory.py`: Enable long-running conversations where the agent remembers previous turns.

3. **Orchestration Patterns**
   - `03-parallel-agents.py`: Run multiple agents at the same time (e.g., checking policy and calendar simultaneously).
   - `03-sequential-agents.py`: Chain agents together so one agent's output feeds into the next.

4. **Next Steps**
   - **Extend**: Replace the sample tools with your own MCP servers or API calls.
   - **Customize**: Swap the vector store ID with your own to search your specific documents.
   - **Experiment**: Try different models (e.g., DeepSeek, Claude) using the LiteLLM configuration.

## Troubleshooting

- **`GOOGLE_CALENDAR_AUTHORIZATION` KeyError** – Make sure the token is present in `.env` and that you restarted the shell after editing it.
- **Vector store not found** – Update the `vector_store_ids` argument to the ID of a store you own from Open AI vector store.
- **Model errors / 401** – Confirm the model name matches the provider you have access to (`gpt-4.1`, `anthropic/claude-*`, etc.) and that the API key is valid.
- **SQLite locking** – Delete the `conversations.db` file if a previous run crashed, or change the session file name.

## Helpful Links

- [OpenAI Agents SDK Docs](https://openai.github.io/openai-agents-python/)
- [OpenAI API Platform](https://openai.com/api/)
- [Anthropic Console](https://console.anthropic.com/dashboard)
- [Google AI Studio](https://aistudio.google.com/app/api-keys)
- [DeepSeek Platform](https://platform.deepseek.com/usage)
- [LiteLLM Providers](https://docs.litellm.ai/docs/providers)
- [LiteLLM Models](https://models.litellm.ai/)
- [OpenAI Agents - LiteLLM Integration](https://openai.github.io/openai-agents-python/models/litellm/)

Feel free to open issues or PRs when you expand these examples—this repo is meant to be a living notebook of agent recipes.

