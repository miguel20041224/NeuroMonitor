"""Sanitización de nombres comerciales de GPU dedicada (lspci/lshw/sysfs)."""

from __future__ import annotations

import re

_PLACEHOLDER_NAMES = frozenset({"", "—", "-", "n/d", "n/a", "nvidia gpu", "amd radeon gpu"})

_RX_BRACKET_RE = re.compile(
    r"\[Radeon\s+RX\s+(\d{4})(?:\s+(XT|XTX|GRE|XL))?(?:/|\]|$)",
    re.IGNORECASE,
)
_RX_PLAIN_RE = re.compile(
    r"Radeon\s+RX\s+(\d{4})(?:\s+(XT|XTX|GRE|XL))?(?:\b|/|\])",
    re.IGNORECASE,
)
_PRO_BRACKET_RE = re.compile(
    r"\[Radeon\s+PRO\s+(W\d{4})(?:/|\]|$)",
    re.IGNORECASE,
)

_NAVI_CODE_MAP: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"Navi\s*31|\b7900\s*XTX\b", re.I), "AMD Radeon RX 7900 XTX"),
    (re.compile(r"Navi\s*31|\b7900\s*XT\b", re.I), "AMD Radeon RX 7900 XT"),
    (re.compile(r"Navi\s*31|\b7900\s*GRE\b", re.I), "AMD Radeon RX 7900 GRE"),
    (re.compile(r"Navi\s*32|\b7800\s*XT\b", re.I), "AMD Radeon RX 7800 XT"),
    (re.compile(r"Navi\s*32|\b7700\s*XT\b", re.I), "AMD Radeon RX 7700 XT"),
    (re.compile(r"Navi\s*33|\b7600\s*XT\b", re.I), "AMD Radeon RX 7600 XT"),
    (re.compile(r"Navi\s*33|\b7600\b", re.I), "AMD Radeon RX 7600"),
    (re.compile(r"Navi\s*23|\b6600\s*XT\b", re.I), "AMD Radeon RX 6600 XT"),
    (re.compile(r"Navi\s*23|\b6600\b", re.I), "AMD Radeon RX 6600"),
    (re.compile(r"Navi\s*22|\b6500\s*XT\b", re.I), "AMD Radeon RX 6500 XT"),
    (re.compile(r"Navi\s*14|\b5500\s*XT\b", re.I), "AMD Radeon RX 5500 XT"),
)

_NOISE_RE = re.compile(
    r"Advanced Micro Devices,?\s*Inc\.?\s*|\[AMD/ATI\]\s*|\[[0-9a-f]{4}:[0-9a-f]{4}\]\s*",
    re.IGNORECASE,
)
_TRAILING_BRACKETS_RE = re.compile(r"\s*\[[^\]]*\]\s*")


def _format_amd_rx(model: str, suffix: str | None) -> str:
    name = f"AMD Radeon RX {model}"
    if suffix:
        name = f"{name} {suffix.upper()}"
    return name


def sanitize_dgpu_commercial_name(raw: str | None) -> str:
    """Convierte el string crudo de lspci/lshw en un nombre comercial limpio."""
    if raw is None:
        return "AMD Radeon GPU"

    text = raw.strip()
    if text.lower() in _PLACEHOLDER_NAMES:
        return "AMD Radeon GPU"

    bracket_rx = _RX_BRACKET_RE.search(text)
    if bracket_rx:
        return _format_amd_rx(bracket_rx.group(1), bracket_rx.group(2))

    plain_rx = _RX_PLAIN_RE.search(text)
    if plain_rx:
        return _format_amd_rx(plain_rx.group(1), plain_rx.group(2))

    pro_match = _PRO_BRACKET_RE.search(text)
    if pro_match:
        return f"AMD Radeon PRO W{pro_match.group(1)}"

    for pattern, product in _NAVI_CODE_MAP:
        if pattern.search(text):
            return product

    cleaned = _NOISE_RE.sub("", text)
    cleaned = _TRAILING_BRACKETS_RE.sub("", cleaned).strip(" /")
    if not cleaned:
        return "AMD Radeon GPU"

    if re.search(r"\bnvidia\b", cleaned, re.I):
        return cleaned

    if re.search(r"\b(radeon|rx|navi|firepro|instinct)\b", cleaned, re.I):
        if not cleaned.lower().startswith("amd"):
            return f"AMD {cleaned}"
        return cleaned

    return cleaned
