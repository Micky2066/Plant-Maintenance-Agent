# MAIA – 100-machine automotive plant demo

## Included
- 100 assets numbered 1000–1099
- 35 CNC lathes, 24 VMCs, 41 SPMs
- Five functional sections: CNC, VMC, SPM, Utilities, Assembly
- 125 operators, 10 technicians, 10 machine suppliers, 10 contractors
- 5 years of synthetic maintenance history, breakdowns and PM records
- OEM task library and plant-vs-OEM task variance analysis
- MTTR, MTBF and availability at machine, section and plant levels
- Persona navigation for Section In-charge, Machine Operator, Plant Manager, CFO and Maintenance Manager
- CFO asset register with straight-line depreciation over 15 years
- AI intent routing that prioritizes read-only queries before create commands

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy update
Upload `app.py`, `requirements.txt`, `README.md`, and `MAIA_100_Machine_Plant_Dataset.xlsx` to the root of the existing GitHub repository connected to Streamlit Community Cloud. Commit/push. Streamlit will rebuild the app.

## Important modelling assumptions
- The plant was commissioned in 2001; 70 machines were purchased in 2016 and 30 were added at three per year from 2017–2026.
- Machine family and functional section are separate attributes to preserve the exact family mix while representing five sections: 20 SPMs are assigned to SPM, 10 SPMs to Utilities, and 11 SPMs to Assembly.
- Maintenance history covers 17-Nov-2021 to 16-Nov-2026.
- 16 scheduled operating hours per day are assumed for indicative MTBF/availability calculations.
- Depreciation is straight-line over 15 years with zero salvage value, time-apportioned from purchase date.
- The OEM task library is illustrative, not actual supplier-approved documentation. Validate all tasks and intervals against each machine's OEM manuals.
- Synthetic failures are seeded with recurring failure modes and increased occurrence propensity in May–September. They are not predictive model outputs.
- Interactive changes are held in Streamlit session state and can be lost on app restart. The workbook is the authoritative demo seed. Production requires managed persistent storage, authentication, tenant isolation, backups, monitoring, and security review.
- The AI assistant uses a deterministic intent router and local pandas queries; it is not connected to a live LLM.
