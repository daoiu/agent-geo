FROM python:3.11-slim

# WeasyPrint system deps (Chinese fonts + cairo + pango)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data

# v0.5 — bge-small-zh-v1.5 模型 (~95MB,gitignore)
# build context 必须有 backend/data/models/models--BAAI--bge-small-zh-v1.5/
# (本地预下载或 CI 单独 step 注入).COPY 失败会让 ReindexService 启动时无模型可用。
COPY data/models /app/data/models

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
