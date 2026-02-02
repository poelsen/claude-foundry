# Language: React

## Component Patterns

- Functional components with hooks
- Composition over inheritance
- Single responsibility per component
- Props for configuration, hooks for behavior

## Component Organization

- Organize by feature/domain, not by type
- Colocate component + test + styles + hooks
- Extract shared components to `components/common/`
- Keep component files under 200 lines

## Error Boundaries

```tsx
class ErrorBoundary extends React.Component<Props, { hasError: boolean }> {
  static getDerivedStateFromError() { return { hasError: true } }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    logError(error, info)
  }
  render() {
    if (this.state.hasError) return this.props.fallback
    return this.props.children
  }
}
```

Wrap route-level and feature-level boundaries. Never wrap individual components.

## State Management

- **Local state**: `useState` for component-scoped state
- **Shared state**: Context for low-frequency updates (theme, auth, locale)
- **Server state**: TanStack Query or SWR for API data (not Redux)
- **Complex state**: `useReducer` for multi-field forms or state machines
- Avoid prop drilling beyond 2 levels — use Context or composition

## Form Handling

- Controlled components for simple forms
- React Hook Form or Formik for complex forms
- Validate on submit, show errors on blur
- Disable submit button during async operations

## Custom Hooks

```typescript
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)

  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(handler)
  }, [value, delay])

  return debouncedValue
}
```

- Extract reusable logic into `use*` hooks
- Keep hooks focused — one concern per hook
- Always specify complete dependency arrays

## Performance

- `useMemo` for expensive computations
- `useCallback` for stable function references passed to children
- `React.memo` for pure component optimization
- List virtualization for large datasets (react-window, react-virtuoso)
- Lazy loading with `React.lazy` + `Suspense`
- Avoid inline object/array literals in JSX props

## Testing

- React Testing Library over Enzyme
- Test behavior, not implementation
- Mock external dependencies
- Use `screen` queries over container queries
- Test user interactions (click, type, submit) not internal state
