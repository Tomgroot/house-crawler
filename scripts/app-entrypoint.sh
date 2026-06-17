#!/bin/bash
set -e

house-crawler db init

exec streamlit run app.py \
  --server.address 0.0.0.0 \
  --server.port 8501 \
  --server.headless true
