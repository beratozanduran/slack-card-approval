#!/usr/bin/env bash
# 에듀카드 Lambda 배포 패키지(zip) 생성.
# 의존성은 순수 파이썬(slack-bolt/gspread/google-auth)이라 macOS에서 빌드해도
# Lambda(Linux)에서 동작한다. boto3는 Lambda 런타임에 기본 포함되어 제외.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PKG="$ROOT/build/pkg"
ZIP="$ROOT/build/lambda.zip"

rm -rf "$PKG" "$ZIP"
mkdir -p "$PKG"

echo "==> 의존성 설치"
python3 -m pip install \
  --target "$PKG" \
  --only-binary=:all: --platform manylinux2014_x86_64 \
  --python-version 3.12 \
  "slack-bolt>=1.18" "gspread>=6.0" "google-auth>=2.28" 2>/dev/null \
  || python3 -m pip install --target "$PKG" \
       "slack-bolt>=1.18" "gspread>=6.0" "google-auth>=2.28"

echo "==> 소스 복사"
# src/ 내용을 zip 루트에 둔다 (핸들러 = lambda_handler.handler)
cp "$ROOT"/src/*.py "$PKG"/
cp -R "$ROOT"/src/handlers "$PKG"/handlers
cp -R "$ROOT"/src/views "$PKG"/views
cp -R "$ROOT"/src/services "$PKG"/services
# 로컬 전용 엔트리포인트는 패키지에서 제외
rm -f "$PKG"/main.py

echo "==> zip 생성: $ZIP"
( cd "$PKG" && zip -qr "$ZIP" . -x '*.pyc' -x '*/__pycache__/*' )

echo "완료: $ZIP"
