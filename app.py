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
             "Equipment_Task_List","Manufacturer_Recommendations","Maintenance_Plans","Maintenance_Orders","External_Service_Orders"]
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
        pages=["Asset Register & Depreciation","Asset Summary","Spare Parts & Procurement Agent","AI Assistant"]
    elif role=="Plant Manager":
        pages=["Plant Dashboard","Section Availability","Machine Reliability","OEM Task Analysis","Asset Summary","Spare Parts & Procurement Agent","AI Assistant"]
    elif role=="OEM / Manufacturer":
        pages=["Equipment Master","OEM Task Analysis","AI Assistant"]
    else:
        pages=["Plant Dashboard","Equipment Master","Maintenance Tasks","Breakdown Register","Preventive Maintenance","Machine Reliability","OEM Task Analysis","Asset Register & Depreciation","Spare Parts & Procurement Agent","AI Assistant","Excel Import / Export","Audit Trail"]
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

elif page=="Spare Parts & Procurement Agent":
    st.subheader("Spare Parts & Procurement Agent")
    st.caption("Demo workflow: forecast demand → estimate reorder timing → select supplier → apply approval policy → issue PO after approval.")
    # Seed deterministic, session-persistent illustrative procurement data
    if "spares_master" not in st.session_state:
        rng=np.random.default_rng(42)
        names=["Spindle bearing set","Hydraulic seal kit","Servo drive module","Coolant pump","Pneumatic valve","Linear guide block","Proximity sensor","Lubrication pump","V-belt set","PLC I/O module","Chuck jaw set","Air filter element","Gearbox oil kit","Encoder assembly","Contactor set","CNC tool holder","Pressure switch","Fan motor","Solenoid valve","Drive coupling"]
        rows=[]
        for i,n in enumerate(names):
            rows.append({"part_id":f"SP-{i+1:03d}","part_name":n,"category":["Mechanical","Electrical","Hydraulic","Pneumatic"][i%4],"unit":"Nos","unit_cost_inr":int(rng.choice([850,1450,3200,5800,12500,28500,62000,95000])),"lead_time_days_avg":int(rng.integers(7,36)),"lead_time_days_p90":int(rng.integers(18,55)),"safety_stock":int(rng.integers(1,4)),"reorder_point":int(rng.integers(2,6)),"preferred_supplier":f"Supplier {(i%10)+1}"})
        st.session_state.spares_master=pd.DataFrame(rows)
        st.session_state.inventory=pd.DataFrame([{"part_id":r.part_id,"on_hand":int(rng.integers(0,8)),"reserved":int(rng.integers(0,2)),"open_po_qty":int(rng.integers(0,3)),"last_12m_consumption":int(rng.integers(3,18))} for r in st.session_state.spares_master.itertuples()])
        st.session_state.procurement_pr=pd.DataFrame(columns=["pr_id","created_at","part_id","part_name","quantity","estimated_value_inr","supplier","estimated_lead_days","recommended_order_by","approval_level","status","reason"])
        st.session_state.procurement_po=pd.DataFrame(columns=["po_id","pr_id","supplier","part_id","quantity","value_inr","status","promised_date"])
    sp=st.session_state.spares_master.copy(); inv=st.session_state.inventory.copy()
    rec=sp.merge(inv,on="part_id")
    rec["available_stock"]=rec.on_hand-rec.reserved+rec.open_po_qty
    rec["avg_monthly_use"]=rec.last_12m_consumption/12
    rec["days_cover"]=np.where(rec.avg_monthly_use>0,rec.available_stock/rec.avg_monthly_use*30,999)
    rec["suggested_qty"]=(rec.reorder_point+rec.safety_stock-rec.available_stock).clip(lower=0).astype(int)
    rec["estimated_value"]=rec.suggested_qty*rec.unit_cost_inr
    rec["order_by_days"]=(rec.days_cover-rec.lead_time_days_p90-7).round().astype(int)
    rec["risk"] = np.where(rec.order_by_days<=0,"Order now",np.where(rec.order_by_days<=14,"Order soon","Healthy"))
    urgent=rec[rec.suggested_qty>0].sort_values("order_by_days")
    m1,m2,m3,m4=st.columns(4)
    m1.metric("Spare part SKUs",len(sp)); m2.metric("Reorder recommendations",len(urgent)); m3.metric("Order-now risks",int((urgent.risk=="Order now").sum())); m4.metric("Indicative replenishment",fmt_inr(urgent.estimated_value.sum()))
    t1,t2,t3=st.tabs(["Demand & inventory","Purchase approvals","PO tracking"])
    with t1:
        st.markdown("#### Agent recommendations")
        st.dataframe(rec[["part_id","part_name","on_hand","reserved","open_po_qty","last_12m_consumption","available_stock","days_cover","lead_time_days_p90","suggested_qty","estimated_value","risk"]].sort_values("order_by_days"),use_container_width=True,hide_index=True)
        a,b=st.columns(2)
        a.plotly_chart(px.pie(rec,names="risk",title="Inventory replenishment risk",hole=.45),use_container_width=True)
        b.plotly_chart(px.bar(urgent.head(12),x="part_name",y="suggested_qty",title="Top recommended replenishment quantities"),use_container_width=True)
        st.markdown("#### Create purchase requisition")
        candidates=urgent[urgent.suggested_qty>0]
        if len(candidates):
            with st.form("create_pr_agent"):
                chosen=st.selectbox("Part",candidates.part_id+" | "+candidates.part_name)
                qty=st.number_input("Quantity",min_value=1,value=int(candidates.iloc[0].suggested_qty),step=1)
                supplier=st.selectbox("Supplier",sorted(sp.preferred_supplier.unique()))
                if st.form_submit_button("Agent: prepare requisition"):
                    pid=chosen.split(" | ")[0]; rr=rec[rec.part_id==pid].iloc[0]; value=int(qty*rr.unit_cost_inr)
                    level="Maintenance In-charge" if value<=10000 else "Plant Manager" if value<=50000 else "Plant Head" if value<=200000 else "CFO / Business Head"
                    pr={"pr_id":f"PR-{len(st.session_state.procurement_pr)+1:04d}","created_at":datetime.now().isoformat(timespec="minutes"),"part_id":pid,"part_name":rr.part_name,"quantity":int(qty),"estimated_value_inr":value,"supplier":supplier,"estimated_lead_days":int(rr.lead_time_days_p90),"recommended_order_by":(date.today()+timedelta(days=max(0,int(rr.order_by_days)))).isoformat(),"approval_level":level,"status":"Pending approval","reason":f"Available stock {rr.available_stock}; estimated cover {rr.days_cover:.0f} days; P90 lead time {rr.lead_time_days_p90} days plus 7-day buffer."}
                    st.session_state.procurement_pr=pd.concat([st.session_state.procurement_pr,pd.DataFrame([pr])],ignore_index=True)
                    add_audit("Prepared","Purchase Requisition",pr["pr_id"],pr["reason"])
                    st.success(f"{pr['pr_id']} prepared and routed to {level}. No PO has been issued.")
        else: st.success("No replenishment action currently recommended by the demo rules.")
        st.caption("Lead-time values and stock/consumption figures are illustrative demo data. Replace with actual stores ledger, PO history, BOM/spares mapping and supplier performance data.")
    with t2:
        prs=st.session_state.procurement_pr
        if prs.empty: st.info("No requisitions yet. Create one from the Demand & inventory tab.")
        else:
            st.dataframe(prs,use_container_width=True,hide_index=True)
            pending=prs[prs.status=="Pending approval"]
            if len(pending):
                selected=st.selectbox("Select requisition to approve",pending.pr_id.tolist())
                if st.button("Approve requisition",type="primary"):
                    ix=st.session_state.procurement_pr.index[st.session_state.procurement_pr.pr_id==selected][0]
                    st.session_state.procurement_pr.loc[ix,"status"]="Approved"
                    add_audit("Approved","Purchase Requisition",selected,"Approved by demo user")
                    st.success("Requisition approved. Create PO in PO tracking tab.")
    with t3:
        approved=st.session_state.procurement_pr[st.session_state.procurement_pr.status=="Approved"]
        if len(approved):
            selected=st.selectbox("Approved requisition",approved.pr_id.tolist())
            if st.button("Create purchase order"):
                rr=approved[approved.pr_id==selected].iloc[0]
                po={"po_id":f"PO-{len(st.session_state.procurement_po)+1:04d}","pr_id":selected,"supplier":rr.supplier,"part_id":rr.part_id,"quantity":rr.quantity,"value_inr":rr.estimated_value_inr,"status":"Issued (demo)","promised_date":(date.today()+timedelta(days=int(rr.estimated_lead_days))).isoformat()}
                st.session_state.procurement_po=pd.concat([st.session_state.procurement_po,pd.DataFrame([po])],ignore_index=True)
                ix=st.session_state.procurement_pr.index[st.session_state.procurement_pr.pr_id==selected][0]
                st.session_state.procurement_pr.loc[ix,"status"]="PO created"
                add_audit("Created","Purchase Order",po["po_id"],f"Linked to {selected}; demo PO only")
                st.success(f"{po['po_id']} created in demo. No external supplier/ERP transmission occurred.")
        else: st.info("Approve a requisition first. The agent cannot bypass approval thresholds.")
        st.dataframe(st.session_state.procurement_po,use_container_width=True,hide_index=True)

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
    for key in ["Equipment_Master","Equipment_Task_List","Manufacturer_Recommendations","Maintenance_Plans","Maintenance_Orders","External_Service_Orders","Maintenance_Tasks_5Y","Breakdown_History_5Y","PM_History_5Y","OEM_Task_Variance"]:
        st.download_button(f"Download {key}",df(key).to_csv(index=False).encode(),f"maia_{key.lower()}.csv","text/csv")

elif page=="Audit Trail":
    st.subheader("Session audit trail")
    audit_df=st.session_state.get("Audit_Trail",pd.DataFrame())
    st.dataframe(audit_df,use_container_width=True,hide_index=True) if not audit_df.empty else st.info("No interactive changes recorded in this session yet.")

st.divider()
st.caption("MAIA prototype · Synthetic illustrative data · Plans bundle approved tasks by cadence; outside-party service orders are drafts pending commercial approval/PO linkage. Persistent multi-user collaboration and production workflow controls are not yet implemented.")
