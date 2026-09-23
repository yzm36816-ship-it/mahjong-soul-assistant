"""Start the dashboard on loopback only."""
import uvicorn
from .api import create_app

uvicorn.run(create_app(), host="127.0.0.1", port=8765, log_level="info")
