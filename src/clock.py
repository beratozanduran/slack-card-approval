"""시각 유틸 — 팀이 한국에서 운영되므로 모든 시각을 KST(UTC+9) 벽시계 기준으로 다룬다."""
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def now_kst_str() -> str:
    """'YYYY-MM-DD HH:MM:SS' (마이크로초 없음) 현재 KST 시각."""
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")


def now_kst_ref() -> str:
    """DB가 없으므로 신청을 식별할 짧은 참조 코드를 KST 시각으로 생성한다.
    예: 260630-104231 (YYMMDD-HHMMSS)."""
    return datetime.now(KST).strftime("%y%m%d-%H%M%S")
