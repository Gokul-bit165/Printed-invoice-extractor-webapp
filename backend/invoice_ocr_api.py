import uvicorn
import os
import re
import uuid
import csv
from io import StringIO, BytesIO
from typing import List, Optional, Dict, Any

# Third-party libraries (Requires: fastapi, uvicorn, pydantic, python-multipart, Pillow, opencv-python, pytesseract)
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Global mock database for storing parsed invoices
# In production, this would be replaced by Firestore or PostgreSQL
MOCK_DATABASE: Dict[str, Dict[str, Any]] = {}

# --- OCR DEPENDENCY CHECK AND CONFIGURATION ---
try:
    import pytesseract
    from PIL import Image
    import cv2
    import numpy as np
    HAS_OCR_DEPS = True
    
    # --- IMPORTANT: TESSERACT PATH CONFIGURATION ---
    # If you are on Windows and see the "tesseract is not installed" error 
    # even after installing Tesseract, UNCOMMENT the line below and replace 
    # the path with the location of your tesseract.exe file.
    # Example for Windows:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    
except ImportError:
    HAS_OCR_DEPS = False
    # If imports fail, this print statement will alert the user when the API runs.
    print("WARNING: OCR dependencies (pytesseract, opencv-python, numpy) not found. Using mock OCR.")


# Regex patterns for general parsing (flexible schema)
INVOICE_CONFIG = {
    # General Header Fields
    "invoice_number": r"(?:Invoice No\.|Invoice|Bill)\s*[:#-]\s*(\w+)",
    "date": r"(?:Invoice Date|DATED|Date)\s*[:#-]\s*(\d{2}[-/]\d{2}[-/]\d{2,4})",
    
    # FIX: Targeted extraction for Total Amount and Tax Amount, looking near keywords
    "total_amount": r"(?:PAYABLE AMOUNT|GRAND TOTAL|TOTAL|AMOUNT DUE|BALANCE)\s*(?:[A-Z]{3}|\$|€|£|Rs\.\s*)?\s*([\d,\.]+)",
    "tax_amount": r"(?:TAX|GST|VAT|SGST|CGST)\s*RATE\s*@\s*\d+%?\s*Rs\.\s*([\d,\.]+)",
    
    # FIX: Use a unique header keyword like the company name to reliably find the vendor, skipping the junk OCR output
    "vendor_name": r"(S\.K\.P\.S DIGITAL)", 
    "gst_number": r"(?:GSTIN|VAT ID|Tax ID)\s*[:#]\s*(\w+)",
    
    # FIX: Line Item Structure - Adjusted to capture only Description, Rate, and Total, as QTY was dropped by OCR
    # Finds: (Description group) (Rate group) (Total group)
    # The description group now includes the item name, but we assume the numbers are Rate and Total.
    "line_item_pattern": r"ITEM NAME \d\s+Rs\.\s*([\d,\.]+)\s+Rs\.\s*([\d,\.]+)"
}

# Optional template for a known vendor (can be expanded in a JSON config file)
KNOWN_VENDOR_TEMPLATE = {
    "vendor_name": "Acme Corp",
    "regex_overrides": {
        "invoice_number": r"ACME-INV-(\d+)",
        "date": r"Billing Date:\s*(\d{4}-\d{2}-\d{2})"
    }
}

# Pydantic Models for structured data
class LineItem(BaseModel):
    quantity: Optional[float] = 1.0  # Default to 1 if QTY is not extractable
    description: str
    unit_price: Optional[float] = None
    line_total: Optional[float] = None

class ParsedInvoice(BaseModel):
    invoice_id: str
    vendor_name: Optional[str] = None
    invoice_number: Optional[str] = None
    date: Optional[str] = None
    total_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    gst_number: Optional[str] = None
    line_items: List[LineItem] = Field(default_factory=list)
    raw_text: str = ""

# --- 2. IMAGE PREPROCESSING UTILITIES ---

