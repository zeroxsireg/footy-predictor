"""Serializzazione valori cache: JSON, opzionalmente gzip+base64 (prefisso esplicito)."""

import base64
import gzip
import json
from typing import Any

COMPRESS_MIN_CHARS = 512
_GZ, _JS = "gz:", "js:"


def encode(data: Any, compress: bool = True) -> str:
    """Serializza `data` (JSON-compatibile). Comprime solo payload grandi."""
    raw = json.dumps(data, ensure_ascii=False)
    if compress and len(raw) >= COMPRESS_MIN_CHARS:
        return _GZ + base64.b64encode(gzip.compress(raw.encode("utf-8"))).decode("ascii")
    return _JS + raw


def decode(value: str) -> Any:
    """Inverso di encode; solleva ValueError se il valore e' corrotto."""
    try:
        if value.startswith(_GZ):
            return json.loads(gzip.decompress(base64.b64decode(value[len(_GZ):])).decode("utf-8"))
        if value.startswith(_JS):
            return json.loads(value[len(_JS):])
        return json.loads(value)
    except Exception as exc:
        raise ValueError(f"cache value corrotto: {exc}") from exc
