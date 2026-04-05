"""Background job executor using threads (local dev, no Celery needed)."""

import json
import tempfile
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..db.models import Job, JobStatus, JobType, ScenarioRecord
from ..models.scenario import ComparisonRequest, Scenario
from ..spine import run_comparison, run_single_scenario

SYNC_DATABASE_URL = "sqlite:///./palm4u.db"

_jobs_progress: dict[int, dict] = {}
_lock = threading.Lock()


def get_job_progress(job_id: int) -> dict:
    with _lock:
        return _jobs_progress.get(job_id, {"status": "unknown"})


def _update_progress(job_id: int, data: dict) -> None:
    with _lock:
        _jobs_progress[job_id] = data


def run_job_background(job_id: int, db_url: str | None = None) -> None:
    thread = threading.Thread(
        target=_execute_job,
        args=(job_id, db_url),
        daemon=True,
    )
    thread.start()


def _execute_job(job_id: int, db_url: str | None = None) -> None:
    sync_engine = create_engine(db_url or SYNC_DATABASE_URL)
    SyncSession = sessionmaker(bind=sync_engine)
    session: Session = SyncSession()

    try:
        job: Job | None = session.query(Job).filter(Job.id == job_id).first()
        if job is None:
            _update_progress(job_id, {"status": "failed", "error": "Job not found"})
            return

        job.status = JobStatus.running
        job.started_at = datetime.now(timezone.utc)
        session.commit()
        _update_progress(job_id, {"status": "running", "progress": 0})

        # Load scenario(s) from DB
        baseline_rec = session.query(ScenarioRecord).filter(
            ScenarioRecord.id == job.baseline_scenario_id
        ).first()
        if not baseline_rec:
            raise RuntimeError(f"Baseline scenario {job.baseline_scenario_id} not found")

        baseline = Scenario(**json.loads(baseline_rec.scenario_json))
        output_dir = Path(tempfile.mkdtemp(prefix=f"palm4u_job_{job_id}_"))

        if job.job_type == JobType.comparison and job.intervention_scenario_id:
            intervention_rec = session.query(ScenarioRecord).filter(
                ScenarioRecord.id == job.intervention_scenario_id
            ).first()
            if not intervention_rec:
                raise RuntimeError(f"Intervention scenario {job.intervention_scenario_id} not found")

            intervention = Scenario(**json.loads(intervention_rec.scenario_json))
            request = ComparisonRequest(
                baseline=baseline,
                intervention=intervention,
                name=f"Job {job_id} comparison",
            )
            _update_progress(job_id, {"status": "running", "progress": 10})
            spine_result = run_comparison(request, output_dir, stub=True)

            result_summary = _serialize_comparison_result(spine_result, baseline)
        else:
            _update_progress(job_id, {"status": "running", "progress": 10})
            spine_result = run_single_scenario(baseline, output_dir, stub=True)

            result_summary = _serialize_single_result(spine_result)

        job.status = JobStatus.completed
        job.result_json = json.dumps(result_summary, default=str)
        job.output_dir = str(output_dir)
        job.completed_at = datetime.now(timezone.utc)
        session.commit()

        _update_progress(job_id, {"status": "completed", "progress": 100})

    except Exception as exc:
        session.rollback()
        error_msg = f"{exc}\n{traceback.format_exc()}"

        try:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.failed
                job.error_message = error_msg
                job.completed_at = datetime.now(timezone.utc)
                session.commit()
        except Exception:
            pass

        _update_progress(job_id, {"status": "failed", "error": str(exc)})

    finally:
        session.close()
        sync_engine.dispose()


def _serialize_single_result(result) -> dict:
    """Extract serializable summary from SpineResult."""
    summary: dict = {
        "type": "single",
        "domain": {
            "west": result.scenario.domain.bbox.west,
            "south": result.scenario.domain.bbox.south,
            "east": result.scenario.domain.bbox.east,
            "north": result.scenario.domain.bbox.north,
            "epsg": result.scenario.domain.epsg,
        },
    }

    if result.postprocessing:
        pp = result.postprocessing
        summary["statistics"] = {}
        for var_name, stats in pp.statistics.items():
            summary["statistics"][var_name] = {
                "mean": stats.mean,
                "median": stats.median,
                "std": stats.std,
                "p05": stats.p05,
                "p95": stats.p95,
                "min_val": stats.min_val,
                "max_val": stats.max_val,
                "n_valid": stats.n_valid,
            }
        if pp.pet_classification:
            pc = pp.pet_classification
            summary["pet_classification"] = {
                "class_fractions": pc.class_fractions,
                "dominant_class": pc.dominant_class,
                "stress_level": pc.stress_level,
            }
        summary["n_timesteps"] = pp.metadata.get("n_timesteps", 0)

    if result.confidence:
        c = result.confidence
        summary["confidence"] = {
            "level": c.level.value,
            "tier": c.tier.value,
            "headline": c.headline,
            "detail": c.detail,
            "caveats": c.caveats,
            "suitable_for": c.suitable_for,
            "not_suitable_for": c.not_suitable_for,
        }

    if result.report_path:
        summary["report_path"] = str(result.report_path)

    return summary


def _serialize_comparison_result(result, baseline_scenario) -> dict:
    """Extract serializable summary from ComparisonSpineResult."""
    summary = _serialize_single_result(result.baseline)
    summary["type"] = "comparison"

    if result.comparison:
        comp = result.comparison
        summary["delta_statistics"] = {}
        for var_name, ds in comp.delta_statistics.items():
            summary["delta_statistics"][var_name] = {
                "mean_delta": ds.mean_delta,
                "median_delta": ds.median_delta,
                "max_improvement": ds.max_improvement,
                "max_worsening": ds.max_worsening,
                "pct_improved": ds.pct_improved,
                "pct_worsened": ds.pct_worsened,
                "pct_unchanged": ds.pct_unchanged,
                "n_valid": ds.n_valid,
            }
        summary["threshold_impacts"] = [
            {
                "variable": ti.variable,
                "threshold_name": ti.threshold_name,
                "threshold_value": ti.threshold_value,
                "cells_above_baseline": ti.cells_above_baseline,
                "cells_above_intervention": ti.cells_above_intervention,
                "cells_improved": ti.cells_improved,
                "cells_worsened": ti.cells_worsened,
                "pct_improved": ti.pct_improved,
            }
            for ti in comp.threshold_impacts
        ]
        summary["ranked_improvements"] = [
            {
                "variable": ri.variable,
                "region_description": ri.region_description,
                "mean_delta": ri.mean_delta,
                "area_m2": ri.area_m2,
            }
            for ri in comp.ranked_improvements
        ]

    if result.confidence:
        c = result.confidence
        summary["confidence"] = {
            "level": c.level.value,
            "tier": c.tier.value,
            "headline": c.headline,
            "detail": c.detail,
            "caveats": c.caveats,
            "suitable_for": c.suitable_for,
            "not_suitable_for": c.not_suitable_for,
        }

    # Include intervention statistics too
    if result.intervention and result.intervention.postprocessing:
        ipp = result.intervention.postprocessing
        summary["intervention_statistics"] = {}
        for var_name, stats in ipp.statistics.items():
            summary["intervention_statistics"][var_name] = {
                "mean": stats.mean,
                "median": stats.median,
                "std": stats.std,
                "p05": stats.p05,
                "p95": stats.p95,
                "min_val": stats.min_val,
                "max_val": stats.max_val,
                "n_valid": stats.n_valid,
            }

    return summary
