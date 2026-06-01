# [F1] Base image
FROM python:3.10-slim

# [F2] Set working directory inside container
WORKDIR /app

# [NEW] Install system build essentials and multimedia dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libsndfile1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# [F3] Copy requirements first (Docker layer caching)
COPY requirements.txt .

# [NEW] Upgrade pip/setuptools to safely process complex dependency wheels
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# [F4] Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# [F5] Copy application code
COPY src/        ./src/
COPY api/        ./api/
COPY monitoring/ ./monitoring/

# [F6] Create reports directory inside container
RUN mkdir -p reports

# [F7] Expose port 8000
EXPOSE 8000

# [F8] Start command
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]