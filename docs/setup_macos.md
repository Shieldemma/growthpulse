# macOS setup (beginner guide)

You will type commands into the **Terminal** app. Nothing here changes system settings; everything lives inside the project folder.

## 0. Vocabulary (2 minutes)
* **Finder** is the folder window you click around in. **Terminal** is a text window where you type commands.
* A **path** is a folder's address, e.g. `/Users/yourname/Documents/growthpulse`. `~` is shorthand for your home folder (`/Users/yourname`).
* **Opening a folder in Finder** (double-click) is *not* the same as **running** it. Typing `/Users/me/growthpulse` alone in Terminal gives *"is a directory"* - that is expected. To go *into* a folder in Terminal, use `cd` ("change directory"): `cd ~/Documents/growthpulse`.
* A **virtual environment** (`.venv`) is a private box of Python packages for this project only, so nothing else on your Mac is affected.

## 1. Put the project somewhere sensible
If you received `growthpulse.zip`: double-click it in Finder (it unzips next to the zip), then drag the `growthpulse` folder into **Documents**. The path is now `~/Documents/growthpulse`.

## 2. Open the project in VS Code
1. Install VS Code from https://code.visualstudio.com if you do not have it.
2. VS Code -> **File -> Open Folder...** -> choose `Documents/growthpulse` -> **Open**. Click *Trust the authors* when asked.
3. Open its built-in terminal: **Terminal -> New Terminal**. It starts *inside* the project folder - the prompt ends with `growthpulse %`.
4. Confirm: type `pwd` and press Return. You should see `.../growthpulse`. Type `ls` - you should see `README.md`, `app`, `scripts`, `src`...
   If not: `cd ~/Documents/growthpulse`.

(Prefer Terminal.app? Open it, then run `cd ~/Documents/growthpulse`.)

## 3. Check Python (needs 3.11 or newer)
```bash
python3 --version
```
If it prints 3.11, 3.12 or 3.13 you are fine. Otherwise install Homebrew (https://brew.sh) and run `brew install python@3.12`, then open a **new** Terminal window.

## 4. One-time setup (creates `.venv`, installs everything)
```bash
bash scripts/setup_mac.sh
```
Takes a few minutes. Manual equivalent:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```
After `source .venv/bin/activate` your prompt starts with `(.venv)`. **Do this in every new Terminal window** before running project commands. VS Code usually does it for you: if it asks to select an interpreter, pick `.venv`.

## 5. Generate data and run the whole pipeline
```bash
python scripts/run_pipeline.py --regenerate
```
Expected output: six numbered steps and `Validation: 102/102 checks passed` (about 1-2 minutes). This generates the synthetic data, loads DuckDB, runs dbt (44 models + 135 tests), fits the experiments and MMM, writes `reports/business_report.md`, a weekly insight brief and 27 BI CSV exports in `dashboard/bi_exports/`.

## 6. Run the tests
```bash
python -m pytest -m "not slow"     # ~15 seconds, unit tests
python -m pytest                   # everything incl. end-to-end pipeline + dashboard smoke tests (~3-5 minutes)
```

## 7. Launch the dashboard
```bash
streamlit run app/streamlit_app.py   # OPTIONAL local viewer; primary BI = Looker Studio (docs/looker_studio/README.md)
```
Your browser opens `http://localhost:8501`. (If not, copy that address into Safari/Chrome.) If Streamlit asks for an email, press Return to skip. Stop the app with **Control + C** in the terminal.

## 8. Later: BigQuery
See `docs/bigquery_setup.md`. Nothing in steps 1-7 needs a Google account.

## Common problems
See `docs/troubleshooting.md`.
