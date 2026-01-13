from fastapi import FastAPI
from app.api import visual_router  # Import the router we made

app = FastAPI(title="Car-Sentry AI Server")

# Include the Visual (YOLO) router
app.include_router(visual_router.router)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Car-Sentry AI Server is running!"}

if __name__ == "__main__":
    import uvicorn
    # Run the server on port 8000
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
