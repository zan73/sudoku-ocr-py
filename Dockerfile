# Use a lightweight Python base
FROM python:3.10-slim

# Install modern system dependencies for OpenCV and PaddleOCR
# libgl1 and libglx-mesa0 replace the obsolete libgl1-mesa-glx
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglx-mesa0 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY main.py .
COPY index.html .

# Disable Paddle PIR mode which is buggy in some versions
ENV FLAGS_enable_pir_api=0

# Expose the port for the FastAPI server
EXPOSE 8000

# Start the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]