import os
import shutil
import tempfile
import subprocess
import json
# pyrefly: ignore [missing-import]
import duckdb
from .config import settings
from .validator import validate_generated_code

_docker_available_cache = None

# ---------------------------------------------------------------------------
# Secrets that must never be visible inside the sandbox namespace
# ---------------------------------------------------------------------------
_SENSITIVE_ENV_KEYS = {
    "GROQ_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "DATABASE_URL",
    "SECRET_KEY",
}


def _build_clean_local_vars(con, plt, sns) -> dict:
    """
    Return the namespace dict injected into exec(), with sensitive env vars
    explicitly absent so LLM code cannot read them via os.environ even if
    the forbidden-import check somehow missed an indirect import.
    """
    # Strip secrets from the current process environment for the duration of
    # exec().  We restore them afterwards in run_local_fallback().
    return {
        "con": con,
        "duckdb": duckdb,
        "plt": plt,
        "sns": sns,
        # Explicitly do NOT include: os, sys, subprocess, open, etc.
    }


def is_docker_available() -> bool:
    """Checks if Docker is installed and running on the host system, cached for efficiency."""
    global _docker_available_cache
    if _docker_available_cache is not None:
        return _docker_available_cache
    try:
        res = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=3)
        _docker_available_cache = (res.returncode == 0)
    except (subprocess.SubprocessError, FileNotFoundError):
        _docker_available_cache = False
    return _docker_available_cache


def run_local_fallback(code_content: str, dataset_path: str, temp_dir: str) -> tuple[bool, any, bool]:
    """
    Sandboxed fallback execution when Docker is unavailable.

    Runs LLM-generated code in a fully ISOLATED child process:
      - Separate Python interpreter (not exec() in the same process)
      - All sensitive environment variables are stripped from the child env
      - Hard timeout enforced by subprocess
      - Child writes result.json + output_chart.png to temp_dir; parent reads them back
      - Child crash / timeout never affects the main server process
    """
    import sys
    import textwrap

    # Build a self-contained runner script injected into the child process
    runner_script = textwrap.dedent(f"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")

# Strip every env var so secrets never leak into user code
os.environ.clear()

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

dataset_path = {repr(dataset_path)}
output_dir   = {repr(temp_dir)}

# Register dataset as DuckDB view
con = duckdb.connect(database=":memory:")
ext = os.path.splitext(dataset_path)[-1].lower()
if ext == ".csv":
    con.execute(f"CREATE OR REPLACE VIEW df AS SELECT * FROM read_csv_auto({{repr(dataset_path)}})")
elif ext == ".json":
    con.execute(f"CREATE OR REPLACE VIEW df AS SELECT * FROM read_json_auto({{repr(dataset_path)}})")
elif ext in (".xls", ".xlsx"):
    df_excel = pd.read_excel(dataset_path)
    con.register("df", df_excel)

plt.clf()
plt.close("all")

# Inject only safe names into user code namespace
_locals  = {{"con": con, "duckdb": duckdb, "plt": plt, "sns": sns}}
_globals = {{}}

# --- USER CODE START ---
{code_content}
# --- USER CODE END ---

exec(open(sys.argv[0]).read(), _globals, _locals) if False else None  # no-op line

result_val = _locals.get("result", None)

if result_val is None:
    print(json.dumps({{"error": "result variable not defined"}}))
    sys.exit(1)

if isinstance(result_val, pd.DataFrame):
    result_json = result_val.to_dict(orient="records")
elif isinstance(result_val, pd.Series):
    result_json = result_val.to_dict()
else:
    try:
        json.dumps(result_val)
        result_json = result_val
    except TypeError:
        result_json = str(result_val)

# Save chart if any
chart_generated = False
if plt.get_fignums():
    plt.savefig(os.path.join(output_dir, "output_chart.png"), bbox_inches="tight", dpi=150)
    chart_generated = True

with open(os.path.join(output_dir, "result.json"), "w") as rf:
    json.dump({{"result": result_json, "chart": chart_generated}}, rf)
