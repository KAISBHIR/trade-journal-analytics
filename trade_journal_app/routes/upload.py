from fastapi import APIRouter, UploadFile, File, Form, Request
from fastapi.responses import RedirectResponse
import pandas as pd
import io
from urllib.parse import urlencode

from trade_journal_app.core.state import JournalStore
from trade_journal_app.services.analyzer import process_trades, detect_strategy

router = APIRouter(prefix="/upload", tags=["Upload"])

def _redirect_with_message(
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


@router.post("/", response_class=RedirectResponse)
async def upload_csv(
    request: Request,
    file: UploadFile = File(...),
):
    """Handle CSV upload (Step 1)."""
    if not file.filename.lower().endswith(".csv"):
        return _redirect_with_message(error="Upload failed: file must be a .csv", step=1)

    store: JournalStore = request.app.state.journal_store

    try:
        content = await file.read()
        if not content:
            return _redirect_with_message(error="Upload failed: the file was empty", step=1)

        try:
            df = pd.read_csv(io.BytesIO(content), sep=";", encoding="utf-8", on_bad_lines="skip")
            if df.shape[1] <= 1:
                df = pd.read_csv(io.BytesIO(content), sep=",", encoding="utf-8", on_bad_lines="skip")
        except Exception:
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8", on_bad_lines="skip")

        required_cols = {"Ticket", "Symbol", "Type", "OpenPrice", "ClosePrice", "OpenTime", "CloseTime", "Profit"}
        missing = required_cols - set(df.columns)
        if missing:
            missing_cols = ", ".join(sorted(missing))
            return _redirect_with_message(error=f"CSV missing required columns: {missing_cols}", step=1)

        for optional in ["Comment", "Lots"]:
            if optional not in df.columns:
                df[optional] = ""

        processed = process_trades(df)
        if "Strategy" not in processed.columns:
            processed["Strategy"] = "Unlabeled"

        # If strategies already exist from a previous session, re-apply detection.
        strategies = store.get_strategies()
        if any(strategies.values()):
            processed["Strategy"] = processed["Comment"].apply(lambda x: detect_strategy(x, strategies))

        store.set_dataframe(processed, filename=file.filename)

    except Exception as exc:
        message = str(exc) or "Unexpected error while processing file"
        return _redirect_with_message(error=f"Upload failed: {message}", step=1)

    success_msg = "CSV uploaded successfully. Continue with Step 2 to name your strategies."
    return _redirect_with_message(success=success_msg, step=1, uploaded=file.filename)
