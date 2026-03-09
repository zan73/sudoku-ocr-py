# Sudoku OCR Python

A robust, Dockerized Sudoku OCR application powered by **FastAPI**, **OpenCV**, and **PaddleOCR**. This application can process photos of Sudoku puzzles, detect the grid using advanced morphological operations, and return a 9x9 digital grid.

## 🌟 Features

- **Automated Grid Detection**: Uses morphological closing and squareness validation to isolate the Sudoku board from complex backgrounds.
- **Deep Learning OCR**: Leveraging PaddleOCR for high-accuracy digit recognition.
- **Interactive UI**: Built-in web interface for testing and debugging.
- **Debug Mode**: Visualize intermediate transformation steps (thresholding, warping) to troubleshoot processing failures.
- **Dockerized**: Easy deployment with all dependencies pre-installed.

## 🚀 Quick Start (Docker)

1. **Build the image**:
   ```bash
   docker build -t sudoku-ocr .
   ```

2. **Run the container**:
   Pass your email configuration as environment variables at runtime (do NOT bake these into the image):
   ```bash
   docker run -p 8000:8000 \
     -e SMTP_HOST="smtp.gmail.com" \
     -e SMTP_PORT=587 \
     -e SMTP_USER="your-email@gmail.com" \
     -e SMTP_PASSWORD="your-app-password" \
     -e DESTINATION_EMAIL="recipient@example.com" \
     sudoku-ocr
   ```

3. **Access the UI**:
   Open [http://localhost:8000](http://localhost:8000) in your browser.

## 🔧 API Endpoints

### `POST /process-sudoku`
Standard endpoint for production use.
- **Input**: `multipart/form-data` with a `file` field containing the image.
- **Output**: JSON containing `grid_string` and processing statistics.

### `POST /debug/process`
Used for troubleshooting grid detection.
- **Input**: `multipart/form-data` with a `file` field.
- **Output**: JSON containing base64 encoded intermediate images (`thresh_image`, `warped_image`) and raw OCR output.

## 🛠️ Local Development (Manual)

### Prerequisites
- Python 3.10+
- System libraries for OpenCV and Paddle (see Dockerfile for list)

### Setup
```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 🏗️ CI/CD (GitHub Actions)

This repository includes a workflow to automatically build and push Docker images to Docker Hub. See `.github/workflows/docker-publish.yml` for details.
