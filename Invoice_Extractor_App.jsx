import React, { useState, useCallback, useRef } from 'react';
import { Download, UploadCloud, FileText, X } from 'lucide-react';

// --- Configuration ---
const API_BASE_URL = 'http://localhost:8000'; // Match the FastAPI server address

// --- Utility Components ---

const LoadingSpinner = () => (
    <div className="flex items-center justify-center space-x-2">
        <div className="w-4 h-4 rounded-full bg-blue-500 animate-pulse"></div>
        <div className="w-4 h-4 rounded-full bg-blue-500 animate-pulse delay-75"></div>
        <div className="w-4 h-4 rounded-full bg-blue-500 animate-pulse delay-150"></div>
    </div>
);

const LineItemsTable = ({ items }) => (
    <div className="mt-6 border border-gray-200 rounded-lg shadow-inner overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
                <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Description</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Quantity</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Unit Price</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Line Total</th>
                </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
                {items.length > 0 ? items.map((item, index) => (
                    <tr key={index} className="hover:bg-indigo-50/50 transition-colors">
                        <td className="px-6 py-4 whitespace-normal text-sm font-medium text-gray-900 w-1/2">{item.description}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 text-right">{item.quantity ?? 'N/A'}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 text-right">${(item.unit_price ?? 0).toFixed(2)}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-semibold text-right">${(item.line_total ?? 0).toFixed(2)}</td>
                    </tr>
                )) : (
                    <tr>
                        <td colSpan="4" className="px-6 py-4 text-center text-sm text-gray-500 italic">No line items could be parsed.</td>
                    </tr>
                )}
            </tbody>
        </table>
    </div>
);

const HeaderDetails = ({ data }) => (
    <dl className="grid grid-cols-1 gap-x-4 gap-y-8 sm:grid-cols-2 lg:grid-cols-3 p-4 bg-white rounded-lg shadow-md border border-gray-100">
        {[
            { label: "Invoice ID", value: data.invoice_id },
            { label: "Vendor Name", value: data.vendor_name || 'N/A' },
            { label: "Invoice Number", value: data.invoice_number || 'N/A' },
            { label: "Date", value: data.date || 'N/A' },
            { label: "GST/Tax ID", value: data.gst_number || 'N/A' },
            { label: "Tax Amount", value: data.tax_amount ? `$${data.tax_amount.toFixed(2)}` : 'N/A' },
            { label: "Total Amount", value: data.total_amount ? `$${data.total_amount.toFixed(2)}` : 'N/A', className: 'sm:col-span-2 lg:col-span-1 text-2xl font-bold text-indigo-600' },
        ].map((item, index) => (
            <div key={index} className="sm:col-span-1">
                <dt className="text-sm font-medium text-gray-500">{item.label}</dt>
                <dd className={`mt-1 text-lg font-medium text-gray-900 ${item.className || ''}`}>{item.value}</dd>
            </div>
        ))}
    </dl>
);

// --- Main Application Component ---

