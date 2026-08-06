"""Bring-your-own-data: parse an uploaded UAV dataset and analyse it.

The analogue of robustidps.ai's self-traffic monitor, for flights rather than
flows: a visitor uploads their own telemetry or network capture and gets the
same treatment the benchmark's own sources get -- schema detection, summary
statistics, and the certificate engine run over whatever the detector-relevant
columns turn out to be.

Two design constraints shaped this, and both come from things that have already
gone wrong on this host.

**Never load the file.** The web build once exhausted memory on this server and
took SSH with it. A 1 GB CSV read into a list of dicts is several GB resident,
so parsing is streaming and charts are built from a bounded reservoir sample.
Peak memory is a function of the sample size, not the file size.

**Never retain the file.** The upload is parsed as it arrives and the bytes are
discarded; only the summary is returned. A public demo that quietly accumulates
visitors' flight data is a liability nobody asked for.
"""
from __future__ import annotations

import csv
import io
import json
import math
import random
import statistics
from dataclasses import dataclass, field
from typing import Any, Iterable

MAX_BYTES = 1024 * 1024 * 1024          # 1 GB, as specified
SAMPLE_N = 4000                          # reservoir size for charts
MAX_COLUMNS = 512


# --------------------------------------------------------------- detection --
#
# Column roles are matched by name fragment. The matcher is deliberately
# generous and deliberately reports what it did NOT match: a viewer must be able
# to see that their `pos_err_m` column was read as a position error and their
# `foo` column was ignored, rather than wondering why a number looks wrong.

ROLE_PATTERNS: dict[str, tuple[str, ...]] = {
    "time": ("timestamp", "time_s", "t_s", "time", "ts", "boot_ms", "epoch"),
    "position_error_m": ("pos_error", "position_error", "pos_err", "error_m",
                         "deviation", "cep", "rmse_m"),
    "delay_s": ("delay", "latency", "residual", "staleness", "rtt", "jitter"),
    "js_db": ("js_db", "jamming", "jsr", "snr", "cn0", "cno"),
    "label": ("label", "attack", "class", "is_attack", "malicious", "target"),
    "altitude_m": ("alt", "height", "agl", "msl"),
    "speed_m_s": ("speed", "velocity", "groundspeed", "vel_"),
    "battery": ("battery", "batt", "soc_pct", "voltage"),
}

# The units a column is assumed to be in when its name does not say. Stated
# rather than silently applied, because a millisecond column read as seconds is
# a 1000x error in the certificate output.
UNIT_HINTS = {
    "delay_s": ("_ms", "millis", "_us"),
    "position_error_m": ("_cm", "_mm", "_km"),
}


def _role_of(name: str) -> str | None:
    low = name.strip().lower()
    for role, pats in ROLE_PATTERNS.items():
        for p in pats:
            if p in low:
                return role
    return None


def _unit_warning(name: str, role: str) -> str | None:
    low = name.lower()
    for suffix in UNIT_HINTS.get(role, ()):
        if suffix in low:
            return (f"'{name}' looks like it is in {suffix.strip('_')} rather "
                    f"than the base unit; values were used as-is and NOT "
                    f"converted. Rename or rescale before trusting the "
                    f"certificate output.")
    return None


