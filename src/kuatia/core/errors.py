"""Exceptions do core kuatia.

Substituem `sys.exit` em paths não-CLI: a GUI captura e exibe na UI,
a CLI captura no entry point e converte em exit code.
"""

from __future__ import annotations


class KuatiaError(Exception):
    """Base exception do kuatia."""


class AudioLoadError(KuatiaError):
    """Falha ao carregar ou decodificar áudio."""


class ModelNotFoundError(KuatiaError):
    """Modelo OpenVINO não encontrado no diretório esperado."""


class TranscriptionError(KuatiaError):
    """Erro durante a transcrição."""
