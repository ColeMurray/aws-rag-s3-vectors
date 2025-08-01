# Source Tracking in OpenTelemetry Traces

This document explains the enhanced source tracking capabilities added to the RAG pipeline's telemetry.

## Overview

The RAG pipeline now captures detailed information about retrieved sources in OpenTelemetry traces, allowing you to:
- See which documents were retrieved for each query
- Track similarity scores and document metadata
- Analyze retrieval patterns and performance
- Debug retrieval issues

## Configuration

Source tracking is controlled by environment variables:

```bash
# Enable/disable source tracking (default: true)
OTEL_CAPTURE_SOURCES=true

# Maximum number of sources to record per trace (default: 10)
OTEL_MAX_SOURCES_PER_TRACE=10

# Optional: Enable content capture to see text previews
OTEL_CAPTURE_CONTENT=true
OTEL_MAX_EVENT_CONTENT_LENGTH=1000
```

## What Gets Tracked

### Span Attributes
On the main `rag.process_query` span, you'll find:
- `rag.sources.count` - Total number of sources retrieved
- `rag.sources.unique_documents` - Number of unique documents
- `rag.sources.avg_similarity_score` - Average similarity score
- `rag.sources.top_document` - Name of the top-scoring document

### Span Events
For each retrieved source (up to `OTEL_MAX_SOURCES_PER_TRACE`):
- **Event Name**: `rag.source.retrieved`
- **Attributes**:
  - `rag.source.index` - Position in results (0-based)
  - `rag.source.name` - Document/file name
  - `rag.source.chunk_index` - Chunk position within document
  - `rag.source.similarity_score` - Similarity score (0-1)
  - `rag.source.preview_length` - Length of text preview
  - `rag.source.text_preview` - Text preview (if content capture enabled)

A summary event is also recorded:
- **Event Name**: `rag.sources.summary`
- **Attributes**:
  - `rag.sources.total_count` - Total sources found
  - `rag.sources.recorded_count` - Sources recorded in trace
  - `rag.sources.avg_similarity` - Average similarity score
  - `rag.sources.unique_documents` - Unique document count
  - `rag.sources.top_documents` - Top 3 document names

## Viewing Sources in Jaeger

1. **Navigate to a trace** for a RAG query
2. **Expand the `rag.process_query` span**
3. **View span attributes** for summary information
4. **Click on "Events"** tab to see individual sources
5. **Expand each event** to see source details

### Filtering Traces by Source
Use Jaeger's search to find traces by source:
- Tag: `rag.sources.top_document` = "your-document.pdf"
- Tag: `rag.sources.count` > 5
- Tag: `rag.sources.avg_similarity_score` > 0.8

## Privacy Considerations

- **Source names and metadata** are captured by default
- **Text previews** are only captured if `OTEL_CAPTURE_CONTENT=true`
- **Sensitive documents**: Set `OTEL_CAPTURE_SOURCES=false` to disable
- **Production**: Consider disabling content capture for privacy

## Example Trace View

```
rag.process_query
├── Attributes:
│   ├── rag.query: "What is the company's revenue?"
│   ├── rag.chunks.retrieved: 6
│   ├── rag.sources.count: 6
│   ├── rag.sources.unique_documents: 3
│   ├── rag.sources.avg_similarity_score: 0.8234
│   └── rag.sources.top_document: "financial_report_2024.pdf"
│
└── Events:
    ├── rag.source.retrieved (0)
    │   ├── rag.source.name: "financial_report_2024.pdf"
    │   ├── rag.source.chunk_index: 42
    │   ├── rag.source.similarity_score: 0.9123
    │   └── rag.source.text_preview: "Total revenue for Q4 2024..."
    │
    ├── rag.source.retrieved (1)
    │   ├── rag.source.name: "earnings_call_transcript.pdf"
    │   ├── rag.source.chunk_index: 15
    │   └── rag.source.similarity_score: 0.8567
    │
    └── rag.sources.summary
        ├── rag.sources.total_count: 6
        ├── rag.sources.recorded_count: 6
        ├── rag.sources.avg_similarity: 0.8234
        └── rag.sources.top_documents: "financial_report_2024.pdf, earnings_call_transcript.pdf, investor_deck.pdf"
```

## Performance Impact

- **Minimal overhead** for metadata tracking
- **Event creation** is fast and asynchronous
- **Text previews** add slight overhead (when enabled)
- **Large result sets** are automatically limited

## Troubleshooting

### Sources Not Appearing in Traces
1. Check `OTEL_CAPTURE_SOURCES=true` in environment
2. Verify traces are being exported successfully
3. Check if query returned any results
4. Look for errors in application logs

### Missing Text Previews
- Set `OTEL_CAPTURE_CONTENT=true`
- Check `OTEL_MAX_EVENT_CONTENT_LENGTH` setting
- Verify source documents contain text

### Too Many Events
- Reduce `OTEL_MAX_SOURCES_PER_TRACE`
- Use `TOP_K` to limit retrieval results
- Filter by similarity threshold

## Best Practices

1. **Development**: Enable full source tracking with content
2. **Staging**: Test with realistic data volumes
3. **Production**: 
   - Disable content capture for privacy
   - Limit sources per trace to 5-10
   - Monitor trace size and storage costs

4. **Debugging**: Temporarily enable full tracking for specific issues

## Integration with Metrics

Source tracking complements existing metrics:
- `rag.chunks.retrieved.count` - Histogram of chunks per query
- `rag.vector.search.duration` - Search latency metrics
- Correlate high latency with number of sources

## Future Enhancements

Potential improvements:
- Source quality scoring
- Document type categorization
- Retrieval strategy tracking
- Source freshness indicators