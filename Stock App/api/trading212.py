import json
from dotenv import load_dotenv
import os
import datetime
import requests
from pathlib import Path

# Responsible for:
# - making API requests to Trading 212
# - handling authentication and headers
# - returning raw JSON responses
# - handling request errors and response status checks

load_dotenv(Path(__file__).parent.parent / "config.env")
t212_api_key = os.getenv("t212_api_key")
t212_secret_key = os.getenv("t212_secret_key")