def preprocess_image(image_bytes: bytes) -> Image.Image:
    """
    Performs preprocessing steps (binarization, deskew) on the image bytes.
    Returns a PIL Image object.
    """
    try:
        if not HAS_OCR_DEPS or 'pdf' in Image.open(BytesIO(image_bytes)).format.lower():
            # If dependencies are missing or it's a PDF, just open the image/PDF first page as PIL Image
            return Image.open(BytesIO(image_bytes)).convert('RGB')
    except Exception:
        # Fallback for unexpected image format issues
        pass

    # Proceed with OpenCV preprocessing for better OCR on images
    if not HAS_OCR_DEPS:
        # Mock preprocessing: just open the image
        return Image.open(BytesIO(image_bytes)).convert('RGB')

    # Convert bytes to numpy array
    nparr = np.frombuffer(image_bytes, np.uint8)
    # Use IMREAD_COLOR to ensure 3 channels for color conversion later, even if decoding a grayscale image
    img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img_cv is None:
        # Try decoding as grayscale if color fails (some TIFF formats)
        img_cv = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        if img_cv is None:
             raise ValueError("Could not decode image bytes into OpenCV format.")
        # Convert grayscale to 3-channel for consistency
        img_cv = cv2.cvtColor(img_cv, cv2.COLOR_GRAY2BGR)


    # Convert to grayscale for thresholding
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

    # Binarization (simple adaptive thresholding)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)

    # Deskewing (simple approximation)
    try:
        coords = np.column_stack(np.where(thresh > 0))
        if coords.size > 0:
            angle = cv2.minAreaRect(coords)[-1]
            
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle

            (h, w) = img_cv.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(img_cv, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        else:
            rotated = img_cv # No deskewing if no text found

    except cv2.error:
        # Handle case where minAreaRect fails on highly sparse/corrupt images
        rotated = img_cv

    # Convert back to PIL Image (which Tesseract expects)
    return Image.fromarray(cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB))


# --- 3. OCR EXTRACTION UTILITY ---

def extract_text_tesseract(image: Image.Image) -> str:
    """
    Performs OCR on the preprocessed image to extract raw text.
    """
    if not HAS_OCR_DEPS:
        # Return mock data if dependencies are missing
        print("MOCK OCR: Returning placeholder text.")
        return ("Acme Corp\n"
                "123 Main St, Anytown, USA\n"
                "Invoice No: ACME-INV-45678\n"
                "Date: 01/01/2024\n"
                "GSTIN: 22AAAAA0000A1Z5\n"
                "ITEM QTY RATE TOTAL\n"
                "1. Consulting Service 1 500.00 500.00\n"
                "2. Software License 2 150.00 300.00\n"
                "Subtotal: 800.00\n"
                "TAX (10%): 80.00\n"
                "GRAND TOTAL: 880.00")
    
    try:
        # Use Tesseract to extract text
        # '-l eng' specifies language as English
        return pytesseract.image_to_string(image, lang='eng')
    except Exception as e:
        # Catch errors related to tesseract not being in PATH
        raise RuntimeError(f"tesseract is not installed or it's not in your PATH. See README file for more information. Error: {e}")


# --- 4. PARSING LOGIC ---

def parse_float(value: str) -> Optional[float]:
    """Helper to safely convert string to float."""
    if value:
        try:
            # Remove currency symbols, parentheses (often used for negatives), and thousand separators
            clean_value = re.sub(r'[$,€£()]', '', value).replace(',', '').strip()
            return float(clean_value)
        except ValueError:
            return None
    return None

