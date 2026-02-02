# Language: C++

## Modern C++ (C++17+)
- RAII for resource management
- Smart pointers over raw pointers (unique_ptr, shared_ptr)
- std::optional over null/sentinel values
- std::variant over unions
- constexpr where possible

## Memory Safety
- [ ] No manual new/delete (use smart pointers or containers)
- [ ] No C-style arrays (use std::array or std::vector)
- [ ] Bounds checking in debug builds
- [ ] Rule of 5 or Rule of 0 for classes

## Style
- Header guards or #pragma once
- Namespace wrapping (no `using namespace` in headers)
- const correctness
- noexcept where applicable
- [[nodiscard]] for functions with important return values

## Build
- CMake preferred
- Compiler warnings as errors (-Werror/-WX)
- Address/Thread sanitizers in CI
- Static analysis (clang-tidy)

## Performance
- Move semantics for large objects
- Prefer stack allocation
- Reserve container capacity when size known
- Avoid virtual functions in hot paths
