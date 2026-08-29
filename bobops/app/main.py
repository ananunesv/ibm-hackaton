from fastapi import FastAPI

app = FastAPI(title="BobOps API")


@app.get("/health")
def health():
    return {"status": "healthy", "service": "bobops-api"}
