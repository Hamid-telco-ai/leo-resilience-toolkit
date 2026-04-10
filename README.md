# LEO Resilience Toolkit

This project simulates and analyzes **LEO satellite connectivity resilience** using:
- Orbital simulation (TLE / Skyfield)
- RF link modeling (FSPL, SINR)
- Event generation
- Backend processing (FastAPI)
- Visualization (Streamlit)

---
# Project Structure

LEO-resilience-toolkit/
│
├── backend/
│   └── app/
│       ├── api/
│       ├── core/
│       ├── db/
│       ├── services/
│       └── requirements.txt
│
├── dashboard/
│   └── streamlit_app.py
│
├── simulation/
│   └── sample_scenarios/
│
├── artifacts/
├── scripts/
├── tests/
└── README.md

