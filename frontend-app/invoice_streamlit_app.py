import streamlit as st
import requests
import pandas as pd
from typing import Dict, Any, Optional

# Configuration
# NOTE: Ensure your FastAPI backend (invoice_ocr_api.py) is running on port 8000
API_URL = "http://localhost:8000"
UPLOAD_ENDPOINT = f"{API_URL}/upload-invoice"
DOWNLOAD_ENDPOINT = f"{API_URL}/download-csv"

# Set up page config with a wide layout
st.set_page_config(
    page_title="Invoice Data Extractor (Streamlit)",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def display_parsed_data(parsed_data: Dict[str, Any]):
    """
    Displays the extracted header and line item data in a clean, metric-based format.
    """
    
    st.subheader("Invoice Header Summary")
    
    # Use columns to display key header metrics
    header_cols = st.columns(3)
    
    # Format Total Amount prominently
    total_amount = f"${parsed_data.get('total_amount', 0.0):.2f}" if parsed_data.get('total_amount') is not None else 'N/A'
    tax_amount = f"${parsed_data.get('tax_amount', 0.0):.2f}" if parsed_data.get('tax_amount') is not None else 'N/A'
    
    with header_cols[0]:
        st.metric(label="Invoice Number", value=parsed_data.get('invoice_number', 'N/A'))
    with header_cols[1]:
        st.metric(label="Vendor Name", value=parsed_data.get('vendor_name', 'N/A'))
    with header_cols[2]:
        st.metric(label="Date", value=parsed_data.get('date', 'N/A'))
    
    header_cols_2 = st.columns(3)
    with header_cols_2[0]:
        st.metric(label="GST/Tax ID", value=parsed_data.get('gst_number', 'N/A'))
    with header_cols_2[1]:
        st.metric(label="Tax Amount", value=tax_amount)
    with header_cols_2[2]:
        st.metric(label="**GRAND TOTAL**", value=total_amount)
    
    st.divider()

    st.subheader("Line Items")

    line_items = parsed_data.get('line_items', [])
    if line_items:
        # Convert list of dictionaries to a Pandas DataFrame for structured display
        df = pd.DataFrame(line_items)
        # Select and rename columns for a user-friendly view
        df = df[['description', 'quantity', 'unit_price', 'line_total']] 
        df.columns = ['Description', 'Quantity', 'Unit Price', 'Line Total']
        
        st.dataframe(df, use_container_width=True, height=len(df)*35 + 38)
    else:
        st.info("No structured line items were extracted. Please check the raw text.")

    # Raw text for debugging/verification
    with st.expander("View Raw Extracted Text"):
        st.code(parsed_data.get('raw_text', 'No raw text available.'), language='text')

def handle_file_upload(uploaded_file: Optional[st.runtime.uploaded_file_manager.UploadedFile]):
    """Handles the file upload, API call, and result display."""
    if uploaded_file is None:
        # Clear state if file is removed
        if 'parsed_data' in st.session_state:
            del st.session_state['parsed_data']
        return

    st.info(f"Uploading and processing file: **{uploaded_file.name}**...")

    # Prepare file payload for the FastAPI endpoint
    files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
    
    try:
        # Call the FastAPI upload endpoint
        with st.spinner('Extracting text and parsing data...'):
            response = requests.post(UPLOAD_ENDPOINT, files=files)
            
        if response.status_code == 200:
            parsed_data = response.json()
            st.session_state['parsed_data'] = parsed_data
            
            st.success("Data successfully extracted!")
            display_parsed_data(parsed_data)

            # CSV Download Button implementation
            invoice_id = parsed_data['invoice_id']
            download_url = f"{DOWNLOAD_ENDPOINT}/{invoice_id}"
            
            # Fetch CSV content directly from the backend
            csv_response = requests.get(download_url)
            
            if csv_response.status_code == 200:
                st.download_button(
                    label="📥 Download Structured CSV",
                    data=csv_response.content, 
                    file_name=f"invoice_data_{invoice_id}.csv",
                    mime="text/csv",
                    type="primary"
                )
            else:
                 st.warning("Could not automatically retrieve CSV for download.")

        else:
            # Handle API errors (e.g., file type, OCR failure)
            error_detail = response.json().get('detail', f"Status code {response.status_code}")
            st.error(f"Extraction Failed (API Error): {error_detail}")
            st.session_state['parsed_data'] = None

    except requests.exceptions.ConnectionError:
        st.error(f"**Connection Error:** Could not connect to the FastAPI backend at {API_URL}. Please ensure the Python backend (`invoice_ocr_api.py`) is running.")
        st.session_state['parsed_data'] = None
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        st.session_state['parsed_data'] = None

# --- Main App Layout ---

st.title("📄 Smart Invoice Data Extractor")
st.markdown("**:blue[Streamlit Frontend]** - Upload your invoice file to the running FastAPI backend for processing.")

st.divider()

# File Uploader component
uploaded_file = st.file_uploader(
    "1. Upload Invoice (JPG, PNG, TIFF, or PDF)",
    type=['jpg', 'jpeg', 'png', 'pdf', 'tiff'],
    accept_multiple_files=False,
    help="Select a single invoice file for OCR and structured data extraction."
)

# Call the handler function when a file is uploaded or changed
if uploaded_file:
    handle_file_upload(uploaded_file)
    
elif 'parsed_data' in st.session_state and st.session_state['parsed_data'] is not None:
    # This prevents the previous results from flashing if the user clicks away
    del st.session_state['parsed_data']