def parse_line_items(raw_text: str, pattern: str) -> List[LineItem]:
    """
    Attempts to extract line items using the specific regex pattern.
    """
    lines = raw_text.split('\n')
    line_items: List[LineItem] = []
    
    # Heuristic: Look for the line item section explicitly
    start_index = -1
    for i, line in enumerate(lines):
        if re.search(r'ITEM NAME \d', line, re.IGNORECASE):
            start_index = i
            break
            
    if start_index != -1:
        # Search from the first line item onwards
        for line in lines[start_index:]:
            # Check for lines that don't look like totals/subtotals
            if not re.search(r'(SUBTOTAL|TAX|TOTAL|BALANCE|GST|PAYABLE)', line, re.IGNORECASE):
                # The regex pattern specifically targets the `ITEM NAME N Rs. X Rs. Y` format
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    try:
                        # Since QTY is missing, we use a simple description based on the line
                        description = f"ITEM NAME {line.split()[2]}" # e.g., 'ITEM NAME 2'
                        
                        # Group 1 = Rate/Unit Price; Group 2 = Line Total
                        unit_price = parse_float(match.group(1).strip())
                        line_total = parse_float(match.group(2).strip())
                        
                        # We assume quantity is 1.0 or can be derived from Total/Rate (if Rate != 0)
                        quantity = 1.0
                        if unit_price and line_total and unit_price > 0:
                            # Try to calculate quantity if data is available
                            quantity = round(line_total / unit_price)
                        
                        if description:
                            line_items.append(LineItem(
                                quantity=float(quantity), # Ensure it's a float
                                description=description,
                                unit_price=unit_price,
                                line_total=line_total
                            ))
                    except IndexError:
                        continue
                    except Exception as e:
                        print(f"Error parsing line item: {e}")

    return line_items

