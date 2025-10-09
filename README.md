# 🧾 Full-Stack Invoice OCR Data Extractor

A full-stack solution to extract structured data from invoice images/PDFs using OCR (Tesseract), advanced regex parsing, and export results to CSV.

## 📂 Repository Contents

- `invoice_ocr_api.py` — Python FastAPI backend
- `invoice_streamlit_app.py` — Python Streamlit frontend

## 🛠️ Prerequisites

- Python 3.8+
- Tesseract OCR (installed and accessible from command line)

## 🚀 Backend Setup (FastAPI)

Handles file upload, image preprocessing, OCR, parsing, and CSV generation.

**Installation**

1. Create a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
2. Install dependencies:
    ```bash
    pip install fastapi uvicorn pydantic python-multipart Pillow opencv-python numpy pytesseract
    ```
    > **Note:** Ensure Tesseract executable is installed on your OS.

**Running the Backend**

1. Save backend code as `invoice_ocr_api.py`.
2. Start the backend:
    ```bash
    uvicorn invoice_ocr_api:app --reload
    ```
3. API available at [http://localhost:8000](http://localhost:8000).

## 🖥️ Frontend Setup (Streamlit)

Provides a Python-based interface for interacting with the FastAPI backend.

**Installation**

1. Activate your virtual environment.
2. Install dependencies:
    ```bash
    pip install streamlit requests pandas
    ```

**Running the Frontend**

1. Save frontend code as `invoice_streamlit_app.py`.
2. Ensure backend is running.
3. Start the frontend:
    ```bash
    streamlit run invoice_streamlit_app.py
    ```
4. App opens in browser (e.g., [http://localhost:8501](http://localhost:8501)).

## 📄 Features

| Feature             | Location                   | Details                                               |
|---------------------|---------------------------|-------------------------------------------------------|
| OCR/Parsing Logic   | `invoice_ocr_api.py`       | Uses pytesseract and regex parsing (backend)          |
| FastAPI Endpoints   | `invoice_ocr_api.py`       | POST `/upload-invoice`, GET `/download-csv/{id}`      |
| Frontend UI         | `invoice_streamlit_app.py` | Simple UI with Streamlit (frontend)                   |
| API Communication   | `invoice_streamlit_app.py` | Uses requests to talk to backend                      |
| CSV Download        | `invoice_streamlit_app.py` | Uses Streamlit's `st.download_button`                 |

## 📦 Project Structure

```
.
├── invoice_ocr_api.py         # FastAPI backend for OCR and parsing
├── invoice_streamlit_app.py   # Streamlit frontend for UI
├── README.md                  # Project documentation
└── requirements.txt           # Python dependencies (optional)
```

## 📝 Usage Example

1. **Start the backend:**
    ```bash
    uvicorn invoice_ocr_api:app --reload
    ```
2. **Start the frontend:**
    ```bash
    streamlit run invoice_streamlit_app.py

    3. **Process invoices:**
        - In the Streamlit app, upload your invoice image or PDF.
        - The backend will extract and parse invoice data automatically.
        - Review the structured results in the app.
        - Download the extracted data as a CSV file for further use.

3. **Upload an invoice:**
    - Use Streamlit UI to upload invoice image or PDF.
    - View extracted data and download CSV.

## 📚 Resources

- [Tesseract OCR Documentation](https://github.com/tesseract-ocr/tesseract)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)

## 📝 License

Licensed under the MIT License.
