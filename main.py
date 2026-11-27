import platform
import time
import shutil
from pathlib import Path
from datetime import datetime, timezone
from collections import deque

import psutil
from fastapi import FastAPI
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent
history = deque(maxlen=60)

last_time = time.monotonic()
last_net = psutil.net_io_counters()
last_disk = psutil.disk_io_counters()

app = FastAPI(title="LEXSUS SERVER", version="1.0.0")

@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(BASE_DIR / "frontend" / "index.html")

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/v1/system")
def system_info():
    global last_time, last_net, last_disk

    now = time.monotonic()
    elapsed = max(now - last_time, 0.001)

    net = psutil.net_io_counters()
    disk_io = psutil.disk_io_counters()

    rx = max(0, net.bytes_recv - last_net.bytes_recv) * 8 / elapsed / 1_000_000
    tx = max(0, net.bytes_sent - last_net.bytes_sent) * 8 / elapsed / 1_000_000

    read_speed = 0
    write_speed = 0

    if disk_io and last_disk:
        read_speed = max(0, disk_io.read_bytes - last_disk.read_bytes) / elapsed / 1024**2
        write_speed = max(0, disk_io.write_bytes - last_disk.write_bytes) / elapsed / 1024**2

    last_time = now
    last_net = net
    last_disk = disk_io

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hostname": platform.node(),
        "os": platform.system(),
        "os_version": platform.release(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "cpu": {
            "cores": psutil.cpu_count(),
            "usage_percent": psutil.cpu_percent(interval=0.2)
        },
        "memory": {
            "total_gb": round(memory.total / 1024**3, 2),
            "used_gb": round(memory.used / 1024**3, 2),
            "usage_percent": memory.percent
        },
        "disk": {
            "total_gb": round(disk.total / 1024**3, 2),
            "free_gb": round(disk.free / 1024**3, 2),
            "usage_percent": disk.percent
        },
        "network": {
            "sent_mb": round(net.bytes_sent / 1024**2, 2),
            "received_mb": round(net.bytes_recv / 1024**2, 2),
            "rx_mbps": round(rx, 3),
            "tx_mbps": round(tx, 3)
        },
        "disk_io": {
            "read_mbps": round(read_speed, 3),
            "write_mbps": round(write_speed, 3)
        },
        "uptime_seconds": int(time.time() - psutil.boot_time())
    }

    history.append({
        "timestamp": result["timestamp"],
        "cpu": result["cpu"]["usage_percent"],
        "ram": memory.percent,
        "network_rx_mbps": result["network"]["rx_mbps"],
        "network_tx_mbps": result["network"]["tx_mbps"],
        "disk_read_mbps": result["disk_io"]["read_mbps"],
        "disk_write_mbps": result["disk_io"]["write_mbps"]
    })

    return result

@app.get("/api/v1/metrics/history")
def metrics_history():
    return {"items": list(history), "count": len(history)}

@app.get("/api/v1/services")
def services():
    programs = {
        "Python": "python3",
        "Node.js": "node",
        "MySQL": "mysql",
        "PHP": "php",
        "Nginx": "nginx",
        "Docker": "docker",
        "PostgreSQL": "psql"
    }

    return {
        name: {
            "installed": bool(shutil.which(command)),
            "path": shutil.which(command)
        }
        for name, command in programs.items()
    }
