# Deploying the demo on PythonAnywhere

The demo is a separate Flask app mounted at `/data-demo` next to the other apps in the
same web app (free accounts have one web app).

1. **Bash console:**
   ```bash
   cd ~
   git clone https://github.com/shafiqa123personal-do/data-pipeline-toolkit.git
   cd data-pipeline-toolkit
   workon <your-virtualenv>
   pip install -r requirements-web.txt
   echo "GEMINI_API_KEY=your-gemini-api-key" > .env
   ```
2. **Web tab → WSGI configuration file.** Just above the line that starts with
   `application = DispatcherMiddleware(`, add:
   ```python
   sys.path.append("/home/<your-username>/data-pipeline-toolkit")
   from web.app import create_app as create_data_demo
   ```
   and inside the `{ ... }` of mounts add:
   ```python
   "/data-demo": create_data_demo(),
   ```
3. **Web tab → Reload**, then open https://systemsyncai.pythonanywhere.com/data-demo/

**Updating later:** `cd ~/data-pipeline-toolkit && git pull`, then Reload.

**Optional daily job (Tasks tab, free plan allows one):**
`cd ~/data-pipeline-toolkit && ~/.virtualenvs/<your-virtualenv>/bin/python run.py books --pages 50`
