from app import monitor, ssh


def test_parse_gpu():
    out = (
        "0, NVIDIA A100 80GB, 85, 20000, 80000\n"
        "1, NVIDIA A100 80GB, 10, 3000, 80000\n"
    )
    gpus = monitor.parse_gpu(out)
    assert len(gpus) == 2
    assert gpus[0] == {
        "index": 0,
        "name": "NVIDIA A100 80GB",
        "utilization": 85,
        "memory_used_mb": 20000,
        "memory_total_mb": 80000,
    }
    assert gpus[1]["index"] == 1


def test_parse_gpu_tolerates_garbage():
    assert monitor.parse_gpu("") == []
    assert monitor.parse_gpu("garbage") == []
    assert monitor.parse_gpu("NVIDIA-SMI has failed because it couldn't communicate") == []
    assert monitor.parse_gpu("0, Name, not-a-number, 1, 2") == []


def test_parse_memory():
    out = (
        "              total        used        free      shared  buff/cache   available\n"
        "Mem:          32000       12345        1000         100       18655       19000\n"
        "Swap:          8192           0        8192\n"
    )
    assert monitor.parse_memory(out) == {"used_mb": 12345, "total_mb": 32000}
    assert monitor.parse_memory("free: command not found") is None
    assert monitor.parse_memory("") is None


def test_parse_disk():
    out = (
        "Filesystem      Size  Used Avail Use% Mounted on\n"
        "/dev/sda1       1.0T  500G  400G  56% /\n"
        "/dev/sdb1       2.0T  1.0T  1.0T  50% /data\n"
    )
    disks = monitor.parse_disk(out)
    assert len(disks) == 2
    assert disks[0]["filesystem"] == "/dev/sda1"
    assert disks[0]["size"] == "1.0T"
    assert disks[0]["used"] == "500G"
    assert disks[0]["use_percent"] == 56
    assert disks[0]["mount"] == "/"
    assert disks[1]["mount"] == "/data"


def test_parse_load():
    assert monitor.parse_load("1.20 0.80 0.50 1/123 4567\n") == [1.2, 0.8, 0.5]
    assert monitor.parse_load("garbage") is None
    assert monitor.parse_load("") is None


def test_parse_processes():
    out = "USER       PID %CPU %MEM\nroot         1  0.0  0.1\nroot         2  0.0  0.2\n"
    assert monitor.parse_processes(out) == [
        "USER       PID %CPU %MEM",
        "root         1  0.0  0.1",
        "root         2  0.0  0.2",
    ]
    assert monitor.parse_processes("") == []


def test_collect_structured(monkeypatch):
    def fake_exec(server, command, timeout=60.0):
        return {
            monitor.GPU_QUERY: "0, NVIDIA A100, 85, 20000, 80000\n",
            monitor.MEMORY_COMMAND: (
                "              total        used        free      shared  buff/cache   available\n"
                "Mem:          32000       12345        1000         100       18655       19000\n"
            ),
            monitor.DISK_COMMAND: (
                "Filesystem      Size  Used Avail Use% Mounted on\n"
                "/dev/sda1       1.0T  500G  400G  56% /\n"
            ),
            monitor.LOAD_COMMAND: "1.2 0.8 0.5 1/1 1\n",
            monitor.PROCESSES_COMMAND: "USER PID\nroot 1\n",
        }[command]

    monkeypatch.setattr(ssh, "exec_command", fake_exec)
    result = monitor.collect({"host": "h"})
    assert result["gpu"][0]["name"] == "NVIDIA A100"
    assert result["memory"] == {"used_mb": 12345, "total_mb": 32000}
    assert result["load"] == [1.2, 0.8, 0.5]
    assert result["disk"][0]["mount"] == "/"
    assert result["processes"] == ["USER PID", "root 1"]
    assert result["raw"] == {}


def test_collect_gpu_fallback(monkeypatch):
    def fake_exec(server, command, timeout=60.0):
        if command == monitor.GPU_QUERY:
            return "NVIDIA-SMI has failed"
        if command == monitor.GPU_RAW:
            return "no gpu here"
        if command == monitor.MEMORY_COMMAND:
            return "free: command not found"
        return "ok"

    monkeypatch.setattr(ssh, "exec_command", fake_exec)
    result = monitor.collect({"host": "h"})
    assert result["gpu"] == []
    assert result["raw"]["gpu"] == "no gpu here"
    assert result["memory"] is None
    assert "free" in result["raw"]["memory"]


def test_collect_command_error_does_not_break(monkeypatch):
    def flaky_exec(server, command, timeout=60.0):
        if command == monitor.GPU_QUERY:
            raise ssh.SSHError("command not found")
        return "ok"

    monkeypatch.setattr(ssh, "exec_command", flaky_exec)
    result = monitor.collect({"host": "h"})
    assert result["gpu"] == []
    assert "执行失败" in result["raw"]["gpu"]
    assert "gpu" in result
    assert "load" in result
    assert "memory" in result
    assert "disk" in result
    assert "processes" in result
    assert "raw" in result
