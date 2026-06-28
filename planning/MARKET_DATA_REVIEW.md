# Market Data Backend — Code Review

**Date:** 2026-06-28  
**Reviewer:** Claude Sonnet 4.6  
**Scope:** `backend/app/market/` (8 source files, ~315 statements) and `backend/tests/market/` (6 test files, 82 tests)  
**Environment:** Python 3.13.7, pytest 9.1.1, ruff 0.15.20

---

## 1. Test Results

**82 tests collected, 82 passed, 0 failed.**

This is an improvement over the archived review (73 tests, 5 failures) — 9 tests were added and all previous failures were resolved. The test run is clean with no warnings or skips.

```
tests/market/test_cache.py           14 passed
tests/market/test_factory.py          7 passed
tests/market/test_massive.py         22 passed
tests/market/test_models.py          11 passed
tests/market/test_simulator.py       18 passed
tests/market/test_simulator_source.py 10 passed
```

**Runtime:** 5.7 seconds (dominated by `asyncio.sleep(0.6)` calls in simulator_source integration tests).

---

## 2. Coverage

| Module | Stmts | Miss | Cover | Uncovered lines |
|---|---|---|---|---|
| `__init__.py` | 8 | 0 | **100%** | — |
| `cache.py` | 31 | 0 | **100%** | — |
| `factory.py` | 9 | 0 | **100%** | — |
| `models.py` | 15 | 0 | **100%** | — |
| `seed_prices.py` | 5 | 0 | **100%** | — |
| `interface.py` | 19 | 1 | 95% | L41 (`get_tickers` default impl) |
| `simulator.py` | 92 | 3 | 97% | L86–88 (event shock branch, probabilistic) |
| `massive_client.py` | 107 | 23 | 79% | L38–50 (start/stop lifecycle), L56, L85–86, L91, L94–101, L125, L128–132 |
| `stream.py` | 29 | 18 | **38%** | L23–37 (route handler), L49–71 (event generator) |
| **TOTAL** | **315** | **45** | **86%** | |

**Overall: 86%.** The five core modules are at 100%. The only meaningful gaps are:

- **`stream.py` (38%)**: The entire SSE route and async generator body are untested. This is the primary interface between the backend and the frontend.
- **`massive_client.py` (79%)**: The `start()` / `stop()` lifecycle methods are not tested (network calls would be needed), which is expected. The `_poll_loop` background task path is also untested.

---

## 3. Lint Results

**Source code (`app/market/`):** All checks passed — zero ruff violations.

**Test files (`tests/market/`):** 4 auto-fixable import order violations (I001 — isort):

| File | Issue |
|---|---|
| `test_cache.py` | Import block unsorted |
| `test_massive.py` | Import block unsorted |
| `test_models.py` | Import block unsorted |
| `test_simulator.py` | Import block unsorted |

All four are trivially fixable with `ruff check --fix tests/market/`.

---

## 4. Architecture Assessment

The subsystem follows a clean strategy pattern with good separation of concerns:

```
MarketDataSource (ABC)
├── SimulatorDataSource  — GBM price engine, default, no external deps
└── MassiveDataSource    — Polygon.io REST poller, optional
        │
        ▼
   PriceCache (thread-safe, version-tracked)
        │
        ▼
   SSE /api/stream/prices → Frontend EventSource
```

**Strengths:**

- **Strategy pattern is properly implemented.** Both sources conform to the ABC; downstream code depends only on the interface. The factory is the single decision point for which source is active — no other code checks `MASSIVE_API_KEY`.
- **GBM math is correct.** `price_t = price_{t-1} * exp((μ − 0.5σ²)Δt + σ√(Δt)Z)` produces log-normal paths; prices can never reach zero (floored at 0.01). The correlated market factor (`Z_i = β·market + √(1−β²)·noise`) is the standard Cholesky decomposition approach.
- **`PriceCache` is the right abstraction.** Producers write once; all consumers read from the same snapshot. Version counter avoids redundant SSE pushes. `get_all()` returns a copy, preventing consumers from holding a reference to internal state.
- **`GBMSimulator` is cleanly separated from `SimulatorDataSource`.** The engine is pure/synchronous; the source adds async lifecycle management. This separation makes the engine independently testable, which is reflected in the dedicated `test_simulator.py`.
- **Background task lifecycle is correct.** Both `SimulatorDataSource.stop()` and `MassiveDataSource.stop()` cancel their task and await cancellation with `contextlib.suppress(CancelledError)`, then set `_task = None`. The `MassiveDataSource` also closes its `httpx.AsyncClient` on stop.
- **SSE anti-buffering headers are correct.** `X-Accel-Buffering: no` and `Cache-Control: no-cache` prevent Nginx and proxies from buffering the event stream.
- **`SystemRandom` in the simulator** sources from the OS CSPRNG rather than Mersenne Twister, providing better unpredictability. This is a thoughtful choice for a price simulator.
- **Seed prices and per-ticker GBM parameters** are well-tuned: TSLA at σ=0.55 vs V at σ=0.17, NVDA drift=0.12 vs JPM drift=0.06 — these reflect real-world relative differences.

