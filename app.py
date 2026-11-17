import streamlit as st
import pandas as pd
import re
from datetime import date, datetime, timedelta
from pathlib import Path

APP_DIR = Path(__file__).parent
DATA_FILE = APP_DIR / "MAIA_100_Machine_Plant_Dataset.xlsx"
st.set_page_config(page_title="MAIA | Plant Maintenance Intelligence", page_icon="🏭", layout="wide")

@st.cache_data
def load_data():
    names = ["Equipment_Master","Operator_Master","Technician_Master","Supplier_Master","Contractor_Master",
             "Section_Master","OEM_Task_Library","PM_History_5Y","OEM_Task_Variance","Breakdown_History_5Y",
             "Maintenance_Tasks_5Y","Machine_Reliability","Section_Reliability","Plant_Reliability","Data_Dictionary"]
    return {n: pd.read_excel(DATA_FILE, sheet_name=n) for n in names}

data = load_data()
for key, df in data.items():
    if key not in st.session_state:
        st.session_state[key] = df.copy()

def df(key): return st.session_state[key]
def add_audit(action, object_type, object_id, details):
    row = {"timestamp":datetime.now().isoformat(timespec="seconds"),"actor":st.session_state.get("actor","Demo user"),
           "action":action,"object_type":object_type,"object_id":str(object_id),"details":details}
    if "Audit_Trail" not in st.session_state:
        st.session_state["Audit_Trail"] = pd.DataFrame(columns=row.keys())
    st.session_state["Audit_Trail"] = pd.concat([st.session_state["Audit_Trail"],pd.DataFrame([row])],ignore_index=True)

def fmt_inr(x):
    return "₹" + format(float(x or 0),",.0f")

def filtered_breakdowns(section=None, equipment_id=None):
    x=df("Breakdown_History_5Y").copy()
    if section: x=x[x.section==section]
    if equipment_id: x=x[x.equipment_id.astype(str)==str(equipment_id)]
    return x

def calc_kpis(b):
    count=len(b); down=float(b.downtime_hours.sum()) if count else 0
    repair=float(b.repair_hours.sum()) if count else 0
    eq=df("Equipment_Master")
    if not b.empty:
        ids=b.equipment_id.astype(str).unique()
        eq=eq[eq.equipment_id.astype(str).isin(ids)]
    op=0
    for _,e in eq.iterrows():
        start=max(date(2021,11,17),date.fromisoformat(str(e.purchase_date)[:10]))
        op += max(1,(date(2026,11,16)-start).days)*16
    return {"Breakdowns":count,"Downtime (h)":round(down,1),"MTBF (h)":round((op-down)/count,1) if count else None,
            "MTTR (h)":round(repair/count,2) if count else None,"Availability (%)":round(100*(op-down)/op,2) if op else None}

st.markdown("""<style>.block-container{padding-top:1.1rem}.small{color:#64748b;font-size:.85rem}</style>""",unsafe_allow_html=True)
with st.sidebar:
    st.title("🏭 MAIA")
    st.caption("Manufacturing Asset Intelligence Assistant")
    role=st.selectbox("Persona",["Section In-charge","Machine Operator","Plant Manager","CFO","Maintenance Manager"])
    st.session_state["actor"]=role
    if role=="Section In-charge":
        section=st.selectbox("My section",["CNC","VMC","SPM","Utilities","Assembly"])
        pages=["Section Availability","Machine Reliability","Maintenance Tasks","Breakdown Register","AI Assistant"]
    elif role=="Machine Operator":
        operator=st.selectbox("Operator",df("Operator_Master").operator_name.tolist())
        pages=["My Machines & Daily Tasks","Maintenance Schedule","Breakdown Register","AI Assistant"]
    elif role=="CFO":
        pages=["Asset Register & Depreciation","Asset Summary","AI Assistant"]
    elif role=="Plant Manager":
        pages=["Plant Dashboard","Section Availability","Machine Reliability","OEM Task Analysis","Asset Summary","AI Assistant"]
    else:
        pages=["Plant Dashboard","Equipment Master","Maintenance Tasks","Breakdown Register","Preventive Maintenance","Machine Reliability","OEM Task Analysis","Asset Register & Depreciation","AI Assistant","Excel Import / Export","Audit Trail"]
    page=st.radio("Navigation",pages)
    st.divider()
    st.caption("DEMO DATA · SYNTHETIC")
    st.caption("100 machines · 5 sections · 5-year history")
    st.caption("Session changes reset on app restart; use external durable storage for production.")

