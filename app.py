from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import warnings

# Import routers
from routers import conversion, documents, tasks, misc

# --- Initial Setup ---
warnings.filterwarnings(action="ignore", category=UserWarning, module="pydantic|torch")
warnings.filterwarnings(action="ignore", category=FutureWarning, module="easyocr")

# Initialize FastAPI app
app = FastAPI(title="Docling 文件轉換應用程式")

# --- Static Files and Templates ---
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize Jinja2Templates and add to app state for sharing
templates = Jinja2Templates(directory="templates")
app.state.templates = templates

# --- Include Routers ---
# Include routers from the routers directory
app.include_router(misc.router, tags=["Miscellaneous"])
# Prefix conversion-related API routes
app.include_router(conversion.router, tags=["Conversion"])
app.include_router(documents.router, tags=["Documents"])
# tasks router already includes /api/tasks prefix
app.include_router(tasks.router) 

# --- Background Task Function (Needs Refactoring) ---
# TODO: Move process_url_conversion logic to a service and call it from the relevant router
# The original process_url_conversion function is removed.
# The /convert-url endpoint needs to be refactored to use BackgroundTasks and call a service function.

# --- Run Application ---
if __name__ == "__main__":
    # Host and port can be configured via environment variables or config file
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True) # Use string for app and enable reload for dev

# --- End of Refactored app.py ---
# All previous route definitions, global variables, utility functions,
# and extensive imports have been removed and migrated.