# Viewing OpenTelemetry Events in Jaeger UI

## Important: Events Show as "Logs" in Jaeger

In Jaeger UI, OpenTelemetry events are displayed in the "Logs" section of each span, not as a separate "Events" section.

## Step-by-Step Guide

### 1. Find Your Trace
1. Open Jaeger UI: http://localhost:16686
2. Select Service: `s3-vectors-rag`
3. Click "Find Traces"
4. Click on a trace that includes a RAG query

### 2. Locate the Events
1. Expand the `rag.process_query` span
2. Look for the **"Logs" section** (it may show a count like "Logs (8)")
3. Click to expand the Logs section

### 3. View Event Details
Each "Log" entry is actually an OpenTelemetry event:

```
▼ Logs (8)
  │ 
  ├─ 10:23:45.123 rag.source.retrieved
  │  └─ Click to expand and see:
  │     - rag.source.index: 0
  │     - rag.source.name: "document.pdf"
  │     - rag.source.similarity_score: 0.9234
  │
  ├─ 10:23:45.124 rag.source.retrieved
  │  └─ Click to expand for next source
  │
  └─ 10:23:45.125 rag.sources.summary
     └─ Click to see summary attributes
```

### 4. Span Attributes
The span attributes are in a separate section:
1. Look for "Tags" or "Process" section
2. Find attributes like:
   - `rag.sources.count`
   - `rag.sources.unique_documents`
   - `rag.sources.avg_similarity_score`
   - `rag.sources.top_document`

## Visual Reference

In Jaeger UI, you'll see:

```
[Span: rag.process_query] ────────────────── 125ms
│
├─ Tags (Attributes)
│  ├─ rag.query: "What is..."
│  ├─ rag.sources.count: 6
│  ├─ rag.sources.unique_documents: 3
│  └─ rag.sources.top_document: "main.pdf"
│
└─ Logs (7)  ← Click here to see events!
   ├─ [timestamp] rag.source.retrieved
   ├─ [timestamp] rag.source.retrieved
   ├─ [timestamp] rag.source.retrieved
   ├─ [timestamp] rag.source.retrieved
   ├─ [timestamp] rag.source.retrieved
   ├─ [timestamp] rag.source.retrieved
   └─ [timestamp] rag.sources.summary
```

## Troubleshooting

### If You Don't See Any Logs
1. **Check the span is expanded** - Click on the span name
2. **Look for "Logs (n)"** - It might be collapsed
3. **Verify in JSON view** - Click "JSON" to see raw data

### If Logs Show But No Details
1. Click on each log entry to expand it
2. Attributes appear as nested fields
3. Some versions of Jaeger require clicking a small arrow

### Alternative Views
- **JSON View**: Shows complete event data
- **Raw View**: Displays all span data
- **Trace Graph**: Visual representation

## Tips for Better Visibility

1. **Use Trace Search**:
   - Tag: `rag.sources.top_document="your-doc.pdf"`
   - Find traces with specific sources

2. **Check Multiple Spans**:
   - `embeddings` spans have their own events
   - `chat` spans show prompt/completion events

3. **Time Range**:
   - Events have precise timestamps
   - Use them to correlate with metrics

## Known Jaeger UI Limitations

- Events always show as "Logs"
- No separate "Events" tab (this is normal)
- Must expand each log to see attributes
- Large numbers of events may be paginated

## Verifying Events Are Recorded

Run this query to check:
```bash
# Check if events are being recorded
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test query"}'

# Then in Jaeger:
# 1. Find the trace
# 2. Expand rag.process_query span
# 3. Expand "Logs" section
# 4. You should see rag.source.retrieved events
```