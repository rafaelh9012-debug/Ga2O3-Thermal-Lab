Ga2O3 THERMAL LAB — EXISTING-PYTHON EDITION
Publisher: RafaelDaSquidman

WHY THIS VERSION EXISTS
-----------------------
This build intentionally contains NO custom EXE and NO automatic Python installer.
It is designed to avoid the SmartScreen/antivirus friction caused by an unsigned EXE
and to use a Python installation or IDE that the user already trusts.

BEST WAY TO RUN IT
------------------
Option A — Spyder / Anaconda / VS Code / PyCharm / IDLE
1. Open START_APP.py in the Python application you already use.
2. Press that application's normal Run button.
3. START_APP.py uses the exact Python interpreter that ran it.
4. On the first run it creates a private .runtime folder and installs only the
   libraries required by this project.
5. Streamlit starts and the Thermal Lab opens in your browser.

Option B — Windows one-click attempt
Double-click RUN_WITH_EXISTING_PYTHON.bat.
It searches only for Python already installed on the computer. It DOES NOT download
or install Python. It recognizes common python.org, Anaconda, and Miniconda locations.
If it cannot find a command-line Python, it tells you to open START_APP.py in Spyder
or another Python application instead.

IMPORTANT
---------
* Python 3.11 through 3.14 is required by this packaged dependency set.
* First-time library installation requires internet access unless the current Python
  environment already contains NumPy, SciPy, pandas, Plotly, Streamlit, and Matplotlib.
* No administrator rights are intentionally requested.
* No executable (.exe) launcher is included.
* The original scientific Python files are in Python_Code\.
* The launcher never downloads or installs Python itself.

WHAT START_APP.py DOES
----------------------
It uses sys.executable, meaning "the Python interpreter that is currently running me."
That is what makes it suitable for Spyder, Anaconda, VS Code, PyCharm, IDLE, or a
normal python.org installation.

The app itself must be started through Streamlit rather than plain `python app.py`.
START_APP.py handles that automatically after the environment is ready.

STOPPING THE APP
----------------
Close/stop the running process in your Python IDE, or press Ctrl+C if you launched it
from a terminal. The browser tab can then be closed normally.

DISPLAY NOTE
------------
The app now forces its intended high-contrast light theme so labels and warnings remain readable even if Windows or the browser is using dark mode.

WEB / BROWSER VERSION
---------------------
Double-click OPEN_WEB_VERSION.htm to open an interactive browser report without
starting Python, Streamlit, or the launcher. The HTML is self-contained, so its
plots and data are stored inside the file and it can be viewed offline.

The browser version is a PRECOMPUTED SNAPSHOT of the default solved cases
(630 um and 50 um substrates at 1500 W/cm^2). You can hover, zoom, pan, inspect
plots, and use the report's browser-side controls, but changing physical inputs
and solving a new thermal field requires the Python/Streamlit application.

Because OPEN_WEB_VERSION.htm is a normal static web page, it can also be uploaded
to a static web host to make the same report accessible through a normal URL.