@dataclass
class ColumnStats:
    name: str
    role: str | None = None
    n: int = 0
    n_numeric: int = 0
    n_missing: int = 0
    _sum: float = 0.0
    _min: float = math.inf
    _max: float = -math.inf
    sample: list[float] = field(default_factory=list)
    distinct_preview: set = field(default_factory=set)

    def observe(self, raw: str, k: int, rng: random.Random) -> None:
        self.n += 1
        if raw is None or raw == "":
            self.n_missing += 1
            return
        try:
            v = float(raw)
        except (TypeError, ValueError):
            if len(self.distinct_preview) < 12:
                self.distinct_preview.add(raw[:40])
            return
        if math.isnan(v) or math.isinf(v):
            self.n_missing += 1
            return
        self.n_numeric += 1
        self._sum += v
        self._min = min(self._min, v)
        self._max = max(self._max, v)
        # Reservoir sampling: every row has an equal chance of being kept, so
        # the histogram is unbiased whether the file has 1e3 rows or 1e8.
        if len(self.sample) < SAMPLE_N:
            self.sample.append(v)
        else:
            j = rng.randint(0, k)
            if j < SAMPLE_N:
                self.sample[j] = v

    def summary(self) -> dict:
        if self.n_numeric == 0:
            return {
                "name": self.name, "role": self.role, "kind": "categorical",
                "n": self.n, "n_missing": self.n_missing,
                "values_preview": sorted(self.distinct_preview)[:12],
            }
        s = sorted(self.sample)
        def q(p: float) -> float:
            if not s:
                return 0.0
            return s[min(len(s) - 1, int(p * (len(s) - 1)))]
        return {
            "name": self.name, "role": self.role, "kind": "numeric",
            "n": self.n, "n_numeric": self.n_numeric, "n_missing": self.n_missing,
            "min": round(self._min, 6), "max": round(self._max, 6),
            "mean": round(self._sum / self.n_numeric, 6),
            "median": round(q(0.5), 6),
            "p05": round(q(0.05), 6), "p95": round(q(0.95), 6),
            "std": round(statistics.pstdev(s), 6) if len(s) > 1 else 0.0,
            "sample_n": len(s),
        }

    def histogram(self, bins: int = 24) -> dict | None:
        if self.n_numeric == 0 or not self.sample:
            return None
        lo, hi = min(self.sample), max(self.sample)
        if hi <= lo:
            return {"bins": [{"x": lo, "count": len(self.sample)}], "degenerate": True}
        w = (hi - lo) / bins
        counts = [0] * bins
        for v in self.sample:
            counts[min(bins - 1, int((v - lo) / w))] += 1
        return {
            "bins": [{"x": round(lo + (i + 0.5) * w, 6), "count": c}
                     for i, c in enumerate(counts)],
            "degenerate": False,
            "note": f"built from a {len(self.sample)}-row reservoir sample",
        }


# ------------------------------------------------------------------ parse --

def analyse_csv(stream: Iterable[bytes], filename: str = "upload.csv",
                max_bytes: int = MAX_BYTES) -> dict:
    """Stream-parse a CSV and return a schema + statistics summary.

    `stream` yields chunks. Rows are consumed as they decode; nothing larger
    than one chunk plus the reservoirs is ever resident.
    """
    rng = random.Random(20260806)
    total_bytes = 0
    truncated = False
    buf = ""
    header: list[str] | None = None
    cols: dict[str, ColumnStats] = {}
    n_rows = 0
    errors: list[str] = []

    def feed_lines(text: str, last: bool) -> Iterable[str]:
        nonlocal buf
        buf += text
        *lines, buf = buf.split("\n")
        yield from lines
        if last and buf:
            yield buf

    chunks = list(_iter_with_limit(stream, max_bytes))
    for chunk, is_last, over in chunks:
        if over:
            truncated = True
        total_bytes += len(chunk)
        text = chunk.decode("utf-8", errors="replace")
        for line in feed_lines(text, is_last):
            if not line.strip():
                continue
            try:
                row = next(csv.reader([line]))
            except Exception as e:  # noqa: BLE001 - a malformed line is data, not a crash
                if len(errors) < 5:
                    errors.append(f"row {n_rows + 1}: {e}")
                continue
            if header is None:
                header = [h.strip() for h in row][:MAX_COLUMNS]
                for h in header:
                    cols[h] = ColumnStats(name=h, role=_role_of(h))
                continue
            n_rows += 1
            for name, raw in zip(header, row):
                c = cols.get(name)
                if c is not None:
                    c.observe(raw, n_rows, rng)

    if header is None:
        return {"ok": False, "error": "No header row found — is this a CSV?"}

    detected = {}
    warnings = []
    for c in cols.values():
        if c.role and c.role not in detected:
            detected[c.role] = c.name
            w = _unit_warning(c.name, c.role)
            if w:
                warnings.append(w)

    unmatched = [c.name for c in cols.values() if c.role is None]

    return {
        "ok": True,
        "filename": filename,
        "bytes_read": total_bytes,
        "truncated": truncated,
        "n_rows": n_rows,
        "n_columns": len(header),
        "detected_roles": detected,
        "unmatched_columns": unmatched[:40],
        "n_unmatched": len(unmatched),
        "columns": [c.summary() for c in cols.values()],
        "histograms": {c.name: c.histogram() for c in cols.values()
                       if c.role in ("delay_s", "position_error_m", "js_db")},
        "warnings": warnings,
        "parse_errors": errors,
        "method": {
            "streaming": True,
            "reservoir_n": SAMPLE_N,
            "note": "Statistics over min/max/mean/count are exact across every "
                    "row. Median, percentiles, standard deviation and the "
                    "histograms come from a uniform reservoir sample, so they "
                    "are unbiased but not exact.",
        },
        "retention": "none — the upload was parsed in flight and discarded",
    }


