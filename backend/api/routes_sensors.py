"""REST endpoints for sensor data."""
from fastapi import APIRouter, Query
from typing import Optional
import csv
import io
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/sensors", tags=["sensors"])
_db = None

def init(db):
    global _db
    _db = db

@router.get("/latest")
def get_latest():
    reading = _db.get_latest_reading()
    if not reading:
        return {"error": "No readings available"}
    return reading

@router.get("/history")
def get_history(hours: int = Query(24, ge=1, le=8760),
                sensor: Optional[str] = Query(None)):
    return _db.get_readings_history(hours=hours, sensor=sensor)

@router.get("/stats")
def get_stats(hours: int = Query(168, ge=1, le=8760)):
    return _db.get_readings_stats(hours=hours)

@router.get("/export")
def export_csv(hours: int = Query(720, ge=1), format: str = Query("csv")):
    rows = _db.get_readings_history(hours=hours)
    if not rows:
        return {"error": "No data to export"}
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=agrimaster_export.csv"}
    )
