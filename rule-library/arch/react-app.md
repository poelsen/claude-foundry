# Architecture: React Applications

## Component Hierarchy

```
pages/         → Route-level components
components/    → Reusable UI components
hooks/         → Custom hooks (shared logic)
services/      → API calls, external integrations
stores/        → State management
```

## State Architecture

- Local state: component-specific, ephemeral
- Global state: shared, persisted
- Server state: use React Query/SWR pattern

## Data Flow

- Props down, events up
- Avoid prop drilling (use context or composition)
- Container/presentational split where helpful
