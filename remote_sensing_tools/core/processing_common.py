"""Shared processor primitives for sensor-specific preprocessing pipelines."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Dict, Optional

import numpy as np


PROCESSED_BAND_NODATA = -9999.0
LANDSAT_L2_SR_SCALE = np.float32(0.0000275)
LANDSAT_L2_SR_OFFSET = np.float32(-0.2)
SENTINEL2_L2A_SR_SCALE = np.float32(0.0001)


def safe_join(output_dir: str, filename: str) -> str:
    """Join output paths using the host OS separator."""
    return str(Path(output_dir) / filename)


def sanitize_index_name(name: Optional[str], fallback: str = "custom_index") -> str:
    """Normalize user-provided index names for output filenames."""
    if not name:
        return fallback

    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    if not safe:
        return fallback

    return safe.lower()


def build_reporter(progress_callback: Optional[Callable[[Dict], None]]) -> Callable[[str, str, Optional[int], str], None]:
    """Create a no-op-safe progress reporter for processor pipelines."""

    def report(step_id: str, detail: str, progress: Optional[int] = None, status: str = "active"):
        if progress_callback:
            progress_callback({
                "step": step_id,
                "detail": detail,
                "progress": progress,
                "status": status,
            })

    return report


def sample_valid_values(
    array: np.ndarray,
    *,
    positive_only: bool = False,
    max_samples: int = 1_000_000,
) -> np.ndarray:
    """Return a finite sample from a raster array for cheap statistics."""
    flat = np.asarray(array).reshape(-1)
    step = max(1, flat.size // max_samples)
    sample = flat[::step]
    mask = np.isfinite(sample)
    if positive_only:
        mask &= sample > 0
    return sample[mask]
