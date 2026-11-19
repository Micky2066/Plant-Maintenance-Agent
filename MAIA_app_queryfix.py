import streamlit as st
import pandas as pd
import re
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from pathlib import Path

APP_DIR = Path(__file__).parent
DATA_FILE = APP_DIR / "MAIA_100_Machine_Plant_Dataset.xlsx"
st.set_page_config(page_title="MAIA | Agentic Maintenance OS", page_icon="🏭", layout="wide")

@st.cache_data
def load_data():
    names = ["Equipment_Master","Operator_Master","Technician_Master","Supplier_Master","Contractor_Master",
             "Section_Master","OEM_Task_Library","PM_History_5Y","OEM_Task_Variance","Breakdown_History_5Y",
             "Maintenance_Tasks_5Y","Machine_Reliability","Section_Reliability","Plant_Reliability","Data_Dictionary",
             "Equipment_Task_List","Manufacturer_Recommendations","Maintenance_Plans","Maintenance_Orders","External_Service_Orders",
             "MRO_Material_Master","MRO_Stock_Balance","MRO_Consumption_History","MRO_Open_Purchase_Orders",
             "MRO_Monthly_Forecast","MRO_Supplier_Performance","MRO_Data_Dictionary"]
    return {n: pd.read_excel(DATA_FILE, sheet_name=n) for n in names}

data = load_data()
# Workforce records are maintained as separate transactional tables in this prototype.
# They start empty; no synthetic time logs or productivity results are fabricated.
data.setdefault("Technician_Shifts", pd.DataFrame(columns=[
    "shift_id","technician_id","shift_date","shift_start","shift_end",
    "scheduled_hours","break_hours","approved_leave_hours","net_available_hours","notes"
]))
data.setdefault("Technician_Leave", pd.DataFrame(columns=[
    "leave_id","technician_id","leave_date","leave_hours","leave_type","approval_status","notes"
]))
data.setdefault("Technician_Time_Log", pd.DataFrame(columns=[
    "time_log_id","technician_id","work_order_id","equipment_id","activity_category",
    "activity_type","start_datetime","end_datetime","duration_hours","remarks",
    "recorded_by","created_at"
]))
data.setdefault("Technician_Activity_Types", pd.DataFrame([
    {"activity_category":"Productive","activity_type":"Repair / corrective maintenance"},
    {"activity_category":"Productive","activity_type":"Preventive maintenance execution"},
    {"activity_category":"Productive","activity_type":"Diagnosis / fault finding"},
    {"activity_category":"Productive","activity_type":"Inspection / condition assessment"},
    {"activity_category":"Productive","activity_type":"Testing / validation"},
    {"activity_category":"Productive","activity_type":"Calibration / adjustment"},
    {"activity_category":"Travel","activity_type":"Travel between work locations"},
    {"activity_category":"Delay","activity_type":"Waiting for material / spare parts"},
    {"activity_category":"Delay","activity_type":"Waiting for machine availability"},
    {"activity_category":"Delay","activity_type":"Waiting for tools / equipment"},
    {"activity_category":"Delay","activity_type":"Waiting for production clearance"},
    {"activity_category":"Delay","activity_type":"Waiting for safety permit / isolation"},
    {"activity_category":"Delay","activity_type":"Other maintenance delay"},
    {"activity_category":"Non-maintenance","activity_type":"Meeting / administration"},
    {"activity_category":"Non-maintenance","activity_type":"Other non-maintenance"}
]))
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

def ensure_workforce_columns():
    """Backfill optional technician attributes without changing existing master fields."""
    tech = df("Technician_Master").copy()
    defaults = {"secondary_skill":"", "grade":"", "default_shift":"General",
                "shift_hours":8.0, "break_hours":0.5, "active_status":"Active"}
    for col, default in defaults.items():
        if col not in tech.columns:
            tech[col] = default
    st.session_state["Technician_Master"] = tech

def workforce_period_bounds(period):
    today = date.today()
    if period == "This week":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    elif period == "This month":
        start = today.replace(day=1)
        end = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    elif period == "Last 30 days":
        start, end = today - timedelta(days=29), today
    else:
        start = end = today
    return start, end

def workforce_kpi(technician_id, start_date, end_date):
    logs = df("Technician_Time_Log").copy()
    shifts = df("Technician_Shifts").copy()
    if not logs.empty:
        logs["log_date"] = pd.to_datetime(logs["start_datetime"], errors="coerce").dt.date
        logs = logs[(logs.technician_id == technician_id) &
                    (logs.log_date >= start_date) & (logs.log_date <= end_date)]
    if not shifts.empty:
        shifts["shift_date_parsed"] = pd.to_datetime(shifts["shift_date"], errors="coerce").dt.date
        shifts = shifts[(shifts.technician_id == technician_id) &
                        (shifts.shift_date_parsed >= start_date) & (shifts.shift_date_parsed <= end_date)]
    productive = float(logs.loc[logs.activity_category == "Productive", "duration_hours"].sum()) if not logs.empty else 0.0
    travel = float(logs.loc[logs.activity_category == "Travel", "duration_hours"].sum()) if not logs.empty else 0.0
    delay = float(logs.loc[logs.activity_category == "Delay", "duration_hours"].sum()) if not logs.empty else 0.0
    nonmaintenance = float(logs.loc[logs.activity_category == "Non-maintenance", "duration_hours"].sum()) if not logs.empty else 0.0
    available = float(shifts.net_available_hours.sum()) if not shifts.empty else 0.0
    wrench = (100 * productive / available) if available > 0 else None
    return {"available":available,"productive":productive,"travel":travel,"delay":delay,
            "nonmaintenance":nonmaintenance,"wrench":wrench,"logs":logs,"shifts":shifts}

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

st.markdown("""<style>
.block-container{padding-top:1.1rem}.small{color:#64748b;font-size:.85rem}
[data-testid="stSidebar"]{background:#101d32}
[data-testid="stSidebar"] *{color:#eef4ff!important}
.maia-brand{display:flex;align-items:center;gap:13px;padding:12px 4px 18px 4px;border-bottom:1px solid #dbe4ef;margin-bottom:14px}
.maia-mark{width:48px;height:48px;border-radius:14px;background:linear-gradient(145deg,#0e7490,#2563eb);display:flex;align-items:center;justify-content:center;color:white;font-size:25px;font-weight:800;box-shadow:0 5px 18px #0e749055}
.maia-name{font-size:25px;font-weight:800;letter-spacing:2px;color:#10233f;line-height:1.0}
.maia-sub{font-size:10px;letter-spacing:1.4px;color:#64748b;margin-top:5px}
.hero{background:linear-gradient(110deg,#10233f,#164e63);padding:18px 22px;border-radius:16px;color:white;margin-bottom:16px}
.hero h2{color:white;margin:0;font-size:25px}.hero p{color:#d8e9f5;margin:5px 0 0 0}
div[data-testid="stMetric"]{background:#f7fafc;border:1px solid #e2e8f0;padding:12px 14px;border-radius:12px}
</style>""",unsafe_allow_html=True)
with st.sidebar:
    st.markdown("""<div class="maia-brand"><div class="maia-mark">M</div><div><div class="maia-name">MAIA</div><div class="maia-sub">AGENTIC MAINTENANCE OS</div></div></div>""",unsafe_allow_html=True)
    st.caption("Manufacturing Asset Intelligence Assistant")
    role=st.selectbox("Persona",["Section In-charge","Machine Operator","Plant Manager","CFO","Maintenance Manager","OEM / Manufacturer"])
    st.session_state["actor"]=role
    if role=="Section In-charge":
        section=st.selectbox("My section",["CNC","VMC","SPM","Utilities","Assembly"])
        pages=["Section Availability","Machine Reliability","Maintenance Tasks","Breakdown Register","AI Assistant"]
    elif role=="Machine Operator":
        operator=st.selectbox("Operator",df("Operator_Master").operator_name.tolist())
        pages=["My Machines & Daily Tasks","Maintenance Schedule","Breakdown Register","AI Assistant"]
    elif role=="CFO":
        pages=["Asset Register & Depreciation","Asset Summary","MRO Inventory Intelligence","AI Assistant"]
    elif role=="Plant Manager":
        pages=["Plant Dashboard","Section Availability","Machine Reliability","OEM Task Analysis","Asset Summary","MRO Inventory Intelligence","AI Assistant"]
    elif role=="OEM / Manufacturer":
        pages=["Equipment Master","OEM Task Analysis","AI Assistant"]
    else:
        pages=["Plant Dashboard","Equipment Master","Maintenance Tasks","Breakdown Register","Preventive Maintenance","Machine Reliability","OEM Task Analysis","Asset Register & Depreciation","MRO Inventory Intelligence","Technicians & Workforce","AI Assistant","Excel Import / Export","Audit Trail"]
    page=st.radio("Navigation",pages)
    st.divider()
    st.caption("DEMO DATA · SYNTHETIC")
    st.caption("100 machines · 5 sections · 5-year history")
    st.caption("Session changes reset on app restart; use external durable storage for production.")

