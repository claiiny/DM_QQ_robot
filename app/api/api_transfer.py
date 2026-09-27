from fastapi import APIRouter

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/transfer")
def link_ai() -> str:
    return "OK"
