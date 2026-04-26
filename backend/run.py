"""
Wrapper de inicio para Python 3.14rc2 + Pydantic 2.13.x.
Aplica el patch de compatibilidad ANTES de importar FastAPI/Pydantic.
"""
import sys
import typing

if sys.version_info >= (3, 14):
    _orig_eval_type = typing._eval_type  # type: ignore[attr-defined]

    def _patched_eval_type(t, globalns, localns, type_params=None, *,
                           prefer_fwd_module=False, **kwargs):
        return _orig_eval_type(t, globalns, localns, type_params=type_params, **kwargs)

    typing._eval_type = _patched_eval_type  # type: ignore[attr-defined]

import uvicorn  # noqa: E402 — import after patch

if __name__ == "__main__":
    uvicorn.run(
        "app.entrypoints.api.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        reload_dirs=["app"],
    )