st.markdown("""<div class="hero"><h2>MAIA | Agentic Maintenance Operating System</h2><p>From equipment reliability to intelligent spare-parts procurement — one connected operating view</p></div>""",unsafe_allow_html=True)
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
    st.markdown("#### Plant analytics")
    c1,c2=st.columns(2)
    by_section=b.groupby("section").downtime_hours.sum().reset_index()
    if not by_section.empty:
        c1.plotly_chart(px.pie(by_section,names="section",values="downtime_hours",hole=.48,title="Downtime mix by section"),use_container_width=True)
    crit_mix=eqs.groupby("criticality").size().reset_index(name="machines")
    c2.plotly_chart(px.pie(crit_mix,names="criticality",values="machines",hole=.48,title="Asset criticality mix"),use_container_width=True)
    left,right=st.columns(2)
    trend=b.copy()
    if not trend.empty:
        trend["month"]=pd.to_datetime(trend["reported_at"],errors="coerce").dt.to_period("M").astype(str)
        monthly=trend.groupby("month").agg(breakdowns=("breakdown_id","count"),downtime_hours=("downtime_hours","sum")).reset_index()
        left.plotly_chart(px.line(monthly,x="month",y="downtime_hours",markers=True,title="Monthly downtime trend"),use_container_width=True)
        right.plotly_chart(px.bar(monthly,x="month",y="breakdowns",title="Monthly breakdown trend"),use_container_width=True)
    st.markdown("#### Downtime by machine – top 15")
    chart=b.groupby("equipment_id").downtime_hours.sum().sort_values(ascending=False).head(15)
    st.bar_chart(chart)
    st.markdown("#### Section comparison")
    st.dataframe(df("Section_Reliability"),use_container_width=True,hide_index=True)

