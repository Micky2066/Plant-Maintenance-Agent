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


## Maintenance plans, orders and external service orders (new)
Equipment Master navigation now follows **Equipment → Maintenance Plan → Maintenance Order → Task List**.
- Four plan cycles are supported: Monthly, Quarterly, Six-monthly and Annual.
- Daily and weekly tasks are bundled into the Monthly plan while preserving their original task-level frequency.
- Quarterly, half-yearly and annual tasks are bundled into their respective plans.
- History-derived suggestions and manufacturer recommendations are excluded from plan generation until client approval. An approved recommendation's own cadence determines its plan cycle.
- Each plan can generate a maintenance order for a scheduled date. The order retains the task list IDs and task count.
- Tasks can be assigned to Client/In-house, Contractor, or Machine Manufacturer/OEM.
- Each maintenance order exposes **Create order for outside vendor / machine manufacturer**. It creates a linked external service order draft containing selected external tasks, party, scope, requested/target dates and commercial reference.

External service orders are draft records only; this prototype does not transmit purchase orders, vendor work orders, emails or service requests. Commercial approvals, ERP/CMMS integration, persistent storage, access controls and notifications remain production requirements. All task data remains illustrative and must be validated against actual OEM documentation and plant history.

## MRO inventory intelligence and monthly purchasing forecast (new)
A new **MRO Inventory Intelligence** navigation page has been added for the CFO, Plant Manager and Maintenance Manager personas.

The synthetic workbook now includes:
- `MRO_Material_Master`: 120 sample maintenance spare SKUs, including category, UOM, OEM reference, equipment compatibility, criticality, demand pattern, unit cost, supplier, lead time, MOQ, order multiple, repairability and target service level.
- `MRO_Stock_Balance`: opening balances and reserved quantities for one central plant store.
- `MRO_Consumption_History`: 24 months of synthetic monthly material issue history (Nov 2024–Oct 2026).
- `MRO_Open_Purchase_Orders`: illustrative open PO lines and expected receipt dates.
- `MRO_Monthly_Forecast`: 12-month item-level demand forecast (Nov 2026–Oct 2027), using simple moving average, trend-adjusted and Croston-style methods.
- `MRO_Supplier_Performance`: illustrative lead-time, on-time delivery and quality data.
- `MRO_Data_Dictionary`: scope, assumptions and limitations.

The app derives an indicative safety stock, reorder point and maximum stock using item demand, lead time and criticality-based service-level defaults. It simulates monthly demand, stock and replenishment to produce a monthly purchasing forecast. Users can prepare a batch of purchase requisitions from a selected month, approve or reject them, and create a purchase-order draft from an approved requisition.

**Important limitations:** all new MRO master, inventory, supplier, transaction and forecast data are synthetic. Forecast methods and stock policy calculations are illustrative prototype logic, not a validated stochastic inventory optimisation engine. Service-level defaults (A 99%, B 97%, C 93%) are demo assumptions. Purchase orders are drafts only and are not transmitted to suppliers or ERP. Interactive requisitions, approvals and PO drafts are held in Streamlit session state and reset on app restart. No code or workbook changes establish production-grade persistence, multi-user authorisation, ERP integration or audit controls.


## Technician productivity and wrench time (new)
A **Technicians & Workforce** module is available to the Maintenance Manager persona:
- Technician master extensions: secondary skill, grade, default shift, scheduled shift hours, break hours and active status.
- Shift calendar: daily shift records with scheduled hours, breaks, approved leave and net available hours.
- Leave records: pending/approved/rejected status; approved leave can reduce an existing shift's availability.
- Manual activity-level time logging linked to technician, maintenance order and optional equipment.
- Categories: Productive (repair, PM, diagnosis, inspection, testing, calibration), Travel, Delay (materials, machine availability, tools, production clearance, safety permits) and Non-maintenance.
- Individual wrench-time KPI: productive maintenance hours divided by net available shift hours. Breaks and approved leave are deducted; travel and delays are reported separately.
- Basic controls: positive duration, no overlapping entries for the same technician, audit events and visible unallocated capacity.

Prototype limitations: workforce transactions are held in Streamlit session state and reset on app restart; there is no durable multi-user database, approval workflow security, mobile technician identity, offline capture or payroll/HR integration. Shift records must be entered for the measurement period; no productivity KPI is fabricated when shift data is missing. The leave form records approval status but does not implement a role-secured approval process. The module is a demonstration workflow, not a production time-and-attendance system.
