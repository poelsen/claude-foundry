# GUI Threading Rules

Non-negotiable rules for multithreaded GUI applications. Violations cause race conditions, UI freezes, and crashes.

## Sources

- MIT 6.005: https://web.mit.edu/6.005/www/fa14/classes/18-thread-safety/
- KDAB: https://www.kdab.com/the-eight-rules-of-multithreaded-qt/
- Flux: https://facebookarchive.github.io/flux/docs/in-depth-overview/
- Redux: https://redux.js.org/faq/immutable-data

---

## Rule 1: UI Thread Does Zero Backend Work

**Source:** KDAB Rules #2, #3

The UI thread ONLY:
- Renders data from models
- Responds to user input
- Dispatches commands to controller

The UI thread NEVER:
- Runs subprocesses
- Performs file I/O
- Makes network requests
- Executes heavy computations
- Blocks waiting for results

**Violation = UI freeze / "not responding"**

---

## Rule 2: Single Controller Owns All State

**Source:** Flux/Redux Store pattern

One controller instance:
- Owns all cached state
- Coordinates all background jobs
- Receives all command requests
- Emits all state change signals

Views and models read from controller's cached state. They never call backend directly.

**Violation = State inconsistency / race conditions**

---

## Rule 3: One-Way Data Flow

**Source:** Facebook Flux Architecture

```
Backend → Controller → Models → Views
```

Data flows in ONE direction. Views never write to backend or models directly.

User actions create commands that flow to controller:
```
View → Command → Controller → Backend
```

**Violation = Cascading updates / unpredictable state**

---

## Rule 4: Refresh is Event-Driven

**Source:** KDAB Rule #1 (event-driven design)

Refresh triggers:
- User action (button click, menu command)
- Filesystem watcher event (debounced)
- Post-operation signal

NEVER refresh on timer/interval for main data.

**Exception:** Favorite repos summary can use long-interval polling.

**Violation = Wasted resources / timing bugs**

---

## Rule 5: Cancel Before New

Before starting a new background job:
1. Cancel any pending job of same type
2. Discard stale results if they arrive

Prevents stale results from overwriting fresh results.

**Violation = Stale data displayed / race conditions**

---

## Rule 6: Immutable Snapshots

**Source:** MIT 6.005 Strategy #2, Redux, Martin Fowler

Data passed between threads MUST be immutable:
- Worker creates snapshot
- Signal carries snapshot
- UI reads snapshot (cannot modify)

Use:
- Frozen dataclasses
- Tuples (not lists)
- Named tuples / records

NEVER pass mutable collections across threads.

**Violation = Race conditions / crashes / corrupted state**

---

## Quick Reference

| Rule | What | Why |
|------|------|-----|
| #1 | UI = render + react only | Prevents freezes |
| #2 | One controller owns state | Single source of truth |
| #3 | One-way data flow | Predictable updates |
| #4 | Event-driven refresh | No wasted polling |
| #5 | Cancel before new | No stale data |
| #6 | Immutable snapshots | Thread safety |

---

## Deviation Protocol

If you believe a rule should be violated:
1. **STOP** - Do not implement
2. **Explain** the proposed deviation
3. **Wait** for explicit approval
4. If approved, document the exception
