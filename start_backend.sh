#!/bin/bash
# Try both common miniconda locations
if [ -f "/root/miniconda3/etc/profile.d/conda.sh" ]; then
    source /root/miniconda3/etc/profile.d/conda.sh
elif [ -f "/opt/miniconda3/etc/profile.d/conda.sh" ]; then
    source /opt/miniconda3/etc/profile.d/conda.sh
fi

conda activate Hermes
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
