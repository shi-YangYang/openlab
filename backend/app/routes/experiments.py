"""Experiment routes: plan generation and remote run orchestration."""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, WebSocket
from fastapi.responses import Response

from .. import database, export, experiment, servers
from ..metrics_extractor import extract_metrics
from ..schemas import (
    ExperimentHistoryItem,
    ExperimentRecord,
    ExperimentRequest,
    ExperimentRun,
    ExperimentRunCompareRequest,
    ExperimentRunCompareResponse,
    ExperimentRunCreate,
    ExperimentRunMetricsUpdate,
    ExperimentRunStartRequest,
)

router = APIRouter()
runs_router = APIRouter()


@router.get("", response_model=List[ExperimentHistoryItem])
async def list_experiments() -> List[dict]:
    return [_experiment_history_item(r) for r in database.list_experiment_history()]


@router.get("/{experiment_id}", response_model=ExperimentRecord)
async def get_experiment(experiment_id: int) -> dict:
    record = database.get_experiment(experiment_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No experiment {experiment_id}")
    return record


@router.get("/{experiment_id}/export")
async def export_experiment(experiment_id: int) -> Response:
    record = database.get_experiment(experiment_id)
    if record is None or record.get("content") is None:
        raise HTTPException(status_code=404, detail=f"No experiment {experiment_id}")
    markdown = export.experiments_to_markdown(
        record["content"],
        _experiment_source_label(record),
        record.get("language", "zh"),
    )
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="experiments-{experiment_id}.md"'
        },
    )


@router.post("", response_model=ExperimentRecord)
async def create_experiment(
    req: ExperimentRequest, background_tasks: BackgroundTasks
) -> dict:
    # Business rule: experiment plans are generated one-to-one from innovation
    # points (spec-007 flow). Direct paper-based generation is not offered.
    if req.source_type != "innovation":
        raise HTTPException(
            status_code=400,
            detail="实验方案必须基于创新点生成（source_type 必须为 'innovation'）",
        )
    if not 1 <= req.count <= 3:
        raise HTTPException(status_code=400, detail="count must be between 1 and 3")

    innovation_id = req.innovation_id
    if innovation_id is None:
        raise HTTPException(
            status_code=400,
            detail="innovation_id is required for source_type=innovation",
        )
    innovation = database.get_innovation(innovation_id)
    if innovation is None:
        raise HTTPException(
            status_code=404, detail=f"Innovation not found: {innovation_id}"
        )
    arxiv_ids = innovation.get("arxiv_ids", [])

    experiment_id = database.insert_experiment(
        req.source_type, innovation_id, arxiv_ids, None, req.language, status="pending"
    )
    background_tasks.add_task(
        experiment.run_experiment_job,
        experiment_id,
        req.source_type,
        innovation_id,
        arxiv_ids,
        req.language,
        req.count,
    )
    record = database.get_experiment(experiment_id)
    if record is None:
        raise HTTPException(status_code=500, detail="experiment record not found")
    return record


@router.delete("/{experiment_id}")
async def delete_experiment(experiment_id: int) -> dict:
    from ..experiment_runner import ExperimentRunDriver, delete_log

    runs = [
        r
        for r in database.list_experiment_runs()
        if r.get("experiment_id") == experiment_id
    ]
    for run in runs:
        driver = ExperimentRunDriver.get(run["id"])
        if driver is not None and driver.task is not None and not driver.task.done():
            await driver.stop_run()
        database.delete_experiment_run(run["id"])
        delete_log(run["id"])
    if not database.delete_experiment(experiment_id):
        raise HTTPException(status_code=404, detail=f"No experiment {experiment_id}")
    return {"status": "ok"}


@router.delete("")
async def clear_experiments() -> dict:
    database.clear_experiments()
    return {"status": "ok"}


# --------------------------- Experiment runs ---------------------------------


@runs_router.get("")
async def list_experiment_runs() -> List[dict]:
    return database.list_experiment_runs()


@runs_router.post("/compare", response_model=ExperimentRunCompareResponse)
async def compare_experiment_runs(req: ExperimentRunCompareRequest) -> dict:
    """Compare 2-10 runs side by side (spec-038 FR-3)."""
    if not 2 <= len(req.ids) <= 10:
        raise HTTPException(status_code=400, detail="ids 必须包含 2-10 个 run id")
    items = []
    metric_keys = set()
    for run_id in req.ids:
        run = database.get_experiment_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
        experiment_record = database.get_experiment(run.get("experiment_id"))
        metrics = run.get("metrics") or {}
        metric_keys.update(metrics)
        items.append(
            {
                "id": run["id"],
                "experiment_title": _experiment_title(experiment_record),
                "mode": run.get("mode") or "manual",
                "status": run.get("status") or "pending",
                "server_id": run.get("server_id") or "",
                "duration_seconds": _parse_duration_seconds(
                    run.get("created_at"), run.get("updated_at")
                ),
                "created_at": run.get("created_at"),
                "metrics": metrics,
                "error": run.get("error") or "",
            }
        )
    return {"runs": items, "metric_keys": sorted(metric_keys)}


