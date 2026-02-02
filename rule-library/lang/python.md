# Language: Python

## Environment & Tooling

- **Package manager**: `uv`
- **Config**: `pyproject.toml` (single source of truth, no setup.py/requirements.txt)
- **Build backend**: `hatchling`
- **Virtual env**: `.venv/` (created by uv)
- **Lock file**: `uv.lock` (commit to repo)

### Setup Commands
```bash
uv venv                    # Create .venv
uv pip install -e .[dev]   # Install with dev deps
```

### Running Commands
```bash
uv run pytest              # Tests
uv run ruff check src tests   # Lint
uv run ruff format src tests  # Format
```

## pyproject.toml Standard

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "myproject"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-cov>=4",
    "ruff>=0.8",
]

[tool.pytest.ini_options]
addopts = "-q --cov=myproject --cov-report=term-missing"
testpaths = ["tests"]

[tool.ruff]
target-version = "py311"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "SIM", "PTH", "RUF"]
ignore = ["E501"]
```

## Style

- PEP 8 compliance
- Type hints for function signatures
- Docstrings for public APIs (Google or NumPy style)
- f-strings over .format() or %

## Code Quality

- [ ] No bare `except:` — catch specific exceptions
- [ ] Context managers for resources (`with` statements)
- [ ] List comprehensions over map/filter where readable
- [ ] Avoid mutable default arguments
- [ ] Use `pathlib` over `os.path`

## Coding Style

### Don't Mutate Caller's Data
```python
# WRONG: Mutates the dict the caller passed in
def update_user(user, name):
    user['name'] = name  # Caller's data changed!
    return user

# CORRECT: Return new object, leave original untouched
def update_user(user, name):
    return {**user, 'name': name}

# With dataclasses
from dataclasses import replace
new_user = replace(user, name=name)
```

Mutating local/owned data is fine. The rule is:
don't surprise callers by modifying their data.

### Error Handling
```python
try:
    result = risky_operation()
    return result
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    raise UserFacingError("Detailed message") from e
```

### Input Validation
```python
from pydantic import BaseModel, EmailStr

class UserInput(BaseModel):
    email: EmailStr
    age: int = Field(ge=0, le=150)

validated = UserInput(**input_data)
```

## Testing

- pytest as test framework
- Fixtures for setup/teardown
- `parametrize` for multiple test cases
- Coverage target: 80%+

## Performance

- Profile before optimizing
- Consider generators for large datasets
- Use appropriate data structures (set for lookups, deque for queues)
