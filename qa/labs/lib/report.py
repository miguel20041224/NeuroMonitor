"""Generador de reportes JSON/Markdown para laboratorios QA."""

from __future__ import annotations

import json
import platform
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

RiskLevel = Literal["alto", "medio", "bajo"]
TestStatus = Literal["PASS", "FAIL", "SKIP", "WARN", "BLOCKED"]


@dataclass
class TestResult:
    id: str
    name: str
    status: TestStatus
    risk: RiskLevel
    message: str
    evidence: str = ""
    duration_ms: float = 0.0
    recommendation: str = ""


@dataclass
class LabReport:
    lab_id: str
    lab_name: str
    started_at: str
    finished_at: str = ""
    environment: dict[str, Any] = field(default_factory=dict)
    results: list[TestResult] = field(default_factory=list)

    def add(self, result: TestResult) -> None:
        self.results.append(result)

    @property
    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.results:
            counts[r.status] = counts.get(r.status, 0) + 1
        return counts

    def finish(self) -> None:
        self.finished_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "lab_id": self.lab_id,
            "lab_name": self.lab_name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "environment": self.environment,
            "summary": self.summary,
            "results": [asdict(r) for r in self.results],
        }


def default_environment() -> dict[str, Any]:
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
    }


def write_lab_report(report: LabReport, reports_dir: Path) -> tuple[Path, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = reports_dir / f"{report.lab_id}_{stamp}.json"
    md_path = reports_dir / f"{report.lab_id}_{stamp}.md"

    json_path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def render_markdown(report: LabReport) -> str:
    lines = [
        f"# {report.lab_name}",
        "",
        f"- **Lab ID:** `{report.lab_id}`",
        f"- **Inicio:** {report.started_at}",
        f"- **Fin:** {report.finished_at}",
        "",
        "## Resumen",
        "",
        "| Estado | Cantidad |",
        "|--------|----------|",
    ]
    for status, count in sorted(report.summary.items()):
        lines.append(f"| {status} | {count} |")

    lines.extend(["", "## Resultados", ""])
    for r in report.results:
        lines.extend(
            [
                f"### {r.id} — {r.name}",
                "",
                f"- **Estado:** {r.status}",
                f"- **Riesgo:** {r.risk}",
                f"- **Duración:** {r.duration_ms:.1f} ms",
                f"- **Mensaje:** {r.message}",
            ]
        )
        if r.evidence:
            lines.append(f"- **Evidencia:** `{r.evidence}`")
        if r.recommendation:
            lines.append(f"- **Recomendación:** {r.recommendation}")
        lines.append("")

    return "\n".join(lines)