---

## 5. Issues Found

### 5.1 Typo in `massive_client.py` (Severity: Low)

**File:** `massive_client.py:69`

```python
max_ticker_lenght = 5   # 'lenght' should be 'length'
```

A local variable with a misspelling. No functional impact, but should be corrected. The equivalent variable in `simulator.py:137` is correctly spelled `max_ticker_length`.

**Fix:**
```python
max_ticker_length = 5
```

---

### 5.2 `stream.py` Accesses Private `_cache` Attribute on the Interface (Severity: Low)

**File:** `stream.py:50`

```python
cache = getattr(source, "_cache", None)
...
current_version = cache.version if cache is not None else 0
```

`_cache` is a private implementation detail of both concrete source classes. The `MarketDataSource` ABC does not expose `version` or any change-detection mechanism. This creates invisible coupling: if a future data source stores prices differently (e.g., a WebSocket-based source), it would need to add `_cache` even though that's not part of the contract.

**Two clean fixes, in order of preference:**

Option A — Add `version` to the ABC (recommended):
```python
# interface.py
@property
def version(self) -> int:
    """Monotonically increasing counter; increments when prices change."""
    ...
```

Option B — Remove version-based change detection from the SSE handler. Simply push all prices every 500ms regardless. Given the simulator already ticks every 500ms, this change has no observable impact on SSE behavior and removes the coupling entirely.

---

### 5.3 `AsyncGenerator` Missing Second Type Parameter (Severity: Low)

**File:** `stream.py:42`

```python
async def _generate_events(
    request: Request, source: MarketDataSource
) -> AsyncGenerator[str]:
```

`collections.abc.AsyncGenerator` requires two type parameters: `AsyncGenerator[YieldType, SendType]`. With one argument, `AsyncGenerator[str]` is technically incorrect and would be flagged by strict type checkers (mypy, pyright). The correct annotation is `AsyncGenerator[str, None]`.

---

### 5.4 `SimulatorDataSource._tick_loop` Has No Exception Guard (Severity: Low)

**File:** `simulator.py:143–148`

```python
async def _tick_loop(self) -> None:
    while True:
        updates = self._simulator.tick()
        if updates:
            await self._cache.set_many(updates)
        await asyncio.sleep(TICK_INTERVAL_S)
```

If `tick()` or `set_many()` raise an unexpected exception (e.g., memory error, corrupted internal state), the asyncio task dies silently. The background loop is the heartbeat of the entire application; it should log and continue rather than dying.

**Recommended fix:**
```python
async def _tick_loop(self) -> None:
    while True:
        try:
            updates = self._simulator.tick()
            if updates:
                await self._cache.set_many(updates)
        except Exception:
            logger.exception("Unexpected error in simulator tick loop")
        await asyncio.sleep(TICK_INTERVAL_S)
```

Note: `MassiveDataSource._poll_loop` already has this pattern correctly — `_poll_once` catches all exception types. The simulator should match it.

---

### 5.5 `version` Property Reads Without Lock (Severity: Informational)

**File:** `cache.py:43–45`

```python
@property
def version(self) -> int:
    return self._version
```

The `version` property reads `self._version` without acquiring `self._lock`, while all writes to `_version` are done under the lock. On CPython with the GIL, reading a Python `int` is atomic, so this is safe in practice. However, under the no-GIL Python 3.13t+ build (PEP 703), this becomes a legitimate data race.

Given this is a course project likely running on standard CPython, this is informational rather than a bug. However, it's inconsistent with the rest of the class and worth noting.

---

### 5.6 `MassiveDataSource.validate_ticker` Returns False When Not Started (Severity: Informational)

**File:** `massive_client.py:76–77`

```python
if self._client is None:
    return False
```

