"""
PrevencionApp — Configuración global de pytest.
Define fixtures compartidas entre tests unitarios, de integración y e2e.
"""
import asyncio
import pytest

@pytest.fixture(scope="session")
def event_loop():
    """Event loop compartido para toda la sesión de tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
