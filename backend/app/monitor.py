"""Structured server monitoring.

Runs a small set of diagnostic commands over SSH and parses them into
structured data, falling back to the raw command output when a command is
missing or its output cannot be parsed. Every parser is defensive: it never
raises, so a single broken command cannot fail the whole monitor request.
"""
import csv
import io
from typing import Any, Dict, List, Optional

from . import ssh

GPU_QUERY = (
    "nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total "
    "--format=csv,noheader,nounits"
)
GPU_RAW = "nvidia-smi"
MEMORY_COMMAND = "free -m"
DISK_COMMAND = "df -h"
LOAD_COMMAND = "cat /proc/loadavg"
PROCESSES_COMMAND = "ps aux --sort=-%mem | head"


def parse_gpu(output: str) -> List[Dict[str, Any]]:
    """Parse ``nvidia-smi --query-gpu=... --format=csv`` output into GPU rows."""
    if not output:
        return []
    gpus: List[Dict[str, Any]] = []
    for row in csv.reader(io.StringIO(output)):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) < 5:
            continue
        try:
            index = int(float(row[0].strip()))
            name = row[1].strip()
            utilization = int(float(row[2].strip()))
            memory_used = int(float(row[3].strip()))
            memory_total = int(float(row[4].strip()))
        except (ValueError, IndexError):
            continue
        gpus.append(
            {
                "index": index,
                "name": name,
                "utilization": utilization,
                "memory_used_mb": memory_used,
                "memory_total_mb": memory_total,
            }
        )
    return gpus


def parse_memory(output: str) -> Optional[Dict[str, int]]:
    """Parse the ``Mem:`` line of ``free -m`` into ``{used_mb, total_mb}``."""
    for line in (output or "").splitlines():
        if not line.startswith("Mem:"):
            continue
        parts = line.split()
        if len(parts) < 3:
            return None
        try:
            total = int(float(parts[1]))
            used = int(float(parts[2]))
        except ValueError:
            return None
        return {"used_mb": used, "total_mb": total}
    return None


def parse_disk(output: str) -> List[Dict[str, Any]]:
    """Parse ``df -h`` output into a list of filesystem rows."""
    disks: List[Dict[str, Any]] = []
    for line in (output or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("Filesystem"):
            continue
        parts = stripped.split()
        if len(parts) < 6:
            continue
        use_percent: Optional[int] = None
        try:
            use_percent = int(float(parts[4].rstrip("%")))
        except ValueError:
            pass
        disks.append(
            {
                "filesystem": parts[0],
                "size": parts[1],
                "used": parts[2],
                "use_percent": use_percent,
                "mount": " ".join(parts[5:]),
            }
        )
    return disks


def parse_load(output: str) -> Optional[List[float]]:
    """Parse ``cat /proc/loadavg`` into ``[1min, 5min, 15min]``."""
    lines = (output or "").strip().splitlines()
    if not lines:
        return None
    parts = lines[0].split()
    if len(parts) < 3:
        return None
    try:
        return [float(parts[0]), float(parts[1]), float(parts[2])]
    except ValueError:
        return None


def parse_processes(output: str) -> List[str]:
    """Split ``ps aux`` output into individual lines."""
    if not output:
        return []
    return [line for line in output.splitlines() if line.strip()]


def _run(server: Dict[str, Any], command: str, raw: Dict[str, str], key: str):
    try:
        return ssh.exec_command(server, command)
    except ssh.SSHError as exc:
        raw[key] = f"执行失败: {exc}"
        return None


def _collect_gpu(server: Dict[str, Any], raw: Dict[str, str]) -> List[Dict[str, Any]]:
    try:
        out = ssh.exec_command(server, GPU_QUERY)
    except ssh.SSHError as exc:
        raw["gpu"] = f"执行失败: {exc}"
        return []
    gpus = parse_gpu(out)
    if gpus:
        return gpus
    try:
        raw["gpu"] = ssh.exec_command(server, GPU_RAW)
    except ssh.SSHError as exc:
        raw["gpu"] = f"执行失败: {exc}"
    return []


def _collect_memory(
    server: Dict[str, Any], raw: Dict[str, str]
) -> Optional[Dict[str, int]]:
    out = _run(server, MEMORY_COMMAND, raw, "memory")
    if out is None:
        return None
    parsed = parse_memory(out)
    if parsed is None:
        raw["memory"] = out
    return parsed


def _collect_disk(server: Dict[str, Any], raw: Dict[str, str]) -> List[Dict[str, Any]]:
    out = _run(server, DISK_COMMAND, raw, "disk")
    if out is None:
        return []
    parsed = parse_disk(out)
    if not parsed:
        raw["disk"] = out
    return parsed


def _collect_load(server: Dict[str, Any], raw: Dict[str, str]) -> List[float]:
    out = _run(server, LOAD_COMMAND, raw, "load")
    if out is None:
        return []
    parsed = parse_load(out)
    if parsed is None:
        raw["load"] = out
        return []
    return parsed


def _collect_processes(
    server: Dict[str, Any], raw: Dict[str, str]
) -> List[str]:
    out = _run(server, PROCESSES_COMMAND, raw, "processes")
    if out is None:
        return []
    parsed = parse_processes(out)
    if not parsed:
        raw["processes"] = out
    return parsed


def collect(server: Dict[str, Any]) -> Dict[str, Any]:
    """Collect and structure monitor data for a server."""
    raw: Dict[str, str] = {}
    result = {
        "gpu": _collect_gpu(server, raw),
        "load": _collect_load(server, raw),
        "memory": _collect_memory(server, raw),
        "disk": _collect_disk(server, raw),
        "processes": _collect_processes(server, raw),
        "raw": raw,
    }
    return result
