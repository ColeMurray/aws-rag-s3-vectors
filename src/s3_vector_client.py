import boto3
import json
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import structlog
from botocore.exceptions import ClientError
import time
from contextlib import nullcontext

from .telemetry import get_telemetry, RAGAttributes
from opentelemetry.trace import Status, StatusCode

logger = structlog.get_logger()

class S3VectorClient:
    """Client for AWS S3 Vectors operations."""
    
    def __init__(self, region: str, bucket_name: str, index_name: str):
        self.s3vectors = boto3.client("s3vectors", region_name=region)
        self.bucket_name = bucket_name
        self.index_name = index_name
        self.max_retries = 3
        self.retry_delay = 1.0
        
    def create_bucket_if_not_exists(self, encryption_type: str = "SSE-S3"):
        """Create vector bucket if it doesn't exist."""
        # Note: In preview, bucket creation might be manual
        logger.info("Assuming vector bucket exists (preview mode)", bucket=self.bucket_name)
    
    def create_index_if_not_exists(self, dimension: int, distance_metric: str, 
                                  non_filterable_keys: List[str] = None):
        """Create vector index if it doesn't exist."""
        # Note: In preview, index creation might be manual
        logger.info("Assuming vector index exists (preview mode)", 
                   index=self.index_name, dimension=dimension)
    
    def upsert_vectors(self, vectors: List[Dict[str, Any]]) -> int:
        """Insert or update vectors in the index with retry logic."""
        telemetry = get_telemetry()
        
        # Create span for S3 Vectors upsert
        span_context = telemetry.tracer.start_as_current_span(
            "s3_vectors.upsert",
            attributes={
                RAGAttributes.S3_VECTOR_BUCKET: self.bucket_name,
                RAGAttributes.S3_VECTOR_INDEX: self.index_name,
                RAGAttributes.S3_VECTOR_OPERATION: "upsert_vectors",
                "s3.vector.total_vectors": len(vectors)
            }
        ) if telemetry else None
        
        with span_context if span_context else nullcontext() as span:
            formatted_vectors = []
            for v in vectors:
                # Ensure values are float32
                values_array = np.array(v["values"], dtype=np.float32)
                formatted_vector = {
                    "key": v["id"],
                    "data": {"float32": values_array.tolist()},
                    "metadata": v["metadata"]
                }
                formatted_vectors.append(formatted_vector)
            
            total_uploaded = 0
            batch_size = 500  # S3 Vectors limit
            total_batches = (len(formatted_vectors) + batch_size - 1) // batch_size
            
            if span:
                span.set_attribute("s3.vector.batch_size", batch_size)
                span.set_attribute("s3.vector.total_batches", total_batches)
            
            for i in range(0, len(formatted_vectors), batch_size):
                batch = formatted_vectors[i:i + batch_size]
                
                # Retry logic for rate limiting
                for attempt in range(self.max_retries):
                    try:
                        batch_start = time.time()
                        self.s3vectors.put_vectors(
                            vectorBucketName=self.bucket_name,
                            indexName=self.index_name,
                            vectors=batch
                        )
                        total_uploaded += len(batch)
                        
                        if span:
                            span.add_event(
                                "batch_uploaded",
                                {
                                    "batch_size": len(batch),
                                    "batch_number": i // batch_size + 1,
                                    "duration_ms": round((time.time() - batch_start) * 1000, 2)
                                }
                            )
                        
                        logger.debug("Uploaded vector batch", size=len(batch))
                        break
                    except ClientError as e:
                        if e.response['Error']['Code'] == 'TooManyRequestsException':
                            if attempt < self.max_retries - 1:
                                time.sleep(self.retry_delay * (2 ** attempt))
                                logger.warning("Rate limited, retrying", attempt=attempt)
                                if span:
                                    span.add_event(
                                        "rate_limit_retry",
                                        {"attempt": attempt, "delay_seconds": self.retry_delay * (2 ** attempt)}
                                    )
                            else:
                                if span:
                                    span.record_exception(e)
                                    span.set_status(Status(StatusCode.ERROR, "Rate limit exceeded"))
                                raise
                        else:
                            if span:
                                span.record_exception(e)
                                span.set_status(Status(StatusCode.ERROR, str(e)))
                            raise
            
            if span:
                span.set_attribute("s3.vector.uploaded_count", total_uploaded)
            
            return total_uploaded
    
    def query_vectors(self, query_embedding: List[float], top_k: int, 
                     filter_dict: Dict[str, Any] = None, 
                     similarity_threshold: float = 0.0) -> List[Dict[str, Any]]:
        """Query vectors for similarity search."""
        telemetry = get_telemetry()
        
        # Create span for S3 Vectors query
        span_context = telemetry.tracer.start_as_current_span(
            "s3_vectors.query",
            attributes={
                RAGAttributes.S3_VECTOR_BUCKET: self.bucket_name,
                RAGAttributes.S3_VECTOR_INDEX: self.index_name,
                RAGAttributes.S3_VECTOR_OPERATION: "query_vectors",
                "s3.vector.top_k": top_k,
                "s3.vector.similarity_threshold": similarity_threshold,
                "s3.vector.has_filter": bool(filter_dict)
            }
        ) if telemetry else None
        
        with span_context if span_context else nullcontext() as span:
            # Ensure query embedding is float32
            query_array = np.array(query_embedding, dtype=np.float32)
            
            params = {
                "vectorBucketName": self.bucket_name,
                "indexName": self.index_name,
                "queryVector": {"float32": query_array.tolist()},
                "topK": top_k,
                "returnDistance": True,
                "returnMetadata": True
            }
            
            if filter_dict:
                params["filter"] = filter_dict
            
            # Track S3 Vectors query latency
            start_time = time.time()
            try:
                response = self.s3vectors.query_vectors(**params)
                query_latency_ms = (time.time() - start_time) * 1000
                duration_s = time.time() - start_time
                
                # Update span with results
                if span:
                    span.set_attribute("s3.vector.response_size", len(response.get("vectors", [])))
                    span.set_attribute("s3.vector.query_latency_ms", round(query_latency_ms, 2))
                
                # Record metric
                if telemetry:
                    telemetry.vector_search_duration.record(
                        duration_s,
                        {
                            RAGAttributes.S3_VECTOR_BUCKET: self.bucket_name,
                            RAGAttributes.S3_VECTOR_INDEX: self.index_name,
                            "s3.vector.top_k": top_k
                        }
                    )
                
                # Log query performance metrics
                logger.info(
                    "S3 Vectors query completed",
                    latency_ms=round(query_latency_ms, 2),
                    top_k=top_k,
                    has_filter=bool(filter_dict),
                    bucket=self.bucket_name,
                    index=self.index_name,
                    response_size=len(response.get("vectors", []))
                )
            except ClientError as e:
                query_latency_ms = (time.time() - start_time) * 1000
                if span:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                logger.error(
                    "S3 Vectors query failed",
                    error=str(e),
                    latency_ms=round(query_latency_ms, 2),
                    bucket=self.bucket_name,
                    index=self.index_name
                )
                raise
        
        # Process results with timing
        processing_start = time.time()
        matches = []
        for vector in response.get("vectors", []):
            # Convert cosine distance to similarity score
            # Cosine distance ranges from 0 (identical) to 2 (opposite)
            distance = vector.get("distance", 0)
            similarity_score = 1 - (distance / 2)
            
            # Apply similarity threshold
            if similarity_score >= similarity_threshold:
                matches.append({
                    "id": vector["key"],
                    "score": similarity_score,
                    "metadata": vector.get("metadata", {})
                })
        
        processing_time_ms = (time.time() - processing_start) * 1000
        
        logger.debug(
            "S3 Vectors result processing completed",
            processing_time_ms=round(processing_time_ms, 2),
            matches_found=len(matches),
            similarity_threshold=similarity_threshold
        )
        
        return matches
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        # Note: S3 Vectors is in preview and some APIs might not be available yet
        # Return placeholder stats for now
        logger.info("Index stats API not available in preview, returning placeholder values")
        return {
            "total_vectors": 0,
            "dimension": self.settings.s3_vector_dimension if hasattr(self, 'settings') else 1024,
            "index_size": 0,
            "status": "preview_mode"
        }
    
    def delete_vectors(self, vector_ids: List[str]) -> int:
        """Delete vectors by ID."""
        deleted_count = 0
        batch_size = 500
        
        for i in range(0, len(vector_ids), batch_size):
            batch = vector_ids[i:i + batch_size]
            try:
                self.s3vectors.delete_vectors(
                    vectorBucketName=self.bucket_name,
                    indexName=self.index_name,
                    keys=batch
                )
                deleted_count += len(batch)
            except ClientError as e:
                logger.error("Failed to delete vectors", error=str(e))
                raise
        
        return deleted_count