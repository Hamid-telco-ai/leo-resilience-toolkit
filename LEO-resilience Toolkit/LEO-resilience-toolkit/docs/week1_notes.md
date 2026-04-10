# Week 1 Notes

This package contains the Week 1 scaffold for LEO Resilience Studio:

- FastAPI backend
- PostgreSQL-ready SQLAlchemy models
- YAML scenario format
- Skyfield visibility engine
- sample scenario and sample TLE file

## Run locally

1. Create a virtual environment.
2. Install requirements from `backend/requirements.txt`.
3. Start PostgreSQL and create the `leo_resilience` database.
4. Run from the `backend` directory:

```bash
uvicorn app.main:app --reload
```

## Endpoints

- `GET /health`
- `POST /scenarios`
- `GET /scenarios`
- `GET /scenarios/{scenario_id}`
- `POST /simulate/visibility/{scenario_id}`

## Notes

The included TLEs are only for initial structure testing. Replace them with a Starlink-like public dataset or a validated surrogate set before using results for demos.
