"""
Local Scheduler Trigger
scripts/trigger_local.py

Sequentially triggers the ingestion pipeline locally.
scrape.py -> chunk.py -> embed.py
"""

import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

def run():
    print("=== STARTING LOCAL SCHEDULER PIPELINE ===")
    
    pipeline_scripts = [
        "ingest/scraper/scrape.py",
        "ingest/chunker/chunk.py",
        "ingest/embedder/embed.py"
    ]
    
    for script in pipeline_scripts:
        script_path = str(ROOT_DIR / script)
        print(f"\n>> Triggering: {script}")
        
        try:
            result = subprocess.run([sys.executable, script_path], check=True)
        except subprocess.CalledProcessError as e:
            print(f"\n[ERROR] Pipeline failed at {script} with exit code {e.returncode}")
            sys.exit(e.returncode)
            
    print("\n=== LOCAL SCHEDULER PIPELINE COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    run()