export default function App() {
    const [file, setFile] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [parsedData, setParsedData] = useState(null);
    const [error, setError] = useState(null);
    const [progress, setProgress] = useState(0); // Mock progress
    
    const fileInputRef = useRef(null);

    const handleFileChange = (selectedFile) => {
        if (selectedFile && ['image/jpeg', 'image/png', 'application/pdf', 'image/tiff'].includes(selectedFile.type)) {
            setFile(selectedFile);
            setError(null);
            setParsedData(null);
        } else {
            setError("Unsupported file type. Please upload a JPG, PNG, TIFF, or PDF invoice.");
            setFile(null);
        }
    };

    const handleDrop = useCallback((event) => {
        event.preventDefault();
        event.stopPropagation();
        if (event.dataTransfer.files && event.dataTransfer.files[0]) {
            handleFileChange(event.dataTransfer.files[0]);
        }
    }, []);

    const handleDragOver = useCallback((event) => {
        event.preventDefault();
        event.stopPropagation();
    }, []);

    const handleUpload = async () => {
        if (!file) {
            setError("Please select a file to upload.");
            return;
        }

        setIsLoading(true);
        setError(null);
        setParsedData(null);
        
        const formData = new FormData();
        formData.append('file', file);

        try {
            // Mock progress bar
            const interval = setInterval(() => {
                setProgress(prev => (prev < 90 ? prev + 10 : 90));
            }, 300);

            const response = await fetch(`${API_BASE_URL}/upload-invoice`, {
                method: 'POST',
                body: formData,
            });
            
            clearInterval(interval);
            setProgress(100);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error! Status: ${response.status}`);
            }

            const data = await response.json();
            setParsedData(data);

        } catch (err) {
            console.error("Upload error:", err.message);
            setError(`Extraction Failed: ${err.message}. Please ensure the backend is running.`);
            setParsedData(null);
            setProgress(0);
        } finally {
            setIsLoading(false);
            setTimeout(() => setProgress(0), 500); // Reset progress after a short delay
        }
    };
    
    const handleDownloadCSV = async () => {
        if (!parsedData || !parsedData.invoice_id) return;
        
        try {
            const response = await fetch(`${API_BASE_URL}/download-csv/${parsedData.invoice_id}`);
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error! Status: ${response.status}`);
            }

            // Create a blob from the response and trigger download
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `invoice_data_${parsedData.invoice_id}.csv`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            
        } catch (err) {
            setError(`CSV Download Failed: ${err.message}.`);
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 font-inter p-4 sm:p-8">
            <div className="max-w-6xl mx-auto">
                <header className="py-6 mb-8 text-center border-b border-indigo-100">
                    <h1 className="text-4xl font-extrabold text-indigo-700">
                        Smart Invoice Data Extractor
                    </h1>
                    <p className="mt-2 text-lg text-gray-500">
                        OCR & Regex Parsing for Structured Data Conversion
                    </p>
                </header>

                {/* Upload Section */}
                <section className="mb-10 p-6 bg-white rounded-xl shadow-lg border border-indigo-100">
                    <h2 className="text-2xl font-semibold text-gray-800 mb-4">1. Upload Invoice File</h2>
                    
                    <div 
                        onDrop={handleDrop} 
                        onDragOver={handleDragOver}
                        onClick={() => fileInputRef.current?.click()}
                        className={`border-4 border-dashed rounded-lg p-12 text-center transition-colors cursor-pointer 
                                   ${file ? 'border-green-400 bg-green-50' : 'border-indigo-300 hover:border-indigo-500 bg-indigo-50'}`}
                    >
                        <input 
                            type="file" 
                            ref={fileInputRef} 
                            onChange={(e) => handleFileChange(e.target.files[0])} 
                            accept=".jpg,.jpeg,.png,.pdf,.tiff"
                            className="hidden"
                        />
                        <UploadCloud className="w-12 h-12 mx-auto text-indigo-500" />
                        <p className="mt-2 text-gray-600 font-medium">
                            {file ? `File Selected: ${file.name}` : "Drag and drop your invoice here, or click to select file (JPG, PNG, PDF)"}
                        </p>
                    </div>

                    {/* Status and Action */}
                    <div className="mt-4 flex flex-col sm:flex-row justify-between items-center space-y-4 sm:space-y-0">
                        {error && (
                            <div className="flex items-center text-red-600 text-sm font-medium p-2 bg-red-50 rounded-lg">
                                <X className="w-4 h-4 mr-1"/> {error}
                            </div>
                        )}
                        <button
                            onClick={handleUpload}
                            disabled={!file || isLoading}
                            className={`px-8 py-3 rounded-xl font-bold text-white transition-all duration-300 shadow-md
                                       ${!file || isLoading ? 'bg-gray-400 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-700 hover:shadow-lg'}`}
                        >
                            {isLoading ? <LoadingSpinner /> : "Extract Data"}
                        </button>
                    </div>
                    
                    {/* Progress Bar */}
                    {isLoading && (
                        <div className="w-full mt-4 bg-gray-200 rounded-full h-2.5">
                            <div className="bg-indigo-600 h-2.5 rounded-full transition-all duration-500" style={{ width: `${progress}%` }}></div>
                        </div>
                    )}
                </section>
                
                {/* Results Section */}
                {parsedData && (
                    <section className="p-6 bg-white rounded-xl shadow-lg border border-green-200 animate-fadeIn">
                        <div className="flex justify-between items-center mb-6 border-b pb-4">
                            <h2 className="text-2xl font-semibold text-green-700 flex items-center">
                                <FileText className="w-6 h-6 mr-2"/>
                                2. Parsed Results (Success)
                            </h2>
                            <button
                                onClick={handleDownloadCSV}
                                className="flex items-center px-4 py-2 bg-green-500 text-white font-medium rounded-lg hover:bg-green-600 transition-colors shadow-md"
                            >
                                <Download className="w-5 h-5 mr-2" />
                                Download CSV
                            </button>
                        </div>

                        <h3 className="text-xl font-bold text-gray-800 mb-4">Invoice Header Summary</h3>
                        <HeaderDetails data={parsedData} />

                        <h3 className="text-xl font-bold text-gray-800 mt-8 mb-4">Line Items</h3>
                        <LineItemsTable items={parsedData.line_items} />

                        <details className="mt-6 p-4 bg-gray-50 rounded-lg cursor-pointer">
                            <summary className="font-semibold text-indigo-600 hover:text-indigo-800 transition-colors">
                                View Raw Extracted Text (For Debugging)
                            </summary>
                            <pre className="mt-2 text-sm text-gray-700 whitespace-pre-wrap break-words max-h-60 overflow-y-auto p-3 border rounded bg-white">
                                {parsedData.raw_text}
                            </pre>
                        </details>

                    </section>
                )}
            </div>
        </div>
    );
}
