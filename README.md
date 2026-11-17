# MAIA – Hosted Client Demo

A Streamlit demo of maintenance workflows for an illustrative automotive components plant.

## What is included
- Executive dashboard
- Equipment master
- Corrective and preventive maintenance tasks
- Breakdown register and equipment history
- AI-style conversational task drafting and historical search
- Excel/CSV import and CSV export
- Audit trail

## Important demo limitations
- The AI assistant uses a deterministic local parser and database queries. It is not connected to a live LLM.
- All plant records and metrics are illustrative sample data.
- The SQLite database is stored in the host's temporary directory. Changes may be lost when the hosted app restarts or its container is recycled. This is suitable for a controlled demo, not production.
- The app is a workflow prototype, not a production-ready CMMS. Production requires durable managed database storage, authentication/authorization, tenant isolation, backups, monitoring, security review and approved LLM integration.

## Deploy to Streamlit Community Cloud

1. Create a **private GitHub repository** named `maia-client-demo`.
2. Upload the contents of this folder to the repository root. Ensure `app.py` and `requirements.txt` are at the root.
3. Open https://share.streamlit.io/ and sign in with GitHub.
4. Connect/authorize GitHub if prompted. Grant access to the private repository when requested.
5. Select **Create app** → **Yup, I have an app**.
6. Select repository `maia-client-demo`, branch `main`, and entrypoint `app.py`.
7. Under **Advanced settings**, choose **Python 3.12**.
8. Deploy. Wait for the build to complete; Streamlit will provide a `*.streamlit.app` URL.
9. Keep the app private. In the app's **Share** settings, invite the client's email address as a viewer. The viewer will need to authenticate to access it.

Official deployment guide: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy

## Updating the demo
Commit and push changes to GitHub. Community Cloud redeploys the app when the repository changes.

## Demo prompts
- Create a high priority task for CNC-04, spindle noise, assign Rajesh, due tomorrow.
- Show me the breakdown history of CNC-04.
- Which machine has the highest recorded downtime?
- Show all overdue maintenance tasks.

## Demo narrative
Breakdown reported → corrective task generated → technician assigned → repair recorded → equipment history updated → management visibility.