elif page=="Equipment Master":
    st.subheader("Equipment → Maintenance Plan → Maintenance Order → Task List")
    a,b,c=st.columns(3)
    fam=a.multiselect("Machine family",sorted(eq.machine_family.unique()),default=sorted(eq.machine_family.unique()))
    sec=b.multiselect("Functional section",sorted(eq.section.unique()),default=sorted(eq.section.unique()))
    crit=c.multiselect("Criticality",sorted(eq.criticality.unique()),default=sorted(eq.criticality.unique()))
    view=eq[eq.machine_family.isin(fam)&eq.section.isin(sec)&eq.criticality.isin(crit)]
    st.dataframe(view,use_container_width=True,hide_index=True)
    if not view.empty:
        chosen=st.selectbox("1. Select equipment / asset",view.equipment_id.tolist(),
            format_func=lambda x:f"{x} – {eq.loc[eq.equipment_id==x,'equipment_name'].iloc[0]}")
        asset=eq[eq.equipment_id==chosen].iloc[0]
        st.markdown(f"### {asset.equipment_name} · {asset.manufacturer} {asset.model}")
        st.caption(f"Section: {asset.section} | Family: {asset.machine_family} | Criticality: {asset.criticality} | Supplier ID: {asset.supplier_id}")
        tasklist=df("Equipment_Task_List").copy()
        recs=df("Manufacturer_Recommendations").copy()
        plans=df("Maintenance_Plans").copy()
        orders=df("Maintenance_Orders").copy()
        ext_orders=df("External_Service_Orders").copy()
        asset_tasks=tasklist[tasklist.equipment_id.astype(str)==str(chosen)].copy()
        asset_recs=recs[recs.equipment_id.astype(str)==str(chosen)].copy()
        # Build a unified view while preserving provenance.
        if not asset_recs.empty:
            asset_recs=asset_recs.copy()
            asset_recs["source_flag"]="MANUFACTURER_RECOMMENDATION"
            asset_recs["task_category"]="Manufacturer recommendation"
            asset_recs["review_status"]=asset_recs["review_status"].fillna("")
            asset_tasks=pd.concat([asset_tasks,asset_recs],ignore_index=True,sort=False)
        if "execution_party" not in asset_tasks.columns:
            asset_tasks["execution_party"]="Client / In-house"
        # Map source cadence to the four plan cycles. Daily and weekly activities are grouped
        # in the monthly plan while retaining their actual task-level frequency.
        def plan_cycle(freq):
            f=str(freq).strip().lower()
            if f in ["daily","weekly","monthly"]: return "Monthly"
            if f=="quarterly": return "Quarterly"
            if f in ["half-yearly","half yearly","semi-annual","six monthly","6 monthly"]: return "Six-monthly"
            if f in ["annual","annually","yearly"]: return "Annual"
            return "Unscheduled – review cadence"
        asset_tasks["plan_cycle"]=asset_tasks["recommended_frequency"].apply(plan_cycle)
        st.markdown("#### 2. Maintenance plans")
        st.caption("A plan groups approved tasks by execution cycle. Task-level frequency remains visible; daily and weekly checks are included in the monthly plan bundle as recurring activities.")
        valid_status=asset_tasks.get("review_status",pd.Series("",index=asset_tasks.index)).fillna("").astype(str)
        eligible=asset_tasks[
            (asset_tasks["source_flag"]=="STANDARD_OEM") |
            (asset_tasks["review_status"].astype(str).isin(["Approve for PM plan","Approve and activate","Active - OEM Standard"]))
        ].copy()
        eligible["plan_cycle"]=eligible["recommended_frequency"].apply(plan_cycle)
        plan_defs=["Monthly","Quarterly","Six-monthly","Annual"]
        pcols=st.columns(4)
        for col,cycle in zip(pcols,plan_defs):
            subset=eligible[eligible.plan_cycle==cycle]
            col.metric(f"{cycle} plan",len(subset))
        with st.expander("Create / refresh maintenance plans for this asset",expanded=False):
            st.write("MAIA will create or refresh one plan per cycle using eligible tasks. History-derived suggestions and OEM recommendations are excluded until approved.")
            if st.button("Generate / refresh plans",key=f"genplans_{chosen}"):
                pnow=st.session_state["Maintenance_Plans"].copy()
                for cycle in plan_defs:
                    sub=eligible[eligible.plan_cycle==cycle]
                    if sub.empty: continue
                    pid=f"MP-{chosen}-{cycle[:3].upper()}"
                    ids=";".join(sub.task_list_id.astype(str).tolist())
                    row={"plan_id":pid,"equipment_id":chosen,"equipment_name":asset.equipment_name,
                         "plan_name":f"{asset.equipment_name} – {cycle} Maintenance Plan",
                         "plan_frequency":cycle,"task_list_ids":ids,"task_count":len(sub),
                         "execution_scope":"Mixed – assign per task","status":"Active",
                         "last_generated":date.today().isoformat(),"next_due_date":"",
                         "created_by":role}
                    if (pnow.plan_id.astype(str)==pid).any():
                        ix=pnow.index[pnow.plan_id.astype(str)==pid][0]
                        for k,v in row.items(): pnow.loc[ix,k]=v
                    else: pnow=pd.concat([pnow,pd.DataFrame([row])],ignore_index=True)
                st.session_state["Maintenance_Plans"]=pnow
                add_audit("Generated","Maintenance Plans",chosen,"Generated/refreshed frequency-based plans")
                st.success("Maintenance plans generated for this asset.")
                st.rerun()
        asset_plans=st.session_state["Maintenance_Plans"]
        asset_plans=asset_plans[asset_plans.equipment_id.astype(str)==str(chosen)]
        if asset_plans.empty:
            st.info("No maintenance plans created yet. Use Generate / refresh plans above.")
        else:
            st.dataframe(asset_plans[["plan_id","plan_name","plan_frequency","task_count","status","last_generated","next_due_date"]],use_container_width=True,hide_index=True)
            selected_plan=st.selectbox("Select maintenance plan",asset_plans.plan_id.tolist(),
                format_func=lambda x:f"{x} – {asset_plans.loc[asset_plans.plan_id==x,'plan_frequency'].iloc[0]}")
            plan=asset_plans[asset_plans.plan_id==selected_plan].iloc[0]
            plan_ids=str(plan.task_list_ids).split(";") if str(plan.task_list_ids).strip() else []
            plan_tasks=asset_tasks[asset_tasks.task_list_id.astype(str).isin(plan_ids)].copy()
            st.markdown(f"#### 3. Plan task list – {plan.plan_frequency}")
            st.dataframe(plan_tasks[["task_list_id","task_name","source_flag","recommended_frequency","review_status","execution_party","task_rationale"]],use_container_width=True,hide_index=True)
            st.markdown("##### Assign execution responsibility")
            if not plan_tasks.empty:
                with st.form(f"assign_party_{selected_plan}"):
                    assignments={}
                    for _,tr in plan_tasks.iterrows():
                        assignments[str(tr.task_list_id)]=st.selectbox(
                            f"{tr.task_name} · {tr.source_flag}",
                            ["Client / In-house","Contractor","Machine Manufacturer / OEM"],
                            index=["Client / In-house","Contractor","Machine Manufacturer / OEM"].index(
                                tr.get("execution_party","Client / In-house") if tr.get("execution_party","Client / In-house") in ["Client / In-house","Contractor","Machine Manufacturer / OEM"] else "Client / In-house"),
                            key=f"party_{selected_plan}_{tr.task_list_id}")
                    if st.form_submit_button("Save task responsibility"):
                        all_tasks=st.session_state["Equipment_Task_List"].copy()
                        if "execution_party" not in all_tasks.columns: all_tasks["execution_party"]="Client / In-house"
                        for tid,party in assignments.items():
                            ix=all_tasks.index[all_tasks.task_list_id.astype(str)==tid]
                            if len(ix): all_tasks.loc[ix[0],"execution_party"]=party
                            else:
                                ri=st.session_state["Manufacturer_Recommendations"].index[st.session_state["Manufacturer_Recommendations"].task_list_id.astype(str)==tid]
                                if len(ri):
                                    if "execution_party" not in st.session_state["Manufacturer_Recommendations"].columns:
                                        st.session_state["Manufacturer_Recommendations"]["execution_party"]="Client / In-house"
                                    st.session_state["Manufacturer_Recommendations"].loc[ri[0],"execution_party"]=party
                        st.session_state["Equipment_Task_List"]=all_tasks
                        add_audit("Updated","Maintenance Plan",selected_plan,"Updated task execution responsibility")
                        st.success("Task responsibility saved for this session.")
                        st.rerun()
            st.markdown("#### 4. Generate maintenance order")
            with st.form(f"create_order_{selected_plan}"):
                scheduled=st.date_input("Scheduled execution date",value=date.today()+timedelta(days=7),key=f"orderdate_{selected_plan}")
                order_note=st.text_input("Order note / shutdown window")
                if st.form_submit_button("Create maintenance order"):
                    existing=st.session_state["Maintenance_Orders"].copy()
                    oid=f"MO-{chosen}-{datetime.now().strftime('%y%m%d%H%M%S')}"
                    parties=[]
                    for _,tr in plan_tasks.iterrows():
                        party=tr.get("execution_party","Client / In-house")
                        parties.append(str(party))
                    scope="Mixed – assign per task" if len(set(parties))>1 else (parties[0] if parties else "Client / In-house")
                    row={"order_id":oid,"plan_id":selected_plan,"equipment_id":chosen,"equipment_name":asset.equipment_name,
                         "plan_frequency":plan.plan_frequency,"scheduled_date":scheduled.isoformat(),
                         "task_list_ids":";".join(plan_tasks.task_list_id.astype(str).tolist()),
                         "task_summary":order_note,"task_count":len(plan_tasks),"execution_scope":scope,
                         "status":"Created","created_by":role,"created_at":datetime.now().isoformat(timespec="seconds")}
                    st.session_state["Maintenance_Orders"]=pd.concat([existing,pd.DataFrame([row])],ignore_index=True)
                    add_audit("Created","Maintenance Order",oid,f"Plan {selected_plan}; {len(plan_tasks)} tasks")
                    st.success(f"Maintenance order {oid} created.")
                    st.rerun()
            st.markdown("#### 5. Maintenance orders and external service orders")
            asset_orders=st.session_state["Maintenance_Orders"]
            asset_orders=asset_orders[asset_orders.equipment_id.astype(str)==str(chosen)]
            if asset_orders.empty:
                st.info("No maintenance orders created for this asset yet.")
            else:
                st.dataframe(asset_orders.sort_values("created_at",ascending=False),use_container_width=True,hide_index=True)
                order_id=st.selectbox("Select maintenance order",asset_orders.order_id.tolist(),key=f"selorder_{chosen}")
                selected_order=asset_orders[asset_orders.order_id==order_id].iloc[0]
                order_task_ids=str(selected_order.task_list_ids).split(";") if str(selected_order.task_list_ids).strip() else []
                order_tasks=asset_tasks[asset_tasks.task_list_id.astype(str).isin(order_task_ids)].copy()
                st.markdown("##### Order task list")
                st.dataframe(order_tasks[["task_list_id","task_name","source_flag","recommended_frequency","execution_party"]],use_container_width=True,hide_index=True)
                external_tasks=order_tasks[order_tasks.execution_party.isin(["Contractor","Machine Manufacturer / OEM"])]
                if st.button("Create order for outside vendor / machine manufacturer",key=f"extbtn_{order_id}"):
                    if external_tasks.empty:
                        st.warning("No tasks are assigned to an outside party. Assign Contractor or Machine Manufacturer / OEM above first.")
                    else:
                        st.session_state[f"show_ext_form_{order_id}"]=True
                if st.session_state.get(f"show_ext_form_{order_id}",False):
                    with st.form(f"external_order_form_{order_id}"):
                        vendor_type=st.selectbox("External party type",["Contractor","Machine Manufacturer / OEM"])
                        vendor_name=st.text_input("Vendor / manufacturer name",value=str(asset.manufacturer) if vendor_type=="Machine Manufacturer / OEM" else "")
                        request_date=st.date_input("Requested service date",value=date.today()+timedelta(days=7))
                        target_date=st.date_input("Target completion date",value=date.today()+timedelta(days=14))
                        scope=st.text_area("Scope of work",value="; ".join(external_tasks.task_name.astype(str).tolist()))
                        commercial=st.text_input("Quotation / contract / PO reference")
                        if st.form_submit_button("Create external service order"):
                            chosen_ext=external_tasks[external_tasks.execution_party==("Contractor" if vendor_type=="Contractor" else "Machine Manufacturer / OEM")]
                            if not vendor_name.strip() or chosen_ext.empty:
                                st.error("Enter the vendor name and ensure at least one order task is assigned to that party.")
                            else:
                                eid=f"ESO-{order_id}-{len(st.session_state['External_Service_Orders'])+1:03d}"
                                erow={"external_order_id":eid,"maintenance_order_id":order_id,"equipment_id":chosen,
                                      "equipment_name":asset.equipment_name,"vendor_type":vendor_type,"vendor_name":vendor_name,
                                      "scope_of_work":scope,"task_list_ids":";".join(chosen_ext.task_list_id.astype(str).tolist()),
                                      "task_count":len(chosen_ext),"requested_date":request_date.isoformat(),
                                      "target_completion_date":target_date.isoformat(),"commercial_reference":commercial,
                                      "approval_status":"Pending approval / PO linkage","status":"Draft – ready for review",
                                      "created_by":role,"created_at":datetime.now().isoformat(timespec="seconds")}
                                st.session_state["External_Service_Orders"]=pd.concat([st.session_state["External_Service_Orders"],pd.DataFrame([erow])],ignore_index=True)
                                add_audit("Created","External Service Order",eid,f"{vendor_type}: {vendor_name}; linked to {order_id}")
                                st.success(f"External service order {eid} created and linked to {order_id}.")
                                st.session_state[f"show_ext_form_{order_id}"]=False
                                st.rerun()
                ext=st.session_state["External_Service_Orders"]
                ext=ext[ext.maintenance_order_id.astype(str)==str(order_id)]
                if not ext.empty:
                    st.markdown("##### Linked external service orders")
                    st.dataframe(ext,use_container_width=True,hide_index=True)
        st.markdown("#### Task list – source collaboration")
        k1,k2,k3=st.columns(3)
        k1.metric("OEM standard tasks",int((asset_tasks.source_flag=="STANDARD_OEM").sum()))
        k2.metric("History-derived tasks",int((asset_tasks.source_flag=="HISTORICAL_INSIGHT").sum()))
        k3.metric("Manufacturer recommendations",int((asset_tasks.source_flag=="MANUFACTURER_RECOMMENDATION").sum()))
        t1,t2,t3=st.tabs(["① OEM standard","② Plant history insights","③ Manufacturer recommendations"])
        with t1:
            st.caption("Standard tasks supplied by the machine supplier/manufacturer. Validate against the actual OEM manual and machine configuration.")
            st.dataframe(asset_tasks[asset_tasks.source_flag=="STANDARD_OEM"],use_container_width=True,hide_index=True)
        with t2:
            st.caption("MAIA-generated candidates based on this asset's breakdown history. These are insights for joint review—not approved PM instructions.")
            historical=asset_tasks[asset_tasks.source_flag=="HISTORICAL_INSIGHT"]
            st.dataframe(historical,use_container_width=True,hide_index=True)
            pending=historical[historical.review_status=="Suggested - Pending Client Validation"]
            if role!="OEM / Manufacturer" and not pending.empty:
                with st.form(f"validate_history_{chosen}"):
                    task_id=st.selectbox("History-derived task to review",pending.task_list_id.tolist())
                    decision=st.selectbox("Client decision",["Approve for PM plan","Reject","Request OEM review"])
                    note=st.text_input("Review note")
                    if st.form_submit_button("Save client review"):
                        ix=st.session_state["Equipment_Task_List"].index[st.session_state["Equipment_Task_List"].task_list_id==task_id][0]
                        st.session_state["Equipment_Task_List"].loc[ix,"review_status"]=decision
                        st.session_state["Equipment_Task_List"].loc[ix,"client_decision"]=note
                        st.session_state["Equipment_Task_List"].loc[ix,"last_reviewed"]=date.today().isoformat()
                        add_audit("Reviewed","Equipment Task",task_id,f"{decision}: {note}")
                        st.success("Review recorded for this session.")
                        st.rerun()
        with t3:
            st.caption("Manufacturer/OEM recommendations based on wider installed-base, service and warranty experience. Client approval is required before activation.")
            st.dataframe(asset_recs,use_container_width=True,hide_index=True)
            with st.expander("Submit a manufacturer recommendation"):
                with st.form(f"manufacturer_recommendation_{chosen}"):
                    rec_task=st.text_input("Recommended task")
                    rec_freq=st.selectbox("Suggested frequency",["Daily","Weekly","Monthly","Quarterly","Half-yearly","Annually","Condition-based","At next service"])
                    rec_reason=st.text_area("Technical rationale / observed pattern")
                    rec_evidence=st.text_input("Evidence (service bulletin, warranty case, fleet observation)")
                    rec_scope=st.text_input("Applicability (model / serial range / machine population)",value=f"{asset.manufacturer} {asset.model}")
                    if st.form_submit_button("Submit recommendation"):
                        if rec_task.strip():
                            new_id=f"TL-{chosen}-MFR-{len(recs)+1:05d}"
                            new={"task_list_id":new_id,"equipment_id":chosen,"equipment_name":asset.equipment_name,
                                 "task_name":rec_task.strip(),"task_category":"Manufacturer recommendation",
                                 "source_flag":"MANUFACTURER_RECOMMENDATION","source_organisation":asset.manufacturer,
                                 "recommended_frequency":rec_freq,"task_rationale":f"{rec_reason.strip()} | Applicability: {rec_scope}",
                                 "evidence_reference":rec_evidence,"historical_occurrences":0,
                                 "review_status":"Submitted - Pending Client Review","submitted_by":role,
                                 "client_decision":"","effective_from":"","last_reviewed":"","execution_party":"Client / In-house"}
                            st.session_state["Manufacturer_Recommendations"]=pd.concat([recs,pd.DataFrame([new])],ignore_index=True)
                            add_audit("Submitted","Manufacturer Recommendation",new_id,rec_task)
                            st.success("Recommendation submitted and flagged for client review.")
                            st.rerun()
                        else: st.error("Enter a recommended task before submitting.")
            pending_rec=asset_recs[asset_recs.review_status=="Submitted - Pending Client Review"]
            if role!="OEM / Manufacturer" and not pending_rec.empty:
                with st.form(f"client_review_oem_{chosen}"):
                    rec_id=st.selectbox("Recommendation to review",pending_rec.task_list_id.tolist())
                    rec_decision=st.selectbox("Client decision",["Approve and activate","Reject","Request clarification"])
                    rec_note=st.text_input("Client review note")
                    if st.form_submit_button("Record recommendation decision"):
                        ix=st.session_state["Manufacturer_Recommendations"].index[st.session_state["Manufacturer_Recommendations"].task_list_id==rec_id][0]
                        st.session_state["Manufacturer_Recommendations"].loc[ix,"review_status"]=rec_decision
                        st.session_state["Manufacturer_Recommendations"].loc[ix,"client_decision"]=rec_note
                        st.session_state["Manufacturer_Recommendations"].loc[ix,"last_reviewed"]=date.today().isoformat()
                        if rec_decision=="Approve and activate":
                            st.session_state["Manufacturer_Recommendations"].loc[ix,"effective_from"]=date.today().isoformat()
                        add_audit("Reviewed","Manufacturer Recommendation",rec_id,f"{rec_decision}: {rec_note}")
                        st.success("Manufacturer recommendation review recorded.")
                        st.rerun()
        st.download_button("Download this asset's complete task list (CSV)",asset_tasks.to_csv(index=False).encode(),
                           f"MAIA_Equipment_{chosen}_Task_List.csv","text/csv")

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