st.title("MAIA")
st.caption("Plant-wide maintenance, reliability and asset intelligence | Automotive manufacturing demo")
eq=df("Equipment_Master"); tasks=df("Maintenance_Tasks_5Y"); bds=df("Breakdown_History_5Y")

if page in ["Plant Dashboard","Section Availability"]:
    if page=="Section Availability":
        sec=section if role=="Section In-charge" else st.selectbox("Section",["CNC","VMC","SPM","Utilities","Assembly"])
        eqs=eq[eq.section==sec]; b=filtered_breakdowns(section=sec)
        st.subheader(f"{sec} section – availability and reliability")
    else:
        eqs=eq; b=bds
        st.subheader("Plant manager dashboard")
    k=calc_kpis(b)
    cols=st.columns(5)
    cols[0].metric("Machines",len(eqs)); cols[1].metric("Breakdowns",k["Breakdowns"])
    cols[2].metric("Downtime",f'{k["Downtime (h)"]} h')
    cols[3].metric("MTTR",f'{k["MTTR (h)"]} h' if k["MTTR (h)"] is not None else "—")
    cols[4].metric("MTBF",f'{k["MTBF (h)"]} h' if k["MTBF (h)"] is not None else "—")
    st.markdown("#### Machine availability / condition")
    kpi=df("Machine_Reliability")
    if page=="Section Availability": kpi=kpi[kpi.section==sec]
    st.dataframe(kpi.sort_values("availability_pct"),use_container_width=True,hide_index=True)
    st.markdown("#### Downtime by machine")
    chart=b.groupby("equipment_id").downtime_hours.sum().sort_values(ascending=False).head(15)
    st.bar_chart(chart)
    st.markdown("#### Section comparison")
    st.dataframe(df("Section_Reliability"),use_container_width=True,hide_index=True)

elif page=="Equipment Master":
    st.subheader("Equipment master – 100 assets")
    a,b,c=st.columns(3)
    fam=a.multiselect("Machine family",sorted(eq.machine_family.unique()),default=sorted(eq.machine_family.unique()))
    sec=b.multiselect("Functional section",sorted(eq.section.unique()),default=sorted(eq.section.unique()))
    crit=c.multiselect("Criticality",sorted(eq.criticality.unique()),default=sorted(eq.criticality.unique()))
    view=eq[eq.machine_family.isin(fam)&eq.section.isin(sec)&eq.criticality.isin(crit)]
    st.dataframe(view,use_container_width=True,hide_index=True)
    st.caption("Machine IDs are sequential: 1000–1099. Machine family and functional section are separate attributes.")

elif page=="Machine Reliability":
    st.subheader("Reliability reports – machine, section and plant")
    scope=st.radio("Reporting level",["Machine","Section","Plant"],horizontal=True)
    if scope=="Machine":
        st.dataframe(df("Machine_Reliability"),use_container_width=True,hide_index=True)
    elif scope=="Section":
        st.dataframe(df("Section_Reliability"),use_container_width=True,hide_index=True)
    else:
        st.dataframe(df("Plant_Reliability"),use_container_width=True,hide_index=True)
    st.info("MTBF = estimated operating hours less downtime, divided by breakdown count. MTTR = recorded repair hours divided by breakdown count. Operating-time assumption: 16 h/day. Indicative synthetic KPIs, not audited production data.")

