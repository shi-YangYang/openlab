"""Heuristic ML-metric extraction from experiment run logs (spec-038 FR-1).

Two strategies are combined:

- Regex scan for ``key=value`` / ``key: value`` / ``key value`` patterns
  where the key matches a whitelist of common metric names plus val_/test_/
  best_-style prefixes. For every metric the last occurrence wins (final
  value).
- Pipe-delimited training tables (``epoch | train_loss | test_loss``): a
  header row is followed by consecutive numeric data rows and the last data
  row of each table provides the final values.

Table values override regex hits on the same key. Parsing is heuristic and
must never raise: any failure yields ``{}``.
"""
import re
from pathlib import Path
from typing import Dict, List, Optional, Union

KEY_PATTERN = (
    r"(?<![A-Za-z0-9_])"
    r"(?:(?:valid|val|test|best|train)[_\- ])?"
    r"(?:accuracy|f1_score|perplexity|spearman|precision|recall|pearson"
    r"|rouge(?:[_\- ]?[12lL])?|loss|acc|f1|map|auc|bleu|ppl)"
    r"(?![A-Za-z0-9_])"
)

_NUMBER = r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"
_VALUE = _NUMBER + r"\s*%?"

_ASSIGNED_RE = re.compile(
    r"(" + KEY_PATTERN + r")\s*[:=]\s*(" + _VALUE + r")(?![\w.])", re.IGNORECASE
)
_SPACE_RE = re.compile(
    r"(" + KEY_PATTERN + r")[ \t]+(" + _VALUE + r")(?![\w.])", re.IGNORECASE
)


def _normalize_key(raw: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")


_INT_CONTEXT_COLUMNS = frozenset({"epoch", "step", "iter", "it"})
_SEPARATOR_CELL_RE = re.compile(r":?-+:?$")


def _is_number(cell: str) -> bool:
    try:
        float(cell)
    except (TypeError, ValueError):
        return False
    return True


def _split_table_cells(line: str) -> Optional[List[str]]:
    """Split a pipe-table row; ``None`` when the line is not a table row."""
    if line.count("|") < 2:
        return None
    cells = [cell.strip() for cell in line.split("|")]
    while cells and not cells[0]:
        cells.pop(0)
    while cells and not cells[-1]:
        cells.pop()
    return cells


def _is_separator_row(cells: List[str]) -> bool:
    return bool(cells) and all(_SEPARATOR_CELL_RE.match(cell) for cell in cells)


def _is_header_row(cells: List[str]) -> bool:
    return (
        len(cells) >= 2
        and not _is_separator_row(cells)
        and any(not _is_number(cell) for cell in cells)
    )


def _is_data_row(cells: List[str], header: List[str]) -> bool:
    return len(cells) == len(header) and all(_is_number(cell) for cell in cells)


def _store_table_metrics(
    header: Optional[List[str]], last_row: Optional[List[str]], metrics: Dict[str, float]
) -> None:
    if header is None or last_row is None:
        return
    for index, name in enumerate(header):
        key = _normalize_key(name)
        if not key or key in _INT_CONTEXT_COLUMNS:
            continue
        try:
            metrics[key] = float(last_row[index])
        except (TypeError, ValueError, IndexError):
            continue


def _extract_table_metrics(text: str) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    header: Optional[List[str]] = None
    last_row: Optional[List[str]] = None
    for line in text.splitlines():
        cells = _split_table_cells(line)
        if cells is None:
            _store_table_metrics(header, last_row, metrics)
            header = last_row = None
            continue
        if header is None:
            if _is_header_row(cells):
                header = cells
            continue
        if _is_data_row(cells, header):
            last_row = cells
        elif _is_separator_row(cells):
            continue
        else:
            _store_table_metrics(header, last_row, metrics)
            header = last_row = None
            if _is_header_row(cells):
                header = cells
    _store_table_metrics(header, last_row, metrics)
    return metrics


def extract_metrics_from_text(text: str) -> Dict[str, float]:
    """Extract metrics from free log text; no matches → ``{}``."""
    if not text:
        return {}
    metrics: Dict[str, float] = {}
    try:
        found = []
        for match in _ASSIGNED_RE.finditer(text):
            found.append((match.start(), match.group(1), match.group(2)))
        for match in _SPACE_RE.finditer(text):
            found.append((match.start(), match.group(1), match.group(2)))
        found.sort(key=lambda item: item[0])
        for _pos, raw_key, raw_value in found:
            try:
                key = _normalize_key(raw_key)
                value = float(raw_value.strip().rstrip("%").strip())
            except (TypeError, ValueError):
                continue
            if key:
                metrics[key] = value
    except Exception:
        metrics = {}
    try:
        for key, value in _extract_table_metrics(text).items():
            metrics[key] = value
    except Exception:
        pass
    return metrics


def extract_metrics(log_path: Union[str, Path]) -> Dict[str, float]:
    """Extract metrics from a log file; missing/unreadable file → ``{}``."""
    try:
        path = Path(log_path)
        if not path.is_file():
            return {}
        return extract_metrics_from_text(
            path.read_text(encoding="utf-8", errors="replace")
        )
    except Exception:
        return {}
