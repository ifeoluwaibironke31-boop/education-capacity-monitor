import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "logs"
PIPELINE_RUN_DIR = LOG_DIR / "pipeline_runs"
LATEST_RUN_PATH = LOG_DIR / "latest_pipeline_run.json"

PIPELINE_STEPS = [
    ("Extract DNEMIS data", PROJECT_ROOT / "src" / "extract" / "download_dnemis.py"),
    ("Validate raw DNEMIS data", PROJECT_ROOT / "src" / "validate" / "validate_dnemis.py"),
    ("Transform DNEMIS data", PROJECT_ROOT / "src" / "transform" / "transform_dnemis.py"),
    ("Build capacity metrics", PROJECT_ROOT / "src" / "transform" / "build_capacity_table.py"),
    ("Build reporting metrics", PROJECT_ROOT / "src" / "transform" / "build_reporting_metrics.py"),
    ("Validate geographic names", PROJECT_ROOT / "src" / "validate" / "validate_geo_names.py"),
    ("Load metrics into PostgreSQL", PROJECT_ROOT / "src" / "load" / "load_postgres.py"),
]

def save_run_metadata(metadata, timestamp):
    """Save timestamped pipeline metadata and the latest-run snapshot."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PIPELINE_RUN_DIR.mkdir(parents=True, exist_ok=True)
    run_log_path = PIPELINE_RUN_DIR / f"{timestamp}.json"
    for path in (run_log_path, LATEST_RUN_PATH):
        with open(path, "w", encoding="utf-8") as file:
            json.dump(metadata, file, indent=4)
    return run_log_path

def run_step(step_number, step_name, script_path):
    """Run one pipeline script and return its execution metadata."""
    print(f"\n{'=' * 70}\nSTEP {step_number}: {step_name}\nScript: {script_path.relative_to(PROJECT_ROOT)}\n{'=' * 70}")
    started_at = datetime.now()
    timer_start = time.perf_counter()
    result = subprocess.run([sys.executable, str(script_path)], cwd=PROJECT_ROOT)
    finished_at = datetime.now()
    duration = round(time.perf_counter() - timer_start, 2)
    status = "SUCCESS" if result.returncode == 0 else "FAILED"
    metadata = {
        "step_number": step_number,
        "step_name": step_name,
        "script": str(script_path.relative_to(PROJECT_ROOT)),
        "status": status,
        "exit_code": result.returncode,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": duration,
    }
    print(f"\n{status}: {step_name}\nDuration: {duration:.2f} seconds")
    return metadata

def main():
    """Run the full education-capacity data pipeline."""
    pipeline_start = datetime.now()
    timer_start = time.perf_counter()
    timestamp = pipeline_start.strftime("%Y%m%d_%H%M%S")
    metadata = {
        "pipeline": "Nigerian Education Capacity Monitor",
        "status": "RUNNING",
        "started_at": pipeline_start.isoformat(timespec="seconds"),
        "finished_at": None,
        "duration_seconds": None,
        "python_executable": sys.executable,
        "project_root": str(PROJECT_ROOT),
        "steps_total": len(PIPELINE_STEPS),
        "steps_completed": 0,
        "failed_step": None,
        "steps": [],
    }

    print(f"{'=' * 70}\nNIGERIAN EDUCATION CAPACITY MONITOR\nDATA PIPELINE\n{'=' * 70}")
    print(f"Started: {pipeline_start:%Y-%m-%d %H:%M:%S}\nPython: {sys.executable}")

    for step_number, (step_name, script_path) in enumerate(PIPELINE_STEPS, start=1):
        if not script_path.exists():
            metadata.update({
                "status": "FAILED",
                "failed_step": step_name,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "duration_seconds": round(time.perf_counter() - timer_start, 2),
            })
            metadata["steps"].append({
                "step_number": step_number,
                "step_name": step_name,
                "script": str(script_path.relative_to(PROJECT_ROOT)),
                "status": "SCRIPT_NOT_FOUND",
            })
            run_log_path = save_run_metadata(metadata, timestamp)
            print(f"\nPIPELINE FAILED\nScript not found: {script_path}\nRun metadata: {run_log_path}")
            sys.exit(1)

        step_metadata = run_step(step_number, step_name, script_path)
        metadata["steps"].append(step_metadata)

        if step_metadata["status"] == "FAILED":
            metadata.update({
                "status": "FAILED",
                "failed_step": step_name,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "duration_seconds": round(time.perf_counter() - timer_start, 2),
            })
            run_log_path = save_run_metadata(metadata, timestamp)
            print(f"\n{'=' * 70}\nPIPELINE FAILED\n{'=' * 70}")
            print(f"Failed step: {step_name}\nRun metadata: {run_log_path}")
            sys.exit(step_metadata["exit_code"])

        metadata["steps_completed"] += 1

    pipeline_end = datetime.now()
    duration = round(time.perf_counter() - timer_start, 2)
    metadata.update({
        "status": "SUCCESS",
        "finished_at": pipeline_end.isoformat(timespec="seconds"),
        "duration_seconds": duration,
    })
    run_log_path = save_run_metadata(metadata, timestamp)

    print(f"\n{'=' * 70}\nPIPELINE COMPLETED SUCCESSFULLY\n{'=' * 70}")
    print(f"Finished: {pipeline_end:%Y-%m-%d %H:%M:%S}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Steps completed: {metadata['steps_completed']} / {metadata['steps_total']}")
    print(f"Run metadata: {run_log_path}")
    print(f"Latest run: {LATEST_RUN_PATH}")

if __name__ == "__main__":
    main()