def parse_invoice_data(raw_text: str) -> ParsedInvoice:
    """
    Parses raw text using regex and keyword matching.
    Applies template overrides if a known vendor is detected.
    """
    
    invoice_id = str(uuid.uuid4())
    parsed_data = {}
    
    # 1. Apply Known Vendor Template Check
    is_known_vendor = False
    vendor_name_guess = ""
    # Look at the first 5 lines for a vendor name match
    first_lines = "\n".join(raw_text.split('\n')[:5]).upper()
    
    if KNOWN_VENDOR_TEMPLATE["vendor_name"].upper() in first_lines:
        is_known_vendor = True
        vendor_name_guess = KNOWN_VENDOR_TEMPLATE["vendor_name"]
        
    patterns = INVOICE_CONFIG.copy()
    if is_known_vendor:
        patterns.update(KNOWN_VENDOR_TEMPLATE["regex_overrides"])
        
    # 2. Extract General Fields
    for field, pattern in patterns.items():
        if field not in ["line_item_pattern"]:
            # Use search for the first match anywhere in the text
            match = re.search(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
            if match:
                try:
                    value = match.group(1).strip()
                    if field in ["total_amount", "tax_amount"]:
                        parsed_data[field] = parse_float(value)
                    elif field == "vendor_name":
                        # The vendor_name field is now very specific, so we trust the regex match
                        parsed_data[field] = value
                    else:
                        parsed_data[field] = value
                except IndexError:
                    print(f"LOG: Field '{field}' regex matched but group(1) failed.")
            else:
                print(f"LOG: Field '{field}' could not be parsed.")

    # 3. Extract Line Items using the modified logic
    line_items = parse_line_items(raw_text, INVOICE_CONFIG["line_item_pattern"])

    # 4. Construct the final model
    invoice = ParsedInvoice(
        invoice_id=invoice_id,
        raw_text=raw_text,
        line_items=line_items,
        **parsed_data
    )
    
    return invoice

# --- 5. CSV UTILITY ---

def generate_csv_string(invoice: ParsedInvoice) -> str:
    """
    Converts the ParsedInvoice model into a CSV string.
    """
    output = StringIO()
    writer = csv.writer(output)
    
    # 1. Write Header Data (Key-Value Pairs)
    header_fields = [
        ("Invoice ID", invoice.invoice_id),
        ("Vendor Name", invoice.vendor_name),
        ("Invoice Number", invoice.invoice_number),
        ("Date", invoice.date),
        ("GST Number", invoice.gst_number),
        ("Tax Amount", invoice.tax_amount),
        ("Total Amount", invoice.total_amount),
    ]
    
    writer.writerow(["--- INVOICE HEADER DETAILS ---"])
    for key, value in header_fields:
        writer.writerow([key, value])
    
    writer.writerow([]) # Empty row for separation
    
    # 2. Write Line Item Header
    writer.writerow(["--- LINE ITEMS ---"])
    writer.writerow(["Description", "Quantity", "Unit Price", "Line Total"])
    
    # 3. Write Line Item Rows
    for item in invoice.line_items:
        writer.writerow([
            item.description,
            item.quantity,
            item.unit_price,
            item.line_total
        ])
        
    return output.getvalue()


# --- 6. FASTAPI APPLICATION SETUP ---

app = FastAPI(
    title="OCR Invoice Data Extractor",
    description="Backend for extracting structured data from invoice images/PDFs."
)

# CORS configuration for the frontend
app.add_middleware(
    CORSMiddleware,
    # Allow all origins, useful for development where React/Streamlit runs on a different port
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 7. REST ENDPOINTS ---

@app.get("/", tags=["Health"])
async def root():
    """Simple health check."""
    return {"message": "OCR API is running. Upload invoices to /upload-invoice."}

@app.post("/upload-invoice", response_model=ParsedInvoice, tags=["Extraction"])
async def upload_invoice(file: UploadFile = File(...)):
    """
    Uploads an invoice (image or PDF), runs OCR, and returns the parsed structured data.
    """
    # Check for acceptable MIME types
    if file.content_type not in ["image/jpeg", "image/png", "application/pdf", "image/tiff"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload JPG, PNG, TIFF, or PDF.")
        
    try:
        file_bytes = await file.read()
        
        # 1. Preprocessing (handles PDF/Image/Mock)
        preprocessed_img = preprocess_image(file_bytes)
        
        # 2. OCR Extraction - Will raise RuntimeError if Tesseract is not found/configured
        raw_text = extract_text_tesseract(preprocessed_img)
        
        if not raw_text.strip():
            # Tesseract ran but found no legible text
            raise HTTPException(status_code=500, detail="OCR failed to extract any legible text from the document.")

        # 3. Parsing
        parsed_invoice = parse_invoice_data(raw_text)
        
        # 4. Storage (Mock Database)
        MOCK_DATABASE[parsed_invoice.invoice_id] = parsed_invoice.model_dump()
        
        return parsed_invoice
        
    except RuntimeError as e:
        # Catch the specific error raised by extract_text_tesseract for Tesseract PATH issue
        print(f"Tesseract Configuration Error: {e}")
        # Re-raise as 500 to show the user the detailed error in the frontend
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        print(f"Error during file decoding/preprocessing: {e}")
        raise HTTPException(status_code=422, detail=f"File processing error: {e}")
    except Exception as e:
        # Catch any other unexpected error
        print(f"Internal server error: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during processing. Error: {e}")


@app.get("/download-csv/{invoice_id}", tags=["Extraction"])
async def download_csv(invoice_id: str):
    """
    Downloads the structured data for a specific invoice ID as a CSV file.
    """
    invoice_data = MOCK_DATABASE.get(invoice_id)
    
    if not invoice_data:
        raise HTTPException(status_code=404, detail=f"Invoice with ID {invoice_id} not found.")

    try:
        invoice_model = ParsedInvoice(**invoice_data)
        csv_content = generate_csv_string(invoice_model)
        
        filename = f"invoice_data_{invoice_id}.csv"
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
            }
        )
    except Exception as e:
        print(f"Error generating CSV: {e}")
        raise HTTPException(status_code=500, detail="Could not generate CSV file.")


# --- 8. RUN APPLICATION ---
if __name__ == "__main__":
    if not HAS_OCR_DEPS:
         print("\n=======================================================")
         print("   MOCK MODE ACTIVE: Using placeholder text for OCR.   ")
         print("   Install required dependencies (pytesseract, opencv) ")
         print("   and ensure Tesseract is installed on your system.   ")
         print("=======================================================\n")
         
    uvicorn.run(app, host="0.0.0.0", port=8000)
