# Use a Python base image with a Linux distribution (like Debian/Ubuntu)
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install Tesseract OCR and dependencies (essential for your project!)
# The apt-get commands install the Tesseract program itself.
RUN apt-get update && \
    apt-get install -y tesseract-ocr libtesseract-dev && \
    apt-get clean

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port (FastAPI default)
EXPOSE 8000

# Command to run the application using Gunicorn (a robust server for production)
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "invoice_ocr_api:app", "--bind", "0.0.0.0:8000"]
