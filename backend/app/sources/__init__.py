"""Adaptadores de fuentes de datos intercambiables.

Cada fuente implementa ``SourceAdapter`` y declara su estado real. Ninguna fuente sin verificar
se activa por defecto: la falta de API oficial no bloquea el proyecto porque el importador de
combat logs funciona de forma independiente.
"""

from app.sources.registry import all_sources

__all__ = ["all_sources"]
