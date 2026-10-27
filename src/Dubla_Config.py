import json
from pathlib import Path

# Absolute path to project root regardless of execution directory
CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs.json"

def get_config(key: str):
    """Retrieve a configuration value from configs.json."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            return data.get(key)
    except Exception as e:
        print(f"Error opening config.json: {e}")
        return None

ROOT = CONFIG_PATH.parent

Quality=get_config("quality_ytdlp")
# Resolve configured paths against the project root so they do not depend on the cwd
TempPath=ROOT / get_config("temp_path")
OutputPath=ROOT / get_config("output_path")
