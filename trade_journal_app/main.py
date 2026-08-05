from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from trade_journal_app.core.state import JournalStore
from trade_journal_app.dash_app.dash_dashboard import init_dashboard
from trade_journal_app.routes.upload import router as upload_router

app = FastAPI(title="Trade Journal Uploader")
app.state.journal_store = JournalStore()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Include upload routes
app.include_router(upload_router)

# ✅ Mount Dash dashboard
dash_middleware = init_dashboard(app.state.journal_store)
app.mount("/dash", dash_middleware)

# Template directory relative to this file so uvicorn can run from project root
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

STEP1_SUCCESS_MESSAGE = "CSV uploaded successfully. Continue with Step 2 to name your strategies."


def redirect_home(
    *,
    success: str | None = None,
    error: str | None = None,
    step: int | None = None,
    uploaded: str | None = None,
) -> RedirectResponse:
    params = {}
    if success:
        params["success"] = success
    if error:
        params["error"] = error
    if step is not None:
        params["flash_step"] = str(step)
    if uploaded:
        params["uploaded"] = uploaded
    query = urlencode(params)
    url = "/" + (f"?{query}" if query else "")
    return RedirectResponse(url=url, status_code=303)


@app.post("/save-strategies")
async def save_strategies(
    request: Request,
    strategy1: str = Form(""),
    strategy2: str = Form(""),
    strategy3: str = Form(""),
    strategy4: str = Form("")
):
    strategies = {
        1: strategy1.strip(),
        2: strategy2.strip(),
        3: strategy3.strip(),
        4: strategy4.strip()
    }

    store: JournalStore = request.app.state.journal_store

    if store.get_dataframe().empty:
        return redirect_home(error="Please upload a CSV before defining strategies.", step=2)

    if not any(value for value in strategies.values()):
        return redirect_home(error="Add at least one strategy name before continuing.", step=2)

    store.set_strategies(strategies)

    return redirect_home(success="Strategies saved. Step 3 unlocked — you can open the dashboard below.", step=2)

# Serve real HTML response for home page
@app.get("/")
async def home(
    request: Request,
    error: str | None = None,
    success: str | None = None,
    flash_step: str | None = None,
    uploaded: str | None = None,
):
    store: JournalStore = request.app.state.journal_store
    strategies = store.get_strategies()
    df = store.get_dataframe()
    has_data = not df.empty
    strategies_dict = {i: strategies.get(i, "") for i in range(1, 5)}
    has_strategies = any(value for value in strategies_dict.values())
    flash_step_num = int(flash_step) if flash_step and flash_step.isdigit() else None
    stored_filename = store.get_uploaded_filename()
    filename_to_show = uploaded or stored_filename
    step_success = {i: (success if flash_step_num == i else None) for i in range(1, 4)}
    step_error = {i: (error if flash_step_num == i else None) for i in range(1, 4)}

    if (
        not step_error[1]
        and not step_success[1]
        and has_data
        and filename_to_show
    ):
        step_success[1] = STEP1_SUCCESS_MESSAGE

    context = {
        "request": request,
        "strategies": strategies_dict,
        "has_data": has_data,
        "has_strategies": has_strategies,
        "flash_step": flash_step,
        "step_success": step_success,
        "step_error": step_error,
        "uploaded_filename": filename_to_show,
    }
    return templates.TemplateResponse("home.html", context)
