"""
PrevencionApp — Configuración global de pytest.
pytest-asyncio 0.21+ gestiona el event_loop automáticamente (asyncio_mode=auto en pyproject.toml).
"""
import sys
import typing

# ── Patch de compatibilidad: Pydantic 2.13.3 en Python 3.14 ──────────────────
# Pydantic llama typing._eval_type(..., prefer_fwd_module=True) pero
# Python 3.14rc2 eliminó ese parámetro. Este patch acepta y descarta el kwarg.
if sys.version_info >= (3, 14):
    _orig_eval_type = typing._eval_type  # type: ignore[attr-defined]

    def _patched_eval_type(t, globalns, localns, type_params=None, *,
                           prefer_fwd_module=False, **kwargs):
        return _orig_eval_type(t, globalns, localns, type_params=type_params, **kwargs)

    typing._eval_type = _patched_eval_type  # type: ignore[attr-defined]
