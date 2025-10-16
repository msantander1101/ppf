import os
from dotenv import load_dotenv

load_dotenv()

HIBP_KEY = os.getenv("HIBP_API_KEY", "")
