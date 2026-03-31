"""PulseBoard-RAG command-line interface.

Entry points registered in pyproject.toml:
    pulseboard-start   → cli:start        (launches API + dashboard)
    pulseboard-config  → cli:setup_wizard (interactive first-time setup)

Usage:
    pulseboard-config   # run once to create .env
    pulseboard-start    # starts API on :8000 and dashboard on :8501
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


# ── Helpers ───────────────────────────────────────────────────

def _print_banner() -> None:
    print("""
╔══════════════════════════════════════════════╗
║           PulseBoard-RAG  v1.0.0             ║
║  Intelligent project monitor + RAG engine    ║
╚══════════════════════════════════════════════╝
""")


def _check_env() -> bool:
    """Return True if .env exists and has at least one LLM key set."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return False
    text = env_path.read_text()
    return "ANTHROPIC_API_KEY=sk-" in text or "GEMINI_API_KEY=AIza" in text


# ── pulseboard-config ─────────────────────────────────────────

def setup_wizard() -> None:
    """Interactive setup wizard — creates a .env file from user input."""
    _print_banner()
    print("=== First-Time Setup Wizard ===\n")

    env_path = PROJECT_ROOT / ".env"
    example_path = PROJECT_ROOT / ".env.example"

    # Seed from example if it exists
    if example_path.exists() and not env_path.exists():
        shutil.copy(example_path, env_path)

    config: dict[str, str] = {}

    print("[ LLM Provider — set at least one ]\n")
    anthropic = input("  Anthropic API key (press Enter to skip): ").strip()
    if anthropic:
        config["ANTHROPIC_API_KEY"] = anthropic

    gemini = input("  Gemini API key (press Enter to skip): ").strip()
    if gemini:
        config["GEMINI_API_KEY"] = gemini

    if not anthropic and not gemini:
        demo = input("\n  No LLM key provided — enable DEMO MODE? [Y/n]: ").strip().lower()
        config["DEMO_MODE"] = "false" if demo == "n" else "true"
    else:
        config["DEMO_MODE"] = "false"

    print("\n[ Slack Integration (optional) ]\n")
    slack_token = input("  Slack bot token (xoxb-...): ").strip()
    if slack_token:
        config["SLACK_BOT_TOKEN"] = slack_token
        channels = input("  Channels to monitor (comma-separated, e.g. general,client-x): ").strip()
        if channels:
            config["SLACK_CHANNELS"] = channels

    print("\n[ GitHub Integration (optional) ]\n")
    github_token = input("  GitHub token (ghp_...): ").strip()
    if github_token:
        config["GITHUB_TOKEN"] = github_token
        repos = input("  Repos to monitor (e.g. org/repo1,org/repo2): ").strip()
        if repos:
            config["GITHUB_REPOS"] = repos

    print("\n[ Notion Integration (optional) ]\n")
    notion_token = input("  Notion integration token (secret_...): ").strip()
    if notion_token:
        config["NOTION_TOKEN"] = notion_token
        db_id = input("  Notion database ID: ").strip()
        if db_id:
            config["NOTION_DATABASE_ID"] = db_id

    print("\n[ Optional Settings ]\n")
    interval = input("  Heartbeat interval in minutes [30]: ").strip()
    config["DIGEST_INTERVAL_MINUTES"] = interval if interval.isdigit() else "30"

    cors = input("  CORS origins for API [http://localhost:8501]: ").strip()
    config["CORS_ORIGINS"] = cors or "http://localhost:8501"

    # Write .env
    lines = []
    if env_path.exists():
        # Preserve existing lines and overwrite matching keys
        existing = {}
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, _, val = line.partition("=")
                existing[key.strip()] = val.strip()
        existing.update(config)
        config = existing

    for key, val in config.items():
        lines.append(f"{key}={val}")

    env_path.write_text("\n".join(lines) + "\n")
    print(f"\n✓ Configuration saved to {env_path}")
    print("\nRun  pulseboard-start  to launch the API and dashboard.\n")


# ── pulseboard-start ──────────────────────────────────────────

def start() -> None:
    """Launch the FastAPI backend and Streamlit dashboard as subprocesses."""
    _print_banner()

    if not _check_env():
        print("⚠  No .env found or no LLM keys configured.")
        print("   Run  pulseboard-config  first, or set DEMO_MODE=true in .env.\n")
        ans = input("Start in DEMO MODE anyway? [Y/n]: ").strip().lower()
        if ans == "n":
            sys.exit(0)
        os.environ["DEMO_MODE"] = "true"

    os.chdir(PROJECT_ROOT)

    api_port = os.environ.get("PORT", "8000")
    dashboard_port = os.environ.get("DASHBOARD_PORT", "8501")

    print(f"\nStarting API on http://localhost:{api_port}")
    print(f"Starting Dashboard on http://localhost:{dashboard_port}\n")
    print("Press Ctrl+C to stop both services.\n")

    python = sys.executable

    api_proc = subprocess.Popen(
        [python, "-m", "uvicorn", "main:app",
         "--host", "0.0.0.0",
         "--port", api_port,
         "--reload"],
        cwd=str(PROJECT_ROOT),
    )

    dashboard_proc = subprocess.Popen(
        [python, "-m", "streamlit", "run", "dashboard.py",
         "--server.port", dashboard_port,
         "--server.address", "0.0.0.0",
         "--server.headless", "true"],
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "API_BASE_URL": f"http://localhost:{api_port}"},
    )

    try:
        api_proc.wait()
        dashboard_proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        api_proc.terminate()
        dashboard_proc.terminate()
        api_proc.wait()
        dashboard_proc.wait()
        print("Done.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    if cmd == "config":
        setup_wizard()
    else:
        start()
