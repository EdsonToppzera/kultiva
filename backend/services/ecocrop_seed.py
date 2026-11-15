"""Idempotent SQLAlchemy seed for FAO EcoCrop limits and synonyms."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.db import models

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_PROCESSED_DIR = ROOT_DIR / "data" / "processed"
_BATCH_SIZE = 1000


def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def _to_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(float(value))


def _to_str(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return None
    return value


def _insert_in_batches(
    db: Session, model: type, rows: List[Dict[str, Any]], batch_size: int = _BATCH_SIZE
) -> None:
    for start in range(0, len(rows), batch_size):
        db.bulk_insert_mappings(model, rows[start : start + batch_size])


def seed_ecocrop(
    db: Session,
    *,
    processed_dir: Optional[Path] = None,
    reset: bool = False,
) -> Tuple[int, int]:
    """Populate ``culturas_limites`` and ``culturas_sinonimos`` from processed CSVs.

    Returns:
        Tuple ``(limites_inserted, sinonimos_inserted)``.
    """
    target_dir = processed_dir or DEFAULT_PROCESSED_DIR
    limites_csv = target_dir / "ecocrop_culturas_limites.csv"
    sinonimos_csv = target_dir / "ecocrop_culturas_sinonimos.csv"

    if not limites_csv.exists():
        logger.warning(
            "Arquivo EcoCrop não encontrado em %s; pulando ingestão.", limites_csv
        )
        return 0, 0

    existing = db.query(models.CulturaLimite).count()
    if existing > 0 and not reset:
        return 0, 0

    if reset and existing > 0:
        db.query(models.CulturaSinonimo).delete(synchronize_session=False)
        db.query(models.CulturaLimite).delete(synchronize_session=False)
        db.flush()

    limites_rows: List[Dict[str, Any]] = []
    with limites_csv.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            sci = _to_str(row.get("scientific_name"))
            if not sci:
                continue
            limites_rows.append(
                {
                    "scientific_name": sci,
                    "ecoport_code": _to_str(row.get("ecoport_code")),
                    "famname_raw": _to_str(row.get("famname_raw")),
                    "family": _to_str(row.get("family")),
                    "comname": _to_str(row.get("comname")),
                    "tmin": _to_float(row.get("tmin")),
                    "tmax": _to_float(row.get("tmax")),
                    "topmn": _to_float(row.get("topmn")),
                    "topmx": _to_float(row.get("topmx")),
                    "rmin": _to_float(row.get("rmin")),
                    "rmax": _to_float(row.get("rmax")),
                    "ropmn": _to_float(row.get("ropmn")),
                    "ropmx": _to_float(row.get("ropmx")),
                    "gmin": _to_int(row.get("gmin")),
                    "gmax": _to_int(row.get("gmax")),
                    "lispa": _to_str(row.get("lispa")),
                    "cat": _to_str(row.get("cat")),
                }
            )

    _insert_in_batches(db, models.CulturaLimite, limites_rows)

    sinonimos_rows: List[Dict[str, Any]] = []
    if sinonimos_csv.exists():
        with sinonimos_csv.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                sci = _to_str(row.get("scientific_name"))
                syn = _to_str(row.get("synonym"))
                if sci and syn:
                    sinonimos_rows.append({"scientific_name": sci, "synonym": syn})
        _insert_in_batches(db, models.CulturaSinonimo, sinonimos_rows)

    db.commit()
    return len(limites_rows), len(sinonimos_rows)


def seed_agrofit(
    db: Session,
    *,
    processed_dir: Optional[Path] = None,
    reset: bool = False,
) -> int:
    """Populate ``cultura_pragas`` from ``cultura_pragas_ecocrop_join.csv``.

    Returns:
        Number of inserted ``CulturaPraga`` rows.
    """
    target_dir = processed_dir or DEFAULT_PROCESSED_DIR
    join_csv = target_dir / "cultura_pragas_ecocrop_join.csv"

    if not join_csv.exists():
        logger.warning(
            "Arquivo AGROFIT x EcoCrop não encontrado em %s; pulando ingestão.",
            join_csv,
        )
        return 0

    existing = db.query(models.CulturaPraga).count()
    if existing > 0 and not reset:
        return 0

    if reset and existing > 0:
        db.query(models.CulturaPraga).delete(synchronize_session=False)
        db.flush()

    rows: List[Dict[str, Any]] = []
    with join_csv.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            sci = _to_str(row.get("scientific_name"))
            cultura_agrofit = _to_str(row.get("cultura_agrofit"))
            if not sci or not cultura_agrofit:
                continue
            rows.append(
                {
                    "scientific_name": sci,
                    "cultura_agrofit": cultura_agrofit,
                    "praga_nome_cientifico": _to_str(row.get("praga_nome_cientifico")),
                    "praga_nome_comum": _to_str(row.get("praga_nome_comum")),
                }
            )

    _insert_in_batches(db, models.CulturaPraga, rows)
    db.commit()
    return len(rows)

