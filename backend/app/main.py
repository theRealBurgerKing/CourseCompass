from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from app.rag.vectorstore import get_vectorstore
from app.api import chat, courses


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm up the FAISS index on startup so the first request is fast."""
    print("[Startup] Loading FAISS vectorstore...")
    get_vectorstore()
    print("[Startup] CourseCompass API is ready.")
    yield


app = FastAPI(
    title="CourseCompass API",
    description="UNSW Course Selection AI Agent — RAG-powered course advisor",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(courses.router, prefix="/api", tags=["Courses"])


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
