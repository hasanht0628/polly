from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "workflow_runs.db"


@dataclass
class WorkflowRun:
    run_id: str
    workflow_type: str
    status: str
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] | None = None
    tool_log: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class AuditLog:
    def __init__(self, db_path: Path = DEFAULT_DB) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    run_id TEXT PRIMARY KEY,
                    workflow_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    inputs TEXT NOT NULL,
                    outputs TEXT,
                    tool_log TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def start_run(self, workflow_type: str, inputs: dict[str, Any]) -> WorkflowRun:
        run = WorkflowRun(
            run_id=str(uuid.uuid4()),
            workflow_type=workflow_type,
            status="proposed",
            inputs=inputs,
        )
        self.save_run(run)
        return run

    def log_tool(self, run: WorkflowRun, tool_name: str, detail: dict[str, Any]) -> None:
        run.tool_log.append(
            {"tool": tool_name, "detail": detail, "at": datetime.now(timezone.utc).isoformat()}
        )
        self.save_run(run)

    def complete_run(self, run: WorkflowRun, outputs: dict[str, Any], *, status: str = "completed") -> None:
        run.status = status
        run.outputs = outputs
        self.save_run(run)

    def save_run(self, run: WorkflowRun) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO workflow_runs
                (run_id, workflow_type, status, inputs, outputs, tool_log, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.workflow_type,
                    run.status,
                    json.dumps(run.inputs),
                    json.dumps(run.outputs) if run.outputs else None,
                    json.dumps(run.tool_log),
                    run.created_at,
                ),
            )

    def get_run(self, run_id: str) -> WorkflowRun | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT run_id, workflow_type, status, inputs, outputs, tool_log, created_at FROM workflow_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        return WorkflowRun(
            run_id=row[0],
            workflow_type=row[1],
            status=row[2],
            inputs=json.loads(row[3]),
            outputs=json.loads(row[4]) if row[4] else None,
            tool_log=json.loads(row[5]),
            created_at=row[6],
        )
