from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agents.audit import AuditLog
from documents.download import PdfStore


@dataclass
class WorkflowDeps:
    pdf_store: PdfStore
    audit: AuditLog
    knowledge_root: Path = field(default_factory=lambda: Path("knowledge/client_manuals"))
