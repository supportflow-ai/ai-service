# Kiến trúc AI Service

## Mục tiêu

`ai-service` là **stateless inference service**, không phải backend nghiệp vụ thứ hai.

Backend ASP.NET Core vẫn là system of record và sở hữu:

- authentication / authorization;
- ticket lifecycle;
- taxonomy nghiệp vụ;
- priority và confidence band;
- AIAnalysis / AISuggestion persistence;
- accept / override / reject / expire;
- Knowledge Base và quyền truy cập;
- audit.

AI service chỉ sở hữu inference capabilities:

- ticket classification;
- embedding generation (capability nội bộ, chưa expose contract);
- model/provider adapters;
- evaluation code.

## Dependency direction

```text
API -> Application -> Ports <- Adapters
                    |
                  Domain
```

Domain/Application không phụ thuộc FastAPI, SDK model hay database.

## Contract boundary

API public được triển khai trong base này:

```text
POST /v1/ticket-classifications
```

Contract v1 phải tương thích bản canonical trong backend.

Không thêm `priority`, `status`, `assignment`, `actions`, role hoặc workflow command vào response.

Request body được giới hạn kích thước ở tầng ASGI; NGINX nên có giới hạn tương ứng.

## Embedding

Backend đã có `IEmbeddingService`, nhưng hiện chưa có external OpenAPI contract tương ứng.
Do đó base code chỉ tạo `TextEmbedder` port và `GenerateEmbedding` use case.

Chỉ expose endpoint embedding sau khi hai repository thống nhất contract versioned.

## RAG

RAG chưa phải nền tảng của service. Khi cần mở rộng:

```text
Embedding -> Retrieval (backend/pgvector) -> Authorization -> Reranking -> Generation
```

AI service không truy cập trực tiếp Service Desk PostgreSQL.

## Provider evolution

```text
classification:
  rule baseline
      -> local transformer
      -> fine-tuned model
      -> external LLM adapter

embedding:
  NoOp
      -> multilingual embedding adapter
```

Mỗi provider triển khai port riêng; HTTP contract và Application use case không đổi.
