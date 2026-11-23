#!/usr/bin/env python3
"""Benchmark GPU-only llama.cpp configurations and save a local recommendation."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

APP = "multi_modal"
GPU_BACKENDS = ("vulkan", "cuda", "rocm", "metal", "sycl", "opencl", "musa")
SOFTWARE_DEVICE_MARKERS = ("llvmpipe", "lavapipe", "swiftshader", "software rasterizer")


class OptimizerError(RuntimeError):
    pass


def find_bench(explicit: str | None) -> Path:
    candidates = [explicit, os.environ.get("MULTI_MODAL_LLAMA_BENCH"), shutil.which("llama-bench")]
    candidates.extend(str(path) for path in Path.home().glob(".local/lib/llama.cpp/*/*/llama-bench"))
    for candidate in candidates:
        if candidate:
            path = Path(candidate).expanduser()
            if path.is_file() and os.access(path, os.X_OK):
                return path.resolve()
    raise OptimizerError("llama-bench not found; install a Vulkan/CUDA-enabled llama.cpp build or set MULTI_MODAL_LLAMA_BENCH")


def gpu_devices(bench: Path) -> tuple[list[tuple[str, str]], str]:
    try:
        result = subprocess.run([str(bench), "--list-devices"], text=True, capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OptimizerError(f"Could not inspect llama.cpp devices: {exc}") from exc
    report = result.stdout + "\n" + result.stderr
    devices: list[tuple[str, str]] = []
    in_list = False
    # Parse only the device table; stderr backend diagnostics can mention
    # Vulkan even when it explicitly reports that no physical device exists.
    for line in result.stdout.splitlines():
        if line.strip().lower() == "available devices:":
            in_list = True
            continue
        if not in_list:
            continue
        if not line.strip() or line.strip().lower() == "(none)":
            break
        match = re.match(r"^\s*([^:]+):\s*(.+?)\s*$", line)
        if not match:
            break
        name, description = match.group(1).strip(), match.group(2).strip()
        joined = f"{name} {description}".lower()
        if name.lower() == "none" or any(marker in joined for marker in SOFTWARE_DEVICE_MARKERS):
            continue
        if any(backend in name.lower() for backend in GPU_BACKENDS):
            devices.append((name, description))
    if result.returncode != 0:
        raise OptimizerError(f"llama-bench device discovery failed (exit {result.returncode}): {report.strip()[-1200:]}")
    return devices, report.strip()


def parse_ints(value: str, label: str, minimum: int) -> list[int]:
    try:
        values = sorted({int(item.strip()) for item in value.split(",")})
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{label} must be comma-separated integers") from exc
    if not values or any(item < minimum for item in values):
        raise argparse.ArgumentTypeError(f"{label} values must be at least {minimum}")
    return values


def private_directory(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def saved_model_path() -> Path:
    config_root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_root / APP / "gpu-optimizer.json"


def load_saved_model() -> str | None:
    try:
        value = json.loads(saved_model_path().read_text(encoding="utf-8"))
        model = value.get("model") if isinstance(value, dict) else None
        return model if isinstance(model, str) and model else None
    except (OSError, json.JSONDecodeError):
        return None


def save_model_choice(model: Path) -> None:
    path = saved_model_path()
    private_directory(path.parent)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump({"model": str(model)}, stream)
        stream.write("\n")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def save_report(report: dict) -> Path:
    state_root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    directory = private_directory(state_root / APP / "gpu-optimizer")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"run-{stamp}.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    os.chmod(path, 0o600)
    return path


def csv_rows(output: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(output))
    if not reader.fieldnames or "avg_ts" not in reader.fieldnames:
        raise OptimizerError("llama-bench returned CSV without an avg_ts throughput column")
    return [row for row in reader if row.get("avg_ts")]


def benchmark(bench: Path, model: Path, device: str, context: int, batch: int, reps: int, timeout: int) -> dict:
    command = [
        str(bench), "--model", str(model), "--device", device,
        "--n-gpu-layers", "99", "--no-host", "1",
        "--ctx-size", str(context), "--batch-size", str(batch),
        "--ubatch-size", str(min(batch, 128)), "--n-prompt", "128", "--n-gen", "64",
        "--repetitions", str(reps), "--output", "csv",
    ]
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return {"context": context, "batch": batch, "status": "timeout", "detail": f"Exceeded {timeout}s"}
    except OSError as exc:
        return {"context": context, "batch": batch, "status": "failed", "detail": str(exc)}
    if result.returncode:
        return {"context": context, "batch": batch, "status": "failed",
                "detail": (result.stderr or result.stdout)[-1800:], "exit_code": result.returncode}
    try:
        rows = csv_rows(result.stdout)
    except OptimizerError as exc:
        return {"context": context, "batch": batch, "status": "failed", "detail": str(exc)}

    try:
        generation = [row for row in rows if int(row.get("n_gen", "0") or 0) > 0]
        prompt = [row for row in rows if int(row.get("n_prompt", "0") or 0) > 0 and int(row.get("n_gen", "0") or 0) == 0]
    except ValueError:
        return {"context": context, "batch": batch, "status": "failed", "detail": "Invalid prompt/generation counts in benchmark CSV"}
    if not generation:
        return {"context": context, "batch": batch, "status": "failed", "detail": "No generation throughput row returned"}
    backends = ",".join(row.get("backends", "") for row in rows).lower()
    if not any(backend in backends for backend in GPU_BACKENDS):
        return {"context": context, "batch": batch, "status": "rejected", "detail": f"Benchmark did not report a GPU backend: {backends or 'unknown'}"}
    if any(int(row.get("n_gpu_layers", "0") or 0) <= 0 for row in generation):
        return {"context": context, "batch": batch, "status": "rejected", "detail": "Benchmark did not report GPU layer offload"}
    gen_tps = sum(float(row["avg_ts"]) for row in generation) / len(generation)
    prompt_tps = sum(float(row["avg_ts"]) for row in prompt) / len(prompt) if prompt else None
    return {"context": context, "batch": batch, "status": "passed", "generation_tokens_per_second": gen_tps,
            "prompt_tokens_per_second": prompt_tps, "gpu_layers": 99, "device": device}


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sweep GPU-only llama.cpp settings and recommend a local model configuration.")
    parser.add_argument("--model", default=os.environ.get("MULTI_MODAL_GPU_MODEL"), help="Local GGUF model path (or MULTI_MODAL_GPU_MODEL)")
    parser.add_argument("--llama-bench", help="llama-bench executable; auto-detected when omitted")
    parser.add_argument("--device", help="Exact GPU device from llama-bench --list-devices; defaults to the first supported GPU")
    parser.add_argument("--contexts", default="4096,8192", help="Comma-separated context sizes to benchmark")
    parser.add_argument("--batches", default="128,256", help="Comma-separated batch sizes to benchmark")
    parser.add_argument("--repetitions", type=int, default=3, help="Repeated measurements per test (default: 3)")
    parser.add_argument("--timeout", type=int, default=900, help="Seconds allowed per configuration (default: 900)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        contexts = parse_ints(args.contexts, "contexts", 512)
        batches = parse_ints(args.batches, "batches", 32)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
    if args.repetitions < 1 or args.timeout < 1:
        parser.error("repetitions and timeout must be positive")

    report: dict = {"started_at": datetime.now(timezone.utc).isoformat(), "status": "blocked", "results": []}
    try:
        bench = find_bench(args.llama_bench)
        devices, device_report = gpu_devices(bench)
        report.update({"llama_bench": str(bench), "device_inventory": device_report})
        if not devices:
            raise OptimizerError("No hardware GPU is visible to llama.cpp. CPU and software Vulkan devices are deliberately excluded.")
        available = {name for name, _ in devices}
        device = args.device or devices[0][0]
        if device not in available:
            raise OptimizerError(f"Requested device {device!r} is not in the hardware GPU list: {', '.join(sorted(available))}")
        model_value = args.model or os.environ.get("MULTI_MODAL_GPU_MODEL") or load_saved_model()
        if not model_value and sys.stdin.isatty():
            print("Choose the local Qwen GGUF file to optimize (usually its first shard if split):")
            model_value = input("Model path: ").strip()
        if not model_value:
            raise OptimizerError("No GGUF model path configured; set MULTI_MODAL_GPU_MODEL or provide --model")
        model = Path(model_value).expanduser().resolve()
        if not model.is_file() or model.suffix.lower() != ".gguf":
            raise OptimizerError(f"Model path must be an existing local .gguf file: {model}")
        try:
            save_model_choice(model)
        except OSError as exc:
            raise OptimizerError(f"Could not save local model selection: {exc}") from exc
        report.update({"model": str(model), "device": device, "contexts": contexts, "batches": batches,
                       "repetitions": args.repetitions, "gpu_layers": 99, "cpu_fallback": False})
        print(f"GPU: {device} — {dict(devices)[device]}")
        print(f"Model: {model}")
        print("Running llama-bench with explicit GPU device, 99 GPU layers, and host offload disabled.")
        for context, batch in product(contexts, batches):
            result = benchmark(bench, model, device, context, batch, args.repetitions, args.timeout)
            report["results"].append(result)
            if result["status"] == "passed":
                print(f"PASS · ctx={context} batch={batch} · {result['generation_tokens_per_second']:.2f} generation tok/s")
            else:
                print(f"{result['status'].upper()} · ctx={context} batch={batch} · {result['detail']}")
        successful = [item for item in report["results"] if item["status"] == "passed"]
        if not successful:
            raise OptimizerError("No GPU configuration completed successfully; no CPU fallback was attempted.")
        best = max(successful, key=lambda item: item["generation_tokens_per_second"])
        report.update({"status": "complete", "best": best})
        print(f"Best measured configuration: ctx={best['context']} batch={best['batch']} · "
              f"{best['generation_tokens_per_second']:.2f} generation tok/s")
    except OptimizerError as exc:
        report["error"] = str(exc)
        print(f"BLOCKED · {exc}", file=sys.stderr)
    try:
        report_path = save_report(report)
        print(f"Local report: {report_path}")
    except OSError as exc:
        print(f"Could not save local report: {exc}", file=sys.stderr)
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
