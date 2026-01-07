"""Package for summarizing entertainment news articles with OpenAI Agents."""

import os

# Disable OpenAI Agents SDK trace export by default to avoid noisy non-fatal retry logs
# when no tracing collector is configured. Override by setting the env var explicitly
# (e.g., `OPENAI_AGENTS_DISABLE_TRACING=false`) before importing this package.
os.environ.setdefault("OPENAI_AGENTS_DISABLE_TRACING", "true")

__all__ = ["config", "models", "workflow"]
