# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-31

### Added
- Initial release of AWS S3 Vectors RAG Application
- Core RAG pipeline using AWS S3 Vectors for vector storage
- Integration with Amazon Bedrock for embeddings (Titan V2) and LLM (Claude 3.5 Haiku)
- FastAPI-based REST API with comprehensive endpoints
- Document ingestion pipeline with chunking and metadata support
- Semantic search with similarity threshold and metadata filtering
- OpenTelemetry instrumentation following GenAI semantic conventions
- Source tracking in distributed traces for better observability
- Docker and Docker Compose support for easy deployment
- Comprehensive documentation including integration guides
- Grafana dashboard for monitoring metrics
- Health check and statistics endpoints
- Retry logic with exponential backoff for AWS services
- Sample data and test scripts

### Security
- IAM-based access control for AWS services
- Support for SSE-S3 and SSE-KMS encryption
- Environment-based configuration management
- No hardcoded credentials or sensitive data

### Performance
- Batch operations for vector insertion (up to 500 vectors per request)
- Optimized chunk size and overlap for better retrieval
- Configurable similarity threshold for search precision
- Connection pooling for AWS clients