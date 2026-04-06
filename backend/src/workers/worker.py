"""Standalone worker that polls the DB queue and executes jobs.

Can run as a separate process: python -m src.workers.worker
"""

import json
import logging
import signal
import tempfile
import threading
import time
import traceback
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..db.models import Job, JobType, ScenarioRecord
from ..models.scenario import ComparisonRequest, Scenario
from ..spine import run_comparison, run_single_scenario
from .queue import (
    claim_next_job,
    generate_worker_id,
    heartbeat,
    mark_completed,
    mark_failed,
    recover_interrupted_jobs,
)

logger = logging.getLogger(__name__)

POLL_INTERVAL = 2.0
HEARTBEAT_INTERVAL = 10.0


class Worker:
    def __init__(self, db_url: str = "sqlite:///./palm4u.db"):
        self.worker_id = generate_worker_id()
        self.engine = create_engine(db_url)
        self.SessionFactory = sessionmaker(bind=self.engine)
        self._running = True
        self._current_job_id: int | None = None

    def start(self) -> None:
        logger.info("Worker %s starting", self.worker_id)

        # Recover any jobs left running from a previous crash
        with self._session() as session:
            recovered = recover_interrupted_jobs(session)
            if recovered:
                logger.info("Recovered %d interrupted jobs", recovered)

        # Start heartbeat thread
        hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        hb_thread.start()

        # Main poll loop
        while self._running:
            try:
                self._poll_and_execute()
            except Exception:
                logger.exception("Error in poll loop")
            time.sleep(POLL_INTERVAL)

        logger.info("Worker %s stopped", self.worker_id)
        self.engine.dispose()

    def stop(self) -> None:
        logger.info("Worker %s stopping gracefully", self.worker_id)
        self._running = False

    def _session(self) -> Session:
        return self.SessionFactory()

    def _poll_and_execute(self) -> None:
        session = self._session()
        try:
            job = claim_next_job(session, self.worker_id)
            if job is None:
                return

            self._current_job_id = job.id
            logger.info("Worker %s claimed job %d", self.worker_id, job.id)

            try:
                self._execute_job(session, job)
            except Exception as exc:
                error_msg = f"{exc}\n{traceback.format_exc()}"
                logger.error("Job %d failed: %s", job.id, exc)
                mark_failed(session, job.id, error_msg)
            finally:
                self._current_job_id = None
        finally:
            session.close()

    def _execute_job(self, session: Session, job: Job) -> None:
        baseline_rec = session.query(ScenarioRecord).filter(
            ScenarioRecord.id == job.baseline_scenario_id
        ).first()
        if not baseline_rec:
            raise RuntimeError(f"Baseline scenario {job.baseline_scenario_id} not found")

        baseline = Scenario(**json.loads(baseline_rec.scenario_json))
        output_dir = Path(tempfile.mkdtemp(prefix=f"palm4u_job_{job.id}_"))

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
                name=f"Job {job.id} comparison",
            )
            spine_result = run_comparison(request, output_dir, stub=True)
            result_summary = _serialize_comparison_result(spine_result, baseline)
        else:
            spine_result = run_single_scenario(baseline, output_dir, stub=True)
            result_summary = _serialize_single_result(spine_result)

        result_json = json.dumps(result_summary, default=str)
        mark_completed(session, job.id, result_json, str(output_dir))
        logger.info("Job %d completed", job.id)

    def _heartbeat_loop(self) -> None:
        while self._running:
            job_id = self._current_job_id
            if job_id is not None:
                try:
                    session = self._session()
                    try:
                        ok = heartbeat(session, job_id, self.worker_id)
                        if not ok:
                            logger.warning("Heartbeat rejected for job %d", job_id)
                    finally:
                        session.close()
                except Exception:
                    logger.exception("Heartbeat error for job %d", job_id)
            time.sleep(HEARTBEAT_INTERVAL)


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


def main():
    import os
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    db_url = os.getenv("DATABASE_URL_SYNC", "sqlite:///./palm4u.db")
    worker = Worker(db_url)

    def handle_signal(sig, frame):
        worker.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    worker.start()


if __name__ == "__main__":
    main()
