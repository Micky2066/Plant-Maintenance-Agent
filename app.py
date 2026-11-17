
import streamlit as st
import pandas as pd
import sqlite3, json, re, os
from datetime import datetime, date, timedelta
from pathlib import Path
import tempfile

APP_DIR = Path(__file__).parent
# Hosted demo database: temporary storage. Data may reset when the cloud instance restarts.
DB_PATH = Path(tempfile.gettempdir()) / "maia_demo.db"

st.set_page_config(page_title="MAIA | Maintenance Intelligence", page_icon="🏭", layout="wide")

# ---------- Data layer ----------
def db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS equipment(
      id TEXT PRIMARY KEY, name TEXT, category TEXT, line TEXT, criticality TEXT,
      manufacturer TEXT, model TEXT, status TEXT DEFAULT 'Operational'
    );
    CREATE TABLE IF NOT EXISTS users(
      id TEXT PRIMARY KEY, name TEXT, role TEXT
    );
    CREATE TABLE IF NOT EXISTS tasks(
      id TEXT PRIMARY KEY, equipment_id TEXT, title TEXT, description TEXT, task_type TEXT,
      priority TEXT, assigned_to TEXT, due_date TEXT, status TEXT, created_at TEXT,
      source TEXT, recurring TEXT DEFAULT '', completion_notes TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS breakdowns(
      id TEXT PRIMARY KEY, equipment_id TEXT, reported_at TEXT, category TEXT, symptoms TEXT,
      machine_status TEXT, downtime_hours REAL DEFAULT 0, root_cause TEXT DEFAULT '',
      root_cause_status TEXT DEFAULT 'Unknown', corrective_action TEXT DEFAULT '',
      technician TEXT DEFAULT '', status TEXT DEFAULT 'Open', linked_task TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS audit(
      id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, actor TEXT, action TEXT, object_type TEXT, object_id TEXT, details TEXT
    );
    """)
    if con.execute("SELECT COUNT(*) FROM equipment").fetchone()[0] == 0:
        eq = [
        ("CNC-01","CNC Turning Centre 01","CNC","Line A","High","DMG Mori","NLX 2500","Operational"),
        ("CNC-02","CNC Turning Centre 02","CNC","Line A","High","Mazak","QT-200","Operational"),
        ("CNC-03","CNC Machining Centre 03","CNC","Line B","High","Makino","V56","Operational"),
        ("CNC-04","CNC Machining Centre 04","CNC","Line B","High","Haas","VF-2","Under Maintenance"),
        ("PRS-01","Hydraulic Press 01","Press","Line C","High","Schuler","HP-250","Operational"),
        ("PRS-02","Hydraulic Press 02","Press","Line C","Medium","AIDA","NC1-200","Operational"),
        ("WLD-01","Robotic Welding Cell 01","Welding","Line D","High","FANUC","ArcMate","Operational"),
        ("CMP-01","Air Compressor 01","Utilities","Utility","High","Atlas Copco","GA45","Operational"),
        ("GRD-01","Cylindrical Grinder 01","Grinding","Line B","Medium","Micromatic","GC-300","Operational"),
        ("CON-01","Conveyor 01","Material Handling","Line A","Medium","Custom","CV-01","Operational"),
        ]
        con.executemany("INSERT INTO equipment VALUES(?,?,?,?,?,?,?,?)", eq)
    if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        con.executemany("INSERT INTO users VALUES(?,?,?)", [
            ("U001","Puneet (Plant Head)","Plant Head"),
            ("U002","Anil Sharma","Maintenance Manager"),
            ("U003","Rajesh Kumar","Technician"),
            ("U004","Amit Verma","Technician"),
            ("U005","Sunil Yadav","Technician"),
        ])
    if con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0:
        today = date.today()
        tasks = [
          ("T-1001","CNC-01","Inspect spindle bearing","Check vibration and bearing temperature","Preventive","High","Rajesh Kumar",(today+timedelta(days=1)).isoformat(),"In Progress",datetime.now().isoformat(),"Manual","Monthly",""),
          ("T-1002","PRS-02","Hydraulic oil leakage repair","Inspect hose and seals","Corrective","Critical","Amit Verma",(today-timedelta(days=1)).isoformat(),"Assigned",datetime.now().isoformat(),"Breakdown","",""),
          ("T-1003","CMP-01","Clean intake filter","Clean and inspect compressor filter","Preventive","Medium","Sunil Yadav",(today+timedelta(days=3)).isoformat(),"Pending",datetime.now().isoformat(),"Schedule","Weekly",""),
          ("T-1004","CNC-04","Investigate spindle noise","Check spindle assembly and lubrication","Corrective","High","Rajesh Kumar",(today+timedelta(days=1)).isoformat(),"In Progress",datetime.now().isoformat(),"AI","",""),
          ("T-1005","WLD-01","Inspect torch cable","Check wear and insulation","Preventive","Low","Amit Verma",(today+timedelta(days=5)).isoformat(),"Completed",datetime.now().isoformat(),"Manual","Monthly","Inspection completed"),
        ]
        con.executemany("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", tasks)
    if con.execute("SELECT COUNT(*) FROM breakdowns").fetchone()[0] == 0:
        today = date.today()
        bds = [
          ("BD-2001","CNC-04",(today-timedelta(days=2)).isoformat()+" 09:15","Mechanical","Spindle abnormal noise and overheating","Stopped",3.5,"Spindle bearing wear","Confirmed","Bearing replaced and alignment checked","Rajesh Kumar","Closed","T-1004"),
          ("BD-2002","CNC-04",(today-timedelta(days=12)).isoformat()+" 14:20","Mechanical","Spindle vibration above normal","Stopped",2.0,"Spindle bearing wear","Suspected","Lubrication and inspection","Rajesh Kumar","Closed",""),
          ("BD-2003","PRS-02",(today-timedelta(days=1)).isoformat()+" 11:00","Hydraulic","Oil leakage near cylinder hose","Stopped",1.5,"Hose seal deterioration","Confirmed","Seal replaced; pressure tested","Amit Verma","Open","T-1002"),
          ("BD-2004","CMP-01",(today-timedelta(days=25)).isoformat()+" 08:30","Electrical","Compressor motor tripped","Running",0.0,"Overload relay trip","Confirmed","Relay reset and load checked","Sunil Yadav","Closed",""),
          ("BD-2005","CNC-04",(today-timedelta(days=35)).isoformat()+" 10:00","Mechanical","Spindle temperature high","Stopped",2.5,"Unknown","Unknown","Cooling path cleaned","Rajesh Kumar","Closed",""),
        ]
        con.executemany("INSERT INTO breakdowns VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", bds)
    con.commit()
    con.close()

def q(sql, params=()):
    con=db(); cur=con.execute(sql, params); rows=cur.fetchall(); con.close()
    return [dict(r) for r in rows]

def run(sql, params=()):
    con=db(); con.execute(sql, params); con.commit(); con.close()

def audit(action, typ, oid, details, actor="Anil Sharma"):
    run("INSERT INTO audit(at,actor,action,object_type,object_id,details) VALUES(?,?,?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"),actor,action,typ,oid,details))

def next_id(prefix, table):
    rows=q(f"SELECT id FROM {table}")
    nums=[]
    for r in rows:
        m=re.search(r'(\d+)$', str(r["id"]))
        if m: nums.append(int(m.group(1)))
    return f"{prefix}-{(max(nums) if nums else 1000)+1}"

def ai_parse_task(text):
    """Deterministic local demo parser; no external AI call required."""
    t=text.lower()
    equipment=q("SELECT id,name FROM equipment")
    eqid=""
    for e in equipment:
        if e["id"].lower() in t or e["name"].lower() in t:
            eqid=e["id"]; break
    users=q("SELECT name FROM users WHERE role='Technician'")
    assignee=""
    for u in users:
        if u["name"].split()[0].lower() in t: assignee=u["name"]; break
    priority="Critical" if any(x in t for x in ["critical","production stopped","machine stopped","urgent"]) else ("High" if "high" in t or "abnormal" in t else "Medium")
    task_type="Preventive" if any(x in t for x in ["preventive","monthly","weekly","lubricat","inspect","clean"]) else "Corrective"
    due=(date.today()+timedelta(days=1)).isoformat() if "tomorrow" in t else date.today().isoformat()
    title=text.strip().capitalize()
    title=re.sub(r"^(create|please create|raise|log)\s+(a\s+)?(task|maintenance task)\s+(for\s+)?","",title,flags=re.I)
    return {"equipment_id":eqid,"title":title[:100],"description":text,"task_type":task_type,"priority":priority,"assigned_to":assignee,"due_date":due,"status":"Pending","source":"AI"}

init_db()

# ---------- Styling ----------
st.markdown("""
<style>
.block-container{padding-top:1.2rem;padding-bottom:2rem}
[data-testid="stMetric"]{background:#f4f6f8;padding:14px 16px;border-radius:8px;border:1px solid #e3e7eb}
h1,h2,h3{color:#142b45}
.small-muted{color:#637381;font-size:0.85rem}
div.stButton>button{border-radius:5px}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 🏭 MAIA")
    st.caption("Manufacturing Asset Intelligence Assistant")
    role=st.selectbox("Demo user",["Plant Head","Maintenance Manager","Technician","SaaS Admin"],index=1)
    actor={"Plant Head":"Puneet (Plant Head)","Maintenance Manager":"Anil Sharma","Technician":"Rajesh Kumar","SaaS Admin":"Platform Admin"}[role]
    page=st.radio("Navigation",["Executive Dashboard","Equipment Master","Maintenance Tasks","Breakdown Register","Preventive Maintenance","AI Assistant","Excel Import / Export","Audit Trail"])
    st.divider()
    st.caption("DEMO ENVIRONMENT")
    st.caption("Automotive Components Plant · Plant 01")
    st.caption("Hosted demo · Sample data · Changes may reset when the server restarts")

st.title("MAIA")
st.caption("Maintenance operations, breakdown intelligence and AI-assisted workflows | Automotive MSME demo")

# ---------- Dashboard ----------
if page=="Executive Dashboard":
    eq=q("SELECT * FROM equipment")
    tasks=q("SELECT * FROM tasks")
    bds=q("SELECT * FROM breakdowns")
    today=date.today().isoformat()
    open_tasks=[x for x in tasks if x["status"] not in ["Closed","Completed"]]
    overdue=[x for x in open_tasks if x["due_date"] and x["due_date"]<today]
    downtime=sum(float(x["downtime_hours"] or 0) for x in bds)
    c=st.columns(5)
    c[0].metric("Machines",len(eq))
    c[1].metric("Operational",sum(1 for x in eq if x["status"]=="Operational"))
    c[2].metric("Open tasks",len(open_tasks))
    c[3].metric("Overdue tasks",len(overdue))
    c[4].metric("Recorded downtime",f"{downtime:.1f} h")
    st.subheader("Plant maintenance overview")
    left,right=st.columns([1.2,1])
    with left:
        st.markdown("#### Breakdown frequency by equipment")
        df=pd.DataFrame(bds)
        if not df.empty:
            chart=df.groupby("equipment_id").size().sort_values(ascending=False)
            st.bar_chart(chart)
        else: st.info("No breakdown data yet.")
    with right:
        st.markdown("#### Task status")
        if tasks:
            st.bar_chart(pd.Series([x["status"] for x in tasks]).value_counts())
    st.markdown("#### Management attention")
    alerts=[]
    for e in eq:
        eb=[b for b in bds if b["equipment_id"]==e["id"]]
        if len(eb)>=2: alerts.append({"Equipment":e["id"],"Issue":f"{len(eb)} recorded breakdowns","Suggested attention":"Review repeat failure history"})
    for t in overdue:
        alerts.append({"Equipment":t["equipment_id"],"Issue":f"Overdue: {t['title']}","Suggested attention":f"Follow up with {t['assigned_to']}"})
    if alerts: st.dataframe(pd.DataFrame(alerts),use_container_width=True,hide_index=True)
    else: st.success("No management alerts based on current demo records.")
    st.info("Demo data is illustrative. Replace it with customer-approved plant data during pilot onboarding.")

# ---------- Equipment ----------
elif page=="Equipment Master":
    st.subheader("Equipment master")
    with st.expander("＋ Add equipment",expanded=False):
        with st.form("add_eq"):
            a,b,c=st.columns(3)
            eid=a.text_input("Equipment ID",placeholder="e.g. CNC-05")
            name=b.text_input("Equipment name")
            cat=c.selectbox("Category",["CNC","Press","Welding","Grinding","Utilities","Material Handling","Other"])
            line=a.text_input("Production line","Line A")
            crit=b.selectbox("Criticality",["High","Medium","Low"])
            maker=c.text_input("Manufacturer")
            model=a.text_input("Model")
            status=b.selectbox("Status",["Operational","Under Maintenance","Stopped"])
            if st.form_submit_button("Save equipment"):
                if eid and name:
                    try:
                        run("INSERT INTO equipment VALUES(?,?,?,?,?,?,?,?)",(eid,name,cat,line,crit,maker,model,status))
                        audit("Created","Equipment",eid,name,actor); st.success("Equipment saved."); st.rerun()
                    except Exception as e: st.error(f"Could not save: {e}")
                else: st.error("Equipment ID and name are required.")
    data=q("SELECT * FROM equipment ORDER BY id")
    st.dataframe(pd.DataFrame(data),use_container_width=True,hide_index=True)
    st.caption(f"{len(data)} equipment records in this local demo.")

# ---------- Tasks ----------
elif page=="Maintenance Tasks":
    st.subheader("Maintenance task management")
    with st.expander("＋ Create task – structured form",expanded=True):
        with st.form("task_form"):
            a,b=st.columns(2)
            eqids=[x["id"] for x in q("SELECT * FROM equipment")]
            eqid=a.selectbox("Equipment",eqids)
            title=b.text_input("Task title")
            desc=st.text_area("Description")
            c,d,e=st.columns(3)
            typ=c.selectbox("Type",["Corrective","Preventive","Inspection","Cleaning","Replacement"])
            pri=d.selectbox("Priority",["Critical","High","Medium","Low"])
            owner=e.selectbox("Assigned technician",[x["name"] for x in q("SELECT * FROM users WHERE role='Technician'")])
            due=st.date_input("Due date",date.today()+timedelta(days=1))
            recur=st.selectbox("Recurrence",["None","Daily","Weekly","Monthly","Quarterly"])
            if st.form_submit_button("Create task"):
                if title:
                    tid=next_id("T","tasks")
                    run("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(tid,eqid,title,desc,typ,pri,owner,due.isoformat(),"Pending",datetime.now().isoformat(), "Manual", "" if recur=="None" else recur,""))
                    audit("Created","Task",tid,title,actor); st.success(f"Task {tid} created."); st.rerun()
                else: st.error("Task title is required.")
    tasks=q("SELECT * FROM tasks ORDER BY due_date")
    st.markdown("#### Task register")
    if tasks:
        st.dataframe(pd.DataFrame(tasks),use_container_width=True,hide_index=True)
        st.markdown("#### Update task")
        ids=[x["id"] for x in tasks]
        selected=st.selectbox("Select task",ids)
        task=next(x for x in tasks if x["id"]==selected)
        a,b=st.columns(2)
        new_status=a.selectbox("Status",["Pending","Assigned","Accepted","In Progress","Completed","Closed"],index=["Pending","Assigned","Accepted","In Progress","Completed","Closed"].index(task["status"]))
        note=b.text_input("Completion / work note",task.get("completion_notes",""))
        if st.button("Save task update"):
            run("UPDATE tasks SET status=?,completion_notes=? WHERE id=?",(new_status,note,selected))
            audit("Updated","Task",selected,f"Status={new_status}; note={note}",actor); st.success("Task updated."); st.rerun()
    else: st.info("No tasks.")

# ---------- Breakdowns ----------
elif page=="Breakdown Register":
    st.subheader("Breakdown reporting and history")
    with st.expander("＋ Report breakdown",expanded=True):
        with st.form("bd_form"):
            a,b=st.columns(2)
            eqids=[x["id"] for x in q("SELECT * FROM equipment")]
            eqid=a.selectbox("Equipment",eqids)
            category=b.selectbox("Failure category",["Mechanical","Electrical","Hydraulic","Pneumatic","Control system","Lubrication","Operator-related","Other"])
            symptoms=st.text_area("Symptoms / problem description")
            c,d,e=st.columns(3)
            machine_status=c.selectbox("Machine status",["Stopped","Running with issue","Intermittent"])
            downtime=d.number_input("Downtime (hours)",min_value=0.0,step=0.5)
            technician=e.selectbox("Reported by",[x["name"] for x in q("SELECT * FROM users WHERE role='Technician'")])
            if st.form_submit_button("Report breakdown and create task"):
                bid=next_id("BD","breakdowns")
                tid=next_id("T","tasks")
                run("INSERT INTO breakdowns VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(bid,eqid,datetime.now().isoformat(timespec="minutes"),category,symptoms,machine_status,downtime,"","Unknown","","","Open",tid))
                run("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(tid,eqid,f"Investigate breakdown: {symptoms[:55]}",symptoms,"Corrective","Critical" if machine_status=="Stopped" else "High",technician,(date.today()+timedelta(days=1)).isoformat(),"Assigned",datetime.now().isoformat(),"Breakdown","",""))
                run("UPDATE equipment SET status=? WHERE id=?",("Stopped" if machine_status=="Stopped" else "Operational",eqid))
                audit("Reported","Breakdown",bid,symptoms,actor); audit("Generated","Task",tid,f"Linked breakdown {bid}",actor)
                st.success(f"Breakdown {bid} reported; linked task {tid} created."); st.rerun()
    bds=q("SELECT * FROM breakdowns ORDER BY reported_at DESC")
    st.markdown("#### Breakdown history")
    if bds:
        st.dataframe(pd.DataFrame(bds),use_container_width=True,hide_index=True)
        st.markdown("#### Record repair outcome")
        bid=st.selectbox("Select breakdown to update",[x["id"] for x in bds])
        bd=next(x for x in bds if x["id"]==bid)
        with st.form("bd_update"):
            root=st.text_input("Root cause",bd["root_cause"])
            rootstatus=st.selectbox("Root cause status",["Unknown","Suspected","Confirmed"],index=["Unknown","Suspected","Confirmed"].index(bd["root_cause_status"]))
            action=st.text_area("Corrective action",bd["corrective_action"])
            status=st.selectbox("Breakdown status",["Open","Under Repair","Closed"],index=["Open","Under Repair","Closed"].index(bd["status"]))
            if st.form_submit_button("Save breakdown outcome"):
                run("UPDATE breakdowns SET root_cause=?,root_cause_status=?,corrective_action=?,status=? WHERE id=?",(root,rootstatus,action,status,bid))
                audit("Updated","Breakdown",bid,f"Root cause={root}; status={status}",actor)
                if status=="Closed":
                    run("UPDATE equipment SET status='Operational' WHERE id=?",(bd["equipment_id"],))
                st.success("Breakdown updated."); st.rerun()
    else: st.info("No breakdown records.")

# ---------- PM ----------
elif page=="Preventive Maintenance":
    st.subheader("Preventive maintenance schedules")
    st.write("Create time-based recurring maintenance. The demo generates the next work order when a schedule is saved.")
    with st.form("pm_form"):
        a,b,c=st.columns(3)
        eqid=a.selectbox("Equipment",[x["id"] for x in q("SELECT * FROM equipment")])
        activity=b.text_input("Maintenance activity",placeholder="e.g. Monthly lubrication")
        freq=c.selectbox("Frequency",["Daily","Weekly","Monthly","Quarterly"])
        owner=st.selectbox("Assigned technician",[x["name"] for x in q("SELECT * FROM users WHERE role='Technician'")])
        due=st.date_input("Next due date",date.today()+timedelta(days=7))
        if st.form_submit_button("Generate preventive task"):
            tid=next_id("T","tasks")
            run("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(tid,eqid,activity,activity,"Preventive","Medium",owner,due.isoformat(),"Pending",datetime.now().isoformat(),"Schedule",freq,""))
            audit("Scheduled","Preventive Task",tid,f"{activity}; {freq}",actor)
            st.success(f"Preventive task {tid} generated."); st.rerun()
    pm=[x for x in q("SELECT * FROM tasks ORDER BY due_date") if x["task_type"]=="Preventive"]
    st.markdown("#### Preventive maintenance calendar / task list")
    st.dataframe(pd.DataFrame(pm),use_container_width=True,hide_index=True) if pm else st.info("No preventive tasks.")

# ---------- AI ----------
elif page=="AI Assistant":
    st.subheader("Ask MAIA – Maintenance Intelligence Assistant")
    st.caption("Local demo mode uses a deterministic intent parser and live local database queries. Connect an approved model/API for production-grade language understanding.")
    prompt=st.text_area("Enter a maintenance request or question",placeholder="Create a high priority task for CNC-04, spindle noise, assign Rajesh, due tomorrow.\n\nOr: Show me the breakdown history of CNC-04.")
    if st.button("Ask MAIA",type="primary") and prompt.strip():
        low=prompt.lower()
        if any(k in low for k in ["create","raise","make a task","maintenance task"]):
            draft=ai_parse_task(prompt)
            st.session_state["draft_task"]=draft
            st.markdown("#### Proposed task – review before saving")
            st.json(draft)
            if not draft["equipment_id"]: st.warning("Equipment ID not identified. Select the machine before saving.")
            else:
                if not draft["assigned_to"]: st.warning("Technician not identified. Choose an assignee in the draft below.")
                with st.form("ai_confirm"):
                    eqid=st.selectbox("Equipment",[x["id"] for x in q("SELECT * FROM equipment")],index=[x["id"] for x in q("SELECT * FROM equipment")].index(draft["equipment_id"]))
                    title=st.text_input("Task title",draft["title"])
                    typ=st.selectbox("Type",["Corrective","Preventive"],index=0 if draft["task_type"]=="Corrective" else 1)
                    pri=st.selectbox("Priority",["Critical","High","Medium","Low"],index=["Critical","High","Medium","Low"].index(draft["priority"]))
                    techs=[x["name"] for x in q("SELECT * FROM users WHERE role='Technician'")]
                    owner=st.selectbox("Assignee",techs,index=techs.index(draft["assigned_to"]) if draft["assigned_to"] in techs else 0)
                    due=date.fromisoformat(draft["due_date"])
                    due=st.date_input("Due date",due)
                    if st.form_submit_button("Confirm and create task"):
                        tid=next_id("T","tasks")
                        run("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(tid,eqid,title,prompt,typ,pri,owner,due.isoformat(),"Pending",datetime.now().isoformat(),"AI","",""))
                        audit("AI-created","Task",tid,prompt,actor); st.success(f"Task {tid} created after confirmation.")
        elif "breakdown" in low or "history" in low or "failure" in low or "repair" in low:
            eqid=next((x["id"] for x in q("SELECT * FROM equipment") if x["id"].lower() in low),None)
            if eqid:
                rows=q("SELECT * FROM breakdowns WHERE equipment_id=? ORDER BY reported_at DESC",(eqid,))
                st.markdown(f"#### Breakdown history: {eqid}")
                st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True) if rows else st.info("No breakdown history found.")
                if len(rows)>=2:
                    st.warning(f"MAIA observation: {eqid} has {len(rows)} recorded breakdowns. Review repeat failure patterns; this is a historical signal, not a prediction.")
            else:
                st.info("Please include an equipment ID such as CNC-04. Available equipment: "+", ".join(x["id"] for x in q("SELECT * FROM equipment")))
        elif "overdue" in low or "pending" in low or "task" in low:
            rows=q("SELECT * FROM tasks WHERE status NOT IN ('Closed','Completed') ORDER BY due_date")
            st.markdown("#### Open maintenance tasks")
            st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        elif "downtime" in low or "machine" in low or "worst" in low:
            rows=q("SELECT equipment_id, SUM(downtime_hours) AS downtime, COUNT(*) AS breakdowns FROM breakdowns GROUP BY equipment_id ORDER BY downtime DESC")
            st.markdown("#### Downtime and breakdown analysis")
            st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        else:
            st.info("I can help create maintenance tasks, find breakdown history, list open tasks and analyse downtime. Try: 'Show breakdown history for CNC-04'.")
    st.divider()
    st.markdown("**Suggested demo prompts**")
    st.code("Create a high priority task for CNC-04, spindle noise, assign Rajesh, due tomorrow.\nShow me the breakdown history of CNC-04.\nWhich machine has the highest recorded downtime?\nShow all overdue maintenance tasks.")

# ---------- Import/export ----------
elif page=="Excel Import / Export":
    st.subheader("Excel data migration and export")
    st.markdown("Upload a customer Excel file. Required sheet format: Equipment columns `id,name,category,line,criticality,manufacturer,model,status`; Breakdown columns `id,equipment_id,reported_at,category,symptoms,machine_status,downtime_hours`.")
    uploaded=st.file_uploader("Upload .xlsx or .csv",type=["xlsx","csv"])
    kind=st.selectbox("Data type",["Equipment","Breakdowns"])
    if uploaded:
        try:
            df=pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
            st.markdown("#### Import preview")
            st.dataframe(df.head(20),use_container_width=True)
            st.caption(f"{len(df)} rows detected.")
            if st.button("Validate and import"):
                required=["id","name","category","line","criticality","manufacturer","model","status"] if kind=="Equipment" else ["id","equipment_id","reported_at","category","symptoms","machine_status","downtime_hours"]
                missing=[x for x in required if x not in df.columns]
                if missing: st.error("Missing columns: "+", ".join(missing))
                else:
                    success=0; errors=[]
                    for _,r in df.iterrows():
                        try:
                            if kind=="Equipment":
                                run("INSERT OR IGNORE INTO equipment VALUES(?,?,?,?,?,?,?,?)",tuple(str(r[x]) for x in required))
                            else:
                                if not q("SELECT * FROM equipment WHERE id=?",(str(r["equipment_id"]),)): raise ValueError("Unknown equipment ID")
                                vals=(str(r["id"]),str(r["equipment_id"]),str(r["reported_at"]),str(r["category"]),str(r["symptoms"]),str(r["machine_status"]),float(r["downtime_hours"] or 0),"","Unknown","","","Closed","")
                                run("INSERT OR IGNORE INTO breakdowns VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",vals)
                            success+=1
                        except Exception as ex: errors.append(f"Row {_+2}: {ex}")
                    audit("Imported","Excel",uploaded.name,f"{success} rows imported; {len(errors)} errors",actor)
                    st.success(f"{success} rows processed.")
                    if errors: st.error("\\n".join(errors[:20]))
        except Exception as ex: st.error(f"Could not read file: {ex}")
    st.markdown("#### Export current records")
    a,b=st.columns(2)
    for label,table,col in [("Equipment","equipment",a),("Tasks","tasks",b)]:
        df=pd.DataFrame(q(f"SELECT * FROM {table}"))
        col.download_button(f"Download {label} CSV",df.to_csv(index=False).encode("utf-8"),file_name=f"maia_{table}.csv",mime="text/csv")
    bd_df=pd.DataFrame(q("SELECT * FROM breakdowns"))
    st.download_button("Download breakdown history CSV",bd_df.to_csv(index=False).encode("utf-8"),file_name="maia_breakdowns.csv",mime="text/csv")

# ---------- Audit ----------
elif page=="Audit Trail":
    st.subheader("Audit trail")
    data=q("SELECT * FROM audit ORDER BY at DESC LIMIT 200")
    st.dataframe(pd.DataFrame(data),use_container_width=True,hide_index=True) if data else st.info("No audit events recorded yet.")

st.divider()
st.caption("MAIA local demonstration build · Sample data only · Not for production or safety-critical maintenance decisions")