elif page=="OEM Task Analysis":
    st.subheader("Supplier maintenance standards vs plant practice")
    st.write("Non-standard tasks are not automatically undesirable; they may encode plant-specific learning. Validate each variance with reliability engineering and the relevant OEM.")
    v=df("OEM_Task_Variance")
    a,b=st.columns(2)
    classification=a.multiselect("Variance class",sorted(v.classification.unique()),default=sorted(v.classification.unique()))
    section_filter=b.multiselect("Section",sorted(v.section.unique()),default=sorted(v.section.unique()))
    v=v[v.classification.isin(classification)&v.section.isin(section_filter)]
    st.metric("Flagged machine/task combinations",len(v))
    st.dataframe(v.sort_values("historical_occurrences",ascending=False),use_container_width=True,hide_index=True)
    st.download_button("Download variance analysis CSV",v.to_csv(index=False).encode(), "maia_oem_task_variance.csv","text/csv")
    st.markdown("#### Supplier task library")
    st.dataframe(df("OEM_Task_Library"),use_container_width=True,hide_index=True)

elif page=="Asset Register & Depreciation":
    st.subheader("CFO – fixed asset register and depreciation")
    asset=eq.copy()
    a,b=st.columns(2)
    asset["purchase_cost_inr"]=pd.to_numeric(asset.purchase_cost_inr)
    st.metric("Gross acquisition value",fmt_inr(asset.purchase_cost_inr.sum()))
    st.metric("Net book value (estimated)",fmt_inr(asset.net_book_value_inr.sum()))
    st.metric("Accumulated depreciation",fmt_inr(asset.accumulated_depreciation_inr.sum()))
    st.dataframe(asset[["equipment_id","equipment_name","section","manufacturer","purchase_date","purchase_cost_inr","useful_life_years","annual_depreciation_inr","accumulated_depreciation_inr","net_book_value_inr"]],use_container_width=True,hide_index=True)
    st.caption("Straight-line depreciation over 15 years, zero residual value. Time-apportioned from purchase date using 365.25 days/year. Tax/accounting policy and capitalization dates require finance validation.")

elif page=="Asset Summary":
    st.subheader("Plant asset portfolio")
    a,b=st.columns(2)
    by_year=eq.groupby("purchase_year").purchase_cost_inr.sum()
    by_section=eq.groupby("section").net_book_value_inr.sum()
    a.markdown("#### Acquisition value by year"); a.bar_chart(by_year)
    b.markdown("#### Net book value by section"); b.bar_chart(by_section)
    st.dataframe(eq.groupby("section").agg(machine_count=("equipment_id","count"),gross_value=("purchase_cost_inr","sum"),net_book_value=("net_book_value_inr","sum")).reset_index(),use_container_width=True,hide_index=True)

elif page in ["My Machines & Daily Tasks","Maintenance Schedule"]:
    op_name=operator if role=="Machine Operator" else st.selectbox("Operator",df("Operator_Master").operator_name.tolist())
    op_id=df("Operator_Master").loc[df("Operator_Master").operator_name==op_name,"operator_id"].iloc[0]
    my_eq=eq[eq.operator_id==op_id]
    st.subheader(f"{op_name} – assigned machine view")
    st.dataframe(my_eq[["equipment_id","equipment_name","section","criticality","status"]],use_container_width=True,hide_index=True)
    pm=df("PM_History_5Y")
    if page=="Maintenance Schedule":
        st.markdown("#### Recent maintenance schedule/history")
        st.dataframe(pm[pm.equipment_id.isin(my_eq.equipment_id)].sort_values("performed_date",ascending=False).head(100),use_container_width=True,hide_index=True)
    else:
        st.markdown("#### Daily operator checks (demo template)")
        daily=pd.DataFrame([{"equipment_id":r.equipment_id,"check":"Clean machine / remove chips","frequency":"Daily","status":"To confirm"} for _,r in my_eq.iterrows()])
        st.dataframe(daily,use_container_width=True,hide_index=True)
        st.markdown("#### Major downtime history")
        st.dataframe(filtered_breakdowns().merge(my_eq[["equipment_id"]],on="equipment_id").sort_values("reported_at",ascending=False).head(50),use_container_width=True,hide_index=True)

