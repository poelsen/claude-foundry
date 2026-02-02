# Architecture: REST APIs

## Endpoint Organization

- Group by resource/domain, not by HTTP method
- Version in URL path (/v1/) or header
- Consistent naming: plural nouns for collections

## Layers

```
routes/        → HTTP handling, validation
services/      → Business logic
repositories/  → Data access
```

## Error Handling

- Centralized error middleware
- Consistent error response format
- Operational vs programmer errors

## Middleware Chain

- Auth → Rate limit → Validation → Handler → Error handler
- Each middleware single-purpose
