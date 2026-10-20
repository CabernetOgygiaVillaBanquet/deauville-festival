# Deauville Festival du Rire 2027

Platform and backend engine for the **Deauville Festival du Rire** (10–13 June 2027). The platform powers both a public-facing website and an administrative scheduling dashboard. It enforces festival scheduling rules, handles late-night calendar transitions, provides interactive CLI tools, and serves a tested REST API.

---

## 1. Quickstart & Installation

### Requirements
- **Python:** `>= 3.12`
- **Package Manager:** [`uv`](https://docs.astral.sh/uv/)

### Installation
Clone the repository and synchronize the environment:

```bash
git clone <repository-url> deauville-festival
cd deauville-festival
uv sync
```

`uv sync` sets up the virtual environment, installs runtime dependencies (FastAPI, Uvicorn, Pydantic), development tools (pytest, ruff, httpx), and registers the editable package console scripts.

---

## 2. Usage

### Command-Line Interface (`deauville`)
The project installs a CLI tool exposed via `uv run deauville`:

```bash
# Display festival summary (venues, artists, total shows)
uv run deauville

# List all venues with slug, capacity, and total seat count
uv run deauville venues

# View chronological programme for a festival day (respecting the 06:00 cutoff)
uv run deauville programme 2027-06-11

# View all stage appearances and roles for a specific artist
uv run deauville artist max-pellerin

# Check shows currently on stage and the next upcoming acts
uv run deauville now 2027-06-11T21:00

# Interactively schedule a new solo show (checks rules and saves to disk)
uv run deauville add

# Cancel a scheduled performance by its unique ID
uv run deauville cancel le-kiosque-2027-06-11-2330
```

### Running the Web Platform & Admin Dashboard
Start the combined API and static web server:

```bash
uv run deauville serve
```

Once running, navigate to:
- **Public Festival Site:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Admin Management Portal:** [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
- **Interactive OpenAPI Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 3. Architecture & Class Design

The codebase adheres to clean separation of concerns under `src/deauville/`:

```text
src/deauville/
├── __init__.py      # Package metadata and version definition
├── errors.py        # Domain exception hierarchy mapped to HTTP status codes
├── models.py        # Domain entities (Venue, Artist, ABC Performance, SoloShow, Lineup, Workshop)
├── festival.py      # Aggregate root Festival object protecting business invariants
├── storage.py       # Persistence abstraction layer (Storage, JSONStorage, MemoryStorage)
├── api.py           # Application factory (create_app), REST endpoints, and static mounts
└── cli.py           # CLI parser, command routing, and direct uvicorn server runner
```

### Domain Models & Polymorphism
- **`Venue`:** Represents physical stages (`slug`, `name`, `capacity`, `address`).
- **`Artist`:** Holds performer profiles (`slug`, `name`, `bio`, `photo_url`). Equality is based on identity slug (`__eq__`).
- **`Performance` (Abstract Base Class):** Base abstraction providing shared temporal attributes and comparisons (`__lt__` sorting by start datetime, then venue):
  - `start_datetime`, `end_datetime`: Python `datetime` calculations.
  - `festival_day`: Computes the effective day using the festival's **06:00 AM cutoff rule**. A performance starting at `01:00` on Saturday belongs to Friday night's programme.
  - `id`: Unique composite identifier formatted as `<venue-slug>-YYYY-MM-DD-HHMM`.
  - Abstract interfaces implemented polymorphically: `check_self_rules()`, `involves()`, `get_involved_artists()`, `summary()`, `get_capacity()`, and `to_view()`.
- **`SoloShow`:** Single artist performances; enforces `min_age` constraints between 0 and 18.
- **`Lineup`:** Multicast performances featuring a host and at least 2 distinct acts. Enforces minimum runtime rules: Minimum duration = (acts*10)+((acts-1)*3)

- **`Workshop`:** Interactive masterclasses with a designated teacher and registered participant tracking. Enforces maximum participant limits and clamps effective capacity: min(max_participants, venue.capacity)

---

## 4. Design & Architectural Questions

### Where do the rules live?
Domain rules are encapsulated entirely within the domain model. Subclass-specific constraints (e.g., lineup minimum duration, uniqueness of acts, age boundaries) execute directly in `check_self_rules()` upon instantiation. Global scheduling constraints (venue availability, artist cross-booking conflicts, festival date boundaries) reside inside `Festival.check_rules()`. Neither CLI parsers nor API route controllers contain validation logic; they delegate validation directly to `Festival` methods.

### How do errors indicate which rule failed?
The application defines a custom hierarchy in `deauville.errors`:
- **`NotFoundError` (HTTP `404`):** Missing artists, unknown venues, or non-existent performance IDs.
- **`ConflictError` (HTTP `409`):** Overlapping stage bookings, artist double-booking (including within the mandatory 30-minute turnaround buffer), duplicate artist registration, or full workshops.
- **`InvalidValueError` (HTTP `422`):** Out-of-bounds duration ($< 1$ or $> 360$ min), lineup runtime violations, or negative age parameters.

FastAPI catches these via a centralized exception handler (`@app.exception_handler(FestivalError)`), guaranteeing consistent error payloads (`{"detail": "..."}`) without scattered `try/except` blocks in route functions.

### What would change with a database?
Because of the **Storage Abstraction** in `deauville.storage`, swapping JSON file persistence for a relational database (e.g., PostgreSQL or SQLite via SQLModel/SQLAlchemy) requires zero modifications to `Festival`, `Performance`, or the API routes. Only a new `SQLStorage(Storage)` implementation would be added, passing it to `create_app(storage=...)` or the CLI entry point.

---

## 5. Testing & Quality Assurance

The test suite covers unit constraints, scheduling rules, and the complete HTTP contract defined in `API.md`. Tests run against an isolated sandbox created via pytest's `tmp_path` fixture, leaving production data files untouched.

```bash
# Run all unit and integration tests
uv run pytest -v

# Check code formatting and linting rules
uv run ruff check .
uv run ruff format --check .

# Build wheel package
uv build
```

---

## 6. Project Status & Delivery

- **Status:** Complete.
- **Known Bugs:** None. (The naive date string slicing issue from Step 02 was resolved in Step 04 using `datetime` offset arithmetic).
- **Packaging:** Packaged via `hatchling`; produces distributable wheel artifacts in `dist/`.