elif page=="Technicians & Workforce":
    ensure_workforce_columns()
    st.subheader("Technicians & Workforce")
    st.caption("Individual technician capacity, manual activity capture and wrench-time measurement. Time records are prototype session data.")
    tabs = st.tabs(["Technician Master","Shifts & Leave","Time & Activity Log","Technician Productivity"])

    with tabs[0]:
        st.markdown("#### Technician master")
        tech = df("Technician_Master").copy()
        with st.form("technician_profile_form"):
            names = tech.technician_name.tolist()
            selected_name = st.selectbox("Technician", names)
            row = tech[tech.technician_name == selected_name].iloc[0]
            c1,c2,c3 = st.columns(3)
            primary = c1.text_input("Primary skill", str(row.get("skill","")))
            secondary = c2.text_input("Secondary skill", str(row.get("secondary_skill","")))
            grade = c3.text_input("Grade", str(row.get("grade","")))
            c4,c5,c6 = st.columns(3)
            shift_name = c4.selectbox("Default shift", ["General","A","B","C"], index=["General","A","B","C"].index(str(row.get("default_shift","General"))) if str(row.get("default_shift","General")) in ["General","A","B","C"] else 0)
            shift_hours = c5.number_input("Scheduled shift hours", min_value=1.0, max_value=16.0, value=float(row.get("shift_hours",8.0)), step=0.5)
            break_hours = c6.number_input("Scheduled break hours", min_value=0.0, max_value=4.0, value=float(row.get("break_hours",0.5)), step=0.25)
            active = st.selectbox("Status", ["Active","Inactive"], index=0 if str(row.get("active_status","Active"))=="Active" else 1)
            save_profile = st.form_submit_button("Save technician profile")
        if save_profile:
            idx = tech.index[tech.technician_name == selected_name][0]
            st.session_state["Technician_Master"].loc[idx, ["skill","secondary_skill","grade","default_shift","shift_hours","break_hours","active_status"]] = [primary,secondary,grade,shift_name,shift_hours,break_hours,active]
            add_audit("Updated","Technician",row.technician_id,f"Profile updated; primary skill {primary}")
            st.success("Technician profile updated.")
        st.dataframe(df("Technician_Master"), use_container_width=True, hide_index=True)

    with tabs[1]:
        st.markdown("#### Shift calendar")
        tech = df("Technician_Master")
        active_tech = tech[tech.active_status == "Active"]
        with st.form("shift_entry_form"):
            tname = st.selectbox("Technician", active_tech.technician_name.tolist(), key="shift_tech")
            trow = active_tech[active_tech.technician_name == tname].iloc[0]
            sdate = st.date_input("Shift date", value=date.today(), key="shift_date")
            c1,c2,c3 = st.columns(3)
            shours = c1.number_input("Scheduled shift hours",1.0,16.0,float(trow.shift_hours),0.5,key="shift_hours")
            breaks = c2.number_input("Break / meal hours",0.0,4.0,float(trow.break_hours),0.25,key="shift_breaks")
            leave_hours = c3.number_input("Approved leave hours on this date",0.0,float(shours),0.0,0.5,key="shift_leave")
            shift_start = st.time_input("Shift start", value=datetime.strptime("08:00","%H:%M").time())
            shift_notes = st.text_input("Notes (optional)")
            save_shift = st.form_submit_button("Save / update shift")
        if save_shift:
            if breaks + leave_hours > shours:
                st.error("Break hours plus approved leave cannot exceed scheduled shift hours.")
            else:
                tid = trow.technician_id
                sid = f"SH-{tid}-{sdate.isoformat()}"
                record = {"shift_id":sid,"technician_id":tid,"shift_date":sdate.isoformat(),
                          "shift_start":shift_start.strftime("%H:%M"),
                          "shift_end":(datetime.combine(sdate,shift_start)+timedelta(hours=shours)).strftime("%H:%M"),
                          "scheduled_hours":shours,"break_hours":breaks,"approved_leave_hours":leave_hours,
                          "net_available_hours":shours-breaks-leave_hours,"notes":shift_notes}
                shifts = df("Technician_Shifts").copy()
                if sid in shifts.shift_id.astype(str).tolist():
                    shifts = shifts[shifts.shift_id.astype(str) != sid]
                st.session_state["Technician_Shifts"] = pd.concat([shifts,pd.DataFrame([record])],ignore_index=True)
                add_audit("Saved","Technician Shift",sid,f"Net available hours: {record['net_available_hours']}")
                st.success(f"Shift saved. Net available hours: {record['net_available_hours']:.2f}")
        st.markdown("#### Leave requests and approvals")
        with st.form("leave_form"):
            ltech = st.selectbox("Technician for leave", active_tech.technician_name.tolist(), key="leave_tech")
            ldate = st.date_input("Leave date", value=date.today(), key="leave_date")
            lhours = st.number_input("Leave hours",0.5,16.0,8.0,0.5)
            ltype = st.selectbox("Leave type",["Annual","Sick","Personal","Other"])
            lstatus = st.selectbox("Approval status",["Pending","Approved","Rejected"])
            lnotes = st.text_input("Leave notes")
            save_leave = st.form_submit_button("Save leave record")
        if save_leave:
            lrow=active_tech[active_tech.technician_name==ltech].iloc[0]
            lid=f"LV-{lrow.technician_id}-{ldate.isoformat()}-{len(df('Technician_Leave'))+1:03d}"
            rec={"leave_id":lid,"technician_id":lrow.technician_id,"leave_date":ldate.isoformat(),
                 "leave_hours":lhours,"leave_type":ltype,"approval_status":lstatus,"notes":lnotes}
            st.session_state["Technician_Leave"]=pd.concat([df("Technician_Leave"),pd.DataFrame([rec])],ignore_index=True)
            # Approved leave is reflected in an existing shift record for that technician/date.
            if lstatus=="Approved":
                sh=df("Technician_Shifts").copy()
                mask=(sh.technician_id==lrow.technician_id)&(pd.to_datetime(sh.shift_date).dt.date==ldate)
                if mask.any():
                    i=sh[mask].index[-1]
                    sh.loc[i,"approved_leave_hours"]=min(float(sh.loc[i,"scheduled_hours"])-float(sh.loc[i,"break_hours"]),float(sh.loc[i,"approved_leave_hours"])+lhours)
                    sh.loc[i,"net_available_hours"]=float(sh.loc[i,"scheduled_hours"])-float(sh.loc[i,"break_hours"])-float(sh.loc[i,"approved_leave_hours"])
                    st.session_state["Technician_Shifts"]=sh
            add_audit("Created","Technician Leave",lid,f"{lstatus}; {lhours} hours")
            st.success("Leave record saved.")
        st.dataframe(df("Technician_Shifts"),use_container_width=True,hide_index=True)
        st.dataframe(df("Technician_Leave"),use_container_width=True,hide_index=True)

    with tabs[2]:
        st.markdown("#### Manual activity-level time capture")
        tech = df("Technician_Master")
        active_tech = tech[tech.active_status == "Active"]
        wo = df("Maintenance_Orders")
        wo_options = ["No work order / approved exception"] + (wo.order_id.astype(str).tolist() if not wo.empty else [])
        equipment_options = [""] + df("Equipment_Master").equipment_id.astype(str).tolist()
        activity_types = df("Technician_Activity_Types")
        with st.form("time_log_form"):
            tname = st.selectbox("Technician",active_tech.technician_name.tolist(),key="log_tech")
            trow=active_tech[active_tech.technician_name==tname].iloc[0]
            work_order = st.selectbox("Maintenance order / work order",wo_options)
            equipment_id = st.selectbox("Equipment ID (optional)",equipment_options)
            category = st.selectbox("Time category",["Productive","Travel","Delay","Non-maintenance"])
            type_options=activity_types[activity_types.activity_category==category].activity_type.tolist()
            activity = st.selectbox("Activity type",type_options)
            c1,c2=st.columns(2)
            start_dt=c1.datetime_input("Start date & time",value=datetime.now().replace(minute=0,second=0,microsecond=0))
            end_dt=c2.datetime_input("End date & time",value=datetime.now().replace(minute=30,second=0,microsecond=0))
            remarks=st.text_input("Remarks")
            save_log=st.form_submit_button("Save time entry")
        if save_log:
            duration=(end_dt-start_dt).total_seconds()/3600
            if duration<=0:
                st.error("End time must be later than start time.")
            else:
                logs=df("Technician_Time_Log").copy()
                overlap=False
                if not logs.empty:
                    logs["s"]=pd.to_datetime(logs.start_datetime)
                    logs["e"]=pd.to_datetime(logs.end_datetime)
                    overlap=((logs.technician_id==trow.technician_id)&(logs.s<end_dt)&(logs.e>start_dt)).any()
                if overlap:
                    st.error("This time overlaps an existing entry for the selected technician.")
                else:
                    logid=f"TL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(logs)+1:03d}"
                    rec={"time_log_id":logid,"technician_id":trow.technician_id,
                         "work_order_id":"" if work_order.startswith("No work") else work_order,
                         "equipment_id":equipment_id,"activity_category":category,"activity_type":activity,
                         "start_datetime":start_dt.isoformat(timespec="minutes"),"end_datetime":end_dt.isoformat(timespec="minutes"),
                         "duration_hours":round(duration,2),"remarks":remarks,"recorded_by":st.session_state.get("actor","Demo user"),
                         "created_at":datetime.now().isoformat(timespec="seconds")}
                    st.session_state["Technician_Time_Log"]=pd.concat([logs.drop(columns=["s","e"],errors="ignore"),pd.DataFrame([rec])],ignore_index=True)
                    add_audit("Created","Technician Time Log",logid,f"{category}: {activity}; {duration:.2f} hours")
                    st.success(f"Time entry saved: {duration:.2f} hours.")
        logs=df("Technician_Time_Log")
        if not logs.empty:
            st.dataframe(logs.sort_values("start_datetime",ascending=False),use_container_width=True,hide_index=True)
            selected_log=st.selectbox("Select a time entry to delete (demo correction)",logs.time_log_id.tolist())
            if st.button("Delete selected time entry"):
                st.session_state["Technician_Time_Log"]=logs[logs.time_log_id!=selected_log].copy()
                add_audit("Deleted","Technician Time Log",selected_log,"Demo correction")
                st.rerun()
        else:
            st.info("No time entries recorded yet. MAIA will not generate a productivity score until shift and activity data exist.")

    with tabs[3]:
        st.markdown("#### Individual technician productivity")
        tech=df("Technician_Master")
        tname=st.selectbox("Technician",tech.technician_name.tolist(),key="kpi_tech")
        trow=tech[tech.technician_name==tname].iloc[0]
        period=st.selectbox("Measurement period",["Today","This week","This month","Last 30 days"],index=1)
        start_date,end_date=workforce_period_bounds(period)
        k=workforce_kpi(trow.technician_id,start_date,end_date)
        st.caption(f"{start_date:%d %b %Y} – {end_date:%d %b %Y} · Individual technician view")
        c=st.columns(5)
        c[0].metric("Wrench time",f"{k['wrench']:.1f}%" if k["wrench"] is not None else "—")
        c[1].metric("Net available",f"{k['available']:.1f} h")
        c[2].metric("Productive",f"{k['productive']:.1f} h")
        c[3].metric("Travel",f"{k['travel']:.1f} h")
        c[4].metric("Delay",f"{k['delay']:.1f} h")
        if k["available"]<=0:
            st.info("No shift calendar hours are available for this period. Add shift records before interpreting wrench time.")
        else:
            st.progress(min(1.0,max(0.0,k["wrench"]/100 if k["wrench"] is not None else 0)))
        if not k["logs"].empty:
            delay=k["logs"][k["logs"].activity_category=="Delay"].groupby("activity_type").duration_hours.sum().reset_index()
            if not delay.empty:
                st.plotly_chart(px.bar(delay,x="activity_type",y="duration_hours",title="Delay hours by cause"),use_container_width=True)
            trend=k["logs"].copy()
            trend["date"]=pd.to_datetime(trend.start_datetime).dt.date.astype(str)
            daily=trend[trend.activity_category=="Productive"].groupby("date").duration_hours.sum().reset_index()
            if not daily.empty:
                st.plotly_chart(px.bar(daily,x="date",y="duration_hours",title="Daily productive maintenance hours"),use_container_width=True)
            st.markdown("#### Time log detail")
            st.dataframe(k["logs"].drop(columns=["log_date"],errors="ignore"),use_container_width=True,hide_index=True)
        else:
            st.info("No activity records for this technician and period. Capture time against maintenance activities to build the baseline.")
        st.caption("Wrench time = productive maintenance hours ÷ net available shift hours. Productive includes repair, PM, diagnosis, inspection, testing and calibration. Travel is reported separately. Breaks and approved leave reduce available hours. Unallocated time is not assumed productive.")

