import io
import json
import zipfile
from dataclasses import dataclass

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from PIL import UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from ..config import settings
from ..database import get_db
from ..image_processing import ResizeResult, process_image
from ..models import Preset
from ..rate_limit import limiter

router = APIRouter(tags=["resize"])

MAX_FILE_BYTES = settings.max_file_size_mb * 1024 * 1024


@dataclass
class Spec:
    width_px: int
    height_px: int
    dpi: int
    min_kb: int
    max_kb: int


async def resolve_spec(
    db: AsyncSession,
    preset_id: str | None,
    width_px: int | None,
    height_px: int | None,
    dpi: int | None,
    min_kb: int | None,
    max_kb: int | None,
) -> Spec:
    if preset_id:
        result = await db.execute(select(Preset).where(Preset.id == preset_id))
        preset = result.scalar_one_or_none()
        if preset is None:
            raise HTTPException(status_code=404, detail=f"Unknown preset_id '{preset_id}'")
        return Spec(
            width_px=preset.width_px,
            height_px=preset.height_px,
            dpi=preset.dpi,
            min_kb=preset.min_kb,
            max_kb=preset.max_kb,
        )

    if None in (width_px, height_px, dpi, min_kb, max_kb):
        raise HTTPException(
            status_code=400,
            detail="Provide either preset_id, or all of width_px/height_px/dpi/min_kb/max_kb",
        )
    assert width_px and height_px and dpi and min_kb and max_kb
    if width_px <= 0 or height_px <= 0 or dpi <= 0 or min_kb <= 0 or max_kb <= 0:
        raise HTTPException(status_code=400, detail="Size/DPI/KB values must be positive")
    if min_kb > max_kb:
        raise HTTPException(status_code=400, detail="min_kb cannot exceed max_kb")

    return Spec(width_px=width_px, height_px=height_px, dpi=dpi, min_kb=min_kb, max_kb=max_kb)


async def _read_and_validate(file: UploadFile) -> bytes:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail=f"'{file.filename}' is empty")
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"'{file.filename}' exceeds the {settings.max_file_size_mb}MB upload limit",
        )
    return data


def _run_processing(data: bytes, spec: Spec, filename: str) -> ResizeResult:
    try:
        return process_image(data, spec.width_px, spec.height_px, spec.dpi, spec.min_kb, spec.max_kb)
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail=f"'{filename}' is not a readable image")


def _result_headers(result: ResizeResult) -> dict[str, str]:
    return {
        "X-Result-Kb": str(result.result_kb),
        "X-In-Range": str(result.in_range).lower(),
        "X-Width-Px": str(result.width_px),
        "X-Height-Px": str(result.height_px),
        "X-Dpi": str(result.dpi),
        "X-Message": result.message,
    }


@router.post("/resize")
@limiter.limit(settings.rate_limit_resize)
async def resize_single(
    request: Request,
    file: UploadFile = File(...),
    preset_id: str | None = Form(None),
    width_px: int | None = Form(None),
    height_px: int | None = Form(None),
    dpi: int | None = Form(None),
    min_kb: int | None = Form(None),
    max_kb: int | None = Form(None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    spec = await resolve_spec(db, preset_id, width_px, height_px, dpi, min_kb, max_kb)
    data = await _read_and_validate(file)
    result = _run_processing(data, spec, file.filename or "upload")

    return Response(
        content=result.data,
        media_type="image/jpeg",
        headers=_result_headers(result),
    )


@router.post("/resize/batch")
@limiter.limit(settings.rate_limit_resize)
async def resize_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    preset_id: str | None = Form(None),
    width_px: int | None = Form(None),
    height_px: int | None = Form(None),
    dpi: int | None = Form(None),
    min_kb: int | None = Form(None),
    max_kb: int | None = Form(None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    if len(files) > settings.max_batch_files:
        raise HTTPException(
            status_code=400,
            detail=f"Batch limited to {settings.max_batch_files} files (got {len(files)})",
        )

    spec = await resolve_spec(db, preset_id, width_px, height_px, dpi, min_kb, max_kb)

    zip_buf = io.BytesIO()
    manifest: list[dict] = []
    used_names: set[str] = set()

    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for upload in files:
            base = (upload.filename or "upload").rsplit(".", 1)[0]
            out_name = f"{base}.jpg"
            suffix = 1
            while out_name in used_names:
                out_name = f"{base}_{suffix}.jpg"
                suffix += 1
            used_names.add(out_name)

            data = await _read_and_validate(upload)
            result = _run_processing(data, spec, upload.filename or "upload")

            zf.writestr(out_name, result.data)
            manifest.append(
                {
                    "source_filename": upload.filename,
                    "output_filename": out_name,
                    "width_px": result.width_px,
                    "height_px": result.height_px,
                    "dpi": result.dpi,
                    "result_kb": result.result_kb,
                    "min_kb": result.min_kb,
                    "max_kb": result.max_kb,
                    "in_range": result.in_range,
                    "message": result.message,
                }
            )

        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    zip_buf.seek(0)
    return Response(
        content=zip_buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="resized_batch.zip"'},
    )
