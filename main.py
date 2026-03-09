import cv2
import numpy as np
from paddleocr import PaddleOCR
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import io
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Enable CORS for local testing and web access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OCR (CPU version)
ocr = None
ocr_init_error = None
try:
    ocr = PaddleOCR(use_angle_cls=False, lang='en')
except Exception as e:
    ocr_init_error = str(e)
    logger.error(f"Failed to initialize OCR: {e}")

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
MAX_DIMENSION = 10000

from fastapi.responses import FileResponse
import os

@app.get("/")
async def get_ui():
    return FileResponse("index.html")

def image_to_base64(img):
    if img is None:
        return None
    try:
        _, buffer = cv2.imencode('.png', img)
        return base64.b64encode(buffer).decode('utf-8')
    except Exception as e:
        logger.error(f"Base64 conversion failed: {e}")
        return None

def warp_grid(img):
    debug_steps = {}
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (9, 9), 0)
        
        # Adaptive thresholding for varying lighting conditions
        thresh = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        debug_steps['thresh_raw'] = thresh
        
        # Morphological Closing to connect broken grid lines
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
        debug_steps['thresh'] = thresh
        
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 5000: continue # Filter out small noise
            
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            
            # Look for 4-sided contours that are somewhat square-ish
            if len(approx) == 4:
                pts = approx.reshape(4, 2)
                rect = np.zeros((4, 2), dtype="float32")
                s = pts.sum(axis=1)
                rect[0] = pts[np.argmin(s)] # TL
                rect[2] = pts[np.argmax(s)] # BR
                diff = np.diff(pts, axis=1)
                rect[1] = pts[np.argmin(diff)] # TR
                rect[3] = pts[np.argmax(diff)] # BL
                
                # Check squareness (Aspect Ratio)
                w = np.linalg.norm(rect[1] - rect[0])
                h = np.linalg.norm(rect[3] - rect[0])
                aspect_ratio = w / h if h > 0 else 0
                
                if 0.75 < aspect_ratio < 1.35:
                    dst = np.array([[0,0], [899,0], [899,899], [0,899]], dtype="float32")
                    M = cv2.getPerspectiveTransform(rect, dst)
                    warped = cv2.warpPerspective(img, M, (900, 900))
                    debug_steps['warped'] = warped
                    return warped, debug_steps
                    
    except Exception as e:
        logger.error(f"Warp perspective failed: {e}")
    return img, debug_steps

@app.post("/debug/process")
async def debug_process(file: UploadFile = File(...)):
    """Special endpoint that returns intermediate processing steps for debugging."""
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large. Max {MAX_FILE_SIZE / 1024 / 1024}MB")
    
    try:
        nparr = np.frombuffer(content, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image file")
            
        warped, steps = warp_grid(img)
        
        response_data = {
            "success": True,
            "thresh_image": image_to_base64(steps.get('thresh')),
            "warped_image": image_to_base64(steps.get('warped'))
        }
        
        if 'warped' in steps and ocr:
            try:
                result = ocr.ocr(steps['warped'])
                response_data["raw_ocr_result"] = str(result)
            except Exception as e:
                response_data["ocr_error"] = str(e)
                
        return response_data
    except Exception as e:
        logger.error(f"Debug process failed: {e}")
        return {"success": False, "error": str(e)}

@app.post("/process-sudoku")
async def process(file: UploadFile = File(...)):
    if not ocr:
        raise HTTPException(status_code=500, detail=f"OCR engine not initialized: {ocr_init_error}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_FILE_SIZE / 1024 / 1024}MB")
    
    try:
        nparr = np.frombuffer(content, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        height, width = img.shape[:2]
        if height > MAX_DIMENSION or width > MAX_DIMENSION:
            raise HTTPException(status_code=400, detail=f"Image dimensions too large. Max {MAX_DIMENSION}x{MAX_DIMENSION}")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Image validation error: {e}")
        raise HTTPException(status_code=400, detail=f"Error processing image input: {str(e)}")

    try:
        warped, _ = warp_grid(img)
        result = ocr.ocr(warped)
        
        grid = [["0" for _ in range(9)] for _ in range(9)]
        if result and result[0]:
            for line in result[0]:
                coords = line[0]
                val = line[1][0]
                if val.isdigit():
                    cx = sum([p[0] for p in coords]) / 4
                    cy = sum([p[1] for p in coords]) / 4
                    col, row = int(cx // 100), int(cy // 100)
                    if 0 <= col < 9 and 0 <= row < 9:
                        grid[row][col] = val[0]

        grid_string = "".join(["".join(r) for r in grid])
        filled_cells = sum(1 for c in grid_string if c != '0')
        
        return {
            "success": True,
            "grid_string": grid_string,
            "statistics": {
                "filled_cells": filled_cells,
                "empty_cells": 81 - filled_cells,
                "image_size_kb": len(content) // 1024
            }
        }
    except Exception as e:
        logger.error(f"OCR process failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }