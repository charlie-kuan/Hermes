#!/bin/bash

CONDA_PATH="/opt/miniconda3"
ENV_NAME="Hermes"
PROJECT_DIR="$(dirname "$0")"

if [ ! -f "$PROJECT_DIR/data/river/osm_rivers.gpkg" ]; then
  echo "⚠️  找不到 OSM 河川資料，地圖匯出將使用政府資料作為備援。"
  echo "   如需完整河川資料，請執行："
  echo "   python scripts/download_osm_rivers.py"
  echo ""
fi

echo "啟動後端..."
"$CONDA_PATH/bin/conda" run -n "$ENV_NAME" uvicorn app.main:app --reload --app-dir "$PROJECT_DIR" &
BACKEND_PID=$!

echo "啟動前端..."
cd "$PROJECT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ 後端：http://localhost:8000"
echo "✅ 前端：http://localhost:5173"
echo ""
echo "按 Ctrl+C 關閉所有服務"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
