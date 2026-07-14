"""Aplicacion web de asistencia facial construida con FastAPI y DeepFace."""

from __future__ import annotations

import base64
import csv
import json
import os
import re
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

try:
    from deepface import DeepFace
except ImportError:  # Permite mostrar una explicacion util si falta la dependencia.
    DeepFace = None


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = Path(os.getenv("ATTENDANCE_DATA_DIR", PROJECT_DIR / "data"))
PEOPLE_FILE = DATA_DIR / "people.json"
ATTENDANCE_FILE = DATA_DIR / "attendance.csv"
MODEL_NAME = os.getenv("DEEPFACE_MODEL", "Facenet512")
DETECTOR_BACKEND = os.getenv("DEEPFACE_DETECTOR", "opencv")
DISTANCE_THRESHOLD = float(os.getenv("FACE_DISTANCE_THRESHOLD", "0.30"))
DATA_LOCK = threading.Lock()


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_storage()
    yield


app = FastAPI(
    title="Presente",
    description="Sistema local de asistencia con reconocimiento facial",
    version="1.0.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ImagePayload(BaseModel):
    image: str = Field(min_length=20, description="Imagen como Data URL base64")


class EnrollmentPayload(ImagePayload):
    student_id: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=2, max_length=100)

    @field_validator("student_id")
    @classmethod
    def clean_student_id(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9_-]+", value):
            raise ValueError("Usa solo letras, numeros, guion o guion bajo")
        return value

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Escribe un nombre valido")
        return value


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not PEOPLE_FILE.exists():
        PEOPLE_FILE.write_text("[]\n", encoding="utf-8")
    if not ATTENDANCE_FILE.exists():
        with ATTENDANCE_FILE.open("w", newline="", encoding="utf-8") as file:
            csv.writer(file).writerow(["date", "time", "student_id", "name", "distance"])


def decode_image(data_url: str) -> np.ndarray:
    """Convierte un Data URL en una imagen OpenCV y limita entradas enormes."""
    try:
        encoded = data_url.split(",", 1)[1] if "," in data_url else data_url
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, "La imagen no tiene un formato base64 valido.") from exc
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(413, "La imagen supera el limite de 10 MB.")
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "No fue posible leer la imagen.")
    return image


def embedding_for(image: np.ndarray) -> list[float]:
    if DeepFace is None:
        raise HTTPException(503, "DeepFace no esta instalado. Ejecuta: pip install -r requirements.txt")
    try:
        representations = DeepFace.represent(
            img_path=image,
            model_name=MODEL_NAME,
            detector_backend=DETECTOR_BACKEND,
            enforce_detection=True,
            align=True,
        )
    except Exception as exc:
        message = str(exc).lower()
        if "face" in message or "detect" in message:
            raise HTTPException(422, "No se detecto un rostro claro. Mira al frente y mejora la iluminacion.") from exc
        raise HTTPException(500, f"DeepFace no pudo procesar la imagen: {exc}") from exc
    if len(representations) != 1:
        raise HTTPException(422, "Debe aparecer exactamente una persona en la imagen.")
    return [float(value) for value in representations[0]["embedding"]]


def load_people() -> list[dict[str, Any]]:
    ensure_storage()
    try:
        return json.loads(PEOPLE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(500, "No fue posible leer el registro de personas.") from exc


def save_people(people: list[dict[str, Any]]) -> None:
    temp_file = PEOPLE_FILE.with_suffix(".tmp")
    temp_file.write_text(json.dumps(people, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_file.replace(PEOPLE_FILE)


def cosine_distance(first: list[float], second: list[float]) -> float:
    a, b = np.asarray(first), np.asarray(second)
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    return 1.0 if denominator == 0 else float(1 - np.dot(a, b) / denominator)


def attendance_rows(date_filter: str | None = None) -> list[dict[str, str]]:
    ensure_storage()
    with ATTENDANCE_FILE.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    if date_filter:
        rows = [row for row in rows if row["date"] == date_filter]
    return list(reversed(rows))


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
def status() -> dict[str, Any]:
    today = datetime.now().date().isoformat()
    return {
        "ready": DeepFace is not None,
        "model": MODEL_NAME,
        "threshold": DISTANCE_THRESHOLD,
        "registered": len(load_people()),
        "present_today": len(attendance_rows(today)),
    }


@app.get("/api/people")
def people() -> list[dict[str, str]]:
    return [{"student_id": person["student_id"], "name": person["name"]} for person in load_people()]


@app.post("/api/enroll", status_code=201)
def enroll(payload: EnrollmentPayload) -> dict[str, Any]:
    embedding = embedding_for(decode_image(payload.image))
    with DATA_LOCK:
        people_list = load_people()
        existing = next((p for p in people_list if p["student_id"] == payload.student_id), None)
        person = {"student_id": payload.student_id, "name": payload.name, "embedding": embedding}
        if existing:
            people_list[people_list.index(existing)] = person
        else:
            people_list.append(person)
        save_people(people_list)
    return {"success": True, "updated": existing is not None, "person": {"student_id": payload.student_id, "name": payload.name}}


@app.post("/api/recognize")
def recognize(payload: ImagePayload) -> dict[str, Any]:
    probe = embedding_for(decode_image(payload.image))
    people_list = load_people()
    if not people_list:
        raise HTTPException(409, "No hay alumnos registrados. Realiza la primera alta.")
    ranked = sorted((cosine_distance(probe, p["embedding"]), p) for p in people_list)
    distance, person = ranked[0]
    if distance > DISTANCE_THRESHOLD:
        return {"success": False, "recognized": False, "distance": round(distance, 4), "message": "Rostro no reconocido"}

    now = datetime.now()
    date, current_time = now.date().isoformat(), now.strftime("%H:%M:%S")
    with DATA_LOCK:
        already_present = any(row["student_id"] == person["student_id"] for row in attendance_rows(date))
        if not already_present:
            with ATTENDANCE_FILE.open("a", newline="", encoding="utf-8") as file:
                csv.writer(file).writerow([date, current_time, person["student_id"], person["name"], f"{distance:.4f}"])
    return {
        "success": True,
        "recognized": True,
        "already_present": already_present,
        "person": {"student_id": person["student_id"], "name": person["name"]},
        "time": current_time,
        "distance": round(distance, 4),
    }


@app.get("/api/attendance")
def attendance(date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")) -> list[dict[str, str]]:
    return attendance_rows(date)


@app.get("/api/attendance/export")
def export_attendance() -> FileResponse:
    ensure_storage()
    return FileResponse(ATTENDANCE_FILE, media_type="text/csv", filename="asistencia.csv")
