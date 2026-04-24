"""Compatibility shim for legacy intel_hub MediaCrawler execution.

保留该文件仅为兼容旧调用入口，实际执行统一转发到 legacy_intel_hub_runner.py。
"""

from __future__ import annotations

from legacy_intel_hub_runner import cli


if __name__ == "__main__":
    raise SystemExit(cli())
