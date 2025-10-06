# Use a Python base image with a Linux distribution (like Debian/Ubuntu)
FROM python:3.10-slim

# Set working directory in the container
WORKDIR /app

# Install Tesseract OCR and dependencies (essential for your project!)
# The apt-get commands install the Tesseract program itself.
RUN apt-get update && \
    apt-get install -y tesseract-ocr libtesseract-dev && \
    apt-get clean

# Copy only the requirements file first for faster layered caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- CRITICAL FIX FOR PATH ---
# If your files (invoice_ocr_api.py) are inside a 'backend' folder in your repo,
# you must ensure they are copied to the root WORKDIR (/app) in the container.
# If your Dockerfile is in the 'backend' folder, use this:
COPY . .
# If your Dockerfile is in the repo root and your files are in 'backend', use:
# COPY backend/ .

# Expose the port (FastAPI default)
EXPOSE 8000

# Command to run the application using Gunicorn
# This command is now correct and MUST be placed directly in Render's Start Command field
# to avoid it being ignored.
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "invoice_ocr_api:app", "--bind", "0.0.0.0:8000"]
