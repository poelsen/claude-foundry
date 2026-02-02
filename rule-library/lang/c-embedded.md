# Language: C (Embedded)

## Safety Standards
- MISRA C guidelines where applicable
- No dynamic memory allocation (malloc/free)
- No recursion (or bounded with proof)
- All variables initialized at declaration

## Types
- Fixed-width integers (uint8_t, int32_t, etc.)
- Explicit signedness
- Careful with implicit promotions
- sizeof() for buffer sizes, not magic numbers

## Style
- Static functions for file-local scope
- Prefix for module namespacing (e.g., `uart_init()`)
- Structs for related data, not parallel arrays
- Enums over #define for related constants

## Memory
- [ ] No buffer overflows (bounds checking)
- [ ] Volatile for hardware registers and shared variables
- [ ] Packed structs only when necessary (with documentation)
- [ ] Alignment requirements respected

## Defensive Programming
- [ ] Assert preconditions (compiled out in release)
- [ ] Check return values
- [ ] Default cases in switch statements
- [ ] Null pointer checks on API boundaries

## Build
- Warnings as errors
- -Wall -Wextra -Wpedantic minimum
- Static analysis (PC-lint, cppcheck)
- Link-time optimization for size
