"""
Gemini API Fallback Module
Uses Google Gemini API for invoice extraction when regex fails.
"""

import os
import json
from typing import Optional
from dataclasses import asdict

# Try to load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import InvoiceData class
try:
    from invoice_parser import InvoiceData, parse_date_to_standard, GSTIN_STATE_MAP
except ImportError:
    from .invoice_parser import InvoiceData, parse_date_to_standard, GSTIN_STATE_MAP


def get_gemini_api_key() -> Optional[str]:
    """Get Gemini API key from environment."""
    key = os.getenv("GEMINI_API_KEY")
    if key and "=" in key:
        # Handle format: GEMINI_API_KEY = value
        key = key.split("=", 1)[-1].strip()
    return key


def extract_with_gemini(pdf_text: str, invoice_type: str = "TAX_INVOICE") -> Optional[InvoiceData]:
    """
    Extract invoice data using Gemini API.
    
    Args:
        pdf_text: Raw text extracted from PDF
        invoice_type: Type of invoice (TAX_INVOICE or DEBIT)
        
    Returns:
        InvoiceData object or None if extraction fails
    """
    api_key = get_gemini_api_key()
    if not api_key:
        print("Gemini API key not found in environment")
        return None
    
    try:
        import google.generativeai as genai
    except ImportError:
        print("google-generativeai package not installed. Install with: pip install google-generativeai")
        return None
    
    # Configure Gemini
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # Create extraction prompt
    prompt = f"""Extract the following information from this airline invoice text and return as JSON:

{{
    "airline": "Name of the airline (Air India, IndiGo, Akasa Air, Gulf Air, Air India Express)",
    "invoice_number": "Invoice or Debit Note number",
    "invoice_date": "Date in DD-MMM-YYYY format",
    "customer_name": "Customer company name",
    "customer_gstin": "15-character GSTIN number",
    "place_of_supply": "State name",
    "state_code": "2-digit state code from GSTIN",
    "currency": "Currency code (usually INR)",
    "taxable_value": "Taxable amount as number",
    "non_taxable_value": "Non-taxable amount as number",
    "cgst_amount": "CGST amount as number",
    "sgst_amount": "SGST amount as number", 
    "igst_amount": "IGST amount as number",
    "total_amount": "Total invoice amount as number",
    "pnr": "PNR code",
    "passenger_name": "Passenger name",
    "flight_from": "3-letter departure airport code",
    "flight_to": "3-letter arrival airport code"
}}

Important:
- Return ONLY valid JSON, no markdown or extra text
- All amounts should be numbers without currency symbols or commas
- Date should be in DD-MMM-YYYY format (e.g., 15-MAY-2025)
- If a field is not found, use empty string for text or 0 for numbers

Invoice Text:
{pdf_text[:4000]}
"""
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean up response if it has markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])
        
        # Parse JSON response
        data_dict = json.loads(response_text)
        
        # Create InvoiceData object
        invoice = InvoiceData(
            airline=data_dict.get("airline", ""),
            invoice_number=data_dict.get("invoice_number", ""),
            invoice_date=data_dict.get("invoice_date", ""),
            invoice_type=invoice_type,
            customer_name=data_dict.get("customer_name", ""),
            customer_gstin=data_dict.get("customer_gstin", ""),
            place_of_supply=data_dict.get("place_of_supply", ""),
            state_code=data_dict.get("state_code", ""),
            currency=data_dict.get("currency", "INR"),
            taxable_value=float(data_dict.get("taxable_value", 0) or 0),
            non_taxable_value=float(data_dict.get("non_taxable_value", 0) or 0),
            cgst_amount=float(data_dict.get("cgst_amount", 0) or 0),
            sgst_amount=float(data_dict.get("sgst_amount", 0) or 0),
            igst_amount=float(data_dict.get("igst_amount", 0) or 0),
            total_amount=float(data_dict.get("total_amount", 0) or 0),
            pnr=data_dict.get("pnr", ""),
            passenger_name=data_dict.get("passenger_name", ""),
            flight_from=data_dict.get("flight_from", ""),
            flight_to=data_dict.get("flight_to", ""),
        )
        
        # Set routing from flight codes
        if invoice.flight_from and invoice.flight_to:
            invoice.routing = f"{invoice.flight_from} TO {invoice.flight_to}"
        elif invoice.flight_from:
            invoice.routing = invoice.flight_from
        
        # Set CGST/SGST rates if amounts are present
        if invoice.cgst_amount > 0:
            invoice.cgst_rate = 2.5
        if invoice.sgst_amount > 0:
            invoice.sgst_rate = 2.5
        if invoice.igst_amount > 0:
            invoice.igst_rate = 5.0
        
        return invoice
        
    except json.JSONDecodeError as e:
        print(f"Failed to parse Gemini response as JSON: {e}")
        return None
    except Exception as e:
        print(f"Gemini extraction error: {e}")
        return None


def parse_invoice_with_fallback(pdf_path: str) -> InvoiceData:
    """
    Parse invoice using regex first, fall back to Gemini if needed.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        InvoiceData object
    """
    from invoice_parser import parse_invoice, extract_text_from_pdf, detect_invoice_type
    
    # Try regex first
    invoice = parse_invoice(pdf_path)
    
    # Check if extraction was successful
    if invoice.invoice_number and invoice.total_amount > 0:
        return invoice
    
    # Fall back to Gemini
    print(f"Regex extraction incomplete, trying Gemini API...")
    
    text = extract_text_from_pdf(pdf_path)
    invoice_type = detect_invoice_type(os.path.basename(pdf_path))
    
    gemini_result = extract_with_gemini(text, invoice_type)
    
    if gemini_result and gemini_result.invoice_number:
        return gemini_result
    
    # Return original result with errors if Gemini also fails
    invoice.extraction_errors.append("Gemini fallback also failed")
    return invoice


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        result = parse_invoice_with_fallback(pdf_path)
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print("Usage: python gemini_fallback.py <pdf_path>")
