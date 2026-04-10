# LEO Resilience Toolkit

## Included

- project skeleton
- FastAPI backend
- PostgreSQL schema via SQLAlchemy models
- Skyfield visibility engine
- YAML scenario configuration
- basic tests

## Project Layout

```text
leo-resilience-studio-week1/
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ config.py
│  │  ├─ db.py
│  │  ├─ models.py
│  │  ├─ schemas.py
│  │  ├─ routes/
│  │  ├─ services/
│  │  └─ utils/
│  └─ requirements.txt
├─ simulation/
│  ├─ visibility_engine.py
│  ├─ constellation.py
│  ├─ region.py
│  └─ sample_scenarios/
├─ docs/
├─ tests/
├─ .env.example
└─ README.md
```

## Quick start

### 1. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# or
.venv\Scripts\activate      # Windows PowerShell
```

### 2. Install dependencies

```bash
pip install -r backend/requirements.txt
```

### 3. Start PostgreSQL

Create a database named `leo_resilience` and update the connection string if needed.

### 4. Run the API

```bash
cd backend
uvicorn app.main:app --reload
```

### 5. Open docs

Visit:

- http://127.0.0.1:8000/docs


### Download live public TLEs
```bash
python tools/download_starlink_tles.py --fallback
```

This saves public TLEs to:

```text
simulation/sample_scenarios/starlink_live.tle
```

Update your scenario YAML so `constellation.tle_file` points to that file.

### Generate a pass visualization
```bash
python scripts/visualize_passes.py   --scenario simulation/sample_scenarios/northern_quebec_starlink_like.yaml   --output artifacts/visibility_passes.html
```

### Launch the Streamlit 3D preview
```bash
streamlit run dashboard/streamlit_app.py
```
