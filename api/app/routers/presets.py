from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Preset
from ..schemas import PresetCreate, PresetOut

router = APIRouter(tags=["presets"])


@router.get("/presets", response_model=list[PresetOut])
async def list_presets(db: AsyncSession = Depends(get_db)) -> list[Preset]:
    result = await db.execute(select(Preset).order_by(Preset.category, Preset.label))
    return list(result.scalars().all())


@router.post("/presets", response_model=PresetOut, status_code=201)
async def create_preset(payload: PresetCreate, db: AsyncSession = Depends(get_db)) -> Preset:
    """No auth — stubbed per current project scope. Do not expose publicly as-is."""
    if payload.min_kb > payload.max_kb:
        raise HTTPException(status_code=400, detail="min_kb cannot exceed max_kb")

    preset = Preset(**payload.model_dump())
    db.add(preset)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Preset id '{payload.id}' already exists")
    await db.refresh(preset)
    return preset
