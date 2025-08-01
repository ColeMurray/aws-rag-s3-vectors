"""Document ingestion service for S3 Vectors."""
import json
import pathlib
from typing import List, Dict, Any
from datetime import datetime, timezone
import hashlib

import boto3
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import structlog

from .config import get_settings
from .s3_vector_client import S3VectorClient

logger = structlog.get_logger()

class DocumentIngester:
    """Handles document ingestion into S3 Vectors."""
    
    def __init__(self):
        self.settings = get_settings()
        self._setup_clients()
        self._setup_text_splitter()
    
    def _setup_clients(self):
        """Initialize AWS clients."""
        # Bedrock client for embeddings
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
        
        # Initialize S3 Vectors infrastructure
        self.vector_client.create_bucket_if_not_exists()
        self.vector_client.create_index_if_not_exists(
            dimension=self.settings.s3_vector_dimension,
            distance_metric=self.settings.s3_vector_distance_metric,
            non_filterable_keys=["source_text"]
        )
        
        logger.info("Clients initialized", region=self.settings.aws_region)
    
    def _setup_text_splitter(self):
        """Initialize text splitter for chunking documents."""
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
            length_function=len,
        )
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using Bedrock Titan."""
        response = self.bedrock_client.invoke_model(
            modelId=self.settings.embed_model_id,
            body=json.dumps({"inputText": text}),
            contentType="application/json",
            accept="application/json",
        )
        
        response_body = json.loads(response["body"].read())
        return response_body["embedding"]
    
    def create_document_id(self, source: str, chunk_index: int) -> str:
        """Create unique document ID."""
        content = f"{source}:{chunk_index}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def process_document(self, file_path: pathlib.Path) -> List[Dict[str, Any]]:
        """Process a single document into chunks with embeddings."""
        logger.info("Processing document", file_path=str(file_path))
        
        # Load document
        loader = TextLoader(str(file_path), encoding='utf-8')
        documents = loader.load()
        
        if not documents:
            logger.warning("No content loaded", file_path=str(file_path))
            return []
        
        # Split into chunks
        chunks = self.text_splitter.split_documents(documents)
        processed_chunks = []
        
        for i, chunk in enumerate(chunks):
            try:
                # Generate embedding
                embedding = self.generate_embedding(chunk.page_content)
                
                # Create metadata
                metadata = {
                    "source": str(file_path),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "file_name": file_path.name,
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                    "text_length": len(chunk.page_content),
                    "source_text": chunk.page_content  # Non-filterable
                }
                
                processed_chunks.append({
                    "id": self.create_document_id(str(file_path), i),
                    "values": embedding,
                    "metadata": metadata
                })
                
            except Exception as e:
                logger.error("Failed to process chunk", chunk_index=i, error=str(e))
                continue
        
        return processed_chunks
    
    def ingest_directory(self, directory_path: str) -> Dict[str, Any]:
        """Ingest all text files from a directory."""
        directory = pathlib.Path(directory_path)
        
        if not directory.exists():
            raise ValueError(f"Directory does not exist: {directory}")
        
        text_files = list(directory.rglob("*.txt"))
        
        if not text_files:
            logger.warning("No text files found", directory=str(directory))
            return {"files_processed": 0, "chunks_ingested": 0}
        
        logger.info("Starting ingestion", file_count=len(text_files))
        
        all_chunks = []
        successful_files = 0
        
        for file_path in text_files:
            try:
                chunks = self.process_document(file_path)
                all_chunks.extend(chunks)
                successful_files += 1
            except Exception as e:
                logger.error("Failed to process file", file_path=str(file_path), error=str(e))
        
        # Upload to S3 Vectors
        chunks_uploaded = 0
        if all_chunks:
            chunks_uploaded = self.vector_client.upsert_vectors(all_chunks)
        
        # Get index stats
        try:
            stats = self.vector_client.get_index_stats()
        except Exception as e:
            logger.warning("Failed to get index stats", error=str(e))
            stats = {"total_vectors": 0, "dimension": 0, "index_size": 0}
        
        return {
            "files_processed": successful_files,
            "total_files": len(text_files),
            "chunks_ingested": chunks_uploaded,
            "index_stats": stats
        }