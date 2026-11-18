# MAIA – Agentic Maintenance Operating System (Demo)

## Included
- Existing maintenance prototype capabilities retained: plant/section dashboards, equipment master, maintenance tasks, breakdown register, preventive maintenance, machine reliability, OEM task variance, asset register/depreciation, persona navigation, AI assistant, Excel preview/export and audit trail.
- New **Spare Parts & Procurement Agent**: indicative consumption/stock-based replenishment, lead-time buffer, purchase requisition creation, configurable approval routing by value, approval action and demo PO creation after approval.
- Plant analytics: section downtime mix, asset criticality mix, monthly downtime and breakdown trends, top downtime machines; procurement risk and replenishment charts.
- MAIA SVG logo and branded UI.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Demo limitations / controls
- The workbook is synthetic. Inventory balances, spare-part demand, unit costs, supplier identities and lead-time history in the procurement module are illustrative demo data, not actual plant records.
- Procurement approval thresholds are illustrative defaults embedded in the demo: up to ₹10,000 Maintenance In-charge; ₹10,001–₹50,000 Plant Manager; ₹50,001–₹2,00,000 Plant Head; above ₹2,00,000 CFO / Business Head. Configure per customer policy before any pilot.
- The app creates a demo requisition and demo PO record only. It does not email suppliers, transmit an ERP purchase order, reserve real stock or make a payment.
- The current app uses session state; changes can be lost on restart. Production requires durable database storage, authentication/authorization, tenant isolation, audit controls, backups, secure integrations and operational monitoring.
- The AI Assistant is a deterministic demo intent router, not a live LLM or autonomous general-purpose agent. Procurement recommendations use transparent deterministic rules. Keep approval and execution controls deterministic and human-governed.
- Excel upload is preview-only. Validate OEM task libraries against the applicable OEM manuals and site standards.

## Deployment
For Streamlit Community Cloud, upload the contents of this folder to the app repository and set `app.py` as the entry point. Do not commit secrets. Keep the workbook in the app repository for this demo; use managed storage/database for production.


## Equipment-specific collaborative task lists
Each asset has a task list with three explicit source flags:
- `STANDARD_OEM`: standard tasks from the supplier/manufacturer task library.
- `HISTORICAL_INSIGHT`: candidate tasks derived from the asset's recorded breakdown history; pending client validation.
- `MANUFACTURER_RECOMMENDATION`: recommendations submitted by an OEM/manufacturer based on wider installed-base, service and warranty experience; pending client review.

The Equipment Master screen includes an OEM / Manufacturer persona to submit recommendations and a client review workflow to approve, reject or request clarification. This is a session-based prototype. Persistent multi-party collaboration, identity/access control, notifications, evidence attachments and audit-grade retention require production backend services.

All current OEM library and historical records are synthetic/illustrative and must be validated against actual machine manuals, service bulletins and customer records.
