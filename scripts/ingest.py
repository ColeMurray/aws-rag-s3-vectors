#!/usr/bin/env python
"""CLI script for document ingestion."""
import argparse
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.ingest_service import DocumentIngester

def main():
    parser = argparse.ArgumentParser(description="Ingest documents into S3 Vectors")
    parser.add_argument("path", help="Directory path containing documents")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=getattr(logging, args.log_level))
    
    try:
        ingester = DocumentIngester()
        result = ingester.ingest_directory(args.path)
        
        print(f"\nIngestion Complete:")
        print(f"Files processed: {result['files_processed']}/{result['total_files']}")
        print(f"Chunks ingested: {result['chunks_ingested']}")
        print(f"Total vectors in index: {result['index_stats']['total_vectors']}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()