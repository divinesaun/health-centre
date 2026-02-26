"""Vercel serverless entry point.

All HTTP traffic is routed through this file via vercel.json.
The FastAPI app instance is imported from the app factory.
"""

from app.main import app