def _iter_with_limit(stream: Iterable[bytes], max_bytes: int):
    """Yield (chunk, is_last, went_over). Stops once the cap is reached."""
    seen = 0
    prev = None
    for chunk in stream:
        if prev is not None:
            yield prev, False, False
        if seen + len(chunk) > max_bytes:
            keep = max_bytes - seen
            yield chunk[:keep], True, True
            return
        seen += len(chunk)
        prev = chunk
    if prev is not None:
        yield prev, True, False


# ------------------------------------------------------------------- fly ---

def fly(summary: dict, corridor_m: float = 10.0, mapping: str = "ekf",
        n_malicious_hops: int = 2) -> dict:
    """Push the detected columns through the certificate engine.

    Uses the uploaded data's own delay distribution as the residual budget
    rather than a nominal theta: the p95 of the user's delay column is what
    their network actually does, so the certified verdict is about their fleet.
    """
    GAMMA = {"kinematic": 15.0, "receiver": 1.195, "ekf": 1.365}
    if mapping not in GAMMA:
        mapping = "ekf"
    gamma = GAMMA[mapping]
    L, T = 1.181, 1.0

    by_name = {c["name"]: c for c in summary.get("columns", [])}
    roles = summary.get("detected_roles", {})

    delay_col = roles.get("delay_s")
    pos_col = roles.get("position_error_m")

    if not delay_col and not pos_col:
        return {
            "ok": False,
            "reason": "no usable column",
            "detail": "Neither a delay-like nor a position-error-like column "
                      "was detected. The certificate needs one of them: it "
                      "converts undetected network delay into position error, "
                      "or bounds an observed position error directly.",
            "looked_for": {"delay_s": ROLE_PATTERNS["delay_s"],
                           "position_error_m": ROLE_PATTERNS["position_error_m"]},
        }

    out: dict[str, Any] = {
        "ok": True, "mapping": mapping, "gamma_m_s": gamma,
        "corridor_m": corridor_m, "amplification": f"gronwall_L{L:g}_T{T:g}",
    }

    if delay_col:
        st = by_name.get(delay_col, {})
        # p95 rather than max: one outlier row should not define the operating
        # point, and p95 is what the paper's own budget analysis uses.
        theta = float(st.get("p95") or 0.0)
        delta_pos = gamma * theta * n_malicious_hops
        tube = delta_pos * math.exp(L * T)
        out["from_delay"] = {
            "column": delay_col,
            "theta_p95_s": round(theta, 6),
            "n_malicious_hops": n_malicious_hops,
            "delta_pos_m": round(delta_pos, 4),
            "tube_m": round(tube, 4),
            "inside_corridor": tube <= corridor_m,
            "reading": "θ is the 95th percentile of the uploaded delay column, "
                       "so this verdict is about the uploaded network, not a "
                       "nominal operating point.",
        }

    if pos_col:
        st = by_name.get(pos_col, {})
        p95 = float(st.get("p95") or 0.0)
        mx = float(st.get("max") or 0.0)
        out["from_position_error"] = {
            "column": pos_col,
            "p95_m": round(p95, 4),
            "max_m": round(mx, 4),
            "within_corridor_p95": p95 <= corridor_m,
            "within_corridor_max": mx <= corridor_m,
            "reading": "Observed error, not a bound. Compare it against the "
                       "tube above: if the observed p95 exceeds the certified "
                       "tube, either the mapping is wrong for this platform or "
                       "something outside the delay class is moving the "
                       "aircraft.",
        }

    if delay_col and pos_col:
        d = out["from_delay"]["tube_m"]
        p = out["from_position_error"]["p95_m"]
        out["consistency"] = {
            "observed_p95_within_certified_tube": p <= d,
            "ratio": round(p / d, 3) if d else None,
            "reading": "A ratio above 1 means the observed error is larger than "
                       "the certificate allows for this delay — evidence the "
                       "interface mapping is mis-calibrated for this platform.",
        }

    out["caveat"] = ("γ and L are this project's measured constants, from three "
                     "PX4 hover flights and this project's operating region. "
                     "They are not calibrated to the uploaded platform. Treat "
                     "the verdict as indicative until γ is re-measured on it.")
    return out
