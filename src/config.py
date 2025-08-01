"""Configuration management for S3 Vectors RAG pipeline."""
import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # AWS Configuration
    aws_region: str = Field(default="us-east-1", env="AWS_REGION")
    aws_access_key_id: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, env="AWS_SECRET_ACCESS_KEY")
    
    # S3 Vectors Configuration
    s3_vector_bucket_name: str = Field(env="S3_VECTOR_BUCKET_NAME")
    s3_vector_index_name: str = Field(default="rag-index", env="S3_VECTOR_INDEX_NAME")
    s3_vector_dimension: int = Field(default=1024, env="S3_VECTOR_DIMENSION")
    s3_vector_distance_metric: str = Field(default="cosine", env="S3_VECTOR_DISTANCE_METRIC")
    
    # Bedrock Model Configuration
    embed_model_id: str = Field(
        default="amazon.titan-embed-text-v2:0",
        env="BEDROCK_EMBED_MODEL_ID"
    )
    llm_model_id: str = Field(
        default="us.anthropic.claude-3-5-haiku-20241022-v1:0",
        env="BEDROCK_LLM_MODEL_ID"
    )
    
    # Text Processing Configuration
    chunk_size: int = Field(
        default=800,
        env="CHUNK_SIZE",
        description="Number of characters per text chunk"
    )
    chunk_overlap: int = Field(
        default=100,
        env="CHUNK_OVERLAP",
        description="Overlap between consecutive chunks"
    )
    
    # Retrieval Configuration
    top_k: int = Field(
        default=6,
        env="TOP_K",
        description="Number of chunks to retrieve for each query"
    )
    similarity_threshold: float = Field(
        default=0.5,
        env="SIMILARITY_THRESHOLD",
        description="Minimum similarity score for retrieved chunks"
    )
    
    # LLM Generation Configuration
    max_tokens: int = Field(
        default=512,
        env="MAX_TOKENS",
        description="Maximum tokens for LLM response"
    )
    temperature: float = Field(
        default=0.2,
        env="TEMPERATURE",
        description="Temperature for LLM generation"
    )
    
    # Data Source Configuration
    s3_bucket_name: Optional[str] = Field(default=None, env="S3_BUCKET_NAME")
    data_directory: str = Field(
        default="./data",
        env="DATA_DIRECTORY",
        description="Local directory for document storage"
    )
    
    # API Configuration
    api_title: str = Field(default="S3 Vectors RAG API", env="API_TITLE")
    api_description: str = Field(
        default="RAG API using AWS S3 Vectors and Bedrock",
        env="API_DESCRIPTION"
    )
    api_version: str = Field(default="1.0.0", env="API_VERSION")
    
    # Logging Configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    debug: bool = Field(default=False, env="DEBUG")
    
    # OpenTelemetry Configuration
    otel_enabled: bool = Field(default=True, env="OTEL_ENABLED")
    otel_service_name: str = Field(default="s3-vectors-rag", env="OTEL_SERVICE_NAME")
    otel_environment: str = Field(default="development", env="OTEL_ENVIRONMENT")
    otel_exporter_endpoint: Optional[str] = Field(
        default="http://otel-collector:4317",
        env="OTEL_EXPORTER_OTLP_ENDPOINT",
        description="OTLP exporter endpoint (gRPC)"
    )
    otel_exporter_insecure: bool = Field(
        default=True,
        env="OTEL_EXPORTER_OTLP_INSECURE",
        description="Use insecure connection for OTLP exporter"
    )
    otel_metrics_export_interval_ms: int = Field(
        default=60000,
        env="OTEL_METRICS_EXPORT_INTERVAL_MS",
        description="Metrics export interval in milliseconds"
    )
    otel_instrument_fastapi: bool = Field(
        default=True,
        env="OTEL_INSTRUMENT_FASTAPI",
        description="Enable automatic FastAPI instrumentation"
    )
    otel_capture_content: bool = Field(
        default=False,
        env="OTEL_CAPTURE_CONTENT",
        description="Capture prompts/completions as events (be mindful of privacy)"
    )
    otel_max_event_content_length: int = Field(
        default=1000,
        env="OTEL_MAX_EVENT_CONTENT_LENGTH",
        description="Maximum length of content to capture in events"
    )
    otel_capture_sources: bool = Field(
        default=True,
        env="OTEL_CAPTURE_SOURCES",
        description="Capture retrieved sources in telemetry traces"
    )
    otel_max_sources_per_trace: int = Field(
        default=10,
        env="OTEL_MAX_SOURCES_PER_TRACE",
        description="Maximum number of sources to record per trace"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings.
    
    Uses LRU cache to ensure settings are loaded only once and reused
    throughout the application lifecycle.
    
    Returns:
        Settings: Configured application settings
    """
    return Settings()


 