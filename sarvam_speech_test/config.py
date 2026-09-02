import os
from pathlib import Path

from dotenv import load_dotenv


# Load the service-local secret file without committing it to source control.
load_dotenv(Path(__file__).with_name(".env"))
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
