"""RAG service for query processing with S3 Vectors."""
import json
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from contextlib import nullcontext
import structlog

import boto3
from botocore.exceptions import ClientError

from .config import Settings
from .s3_vector_client import S3VectorClient
from .telemetry import (
    get_telemetry, 
    GenAIAttributes, 
    GenAIEventNames,
    RAGAttributes
)

logger = structlog.get_logger()

class RAGService:
    """Service for RAG operations using S3 Vectors."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._setup_clients()
    
    def _setup_clients(self):
        """Initialize AWS clients."""
        # Bedrock client
        self.bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=self.settings.aws_region
        )
        
        # S3 Vectors client
        self.vector_client = S3VectorClient(
            region=self.settings.aws_region,
            bucket_name=self.settings.s3_vector_bucket_name,
            index_name=self.settings.s3_vector_index_name
        )
        
        logger.info("RAG service initialized")
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Bedrock."""
        telemetry = get_telemetry()
        start_time = time.time()
        
        # Start GenAI span for embeddings operation
        span_context = telemetry.genai_span(
            operation_name="embeddings",
            system="aws.bedrock",
            model=self.settings.embed_model_id
        ) if telemetry else None
        
        with span_context if span_context else nullcontext() as span:
            try:
                # Record user message event
                if telemetry and span:
                    telemetry.record_genai_event(
                        span,
                        GenAIEventNames.USER_MESSAGE,
                        text,
                        role="user",
                        text_length=len(text)
                    )
                
                response = self.bedrock_client.invoke_model(
                    modelId=self.settings.embed_model_id,
                    body=json.dumps({"inputText": text}),
                    contentType="application/json",
                    accept="application/json",
                )
                
                response_body = json.loads(response["body"].read())
                embedding = response_body["embedding"]
                
                # Calculate metrics
                latency_ms = (time.time() - start_time) * 1000
                duration_s = time.time() - start_time
                
                # Set span attributes
                if span:
                    span.set_attribute(GenAIAttributes.GEN_AI_RESPONSE_MODEL, self.settings.embed_model_id)
                    span.set_attribute("embedding.dimension", len(embedding))
                    span.set_attribute("text.length", len(text))
                
                # Record metrics
                if telemetry:
                    telemetry.record_operation_duration(
                        duration_s,
                        system="aws.bedrock",
                        model=self.settings.embed_model_id,
                        operation="embeddings"
                    )
                    # Estimate token usage (rough approximation)
                    estimated_tokens = len(text.split()) * 1.3
                    telemetry.record_token_usage(
                        system="aws.bedrock",
                        model=self.settings.embed_model_id,
                        operation="embeddings",
                        input_tokens=int(estimated_tokens)
                    )
                
                logger.info(
                    "Bedrock embedding generated",
                    latency_ms=round(latency_ms, 2),
                    text_length=len(text),
                    embedding_dimension=len(embedding),
                    model_id=self.settings.embed_model_id
                )
                
                return embedding
                
            except ClientError as e:
                latency_ms = (time.time() - start_time) * 1000
                logger.error(
                    "Bedrock embedding generation failed",
                    error=str(e),
                    latency_ms=round(latency_ms, 2),
                    model_id=self.settings.embed_model_id
                )
                raise
    
    async def search_similar_chunks(
        self, 
        query_embedding: List[float], 
        top_k: int, 
        threshold: float,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar chunks in S3 Vectors."""
        try:
            matches = self.vector_client.query_vectors(
                query_embedding=query_embedding,
                top_k=top_k,
                filter_dict=filter_dict,
                similarity_threshold=threshold
            )
            
            logger.info("Similarity search completed", matches_found=len(matches))
            return matches
            
        except Exception as e:
            logger.error("Vector search failed", error=str(e))
            raise
    
    async def generate_answer(self, query: str, context: str) -> str:
        """Generate answer using Bedrock LLM."""
        prompt = (
            "You are a helpful assistant. Use the context below to answer the question. "
            "If the context doesn't contain enough information, say so clearly."
            "When answering a question, be concise and to the point."
            "For off topic questions, respond with 'I'm sorry, I can't help with that.'\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            "Answer:"
        )
        
        telemetry = get_telemetry()
        start_time = time.time()
        
        # Start GenAI span for chat operation
        span_context = telemetry.genai_span(
            operation_name="chat",
            system="aws.bedrock",
            model=self.settings.llm_model_id,
            **{
                GenAIAttributes.GEN_AI_REQUEST_TEMPERATURE: self.settings.temperature,
                GenAIAttributes.GEN_AI_REQUEST_MAX_TOKENS: self.settings.max_tokens,
            }
        ) if telemetry else None
        
        with span_context if span_context else nullcontext() as span:
            try:
                # Record user message event
                if telemetry and span:
                    telemetry.record_genai_event(
                        span,
                        GenAIEventNames.USER_MESSAGE,
                        prompt,
                        role="user",
                        prompt_length=len(prompt)
                    )
                
                response = self.bedrock_client.invoke_model(
                    modelId=self.settings.llm_model_id,
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": self.settings.max_tokens,
                        "temperature": self.settings.temperature,
                        "messages": [
                            {
                                "role": "user",
                                "content": [{"type": "text", "text": prompt}],
                            }
                        ]
                    }),
                    contentType="application/json",
                    accept="application/json",
                )
                
                response_body = json.loads(response["body"].read())
                
                if "content" in response_body and response_body["content"]:
                    answer = response_body["content"][0]["text"].strip()
                    finish_reason = response_body.get("stop_reason", "unknown")
                    usage = response_body.get("usage", {})
                    
                    # Calculate metrics
                    latency_ms = (time.time() - start_time) * 1000
                    duration_s = time.time() - start_time
                    
                    # Set span attributes
                    if span:
                        span.set_attribute(GenAIAttributes.GEN_AI_RESPONSE_MODEL, self.settings.llm_model_id)
                        span.set_attribute(GenAIAttributes.GEN_AI_RESPONSE_FINISH_REASON, finish_reason)
                        if usage:
                            span.set_attribute(GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS, usage.get("input_tokens", 0))
                            span.set_attribute(GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS, usage.get("output_tokens", 0))
                    
                    # Record assistant message event
                    if telemetry and span:
                        telemetry.record_genai_event(
                            span,
                            GenAIEventNames.ASSISTANT_MESSAGE,
                            answer,
                            role="assistant",
                            answer_length=len(answer),
                            finish_reason=finish_reason
                        )
                    
                    # Record metrics
                    if telemetry:
                        telemetry.record_operation_duration(
                            duration_s,
                            system="aws.bedrock",
                            model=self.settings.llm_model_id,
                            operation="chat"
                        )
                        if usage:
                            telemetry.record_token_usage(
                                system="aws.bedrock",
                                model=self.settings.llm_model_id,
                                operation="chat",
                                input_tokens=usage.get("input_tokens", 0),
                                output_tokens=usage.get("output_tokens", 0)
                            )
                    
                    logger.info(
                        "Bedrock LLM answer generated",
                        latency_ms=round(latency_ms, 2),
                        prompt_length=len(prompt),
                        answer_length=len(answer),
                        model_id=self.settings.llm_model_id,
                        max_tokens=self.settings.max_tokens,
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0)
                    )
                    
                    return answer
                
                raise ValueError("Unexpected response format")
                
            except ClientError as e:
                latency_ms = (time.time() - start_time) * 1000
                logger.error(
                    "Bedrock LLM generation failed",
                    error=str(e),
                    latency_ms=round(latency_ms, 2),
                    model_id=self.settings.llm_model_id
                )
                raise
    
    async def process_query(
        self, 
        query: str,
        max_chunks: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process a complete RAG query."""
        telemetry = get_telemetry()
        start_time = time.time()
        
        # Use defaults if not provided
        max_chunks = max_chunks or self.settings.top_k
        similarity_threshold = similarity_threshold or self.settings.similarity_threshold
        
        # Create span for overall RAG process
        span_context = telemetry.tracer.start_as_current_span(
            "rag.process_query",
            attributes={
                RAGAttributes.RAG_QUERY: query[:100],
                RAGAttributes.RAG_CHUNKS_THRESHOLD: similarity_threshold,
                "rag.max_chunks": max_chunks,
                "rag.has_filter": bool(metadata_filter)
            }
        ) if telemetry else None
        
        with span_context if span_context else nullcontext() as span:
            logger.info("Processing query", query=query, max_chunks=max_chunks)
            
            # Track timing for each phase
            phase_start = time.time()
            
            # Generate query embedding
            query_embedding = await self.generate_embedding(query)
            embedding_time_ms = (time.time() - phase_start) * 1000
            
            # Search for similar chunks
            phase_start = time.time()
            similar_chunks = await self.search_similar_chunks(
                query_embedding, 
                max_chunks, 
                similarity_threshold,
                metadata_filter
            )
            search_time_ms = (time.time() - phase_start) * 1000
            
            # Record chunks retrieved metric
            if telemetry:
                telemetry.chunks_retrieved.record(
                    len(similar_chunks),
                    {
                        "rag.has_results": len(similar_chunks) > 0,
                        "rag.max_chunks": max_chunks
                    }
                )
            
            if not similar_chunks:
                result = {
                    "answer": "I couldn't find any relevant information to answer your question.",
                    "query": query,
                    "sources": [],
                    "processing_time_ms": round((time.time() - start_time) * 1000, 2),
                    "chunks_found": 0,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                if span:
                    span.set_attribute(RAGAttributes.RAG_CHUNKS_RETRIEVED, 0)
                    span.set_attribute("rag.no_results", True)
                return result
            
            # Prepare context from chunks
            context_parts = []
            sources = []
            
            for i, match in enumerate(similar_chunks):
                chunk_text = match["metadata"].get("source_text", "")
                context_parts.append(f"[Source {i+1}]: {chunk_text}")
                
                sources.append({
                    "source": match["metadata"].get("source", "Unknown"),
                    "chunk_index": match["metadata"].get("chunk_index", 0),
                    "similarity_score": round(match["score"], 4),
                    "text_preview": chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text
                })
            
            context = "\n\n".join(context_parts)
            
            # Generate answer
            phase_start = time.time()
            answer = await self.generate_answer(query, context)
            generation_time_ms = (time.time() - phase_start) * 1000
            
            processing_time = round((time.time() - start_time) * 1000, 2)
            
            # Update span with final attributes
            if span:
                span.set_attribute(RAGAttributes.RAG_CHUNKS_RETRIEVED, len(similar_chunks))
                span.set_attribute("rag.context_length", len(context))
                span.set_attribute("rag.answer_length", len(answer))
                
                # Add source summary attributes
                if sources:
                    span.set_attribute("rag.sources.count", len(sources))
                    span.set_attribute("rag.sources.unique_documents", len(set(s.get("source", "") for s in sources)))
                    avg_similarity = sum(s.get("similarity_score", 0) for s in sources) / len(sources) if sources else 0
                    span.set_attribute("rag.sources.avg_similarity_score", round(avg_similarity, 4))
                    
                    # Add top source name for easy filtering
                    if sources[0].get("source"):
                        span.set_attribute("rag.sources.top_document", sources[0]["source"])
                
                # Record source events and summary
                if telemetry and sources:
                    telemetry.record_sources_summary(span, sources)
                span.set_attribute("rag.total_duration_ms", processing_time)
            
            # Log complete performance breakdown
            logger.info(
                "RAG query completed",
                total_time_ms=processing_time,
                embedding_time_ms=round(embedding_time_ms, 2),
                vector_search_time_ms=round(search_time_ms, 2),
                llm_generation_time_ms=round(generation_time_ms, 2),
                chunks_found=len(similar_chunks),
                query_length=len(query),
                context_length=len(context)
            )
            
            return {
                "answer": answer,
                "query": query,
                "sources": sources,
                "processing_time_ms": processing_time,
                "chunks_found": len(similar_chunks),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "performance_breakdown": {
                    "embedding_ms": round(embedding_time_ms, 2),
                    "vector_search_ms": round(search_time_ms, 2),
                    "llm_generation_ms": round(generation_time_ms, 2),
                    "total_ms": processing_time
                }
            }
    
    async def health_check(self) -> Dict[str, str]:
        """Check health of all services."""
        services = {}
        
        # Test Bedrock
        try:
            await self.generate_embedding("test")
            services["bedrock"] = "healthy"
        except Exception:
            services["bedrock"] = "unhealthy"
        
        # Test S3 Vectors
        try:
            self.vector_client.get_index_stats()
            services["s3_vectors"] = "healthy"
        except Exception:
            services["s3_vectors"] = "unhealthy"
        
        return services