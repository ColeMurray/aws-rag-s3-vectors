"""OpenTelemetry instrumentation for S3 Vectors RAG pipeline with GenAI semantic conventions."""
import os
import json
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
from functools import wraps
import time

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.trace import Status, StatusCode
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.semconv.resource import ResourceAttributes

import structlog

logger = structlog.get_logger()

# GenAI Semantic Convention Attributes (following OpenTelemetry GenAI spec)
class GenAIAttributes:
    # System and operation
    GEN_AI_SYSTEM = "gen_ai.system"
    GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
    
    # Request attributes
    GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
    GEN_AI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
    GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
    GEN_AI_REQUEST_TOP_K = "gen_ai.request.top_k"
    
    # Response attributes
    GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
    GEN_AI_RESPONSE_FINISH_REASON = "gen_ai.response.finish_reason"
    
    # Usage attributes
    GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
    GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
    
    # Tool attributes
    GEN_AI_TOOL_NAME = "gen_ai.tool.name"
    GEN_AI_TOOL_DESCRIPTION = "gen_ai.tool.description"

# Custom attributes for RAG pipeline
class RAGAttributes:
    RAG_QUERY = "rag.query"
    RAG_CHUNKS_RETRIEVED = "rag.chunks.retrieved"
    RAG_CHUNKS_THRESHOLD = "rag.chunks.threshold"
    RAG_VECTOR_DIMENSION = "rag.vector.dimension"
    RAG_VECTOR_SIMILARITY_METRIC = "rag.vector.similarity_metric"
    
    # S3 Vectors specific
    S3_VECTOR_BUCKET = "s3.vector.bucket"
    S3_VECTOR_INDEX = "s3.vector.index"
    S3_VECTOR_OPERATION = "s3.vector.operation"

# Event names following GenAI spec
class GenAIEventNames:
    SYSTEM_MESSAGE = "gen_ai.system.message"
    USER_MESSAGE = "gen_ai.user.message"
    ASSISTANT_MESSAGE = "gen_ai.assistant.message"
    TOOL_MESSAGE = "gen_ai.tool.message"
    CHOICE = "gen_ai.choice"

# RAG-specific event names
class RAGEventNames:
    SOURCE_RETRIEVED = "rag.source.retrieved"
    SOURCES_SUMMARY = "rag.sources.summary"

