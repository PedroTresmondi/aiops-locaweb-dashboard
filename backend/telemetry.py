"""Telemetria opcional via Azure Application Insights / Log Analytics.

Ativa somente quando ``APPLICATIONINSIGHTS_CONNECTION_STRING`` está no ambiente
(caso do Azure Container Instance) e o pacote ``azure-monitor-opentelemetry`` está
instalado. Fora do Azure — desenvolvimento local, testes — não faz nada e não é
dependência: o app funciona igual sem telemetria.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("visionops")

_CONFIGURADO = False


def configurar_telemetria(app) -> bool:
    """Liga a exportação de traces/logs para o Application Insights, se possível."""
    global _CONFIGURADO
    if _CONFIGURADO:
        return True

    connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        return False

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        configure_azure_monitor(connection_string=connection_string, logger_name="visionops")
        FastAPIInstrumentor.instrument_app(app)
        _CONFIGURADO = True
        logger.info("Application Insights configurado.")
        return True
    except Exception as exc:  # telemetria nunca deve derrubar a API
        logger.warning("Application Insights não pôde ser inicializado: %s", exc)
        return False