elif page=="Maintenance Tasks":
    st.subheader("Maintenance task register")
    open_tasks=tasks[tasks.status!="Completed"]
    st.metric("Open tasks",len(open_tasks))
    st.dataframe(tasks.sort_values("created_date",ascending=False),use_container_width=True,hide_index=True)
    st.markdown("#### Create a new maintenance task")
    with st.form("newtask"):
        x,y,z=st.columns(3)
        machine=x.selectbox("Machine ID",eq.equipment_id.tolist())
        title=y.text_input("Task title")
        typ=z.selectbox("Task type",["Corrective","Preventive","Inspection","Cleaning"])
        desc=st.text_area("Description")
        pri=x.selectbox("Priority",["Critical","High","Medium","Low"])
        tech=y.selectbox("Technician",df("Technician_Master").technician_name.tolist())
        due=z.date_input("Due date",date.today()+timedelta(days=1))
        if st.form_submit_button("Create task"):
            new={"task_id":f"MT-NEW-{len(tasks)+1:04d}","equipment_id":machine,"section":eq.loc[eq.equipment_id==machine,"section"].iloc[0],"task_title":title,
                 "description":desc,"task_type":typ,"priority":pri,"assigned_technician_id":df("Technician_Master").loc[df("Technician_Master").technician_name==tech,"technician_id"].iloc[0],
                 "contractor_id":"","created_date":date.today().isoformat(),"due_date":due.isoformat(),"completed_date":"","status":"Open","source":"Manual","downtime_hours":0,
                 "labor_hours":0,"standard_status":"To be assessed","is_overdue":False}
            st.session_state["Maintenance_Tasks_5Y"]=pd.concat([tasks,pd.DataFrame([new])],ignore_index=True)
            add_audit("Created","Maintenance Task",new["task_id"],title)
            st.success("Task created in this demo session. Use Excel export to retain it.")

elif page=="Breakdown Register":
    st.subheader("Breakdown register – 5-year history")
    st.dataframe(bds.sort_values("reported_at",ascending=False),use_container_width=True,hide_index=True)
    st.markdown("#### Report a new breakdown")
    with st.form("newbd"):
        a,b,c=st.columns(3)
        machine=a.selectbox("Machine",eq.equipment_id.tolist())
        category=b.selectbox("Failure category",["Mechanical","Electrical","Hydraulic","Pneumatic","Controls","Lubrication","Coolant","Other"])
        dt=c.number_input("Downtime hours",min_value=0.0,value=1.0,step=.25)
        symptom=st.text_area("Symptoms")
        if st.form_submit_button("Add breakdown"):
            sec=eq.loc[eq.equipment_id==machine,"section"].iloc[0]
            row={"breakdown_id":f"BD-NEW-{len(bds)+1:04d}","equipment_id":machine,"section":sec,"reported_at":datetime.now().isoformat(),
                 "failure_category":category,"failure_mode":"Pending diagnosis","symptoms":symptom,"machine_status":"Stopped","downtime_hours":dt,"repair_hours":0,
                 "root_cause":"Pending","root_cause_status":"Unknown","corrective_action":"","technician_id":"","contractor_id":"","linked_task_id":"","breakdown_status":"Open","season":"Current"}
            st.session_state["Breakdown_History_5Y"]=pd.concat([bds,pd.DataFrame([row])],ignore_index=True)
            add_audit("Reported","Breakdown",row["breakdown_id"],symptom)
            st.success("Breakdown added in this demo session.")

elif page=="Preventive Maintenance":
    st.subheader("Preventive maintenance")
    st.dataframe(df("PM_History_5Y").sort_values("performed_date",ascending=False).head(500),use_container_width=True,hide_index=True)
    st.caption("6,000 synthetic PM history records are supplied; use the operator schedule view for machine-specific work history.")

