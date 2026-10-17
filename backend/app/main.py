from fastapi import FastAPI

app = FastAPI(title="Asset Intelligence Copilot")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
