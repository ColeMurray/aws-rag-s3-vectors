"""FastAPI application for S3 Vectors RAG pipeline."""
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import get_settings
from .rag_service import RAGService
from .telemetry import init_telemetry, get_telemetry

# Request/Response models
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    max_chunks: Optional[int] = Field(default=None, ge=1, le=20)
    similarity_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    metadata_filter: Optional[Dict[str, Any]] = Field(default=None)

class QueryResponse(BaseModel):
    answer: str
    query: str
    sources: list
    processing_time_ms: float
    chunks_found: int
    timestamp: str
    performance_breakdown: Optional[Dict[str, float]] = None

# Initialize FastAPI app
def create_app() -> FastAPI:
    settings = get_settings()
    
    app = FastAPI(
        title=settings.api_title,
        description=settings.api_description,
        version=settings.api_version
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app

app = create_app()
rag_service = None

@app.on_event("startup")
async def startup_event():
    global rag_service
    settings = get_settings()
    # Initialize OpenTelemetry
    init_telemetry(settings)
    rag_service = RAGService(settings)

def get_rag_service() -> RAGService:
    if rag_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return rag_service

# API Endpoints
@app.get("/")
async def root():
    settings = get_settings()
    return {
        "message": f"Welcome to {settings.api_title}",
        "version": settings.api_version,
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health_check(service: RAGService = Depends(get_rag_service)):
    services = await service.health_check()
    status = "healthy" if all(s == "healthy" for s in services.values()) else "degraded"
    
    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": services
    }

@app.post("/query", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    service: RAGService = Depends(get_rag_service)
):
    """Query documents using RAG with S3 Vectors."""
    result = await service.process_query(
        query=request.query,
        max_chunks=request.max_chunks,
        similarity_threshold=request.similarity_threshold,
        metadata_filter=request.metadata_filter
    )
    return QueryResponse(**result)

@app.get("/stats")
async def get_index_stats(service: RAGService = Depends(get_rag_service)):
    """Get S3 Vectors index statistics."""
    try:
        stats = service.vector_client.get_index_stats()
        return {
            "index_stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
async def get_metrics():
    """Expose Prometheus metrics (if using Prometheus exporter)."""
    telemetry = get_telemetry()
    if not telemetry:
        raise HTTPException(status_code=503, detail="Telemetry not enabled")
    
    # Note: In a production setup, you would use prometheus_client to expose metrics
    # For now, return a simple status
    return {
        "status": "OpenTelemetry metrics are being exported to collector",
        "exporter_endpoint": telemetry.settings.otel_exporter_endpoint,
        "metrics_available": [
            "gen_ai.client.token.usage",
            "gen_ai.client.operation.duration",
            "rag.vector.search.duration",
            "rag.chunks.retrieved.count"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "src.app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )