"""Google 서비스 계정 JSON을 어디서 읽을지 해결한다.

- 로컬: GOOGLE_SERVICE_ACCOUNT_JSON = 파일 경로 (기존 방식)
- Lambda: GOOGLE_SA_SSM_PARAM = SSM Parameter Store(SecureString) 이름
          → cold start 시 값을 가져와 /tmp/sa.json 에 기록하고 그 경로를 반환

DB가 없는 서버리스 구조라 작은 시크릿은 Lambda env, 비교적 큰 SA JSON은 SSM에 둔다.
"""
import logging
import os

log = logging.getLogger(__name__)

_CACHE_PATH = "/tmp/sa.json"


def resolve_service_account_json() -> str:
    """사용 가능한 SA JSON 파일 경로를 반환한다."""
    path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if path:
        return path

    param = os.environ.get("GOOGLE_SA_SSM_PARAM")
    if not param:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON 또는 GOOGLE_SA_SSM_PARAM 중 하나가 필요합니다."
        )

    # boto3는 Lambda 런타임에 기본 포함된다(로컬에서는 dev 의존성).
    import boto3  # noqa: PLC0415

    ssm = boto3.client("ssm")
    value = ssm.get_parameter(Name=param, WithDecryption=True)["Parameter"]["Value"]
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        f.write(value)
    log.info("SSM에서 서비스 계정 JSON 로드 완료 → %s", _CACHE_PATH)
    return _CACHE_PATH
