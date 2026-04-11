# hermes-agent (git submodule)

This directory is a git submodule placeholder pointing at
<https://github.com/NousResearch/hermes-agent>.

To populate it after cloning the parent repo:

```bash
git submodule update --init third_party/hermes-agent
```

## Vendored Council SOUL helpers

Hermes-style **context scanning and truncation** for committee `SOUL.md` files lives in
[`apps/content_planning/agents/soul_context_hermes.py`](../../apps/content_planning/agents/soul_context_hermes.py)
(importable from Python; this folder name contains a hyphen and is not a Python package).

A short pointer file: [`core/soul_context.py`](core/soul_context.py).