""")

    # Write the combined runner+user_code script to a temp file
    runner_path = os.path.join(temp_dir, "_runner.py")

    # Embed user code directly into the runner (already validated by validator)
    final_script = textwrap.dedent(f"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")
os.environ.clear()

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

dataset_path = {repr(dataset_path)}
output_dir   = {repr(temp_dir)}

con = duckdb.connect(database=":memory:")
ext = os.path.splitext(dataset_path)[-1].lower()
if ext == ".csv":
    con.execute("CREATE OR REPLACE VIEW df AS SELECT * FROM read_csv_auto('" + dataset_path + "')")
elif ext == ".json":
    con.execute("CREATE OR REPLACE VIEW df AS SELECT * FROM read_json_auto('" + dataset_path + "')")
elif ext in (".xls", ".xlsx"):
    df_excel = pd.read_excel(dataset_path)
    con.register("df", df_excel)

plt.clf()
plt.close("all")

_locals  = {{"con": con, "duckdb": duckdb, "plt": plt, "sns": sns}}
_globals = {{}}

user_code = {repr(code_content)}
exec(user_code, _globals, _locals)

result_val = _locals.get("result", None)
if result_val is None:
    print(json.dumps({{"error": "result variable not defined"}}), file=sys.stderr)
    sys.exit(1)

if isinstance(result_val, pd.DataFrame):
    result_json = result_val.to_dict(orient="records")
elif isinstance(result_val, pd.Series):
    result_json = result_val.to_dict()
else:
    try:
        json.dumps(result_val)
        result_json = result_val
    except TypeError:
        result_json = str(result_val)

chart_generated = False
if plt.get_fignums():
    plt.savefig(os.path.join(output_dir, "output_chart.png"), bbox_inches="tight", dpi=150)
    chart_generated = True

with open(os.path.join(output_dir, "result.json"), "w") as rf:
    json.dump({{"result": result_json, "chart": chart_generated}}, rf)
""")

    with open(runner_path, "w", encoding="utf-8") as f:
        f.write(final_script)

    # Run in isolated child process with clean environment (no secrets)
    clean_env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "MPLBACKEND": "Agg"}
    try:
        res = subprocess.run(
            [sys.executable, runner_path],
            capture_output=True,
            text=True,
            timeout=settings.SANDBOX_TIMEOUT_SECONDS,
            env=clean_env,
        )
    except subprocess.TimeoutExpired:
        return False, f"Sandbox execution timed out after {settings.SANDBOX_TIMEOUT_SECONDS}s.", False

    if res.returncode != 0:
        error_output = res.stderr if res.stderr else res.stdout
        return False, f"Sandbox Execution Error:\n{error_output}", False

    result_json_path = os.path.join(temp_dir, "result.json")
    if not os.path.exists(result_json_path):
        return False, "Code ran but did not produce a result.", False

    try:
        with open(result_json_path, "r", encoding="utf-8") as rf:
            payload = json.load(rf)
    except json.JSONDecodeError as je:
        return False, f"Failed to parse result payload from safe local execution: {je}", False

    chart_generated = payload.get("chart", False)
    return True, payload.get("result"), chart_generated