If `validate_ticker` is called before `start()`, it silently reports any ticker as invalid. Calling `validate_ticker` before `start()` is a misuse of the API, but the silent `False` return makes this hard to debug. An assertion or logged warning would be more helpful.

---

## 6. Test Quality Assessment

**What the tests do well:**

- **Core logic is exhaustively covered.** The 100% coverage across `models.py`, `cache.py`, `factory.py`, and `seed_prices.py` means every branch in the most-used code paths is exercised.
- **GBM math is stress-tested with 500–1000 tick runs** (`test_prices_always_positive`, `test_gbm_price_formula_valid`), providing statistical confidence in the price floor and finite-number guarantees.
- **Edge cases are covered.** Zero-price division in `PriceUpdate`, empty ticker sets, unknown tickers, duplicate adds, lowercase normalization, whitespace API keys.
- **Error paths in `MassiveDataSource` are tested via mock injection.** The 429, 403, and timeout handlers all have tests that verify the correct log-level and message content.
- **Idempotence of `stop()` is indirectly verified** — `test_stop_cancels_background_task` checks the task state post-stop.

**Missing tests:**

1. **SSE endpoint (`stream.py`, 38% coverage).** The version-based change detection, JSON payload format, and disconnection handling are all untested. These are the primary behaviors the frontend depends on. A test using `httpx.AsyncClient` with an ASGI transport would cover this:

   ```python
   async def test_sse_emits_price_events():
       source = SimulatorDataSource()
       app = FastAPI()
       app.include_router(create_stream_router(source), prefix="/api")
       async with LifespanManager(app):
           async with httpx.AsyncClient(app=app) as client:
               async with client.stream("GET", "/api/stream/prices") as resp:
                   # collect first event...
   ```

2. **`MassiveDataSource.start()` / `stop()` lifecycle.** The async client setup and teardown (lines 38–50) are not tested. A test verifying that `_client` is set after start and `None` after stop would add confidence.

3. **`PriceCache` concurrent writes.** There is no test exercising multiple concurrent async writers. The lock appears correct from inspection, but a concurrent stress test (two tasks calling `set_many` simultaneously) would verify empirically.

4. **`interface.py` `get_tickers()` default implementation** (line 41, 95% coverage). The default `get_tickers()` derives the set from `get_all_prices().keys()` — this could be tested directly against the ABC's default rather than always going through the concrete implementations.

---

## 7. Comparison to Prior Review (Archive: 2026-02-10)

The archived review found 7 issues. All 7 have been resolved:

| Prior Issue | Status |
|---|---|
| `pyproject.toml` missing `[tool.hatch.build.targets.wheel]` | ✅ Fixed |
| Lazy imports of `massive` broke test patching | ✅ Fixed (switched to direct mock injection via `source._client`) |
| `_generate_events` return type annotation `-> None` | ✅ Fixed (`-> AsyncGenerator[str]`) |
| `GBMSimulator` lacked public `get_tickers()` | ✅ Fixed |
| Unused `DEFAULT_CORR` constant confusing vs `CROSS_GROUP_CORR` | ✅ Fixed (cleaned up in `seed_prices.py`) |
| Unused imports in test files | ✅ Fixed (all imports are now used) |
| Module-level router object footgun | ✅ Fixed (`create_stream_router()` factory pattern) |

The 5 test failures in the archived review are gone. 9 additional tests were added (82 vs 73). The `massive_client.py` test coverage improved significantly (56% → 79%) thanks to the new direct mock injection approach.

---

## 8. Verdict

The market data backend is production-quality for a course project. The architecture is clean, the math is correct, the tests are thorough on the core logic, and all previously identified issues have been resolved.

**Must fix:**
- Nothing is blocking.

**Should fix before integration with the rest of the backend:**
1. **Typo `max_ticker_lenght`** (`massive_client.py:69`) — trivial one-character fix.
2. **Import ordering in 4 test files** — run `ruff check --fix tests/market/`.
3. **`AsyncGenerator[str]` → `AsyncGenerator[str, None]`** (`stream.py:42`) — type correctness.
4. **Exception guard in `_tick_loop`** (`simulator.py`) — prevents silent task death on unexpected error, matching `MassiveDataSource`'s existing pattern.

**Nice to have:**
5. **SSE integration test** — even a single test verifying that prices appear in the event stream would close the biggest coverage gap.
6. **Expose `version` via the ABC** — removes private attribute access from `stream.py`, keeps the abstraction clean.
7. **Log a warning when `validate_ticker` is called before `start()`** — aids debugging.
