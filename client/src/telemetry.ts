import { context, propagation, trace } from '@opentelemetry/api'
import { ZoneContextManager } from '@opentelemetry/context-zone'
import {
  CompositePropagator,
  W3CBaggagePropagator,
  W3CTraceContextPropagator,
} from '@opentelemetry/core'
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http'
import { registerInstrumentations } from '@opentelemetry/instrumentation'
import { DocumentLoadInstrumentation } from '@opentelemetry/instrumentation-document-load'
import { FetchInstrumentation } from '@opentelemetry/instrumentation-fetch'
import { UserInteractionInstrumentation } from '@opentelemetry/instrumentation-user-interaction'
import { resourceFromAttributes } from '@opentelemetry/resources'
import { BatchSpanProcessor, TracerProvider } from '@opentelemetry/sdk-trace'

// Browser tracing: page loads, clicks and fetch calls. The fetch spans send a
// `traceparent` header to /api, so browser and FastAPI spans join into one trace.
// Spans are exported to /v1/traces, which Vite proxies to the OTLP collector.
if (import.meta.env.VITE_OTEL_DISABLED !== 'true') {
  const provider = new TracerProvider({
    resource: resourceFromAttributes({ 'service.name': 'disasterwarning-client' }),
    spanProcessors: [
      new BatchSpanProcessor({ exporter: new OTLPTraceExporter({ url: '/v1/traces' }) }),
    ],
  })

  context.setGlobalContextManager(new ZoneContextManager().enable())
  propagation.setGlobalPropagator(
    new CompositePropagator({
      propagators: [new W3CTraceContextPropagator(), new W3CBaggagePropagator()],
    }),
  )
  trace.setGlobalTracerProvider(provider)

  registerInstrumentations({
    instrumentations: [
      new DocumentLoadInstrumentation(),
      new UserInteractionInstrumentation(),
      new FetchInstrumentation({ ignoreUrls: [/\/v1\/traces/] }),
    ],
  })
}