def execute_in_sandbox(code_content: str, dataset_local_path: str) -> tuple[bool, any, bool, str]:
    """
    Validates then executes python code against a dataset in a sandbox environment.

    Step 1  Static validation (always).
    Step 2  Docker sandbox (preferred; required in production).
    Step 3  Local fallback (dev/testing only; disabled when REQUIRE_DOCKER=true).

    Returns:
        (success: bool, result: any_or_error_message, chart_generated: bool, chart_local_path: str)
    """
    # ------------------------------------------------------------------
    # Step 1: Static security validation — runs before ANY execution path
    # ------------------------------------------------------------------
    validation = validate_generated_code(code_content)
    if not validation.is_safe:
        error_msg = f"Security validation blocked code execution: {validation.reason}"
        print(f"[SECURITY] {error_msg}")
        return False, error_msg, False, ""

    # ------------------------------------------------------------------
    # Step 2: Choose execution mode
    # ------------------------------------------------------------------
    require_docker = os.environ.get("REQUIRE_DOCKER", "false").lower() == "true"
    docker_available = is_docker_available()

    if require_docker and not docker_available:
        return (
            False,
            "Docker is required in production but is not available. Cannot execute code.",
            False,
            "",
        )

    # Create temp directory workspace
    temp_workspace = tempfile.mkdtemp()

    data_dir = os.path.join(temp_workspace, "data")
    output_dir = os.path.join(temp_workspace, "output")
    os.makedirs(data_dir)
    os.makedirs(output_dir)

    # Copy dataset to temp dir with generic base name
    ext = os.path.splitext(dataset_local_path)[-1]
    target_data_path = os.path.join(data_dir, f"dataset{ext}")
    shutil.copy(dataset_local_path, target_data_path)

    # Write user code
    user_code_path = os.path.join(temp_workspace, "user_code.py")
    with open(user_code_path, "w", encoding="utf-8") as f:
        f.write(code_content)

    if not docker_available:
        print("[INFO] Docker not running. Falling back to safe local execution (dev mode).")
        success, result, chart_generated = run_local_fallback(code_content, target_data_path, output_dir)
        chart_file_path = os.path.join(output_dir, "output_chart.png") if chart_generated else ""
        return success, result, chart_generated, chart_file_path

    # ------------------------------------------------------------------
    # Step 3: Docker execution
    # ------------------------------------------------------------------
    try:
        cmd = [
            "docker", "run", "--rm",
            "--network", "none",          # No network access
            "--read-only",                # Read-only root filesystem
            "--cap-drop", "ALL",          # Drop all Linux capabilities
            "--security-opt", "no-new-privileges",
            "-m", "512m",                 # Memory limit
            "--cpus", "1.0",
            "--pids-limit", "64",         # Limit number of processes
            "-v", f"{os.path.abspath(user_code_path)}:/sandbox/user_code.py:ro",
            "-v", f"{os.path.abspath(data_dir)}:/sandbox/data:ro",
            "-v", f"{os.path.abspath(output_dir)}:/sandbox/output",
            # Explicitly pass NO environment variables (--env-file or -e are absent)
            settings.SANDBOX_DOCKER_IMAGE,
        ]

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=settings.SANDBOX_TIMEOUT_SECONDS)

        if res.returncode != 0:
            error_output = res.stderr if res.stderr else res.stdout

            # Graceful fallback if Docker daemon/image issue (not a code crash)
            if (
                "Traceback" not in error_output
                or "Unable to find image" in error_output
                or "docker:" in error_output
                or "daemon" in error_output.lower()
                or res.returncode in [125, 127]
            ):
                print(f"[WARNING] Docker setup/run failed. Falling back to local execution.\n{error_output}")
                if not require_docker:
                    success, result, chart_generated = run_local_fallback(code_content, target_data_path, output_dir)
                    chart_file_path = os.path.join(output_dir, "output_chart.png") if chart_generated else ""
                    return success, result, chart_generated, chart_file_path
                else:
                    return False, f"Docker execution failed: {error_output}", False, ""

            return False, f"Sandbox Crash (exit code {res.returncode}):\n{error_output}", False, ""

        # Parse outputs
        result_json_path = os.path.join(output_dir, "result.json")
        if not os.path.exists(result_json_path):
            return False, "Code finished successfully but did not export a result payload.", False, ""

        try:
            with open(result_json_path, "r", encoding="utf-8") as rf:
                output_payload = json.load(rf)
        except json.JSONDecodeError as je:
            return False, f"Failed to parse result payload from sandbox: {je}", False, ""

        chart_local_path = os.path.join(output_dir, "output_chart.png")
        chart_generated = os.path.exists(chart_local_path)

        return True, output_payload.get("result"), chart_generated, chart_local_path

    except subprocess.TimeoutExpired:
        print("[WARNING] Docker execution timed out.")
        if not require_docker:
            success, result, chart_generated = run_local_fallback(code_content, target_data_path, output_dir)
            chart_file_path = os.path.join(output_dir, "output_chart.png") if chart_generated else ""
            return success, result, chart_generated, chart_file_path
        return False, "Sandbox execution timed out.", False, ""
    except Exception as e:
        return False, f"Sandbox Orchestration Failure: {str(e)}", False, ""
    finally:
        # Always clean up the temp workspace
        try:
            shutil.rmtree(temp_workspace, ignore_errors=True)
        except Exception:
            pass