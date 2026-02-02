# Language: C

## Standard

- Target C11 (or C99 where required by toolchain)
- Compile with `-Wall -Wextra -Werror -pedantic`
- Use static analysis (cppcheck, clang-tidy, or Coverity)

## Memory Safety

- Every `malloc` must have a corresponding `free` on all paths
- Check return value of `malloc` — never assume success
- Set pointers to `NULL` after `free`
- Use `sizeof(*ptr)` not `sizeof(type)` in allocations
- Prefer stack allocation for small, fixed-size data
- Use RAII-like patterns: init/cleanup function pairs

## Defensive Coding

- Validate all function parameters (assert or early return)
- Check return values of all system/library calls
- Use `const` liberally — especially for function parameters
- Prefer `size_t` for sizes and indices
- Avoid `gets`, `sprintf`, `strcpy` — use bounded variants (`fgets`, `snprintf`, `strncpy`)
- No VLAs in production code

## File Organization

```
include/       # Public headers (.h)
src/           # Implementation (.c) + internal headers
tests/         # Test files
```

- One module = one `.c` + one `.h`
- Header guards: `#ifndef PROJECT_MODULE_H` / `#define` / `#endif`
- Forward declarations over unnecessary includes

## Naming

- `snake_case` for functions and variables
- `UPPER_SNAKE_CASE` for macros and constants
- Prefix public API with module name: `parser_init()`, `parser_free()`
- Prefix private/static functions with `_` or keep `static`

## Error Handling

- Return error codes (0 = success, negative = error)
- Use `enum` for error codes, not raw integers
- Goto-based cleanup for multi-resource functions:

```c
int process(void) {
    int *buf = malloc(SIZE);
    if (!buf) return -ENOMEM;
    FILE *f = fopen(path, "r");
    if (!f) { free(buf); return -EIO; }
    // ... work ...
    fclose(f);
    free(buf);
    return 0;
}
```

## Testing

- Unity, CMocka, or Check for unit tests
- Test edge cases: NULL inputs, zero sizes, max values
- Run under Valgrind or AddressSanitizer (`-fsanitize=address`)