elif page=="MRO Inventory Intelligence":
    st.subheader("MRO Inventory Intelligence")
    st.caption("Synthetic MRO material master, demand forecasting and approval-based monthly purchasing plan. All values are illustrative; no supplier or ERP transactions are transmitted.")
    mm=df("MRO_Material_Master").copy()
    stock=df("MRO_Stock_Balance").copy()
    hist=df("MRO_Consumption_History").copy()
    openpo=df("MRO_Open_Purchase_Orders").copy()
    base_fc=df("MRO_Monthly_Forecast").copy()
    perf=df("MRO_Supplier_Performance").copy()
    if "mro_pr" not in st.session_state:
        st.session_state.mro_pr=pd.DataFrame(columns=["pr_id","created_at","forecast_month","item_id","item_description","quantity","estimated_value_inr","supplier_id","supplier_name","lead_time_days","approval_status","reason"])
    if "mro_po" not in st.session_state:
        st.session_state.mro_po=pd.DataFrame(columns=["po_id","pr_id","item_id","item_description","quantity","value_inr","supplier_name","status","promised_date"])

    # Derive stock policy and simulate monthly replenishment for the 12-month horizon.
    zmap={"A":2.33,"B":1.88,"C":1.48}
    forecast_rows=[]
    item_policy=[]
    forecast_months=sorted(base_fc.forecast_month.unique().tolist())
    for r in mm.itertuples():
        h=hist[hist.item_id==r.item_id].copy()
        hmap=dict(zip(h.transaction_month.astype(str),h.issue_quantity.astype(float)))
        hist_months=sorted(hmap)
        y=np.array([hmap.get(m,0.0) for m in hist_months],dtype=float)
        avg=float(np.mean(y[-6:])) if len(y) else 0.0
        std=float(np.std(y[-12:],ddof=1)) if len(y)>1 else 0.0
        lead_months=max(1,int(np.ceil(float(r.average_lead_time_days)/30)))
        safety=int(np.ceil(zmap.get(str(r.criticality_class),1.48)*std*np.sqrt(lead_months)))
        # Use forecast series from workbook, generated using item-specific demand method.
        fitem=base_fc[base_fc.item_id==r.item_id].sort_values("forecast_month")
        mean_fc=float(fitem.forecast_demand_qty.mean()) if len(fitem) else avg
        rop=int(np.ceil(mean_fc*lead_months+safety))
        max_stock=int(np.ceil(rop+max(mean_fc,1)))
        sr=stock[stock.item_id==r.item_id].iloc[0]
        onhand=int(sr.opening_on_hand_qty); reserved=int(sr.reserved_qty)
        open_lines=openpo[openpo.item_id==r.item_id]
        receipts={}
        for po in open_lines.itertuples():
            pm=str(pd.Period(pd.to_datetime(po.promised_delivery_date),freq="M"))
            receipts[pm]=receipts.get(pm,0)+int(po.open_qty)
        scheduled={}
        inventory=onhand-reserved
        for m in forecast_months:
            inventory += receipts.get(m,0)+scheduled.get(m,0)
            demand=float(fitem.loc[fitem.forecast_month==m,"forecast_demand_qty"].sum())
            inventory=max(-9999,inventory-demand)
            qty=0
            # Reorder against inventory position, including outstanding receipts, to avoid duplicate buys.
            inbound_pipeline=sum(v for month_key,v in receipts.items() if month_key>m)+sum(v for month_key,v in scheduled.items() if month_key>=m)
            inventory_position=inventory+inbound_pipeline
            if inventory_position < rop:
                qty=max(0,int(np.ceil(max_stock-inventory_position)))
                moq=int(r.minimum_order_quantity); multiple=int(r.order_multiple)
                qty=max(moq,int(np.ceil(qty/max(1,multiple))*max(1,multiple))) if qty>0 else 0
                receipt_period=pd.Period(m,freq="M")+lead_months
                if str(receipt_period) in forecast_months:
                    scheduled[str(receipt_period)]=scheduled.get(str(receipt_period),0)+qty
            value=qty*int(r.unit_cost_inr)
            forecast_rows.append({"forecast_month":m,"item_id":r.item_id,"item_description":r.item_description,"category":r.category,
                "criticality_class":r.criticality_class,"forecast_demand_qty":round(demand,2),"projected_closing_stock":round(inventory,2),
                "recommended_purchase_qty":qty,"estimated_purchase_value_inr":value,"supplier_name":r.preferred_supplier_name,
                "lead_time_days":int(r.average_lead_time_days),"forecast_method":str(fitem.forecast_method.iloc[0]) if len(fitem) else "Not available",
                "purchase_action":"Purchase recommended" if qty>0 else "No purchase planned"})
        item_policy.append({"item_id":r.item_id,"item_description":r.item_description,"category":r.category,"criticality_class":r.criticality_class,
            "on_hand_qty":onhand,"reserved_qty":reserved,"open_po_qty":int(open_lines.open_qty.sum()),"inventory_position":onhand-reserved+int(open_lines.open_qty.sum()),
            "average_monthly_demand":round(avg,2),"safety_stock_qty":safety,"reorder_point_qty":rop,"maximum_stock_qty":max_stock,
            "average_lead_time_days":int(r.average_lead_time_days),"unit_cost_inr":int(r.unit_cost_inr),"preferred_supplier_name":r.preferred_supplier_name})
    fc=pd.DataFrame(forecast_rows)
    policy=pd.DataFrame(item_policy)
    # Filters and summary
    c1,c2,c3,c4=st.columns(4)
    c1.metric("MRO spare SKUs",f"{len(mm):,}")
    c2.metric("Central store value",fmt_inr((stock.merge(mm,on="item_id").eval("opening_on_hand_qty * unit_cost_inr")).sum()))
    c3.metric("Historical issue lines",f"{len(hist):,}")
    c4.metric("Forecast horizon",f"{len(forecast_months)} months")
    tab1,tab2,tab3,tab4=st.tabs(["Material Master","Monthly Purchasing Forecast","Inventory & Stock Policy","Approvals & PO Tracking"])
    with tab1:
        st.markdown("#### MRO Material Master")
        a,b,c=st.columns(3)
        cats=["All"]+sorted(mm.category.dropna().unique().tolist())
        cat_filter=a.selectbox("Category",cats,key="mro_cat_filter")
        crit_filter=b.selectbox("Criticality",["All","A","B","C"],key="mro_crit_filter")
        search=c.text_input("Search item / OEM part",key="mro_search")
        view=mm.copy()
        if cat_filter!="All": view=view[view.category==cat_filter]
        if crit_filter!="All": view=view[view.criticality_class==crit_filter]
        if search.strip():
            mask=view.astype(str).apply(lambda col:col.str.contains(search.strip(),case=False,na=False)).any(axis=1)
            view=view[mask]
        st.dataframe(view[["item_id","item_description","category","base_uom","oem_manufacturer","oem_part_number","equipment_compatibility_ids","primary_section","criticality_class","demand_pattern","unit_cost_inr","average_lead_time_days","p90_lead_time_days","minimum_order_quantity","preferred_supplier_name","repairable_flag","service_level_target"]],use_container_width=True,hide_index=True)
        st.download_button("Download MRO Material Master (CSV)",view.to_csv(index=False).encode("utf-8"),"MAIA_MRO_Material_Master.csv","text/csv")
        st.caption("120 synthetic MRO spare SKUs linked to the existing 100-machine plant. OEM part numbers, compatibility, prices and suppliers are illustrative, not validated OEM data.")
    with tab2:
        st.markdown("#### Rolling 12-month spare-parts purchasing forecast")
        selected_month=st.selectbox("Forecast month",forecast_months,index=0,format_func=lambda x:pd.Period(x,freq="M").strftime("%b %Y"),key="mro_fc_month")
        fview=fc[fc.forecast_month==selected_month].copy()
        a,b,c,d=st.columns(4)
        a.metric("Forecast demand",f"{fview.forecast_demand_qty.sum():,.0f} units")
        b.metric("Items to purchase",f"{int((fview.recommended_purchase_qty>0).sum()):,}")
        c.metric("Recommended purchase",fmt_inr(fview.estimated_purchase_value_inr.sum()))
        d.metric("Critical A items",int(((fview.criticality_class=="A")&(fview.recommended_purchase_qty>0)).sum()))
        monthly=fc.groupby("forecast_month",as_index=False).agg(forecast_demand_qty=("forecast_demand_qty","sum"),recommended_purchase_qty=("recommended_purchase_qty","sum"),estimated_purchase_value_inr=("estimated_purchase_value_inr","sum"))
        monthly["month_label"]=pd.to_datetime(monthly.forecast_month+"-01").dt.strftime("%b %Y")
        left,right=st.columns(2)
        left.plotly_chart(px.bar(monthly,x="month_label",y="forecast_demand_qty",title="Forecast MRO spare demand by month"),use_container_width=True)
        right.plotly_chart(px.bar(monthly,x="month_label",y="estimated_purchase_value_inr",title="Indicative purchasing forecast by month"),use_container_width=True)
        st.dataframe(fview.sort_values(["criticality_class","estimated_purchase_value_inr"],ascending=[True,False]),use_container_width=True,hide_index=True)
        st.download_button("Download 12-month purchasing forecast (CSV)",fc.to_csv(index=False).encode("utf-8"),"MAIA_12_Month_MRO_Purchasing_Forecast.csv","text/csv")
        st.markdown("#### Prepare purchase requisitions")
        eligible=fview[fview.recommended_purchase_qty>0]
        if len(eligible):
            if st.button(f"Prepare approval batch for {len(eligible)} item recommendations",type="primary",key="mro_prepare_batch"):
                existing=set(st.session_state.mro_pr.item_id.astype(str)+"|"+st.session_state.mro_pr.forecast_month.astype(str)) if len(st.session_state.mro_pr) else set()
                new=[]
                for rr in eligible.itertuples():
                    key=str(rr.item_id)+"|"+str(rr.forecast_month)
                    if key in existing: continue
                    mr=mm[mm.item_id==rr.item_id].iloc[0]
                    new.append({"pr_id":f"MRO-PR-{len(st.session_state.mro_pr)+len(new)+1:05d}","created_at":datetime.now().isoformat(timespec="minutes"),"forecast_month":rr.forecast_month,"item_id":rr.item_id,"item_description":rr.item_description,"quantity":int(rr.recommended_purchase_qty),"estimated_value_inr":int(rr.estimated_purchase_value_inr),"supplier_id":mr.preferred_supplier_id,"supplier_name":rr.supplier_name,"lead_time_days":int(rr.lead_time_days),"approval_status":"Pending approval","reason":f"Forecast month {rr.forecast_month}; criticality {rr.criticality_class}; demand {rr.forecast_demand_qty}; recommended quantity {rr.recommended_purchase_qty}."})
                if new:
                    st.session_state.mro_pr=pd.concat([st.session_state.mro_pr,pd.DataFrame(new)],ignore_index=True)
                    add_audit("Prepared","MRO Purchase Requisition Batch",f"{rr.forecast_month}",f"{len(new)} synthetic forecast recommendations routed for approval")
                    st.success(f"{len(new)} requisitions prepared for approval. No purchase orders have been released.")
                else: st.info("Requisitions for this month have already been prepared.")
        else: st.success("No purchasing requirement forecast for this month.")
        st.caption("Forecasts use 24 months of synthetic issue history and illustrative moving-average, trend-adjusted and Croston-style methods. The month-by-month stock simulation is a prototype policy calculation, not a validated stochastic optimisation model.")
    with tab3:
        st.markdown("#### Central plant store – inventory position and replenishment policy")
        a,b=st.columns(2)
        a.metric("Items below reorder point",int((policy.inventory_position<policy.reorder_point_qty).sum()))
        b.metric("Estimated on-hand inventory value",fmt_inr((policy.on_hand_qty*policy.unit_cost_inr).sum()))
        st.dataframe(policy.sort_values(["criticality_class","inventory_position"],ascending=[True,True]),use_container_width=True,hide_index=True)
        st.markdown("#### Supplier performance (synthetic reference data)")
        st.dataframe(perf[["supplier_id","supplier_name","historical_avg_lead_time_days","on_time_delivery_pct","quality_acceptance_pct"]],use_container_width=True,hide_index=True)
    with tab4:
        st.markdown("#### Approval queue")
        prs=st.session_state.mro_pr
        if prs.empty: st.info("No MRO purchase requisitions have been prepared yet. Prepare a batch from the Monthly Purchasing Forecast tab.")
        else:
            st.dataframe(prs,use_container_width=True,hide_index=True)
            pending=prs[prs.approval_status=="Pending approval"]
            if len(pending):
                selected_pr=st.selectbox("Requisition to review",pending.pr_id.tolist(),key="mro_pr_approve_select")
                pr=pending[pending.pr_id==selected_pr].iloc[0]
                st.info(f"{pr.item_id} · {pr.item_description} · {int(pr.quantity)} units · {fmt_inr(pr.estimated_value_inr)} · Supplier: {pr.supplier_name}")
                x1,x2=st.columns(2)
                if x1.button("Approve requisition",type="primary",key="mro_approve"):
                    ix=st.session_state.mro_pr.index[st.session_state.mro_pr.pr_id==selected_pr][0]
                    st.session_state.mro_pr.loc[ix,"approval_status"]="Approved"
                    add_audit("Approved","MRO Purchase Requisition",selected_pr,"Approved by demo user")
                    st.success("Approved. You can now create a draft purchase order.")
                if x2.button("Reject requisition",key="mro_reject"):
                    ix=st.session_state.mro_pr.index[st.session_state.mro_pr.pr_id==selected_pr][0]
                    st.session_state.mro_pr.loc[ix,"approval_status"]="Rejected"
                    add_audit("Rejected","MRO Purchase Requisition",selected_pr,"Rejected by demo user")
                    st.warning("Requisition rejected.")
            approved=prs[prs.approval_status=="Approved"]
            if len(approved):
                st.markdown("#### Create purchase order from approved requisition")
                approved_ids=approved.pr_id.tolist()
                selected_approved=st.selectbox("Approved requisition",approved_ids,key="mro_po_select")
                if st.button("Create purchase order (demo draft)",type="primary",key="mro_create_po"):
                    rr=approved[approved.pr_id==selected_approved].iloc[0]
                    po={"po_id":f"MRO-PO-{len(st.session_state.mro_po)+1:05d}","pr_id":selected_approved,"item_id":rr.item_id,"item_description":rr.item_description,"quantity":int(rr.quantity),"value_inr":int(rr.estimated_value_inr),"supplier_name":rr.supplier_name,"status":"Draft – not transmitted","promised_date":(date.today()+timedelta(days=int(rr.lead_time_days))).isoformat()}
                    st.session_state.mro_po=pd.concat([st.session_state.mro_po,pd.DataFrame([po])],ignore_index=True)
                    ix=st.session_state.mro_pr.index[st.session_state.mro_pr.pr_id==selected_approved][0]
                    st.session_state.mro_pr.loc[ix,"approval_status"]="PO draft created"
                    add_audit("Created","MRO Purchase Order Draft",po["po_id"],f"Linked to {selected_approved}; not transmitted")
                    st.success(f"{po['po_id']} created as a draft. No supplier or ERP transmission occurred.")
        st.markdown("#### Purchase order register")
        st.dataframe(st.session_state.mro_po,use_container_width=True,hide_index=True) if len(st.session_state.mro_po) else st.info("No purchase order drafts created yet.")
        st.download_button("Download requisition register",st.session_state.mro_pr.to_csv(index=False).encode("utf-8"),"MAIA_MRO_Requisitions.csv","text/csv")
        st.download_button("Download PO draft register",st.session_state.mro_po.to_csv(index=False).encode("utf-8"),"MAIA_MRO_PO_Drafts.csv","text/csv")

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
            # Master-data questions should be answered directly before falling
            # through to the narrower maintenance-performance query handlers.
            if "technician" in low or "technicians" in low or "maintenance staff" in low:
                tech_master=df("Technician_Master").copy()
                total_count=len(tech_master)
                if "active_status" in tech_master.columns:
                    active_count=int((tech_master["active_status"].astype(str).str.lower()=="active").sum())
                    inactive_count=total_count-active_count
                else:
                    active_count=total_count
                    inactive_count=0
                st.markdown("#### Technician workforce")
                m1,m2,m3=st.columns(3)
                m1.metric("Total technicians",total_count)
                m2.metric("Active technicians",active_count)
                m3.metric("Inactive technicians",inactive_count)
                if "skill" in tech_master.columns:
                    skill_summary=tech_master.groupby("skill",dropna=False).size().reset_index(name="technician_count")
                    st.markdown("**Technicians by primary skill**")
                    st.dataframe(skill_summary,use_container_width=True,hide_index=True)
                st.caption("Counts are taken from the Technician Master currently loaded in MAIA.")
            elif "task" in low or "pending" in low or "open" in low:
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
    for key in ["Equipment_Master","Equipment_Task_List","Manufacturer_Recommendations","Maintenance_Plans","Maintenance_Orders","External_Service_Orders","Maintenance_Tasks_5Y","Breakdown_History_5Y","PM_History_5Y","OEM_Task_Variance","MRO_Material_Master","MRO_Stock_Balance","MRO_Consumption_History","MRO_Open_Purchase_Orders","MRO_Monthly_Forecast","MRO_Supplier_Performance"]:
        st.download_button(f"Download {key}",df(key).to_csv(index=False).encode(),f"maia_{key.lower()}.csv","text/csv")

elif page=="Audit Trail":
    st.subheader("Session audit trail")
    audit_df=st.session_state.get("Audit_Trail",pd.DataFrame())
    st.dataframe(audit_df,use_container_width=True,hide_index=True) if not audit_df.empty else st.info("No interactive changes recorded in this session yet.")

st.divider()
st.caption("MAIA prototype · Synthetic illustrative data · Plans bundle approved tasks by cadence; outside-party service orders are drafts pending commercial approval/PO linkage. Persistent multi-user collaboration and production workflow controls are not yet implemented.")
