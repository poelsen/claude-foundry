# Python/Qt Rules

Rules and checklists for Python/Qt desktop applications using PySide6.

**See also:** `.claude/rules/gui-threading.md` for threading rules.

## Sources

- KDAB: https://www.kdab.com/the-eight-rules-of-multithreaded-qt/
- MIT 6.005: https://web.mit.edu/6.005/www/fa14/classes/18-thread-safety/
- Python dataclasses: https://docs.python.org/3/library/dataclasses.html
- Qt 6 QThreadPool: https://doc.qt.io/qt-6/qthreadpool.html

---

## Style

- Use **PySide6** over PyQt6 (LGPL vs GPL licensing)
- Add `from __future__ import annotations` to all modules
- Type hints on all public functions
- Use `@dataclass(frozen=True)` for snapshot/immutable data
- Line length: 100 characters (compatible with Qt naming)

---

## Threading Rules Checklist

Before code review, verify:

- [ ] **KDAB #2**: No GUI operations off main thread
- [ ] **KDAB #3**: Main thread never blocks (no subprocess.run, no sleep)
- [ ] **KDAB #7**: Using QRunnable workers, not QThread subclasses
- [ ] **MIT**: Cross-thread data is immutable (frozen dataclass + tuple)
- [ ] Cancel pending jobs before starting new ones
- [ ] JobSignals inherits QObject for signal support
- [ ] Worker sets `setAutoDelete(True)`

---

## Data Patterns Checklist

- [ ] Snapshots use `@dataclass(frozen=True)`
- [ ] Collections use `tuple`, not `list`
- [ ] Type hints: `tuple[X, ...]` for variable-length tuples
- [ ] No mutable types inside frozen dataclasses
- [ ] Change detection via identity: `old is not new`

Example:
```python
@dataclass(frozen=True)
class StatusSnapshot:
    files: tuple[FileEntry, ...] = ()  # NOT list!
```

---

## QDockWidget Rules Checklist

- [ ] Call `setDockNestingEnabled(True)` on main window
- [ ] Assign corners with `setCorner()`
- [ ] Set `setObjectName()` on each dock (required for state persistence)
- [ ] Use `splitDockWidget()` for resize handles between docks
- [ ] Use hidden central widget for dock-only layouts
- [ ] Bump `LAYOUT_VERSION` when changing dock structure

---

## Persistence Checklist

- [ ] Use `QSettings` for state persistence
- [ ] Save geometry with `saveGeometry()`
- [ ] Save state with `saveState()`
- [ ] Track layout version number
- [ ] Skip restore if version mismatch
- [ ] Save on `closeEvent()`

---

## Signal/Slot Rules

- [ ] Use new-style connections: `signal.connect(slot)`
- [ ] Use `blockSignals(True)` to prevent feedback loops
- [ ] Create signals in `__init__` body or class body
- [ ] Lambda slots need explicit capture of referenced variables
- [ ] Prefer direct slot methods over lambdas for debuggability

---

## Testing Guidance

### Unit Tests

Test workers in isolation without Qt event loop:
```python
def test_worker_execute():
    job = MyJob(input_data)
    result = job.execute()  # Direct call, no threading
    assert result == expected
```

### Integration Tests

Use `pytest-qt` for Qt testing:
```python
def test_controller_refresh(qtbot):
    controller = RepoController()
    with qtbot.waitSignal(controller.status_changed):
        controller.request_refresh()
```

### What to Test

- [ ] Worker execute() logic (no Qt dependency)
- [ ] Controller state transitions
- [ ] View updates on signal emission
- [ ] Cancellation behavior
- [ ] Error handling paths

---

## Known Platform Issues

### WSL2 / X11

- Floating docks may freeze application
- Workaround: Disable `DockWidgetFloatable` feature

### macOS

- High-DPI and title bar unification quirks
- Test with `Qt::AA_UseHighDpiPixmaps`

### Windows

- Path separators: use `pathlib.Path`, not string concat
- Long paths: may need registry key for >260 char paths

---

## Quick Reference

| Pattern | Implementation |
|---------|----------------|
| Background work | `QThreadPool` + `QRunnable` |
| Thread signals | `QObject` with `Signal()` |
| Immutable data | `@dataclass(frozen=True)` |
| Debounce | `QTimer(singleShot=True)` |
| State persistence | `QSettings` |
| Prevent feedback | `blockSignals(True)` |