class TelemetryManager:
    """Manages OpenTelemetry instrumentation for the RAG pipeline."""
    
    def __init__(self, settings):
        self.settings = settings
        self.resource = self._create_resource()
        self._setup_tracing()
        self._setup_metrics()
        self._instrument_fastapi()
        
    def _create_resource(self) -> Resource:
        """Create resource with service information."""
        return Resource.create({
            ResourceAttributes.SERVICE_NAME: self.settings.otel_service_name,
            ResourceAttributes.SERVICE_VERSION: self.settings.api_version,
            "environment": self.settings.otel_environment,
            "deployment.environment": self.settings.otel_environment,
        })
    
    def _setup_tracing(self):
        """Set up OpenTelemetry tracing."""
        # Create tracer provider
        provider = TracerProvider(resource=self.resource)
        
        # Configure OTLP exporter if endpoint is set
        if self.settings.otel_exporter_endpoint:
            logger.info("Configuring OTLP exporter", 
                       endpoint=self.settings.otel_exporter_endpoint,
                       insecure=self.settings.otel_exporter_insecure)
            try:
                otlp_exporter = OTLPSpanExporter(
                    endpoint=self.settings.otel_exporter_endpoint,
                    insecure=self.settings.otel_exporter_insecure,
                )
                provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                logger.info("OTLP exporter configured successfully")
            except Exception as e:
                logger.error("Failed to configure OTLP exporter", 
                           error=str(e),
                           endpoint=self.settings.otel_exporter_endpoint)
        
        # Set global tracer provider
        trace.set_tracer_provider(provider)
        self.tracer = trace.get_tracer(__name__)
        
        logger.info("OpenTelemetry tracing initialized",
                   endpoint=self.settings.otel_exporter_endpoint)
    
    def _setup_metrics(self):
        """Set up OpenTelemetry metrics."""
        # Create metric reader and provider
        if self.settings.otel_exporter_endpoint:
            metric_exporter = OTLPMetricExporter(
                endpoint=self.settings.otel_exporter_endpoint,
                insecure=self.settings.otel_exporter_insecure,
            )
            metric_reader = PeriodicExportingMetricReader(
                exporter=metric_exporter,
                export_interval_millis=self.settings.otel_metrics_export_interval_ms
            )
            provider = MeterProvider(resource=self.resource, metric_readers=[metric_reader])
        else:
            provider = MeterProvider(resource=self.resource)
        
        # Set global meter provider
        metrics.set_meter_provider(provider)
        self.meter = metrics.get_meter(__name__)
        
        # Create metrics following GenAI spec
        self._create_genai_metrics()
        
        logger.info("OpenTelemetry metrics initialized")
    
    def _create_genai_metrics(self):
        """Create GenAI semantic convention metrics."""
        # Token usage metric
        self.token_usage = self.meter.create_counter(
            name="gen_ai.client.token.usage",
            description="Number of tokens used in GenAI operations",
            unit="token"
        )
        
        # Operation duration metric
        self.operation_duration = self.meter.create_histogram(
            name="gen_ai.client.operation.duration",
            description="Duration of GenAI operations",
            unit="s"
        )
        
        # RAG-specific metrics
        self.vector_search_duration = self.meter.create_histogram(
            name="rag.vector.search.duration",
            description="Duration of vector similarity searches",
            unit="s"
        )
        
        self.chunks_retrieved = self.meter.create_histogram(
            name="rag.chunks.retrieved.count",
            description="Number of chunks retrieved per query",
            unit="chunk"
        )
    
    def _instrument_fastapi(self):
        """Instrument FastAPI application."""
        if self.settings.otel_instrument_fastapi:
            FastAPIInstrumentor().instrument()
            logger.info("FastAPI instrumentation enabled")
    
    @contextmanager
    def genai_span(self, operation_name: str, system: str, model: Optional[str] = None, **attributes):
        """Create a span following GenAI semantic conventions."""
        # Construct span name: {gen_ai.operation.name} {gen_ai.request.model}
        span_name = operation_name
        if model:
            span_name = f"{operation_name} {model}"
        
        with self.tracer.start_as_current_span(span_name) as span:
            # Set required attributes
            span.set_attribute(GenAIAttributes.GEN_AI_OPERATION_NAME, operation_name)
            span.set_attribute(GenAIAttributes.GEN_AI_SYSTEM, system)
            
            if model:
                span.set_attribute(GenAIAttributes.GEN_AI_REQUEST_MODEL, model)
            
            # Set additional attributes
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(key, value)
            
            try:
                yield span
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute(SpanAttributes.EXCEPTION_TYPE, type(e).__name__)
                raise
    
    def record_genai_event(self, span, event_name: str, content: str, **attributes):
        """Record a GenAI event (prompt/completion) on a span."""
        if not self.settings.otel_capture_content:
            # Skip content capture if disabled for privacy
            return
        
        event_attributes = {
            "gen_ai.event.content": content[:self.settings.otel_max_event_content_length]
        }
        event_attributes.update(attributes)
        
        span.add_event(event_name, attributes=event_attributes)
    
    def record_source_retrieved(self, span, source: Dict[str, Any], index: int):
        """Record a single retrieved source as an event."""
        if not self.settings.otel_capture_sources:
            return
        
        # Extract key metadata without exposing full content
        event_attributes = {
            "rag.source.index": index,
            "rag.source.name": source.get("source", "Unknown"),
            "rag.source.chunk_index": source.get("chunk_index", 0),
            "rag.source.similarity_score": source.get("similarity_score", 0.0),
            "rag.source.preview_length": len(source.get("text_preview", "")),
        }
        
        # Optionally include text preview if content capture is enabled
        if self.settings.otel_capture_content and "text_preview" in source:
            preview = source["text_preview"]
            max_len = min(200, self.settings.otel_max_event_content_length)
            event_attributes["rag.source.text_preview"] = preview[:max_len]
        
        span.add_event(RAGEventNames.SOURCE_RETRIEVED, attributes=event_attributes)
    
    def record_sources_summary(self, span, sources: List[Dict[str, Any]]):
        """Record a summary of all retrieved sources."""
        if not self.settings.otel_capture_sources or not sources:
            return
        
        # Limit number of sources to record
        max_sources = min(len(sources), self.settings.otel_max_sources_per_trace)
        
        # Record individual source events
        for i, source in enumerate(sources[:max_sources]):
            self.record_source_retrieved(span, source, i)
        
        # Record summary event
        summary_attributes = {
            "rag.sources.total_count": len(sources),
            "rag.sources.recorded_count": max_sources,
            "rag.sources.avg_similarity": sum(s.get("similarity_score", 0) for s in sources) / len(sources) if sources else 0,
            "rag.sources.unique_documents": len(set(s.get("source", "") for s in sources)),
        }
        
        # Add top sources summary
        if sources:
            top_sources = [s.get("source", "Unknown") for s in sources[:3]]
            summary_attributes["rag.sources.top_documents"] = ", ".join(top_sources)
        
        span.add_event(RAGEventNames.SOURCES_SUMMARY, attributes=summary_attributes)
    
    def record_token_usage(self, system: str, model: str, operation: str, 
                          input_tokens: int = 0, output_tokens: int = 0):
        """Record token usage metrics."""
        common_attrs = {
            GenAIAttributes.GEN_AI_SYSTEM: system,
            GenAIAttributes.GEN_AI_REQUEST_MODEL: model,
            GenAIAttributes.GEN_AI_OPERATION_NAME: operation,
        }
        
        if input_tokens > 0:
            self.token_usage.add(input_tokens, {**common_attrs, "gen_ai.token.type": "input"})
        
        if output_tokens > 0:
            self.token_usage.add(output_tokens, {**common_attrs, "gen_ai.token.type": "output"})
    
    def record_operation_duration(self, duration_seconds: float, system: str, 
                                 model: str, operation: str, **attributes):
        """Record operation duration metric."""
        attrs = {
            GenAIAttributes.GEN_AI_SYSTEM: system,
            GenAIAttributes.GEN_AI_REQUEST_MODEL: model,
            GenAIAttributes.GEN_AI_OPERATION_NAME: operation,
        }
        attrs.update(attributes)
        
        self.operation_duration.record(duration_seconds, attrs)

# Global telemetry manager instance
_telemetry_manager: Optional[TelemetryManager] = None

def init_telemetry(settings):
    """Initialize the global telemetry manager."""
    global _telemetry_manager
    if settings.otel_enabled:
        _telemetry_manager = TelemetryManager(settings)
        logger.info("OpenTelemetry instrumentation enabled")
    else:
        logger.info("OpenTelemetry instrumentation disabled")
    return _telemetry_manager

def get_telemetry() -> Optional[TelemetryManager]:
    """Get the global telemetry manager instance."""
    return _telemetry_manager

# Decorator for easy span creation
def trace_genai_operation(operation_name: str, system: str):
    """Decorator to trace GenAI operations."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            telemetry = get_telemetry()
            if not telemetry:
                return await func(*args, **kwargs)
            
            # Extract model from kwargs or args
            model = kwargs.get('model') or (args[1] if len(args) > 1 else None)
            
            with telemetry.genai_span(operation_name, system, model):
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            telemetry = get_telemetry()
            if not telemetry:
                return func(*args, **kwargs)
            
            # Extract model from kwargs or args
            model = kwargs.get('model') or (args[1] if len(args) > 1 else None)
            
            with telemetry.genai_span(operation_name, system, model):
                return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator