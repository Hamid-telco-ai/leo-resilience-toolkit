# LEO Link Resilience Toolkit

This project simulates and analyzes **LEO satellite connectivity resilience** using:
- Orbital simulation (TLE / Skyfield)
- RF link modeling (FSPL, SINR)
- Event generation
- Backend processing (FastAPI)
- Visualization (Streamlit)

<img width="1892" height="907" alt="image" src="https://github.com/user-attachments/assets/1a02f95f-efd8-4fb3-b1d7-a9a389e57a45" />


## Included

- project skeleton
- FastAPI backend
- PostgreSQL schema via SQLAlchemy models
- Skyfield visibility engine
- YAML scenario configuration
- basic tests

## Project Layout

```text
leo-resilience-toolkit/
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
---

## References

- 3GPP TR 38.863 V19.1.0 – *NR NTN Enhancements*
- O-RAN.WG1.TR.RIC4NTN-R005-v02.00 – *RIC Enabling NTN Deployments*
- https://celestrak.org
- https://lnkd.in/eP2Jt6tB
- D. A. Vallado et al., *“Revisiting Spacetrack Report #3,”* 2006
- ITU-R P.525 – *Free-space propagation model*

