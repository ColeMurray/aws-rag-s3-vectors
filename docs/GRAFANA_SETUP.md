# Grafana Setup for S3 Vectors RAG Observability

## 1. Add Prometheus Data Source

1. Open Grafana at http://localhost:3000 (login: admin/admin)
2. Go to **Configuration** → **Data sources** (or navigate to http://localhost:3000/datasources)
3. Click **Add data source**
4. Select **Prometheus**
5. Configure the data source:
   - **Name**: `Prometheus-OTEL`
   - **URL**: `http://otel-collector:8889`
   - Leave other settings as default
6. Click **Save & test**

## 2. Import the Dashboard

### Option A: Import JSON File
1. Go to **Dashboards** → **Import** (or navigate to http://localhost:3000/dashboard/import)
2. Click **Upload JSON file**
3. Select the `grafana-dashboard.json` file from this repository
4. Select the Prometheus data source you just created
5. Click **Import**

### Option B: Manual Import
1. Go to **Dashboards** → **Import**
2. Copy the contents of `grafana-dashboard.json`
3. Paste into the **Import via panel json** text area
4. Click **Load**
5. Select the Prometheus data source
6. Click **Import**

## 3. Available Metrics

The dashboard shows:

### GenAI Metrics
- **Operations per Second**: Rate of embeddings and chat operations
- **Operation Latency (p95)**: 95th percentile latency for each operation type
- **Token Usage Rate**: Tokens consumed per minute by operation
- **Total Tokens Used**: Cumulative token count by type (input/output)

### RAG Pipeline Metrics
- **Vector Search Latency**: S3 Vectors query performance (p50, p95)
- **Chunks Retrieved per Query**: Distribution of retrieved chunks
- **Operation Breakdown**: Table showing operation counts by model

## 4. Creating Custom Queries

Example PromQL queries you can use:

```promql
# Average latency by operation
avg by (gen_ai_operation_name) (
  rate(s3_vectors_rag_gen_ai_client_operation_duration_seconds_sum[5m]) /
  rate(s3_vectors_rag_gen_ai_client_operation_duration_seconds_count[5m])
)

# Token cost estimation (adjust rates as needed)
sum(s3_vectors_rag_gen_ai_client_token_usage_total) by (gen_ai_request_model, gen_ai_token_type) * 
  on (gen_ai_request_model, gen_ai_token_type) group_left()
  (
    label_replace(vector(0.00001), "gen_ai_request_model", "amazon.titan-embed-text-v2:0", "", "") or
    label_replace(vector(0.003), "gen_ai_request_model", "us.anthropic.claude-3-5-haiku-20241022-v1:0", "", "")
  )

# Error rate
sum(rate(s3_vectors_rag_gen_ai_client_operation_duration_seconds_count{error="true"}[5m])) /
sum(rate(s3_vectors_rag_gen_ai_client_operation_duration_seconds_count[5m]))
```

## 5. Troubleshooting

### No Data Showing
1. Verify metrics are being exported:
   ```bash
   curl http://localhost:8889/metrics | grep s3_vectors_rag
   ```

2. Check Prometheus targets:
   - Go to http://localhost:9090/targets
   - Ensure `otel-collector` target is UP

3. Verify time range:
   - Metrics only appear after you've made queries to the RAG API
   - Adjust the time range in Grafana to include when you made requests

### Missing Metrics
- Token usage metrics only appear for models that return usage information
- Some operations may not emit all metrics if they fail

## 6. Advanced Configuration

### Add Alerts
1. Edit any panel and go to the **Alert** tab
2. Create alert conditions, e.g.:
   - High latency: `avg(rate(...)) > 5`
   - High token usage: `rate(...) > 1000`

### Create Variables
1. Go to Dashboard settings → Variables
2. Add variables for:
   - `model`: `label_values(gen_ai_request_model)`
   - `operation`: `label_values(gen_ai_operation_name)`
3. Use in queries: `{gen_ai_request_model="$model"}`

## 7. Monitoring Best Practices

1. **Set up alerts** for:
   - Latency > 10s for any operation
   - Error rate > 5%
   - Token usage exceeding budget

2. **Create separate dashboards** for:
   - Development (detailed metrics)
   - Production (key metrics and alerts)
   - Cost tracking (token usage focus)

3. **Regular reviews**:
   - Check for performance degradation
   - Monitor token usage trends
   - Identify slow queries or operations