#!/usr/bin/env python3
"""Local runner for equest_extractor.py using a JSON config file."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SUPPORTED_MODEL_RUN_TYPES = {
    "Baseline",
    "Proposed",
    "ECM-1",
    "ECM-2",
    "ECM-3",
    "ECM-4",
    "ECM-5",
    "ECM-6",
    "ECM-7",
}


def resolve_model_run_type(config: dict, default: str) -> str:
    model_run_type = config.get("model_run_type", default)
    if model_run_type not in SUPPORTED_MODEL_RUN_TYPES:
        supported = ", ".join(["Baseline", "Proposed", "ECM-1", "ECM-2", "ECM-3", "ECM-4", "ECM-5", "ECM-6", "ECM-7"])
        raise ValueError(f"Unsupported model_run_type: {model_run_type}. Supported options: {supported}")
    return model_run_type


def build_command(config: dict) -> list[str]:
    sim_file = config["sim_file"]
    command = [sys.executable, "equest_extractor.py", sim_file]
    mode = config.get("mode", "extract_report")
    if mode == "extract_report":
        command.extend(["--report", config.get("report", "all")])
    elif mode == "master_room_list":
        command.extend(
            [
                "--populate-master-room-list",
                config["workbook_path"],
                "--model-run-type",
                resolve_model_run_type(config, "Baseline"),
                "--output-workbook",
                config["output_workbook_path"],
            ]
        )
    elif mode == "ecm_data":
        command.extend(
            [
                "--update-ecm-data",
                config["workbook_path"],
                "--model-run-type",
                resolve_model_run_type(config, "ECM-1"),
                "--output-workbook",
                config["output_workbook_path"],
            ]
        )
    elif mode == "schedule_importer":
        command.extend(
            [
                "--populate-schedules",
                config["workbook_path"],
                "--output-workbook",
                config["output_workbook_path"],
            ]
        )
    elif mode == "combined":
        raise ValueError("Use build_combined_commands() for mode='combined'.")
    else:
        raise ValueError(f"Unsupported mode: {mode}")
    return command


def build_combined_commands(config: dict, intermediate_output_path: str) -> list[list[str]]:
    """Build two-step command list: Master Room List then ECM Data."""
    combined_model_run_type = resolve_model_run_type(config, "Baseline")
    sim_file = config["sim_file"]
    workbook_path = config["workbook_path"]
    output_workbook_path = config["output_workbook_path"]
    return [
        [
            sys.executable,
            "equest_extractor.py",
            sim_file,
            "--populate-master-room-list",
            workbook_path,
            "--model-run-type",
            combined_model_run_type,
            "--output-workbook",
            intermediate_output_path,
        ],
        [
            sys.executable,
            "equest_extractor.py",
            sim_file,
            "--update-ecm-data",
            intermediate_output_path,
            "--model-run-type",
            combined_model_run_type,
            "--output-workbook",
            output_workbook_path,
        ],
    ]


def main() -> None:
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("local_inputs.json")
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}. Copy local_inputs.template.json to local_inputs.json and edit paths."
        )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    mode = config.get("mode", "extract_report")
    if mode == "combined":
        with tempfile.TemporaryDirectory() as temp_dir:
            intermediate_output = str(Path(temp_dir) / "master_room_intermediate.xlsm")
            commands = build_combined_commands(config, intermediate_output_path=intermediate_output)
            for command in commands:
                result = subprocess.run(command, text=True, capture_output=True, cwd=Path(__file__).resolve().parent)
                if result.stdout:
                    print(result.stdout)
                if result.returncode != 0:
                    if result.stderr:
                        print(result.stderr, file=sys.stderr)
                    raise SystemExit(result.returncode)
    else:
        command = build_command(config)
        result = subprocess.run(command, text=True, capture_output=True, cwd=Path(__file__).resolve().parent)
        if result.stdout:
            print(result.stdout)
        if result.returncode != 0:
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