elif page=="AI Assistant":
    st.subheader("Ask MAIA – Maintenance Intelligence Assistant")
    st.caption("This build uses a deterministic intent router and pandas queries, not a live LLM. Read-only queries are classified before task-creation commands.")
    prompt=st.text_area("Ask a question or request an action",placeholder="Show open maintenance tasks for critical machines.\nWhich section has the highest downtime?\nCreate a task for machine 1000 to inspect spindle vibration.")
    if st.button("Ask MAIA",type="primary") and prompt.strip():
        p=prompt.strip(); low=p.lower()
        # Read/query intent must be tested before create/action intent.
        query_terms=["show","list","find","which","what","how many","analyse","analyze","history","report","compare","summarise","summarize","open tasks","pending tasks","downtime","mttr","mtbf","availability","critical equipment"]
        create_terms=["create","raise","log","generate","schedule","add a task","make a task"]
        machine=next((str(x) for x in eq.equipment_id if re.search(rf"(?<!\\d){x}(?!\\d)",p)),None)
        if any(t in low for t in query_terms):
            if "task" in low or "pending" in low or "open" in low:
                view=tasks.copy()
                view=view[view.status.astype(str).str.lower().isin(["open","pending","assigned","in progress"])]
                if "critical" in low:
                    crit=set(eq.loc[eq.criticality=="High","equipment_id"])
                    view=view[view.equipment_id.isin(crit)]
                if machine: view=view[view.equipment_id.astype(str)==machine]
                st.markdown("#### Existing open maintenance tasks")
                st.dataframe(view.sort_values("priority"),use_container_width=True,hide_index=True)
                st.caption(f"{len(view)} existing open tasks found. No new task was created.")
            elif "breakdown" in low or "history" in low:
                if machine:
                    view=bds[bds.equipment_id.astype(str)==machine]
                    st.dataframe(view.sort_values("reported_at",ascending=False),use_container_width=True,hide_index=True)
                else: st.dataframe(bds.sort_values("reported_at",ascending=False).head(100),use_container_width=True,hide_index=True)
            elif "section" in low or "plant" in low or "availability" in low or "mttr" in low or "mtbf" in low:
                st.dataframe(df("Section_Reliability") if "section" in low else df("Plant_Reliability"),use_container_width=True,hide_index=True)
            elif "downtime" in low:
                st.dataframe(bds.groupby("equipment_id").downtime_hours.sum().sort_values(ascending=False).head(20),use_container_width=True)
            else:
                st.info("Query intent detected. Try asking about open tasks, breakdown history, downtime, availability, MTTR or MTBF.")
        elif any(t in low for t in create_terms):
            st.warning("Action request detected. This demo build supports task creation through the Maintenance Tasks form. No task has been created here.")
            st.info("Open Maintenance Tasks to create and confirm a work order.")
        else:
            st.info("I could not confidently classify the request. Try a read-only query (e.g. 'List open tasks') or an explicit action (e.g. 'Create a task for machine 1000').")
    st.markdown("#### Suggested questions")
    st.code("Show all open maintenance tasks for critical equipment.\nWhich machine has the highest downtime?\nCompare MTTR by section.\nShow breakdown history for machine 1000.")

elif page=="Excel Import / Export":
    st.subheader("Excel import / export")
    uploaded=st.file_uploader("Upload workbook or CSV",type=["xlsx","csv"])
    target=st.selectbox("Import into",["Equipment_Master","Maintenance_Tasks_5Y","Breakdown_History_5Y"])
    if uploaded and st.button("Preview import"):
        incoming=pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
        st.dataframe(incoming.head(30),use_container_width=True)
        st.caption(f"{len(incoming)} rows detected. This prototype preview does not merge imported data automatically.")
    for key in ["Equipment_Master","Maintenance_Tasks_5Y","Breakdown_History_5Y","PM_History_5Y","OEM_Task_Variance"]:
        st.download_button(f"Download {key}",df(key).to_csv(index=False).encode(),f"maia_{key.lower()}.csv","text/csv")

elif page=="Audit Trail":
    st.subheader("Session audit trail")
    audit_df=st.session_state.get("Audit_Trail",pd.DataFrame())
    st.dataframe(audit_df,use_container_width=True,hide_index=True) if not audit_df.empty else st.info("No interactive changes recorded in this session yet.")

st.divider()
st.caption("MAIA prototype · Synthetic illustrative data · Not production-ready or a substitute for OEM procedures, safety controls or approved maintenance decisions.")