@runs_router.get("/{run_id}")
async def get_experiment_run(run_id: int) -> dict:
    run = database.get_experiment_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    from ..experiment_runner import read_log_tail

    return {**run, "log_tail": read_log_tail(run_id, 200)}


@runs_router.post("")
async def create_experiment_run(req: ExperimentRunCreate) -> dict:
    if database.get_experiment(req.experiment_id) is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if servers.get_server(req.server_id) is None:
        raise HTTPException(status_code=404, detail="Server not found")
    from ..experiment_runner import build_default_steps

    default_workdir = f"~/openlab-experiments/{req.experiment_id}"
    workdir = req.remote_workdir.strip() or default_workdir
    steps = build_default_steps(workdir, req.repo_url.strip())
    run = database.create_experiment_run(
        experiment_id=req.experiment_id,
        server_id=req.server_id,
        mode=req.mode,
        remote_workdir=workdir,
        launch_command=steps.get("launch_training", ""),
    )
    return {**run, "steps": steps}


@runs_router.post("/{run_id}/start")
async def start_experiment_run(run_id: int, req: ExperimentRunStartRequest) -> dict:
    if database.get_experiment_run(run_id) is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    from ..experiment_runner import ExperimentRunDriver

    driver = ExperimentRunDriver.get_or_create(run_id)
    try:
        driver.start(req.steps)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"status": "started", "run_id": run_id}


@runs_router.delete("/{run_id}")
async def delete_experiment_run_endpoint(run_id: int) -> dict:
    from ..experiment_runner import ExperimentRunDriver, delete_log

    driver = ExperimentRunDriver.get(run_id)
    if driver is not None and driver.task is not None and not driver.task.done():
        await driver.stop_run()
    if not database.delete_experiment_run(run_id):
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    delete_log(run_id)
    return {"status": "ok"}


@runs_router.post("/{run_id}/metrics/extract", response_model=ExperimentRun)
async def extract_run_metrics(run_id: int) -> dict:
    """Re-extract metrics from the run's log file (spec-038 FR-3)."""
    run = database.get_experiment_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    log_path = run.get("log_path")
    if not log_path:
        from ..experiment_runner import run_log_path

        log_path = str(run_log_path(run_id))
    if not Path(log_path).is_file():
        raise HTTPException(status_code=400, detail=f"日志文件不存在: {log_path}")
    metrics = extract_metrics(log_path)
    database.set_experiment_run_metrics(run_id, metrics)
    return database.get_experiment_run(run_id)


@runs_router.put("/{run_id}/metrics", response_model=ExperimentRun)
async def update_run_metrics(run_id: int, req: ExperimentRunMetricsUpdate) -> dict:
    """Manually edit/overwrite a run's metrics (spec-038 FR-3)."""
    if database.get_experiment_run(run_id) is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    cleaned: Dict[str, float] = {}
    for key, value in req.metrics.items():
        try:
            cleaned[str(key)] = float(value)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400, detail=f"指标值无法转为数字: {key}={value}"
            )
    database.set_experiment_run_metrics(run_id, cleaned)
    return database.get_experiment_run(run_id)


@runs_router.websocket("/ws")
async def experiment_run_ws(websocket: WebSocket, run_id: int) -> None:
    from .. import experiment_runner as runner_module

    await websocket.accept()
    driver = runner_module.ExperimentRunDriver.get_or_create(run_id)

    async def on_event(event: dict) -> None:
        try:
            await websocket.send_text(json.dumps(event, ensure_ascii=False))
        except Exception:
            pass

    driver.attach(on_event)
    try:
        while True:
            message = await websocket.receive_text()
            try:
                data = json.loads(message)
            except ValueError:
                continue
            action = data.get("action")
            if action in ("retry", "skip"):
                try:
                    driver.resume_with_action(
                        action,
                        str(data.get("step") or ""),
                        str(data.get("command") or ""),
                    )
                except (RuntimeError, ValueError):
                    pass
            elif data.get("type") == "stop":
                await driver.stop_run()
    except Exception:
        pass
    finally:
        driver.detach(on_event)


def _experiment_source_label(record: dict) -> str:
    if record.get("source_type") == "innovation":
        return f"创新点 #{record.get('innovation_id')}"
    arxiv_ids = record.get("arxiv_ids", [])
    return "论文: " + (", ".join(arxiv_ids) if arxiv_ids else "-")


def _experiment_title(record: Optional[dict]) -> str:
    if not record:
        return ""
    if record.get("source_type") == "innovation":
        return f"创新点 #{record.get('innovation_id')}"
    paper_count = len(record.get("arxiv_ids") or [])
    return f"论文: {paper_count} 篇"


def _parse_timestamp(value: object) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _parse_duration_seconds(
    created_at: object, updated_at: object
) -> Optional[float]:
    created = _parse_timestamp(created_at)
    updated = _parse_timestamp(updated_at)
    if created is None or updated is None:
        return None
    seconds = (updated - created).total_seconds()
    return round(seconds, 1) if seconds >= 0 else None


def _experiment_history_item(record: dict) -> dict:
    record["source_label"] = (
        f"创新点 #{record.get('innovation_id')}"
        if record.get("source_type") == "innovation"
        else f"论文: {len(record.get('arxiv_ids', []))} 篇"
    )
    return record
