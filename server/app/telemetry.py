"""OpenTelemetry setup: traces, metrics and logs exported over OTLP/HTTP.

By default everything goes to the local Grafana LGTM stack from the repo's
docker-compose.yml (Tempo for traces, Prometheus for metrics, Loki for logs).
"""

import logging

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_SDK_DISABLED, OTEL_SERVICE_NAME

logger = logging.getLogger(__name__)


def setup_telemetry(app: FastAPI) -> None:
    if OTEL_SDK_DISABLED:
        logger.info("OpenTelemetry disabled via OTEL_SDK_DISABLED")
        return

    resource = Resource.create({"service.name": OTEL_SERVICE_NAME})
    endpoint = OTEL_EXPORTER_OTLP_ENDPOINT.rstrip("/")

    # Traces
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
    )
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"),
        export_interval_millis=15_000,
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))

    # Logs (stdlib logging -> OTLP, with trace/span ids attached)
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{endpoint}/v1/logs"))
    )
    set_logger_provider(logger_provider)
    logging.getLogger().addHandler(LoggingHandler(logger_provider=logger_provider))
    logging.getLogger().setLevel(logging.INFO)
    LoggingInstrumentor().instrument(set_logging_format=False)

    # Auto-instrumentation
    FastAPIInstrumentor.instrument_app(app, excluded_urls="/api/health")
    HTTPXClientInstrumentor().instrument()  # outbound calls to Apify
    SystemMetricsInstrumentor().instrument()  # CPU, memory, GC, threads, etc.

    logger.info("OpenTelemetry enabled, exporting to %s", endpoint)
