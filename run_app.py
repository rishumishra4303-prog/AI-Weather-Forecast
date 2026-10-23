import subprocess
import webbrowser

# Open the browser automatically
webbrowser.open("http://localhost:8501")

# Run the Streamlit app
subprocess.run(["streamlit", "run", "streamlit_app.py"])

