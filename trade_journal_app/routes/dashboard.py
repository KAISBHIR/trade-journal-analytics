from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/", response_class=HTMLResponse)
async def dashboard_home():
    return """
    <html>
        <head><title>Dashboard</title></head>
        <body style='background:#0E1117;color:white;font-family:sans-serif;'>
            <h1>📈 FastAPI Dashboard Placeholder</h1>
            <p>Dashboard route is working! Visit <a href='/dash'>/dash</a> for the Plotly Dash UI.</p>
        </body>
    </html>
    """
