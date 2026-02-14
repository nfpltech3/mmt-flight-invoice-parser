"""
Invoice Parser Module for Airline PDF Invoices
Extracts data from Air India, Air India Express, IndiGo, Akasa Air, and Gulf Air invoices.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
import pdfplumber


@dataclass
class InvoiceData:
    """Structured invoice data extracted from PDF."""
    airline: str = ""
    invoice_number: str = ""
    invoice_date: str = ""  # DD-MMM-YYYY format
    invoice_type: str = ""  # TAX_INVOICE or DEBIT
    customer_name: str = ""
    customer_gstin: str = ""
    vendor_gstin: str = ""   # Added field for Supplier GSTIN
    place_of_supply: str = ""
    state_code: str = ""
    currency: str = "INR"
    taxable_value: float = 0.0
    non_taxable_value: float = 0.0
    cgst_rate: float = 0.0
    cgst_amount: float = 0.0
    sgst_rate: float = 0.0
    sgst_amount: float = 0.0
    igst_rate: float = 0.0
    igst_amount: float = 0.0
    total_amount: float = 0.0
    pnr: str = ""
    passenger_name: str = ""
    routing: str = ""
    flight_from: str = ""
    flight_to: str = ""
    raw_text: str = ""
    extraction_errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "airline": self.airline,
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "invoice_type": self.invoice_type,
            "customer_name": self.customer_name,
            "customer_gstin": self.customer_gstin,
            "place_of_supply": self.place_of_supply,
            "state_code": self.state_code,
            "currency": self.currency,
            "taxable_value": self.taxable_value,
            "non_taxable_value": self.non_taxable_value,
            "cgst_rate": self.cgst_rate,
            "cgst_amount": self.cgst_amount,
            "sgst_rate": self.sgst_rate,
            "sgst_amount": self.sgst_amount,
            "igst_rate": self.igst_rate,
            "igst_amount": self.igst_amount,
            "total_amount": self.total_amount,
            "pnr": self.pnr,
            "passenger_name": self.passenger_name,
            "routing": self.routing,
            "flight_from": self.flight_from,
            "flight_to": self.flight_to,
            "extraction_errors": self.extraction_errors
        }


# GSTIN State Code to State Name mapping
GSTIN_STATE_MAP = {
    "01": "JAMMU AND KASHMIR", "02": "HIMACHAL PRADESH", "03": "PUNJAB",
    "04": "CHANDIGARH", "05": "UTTARAKHAND", "06": "HARYANA", "07": "DELHI",
    "08": "RAJASTHAN", "09": "UTTAR PRADESH", "10": "BIHAR", "11": "SIKKIM",
    "12": "ARUNACHAL PRADESH", "13": "NAGALAND", "14": "MANIPUR", "15": "MIZORAM",
    "16": "TRIPURA", "17": "MEGHALAYA", "18": "ASSAM", "19": "WEST BENGAL",
    "20": "JHARKHAND", "21": "ODISHA", "22": "CHATTISGARH", "23": "MADHYA PRADESH",
    "24": "GUJARAT", "26": "DADRA AND NAGAR HAVELI", "27": "MAHARASHTRA", "28": "ANDHRA PRADESH",
    "29": "KARNATAKA", "30": "GOA", "31": "LAKSHADWEEP", "32": "KERALA",
    "33": "TAMIL NADU", "34": "PUDUCHERRY", "35": "ANDAMAN AND NICOBAR ISLANDS",
    "36": "TELANGANA", "37": "ANDHRA PRADESH (NEW)", "38": "LADAKH"
}


def parse_date_to_standard(date_str: str) -> str:
    """Convert various date formats to DD-MMM-YYYY format."""
    if not date_str:
        return ""
    
    date_str = date_str.strip()
    
    # Try different date formats
    formats = [
        "%d/%m/%Y",      # 15/05/2025
        "%d-%m-%Y",      # 15-05-2025
        "%d-%b-%Y",      # 15-May-2025
        "%d-%B-%Y",      # 15-May-2025
        "%Y-%m-%d",      # 2025-05-15
        "%d %b %Y",      # 15 May 2025
        "%d %B %Y",      # 15 May 2025
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%d-%b-%Y") # Title Case: 14-May-2025
        except ValueError:
            continue
    
    return date_str  # Return as-is if no format matches


def parse_amount(amount_str: str) -> float:
    """Parse amount string to float, handling commas and currency symbols."""
    if not amount_str:
        return 0.0
    
    # Remove currency symbols, commas, and whitespace
    cleaned = re.sub(r'[₹$,\s]', '', str(amount_str))
    
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


class BaseParser(ABC):
    """Abstract base class for airline invoice parsers."""
    
    airline_name: str = ""
    
    @abstractmethod
    def can_parse(self, text: str) -> bool:
        """Check if this parser can handle the given text."""
        pass
    
    @abstractmethod
    def extract(self, text: str, invoice_type: str) -> InvoiceData:
        """Extract invoice data from text."""
        pass
    
    def _safe_search(self, pattern: str, text: str, group: int = 1, default: str = "") -> str:
        """Safely search for a pattern and return the match or default."""
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            try:
                return match.group(group).strip()
            except IndexError:
                return default
        return default
    
    def _extract_gstin_state(self, gstin: str) -> tuple:
        """Extract state code and name from GSTIN."""
        if len(gstin) >= 2:
            state_code = gstin[:2]
            state_name = GSTIN_STATE_MAP.get(state_code, "UNKNOWN")
            return state_code, state_name
        return "", ""


class AirIndiaParser(BaseParser):
    """Parser for Air India and Air India LTD invoices."""
    
    airline_name = "AIR INDIA"
    
    def can_parse(self, text: str) -> bool:
        return "AIR INDIA LTD" in text.upper() and "AIR INDIA EXPRESS" not in text.upper()
    
    def extract(self, text: str, invoice_type: str) -> InvoiceData:
        data = InvoiceData(airline=self.airline_name, invoice_type=invoice_type, raw_text=text)
        
        # Invoice/Debit Note Number - handle both formats
        inv_match = re.search(r'(?:Invoice|Debit\s*Note)\s*Number\s*[:\s]*([A-Z0-9]+)', text, re.IGNORECASE)
        if inv_match:
            data.invoice_number = inv_match.group(1).strip()
        
        # Vendor GSTIN (Supplier) - usually first GSTIN occurrence
        vendor_match = re.search(r'GSTIN\s*[:\s]*(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2})', text, re.IGNORECASE)
        if vendor_match:
            data.vendor_gstin = vendor_match.group(1)
        
        # Invoice/Debit Note Date
        date_match = re.search(r'(?:Invoice|Debit\s*Note)\s*Date\s*[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})', text, re.IGNORECASE)
        if date_match:
            data.invoice_date = parse_date_to_standard(date_match.group(1))
        
        # Customer GSTIN
        gstin_match = re.search(r'Customer\s*GSTIN\s*[:\s]*(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2})', text, re.IGNORECASE)
        if gstin_match:
            data.customer_gstin = gstin_match.group(1)
            data.state_code, data.place_of_supply = self._extract_gstin_state(data.customer_gstin)
        
        # Customer Name - stop at newline or Reference
        cust_match = re.search(r'Customer\s*[:\s]*([A-Z][A-Z\s]+(?:PRIVATE\s+)?(?:LIMITED|LTD)?)', text)
        if cust_match:
            name = cust_match.group(1).strip()
            data.customer_name = name.split('\n')[0].strip()  # Take only first line
        
        # PNR
        pnr_match = re.search(r'PNR\s*[:\s]*([A-Z0-9]{6})', text, re.IGNORECASE)
        if pnr_match:
            data.pnr = pnr_match.group(1)
        
        # Passenger Name
        pass_match = re.search(r'Passenger\s*Name\s*[:\s]*([A-Z][A-Z\s]+(?:MR|MS|MRS)?)', text, re.IGNORECASE)
        if pass_match:
            data.passenger_name = pass_match.group(1).strip()
        
        # Routing
        routing_match = re.search(r'Routing\s*[:\s]*([A-Z]{6,})', text, re.IGNORECASE)
        if routing_match:
            routing = routing_match.group(1)
            if len(routing) >= 6:
                data.flight_from = routing[:3]
                data.flight_to = routing[3:6]
                data.routing = f"{data.flight_from} TO {data.flight_to}"
        
        # Total Amount - look for the final "Total" line with amount at end
        total_match = re.search(r'(?:^|\n)Total\s+(\d[\d,]*\.?\d*)\s*$', text, re.MULTILINE)
        if total_match:
            data.total_amount = parse_amount(total_match.group(1))
        
        # Air India: 996425 row
        # Pattern: 996425-...service 3,792.00 170.00 236.00 0.00 3,962.00 5 % 99.50 99.50 0.00 4,397.00
        sac_line = re.search(r'996425[^\n]*?(\d[\d,]*\.\d+)\s+[\d,\.]+\s+[\d,\.]+\s+[\d,\.]+\s+(\d[\d,]*\.\d+)\s+\d+\s*%', text)
        if sac_line:
            data.taxable_value = parse_amount(sac_line.group(1))  # First amount after SAC
        
        # For Air India, parse tax from the table row ending with tax amounts
        # The 996425 row ends with: taxable 5% CGST SGST IGST Total
        # e.g., 3,962.00 5 % 99.50 99.50 0.00 4,397.00
        tax_row = re.search(r'(\d[\d,]*\.\d+)\s+5\s*%\s+(\d[\d,]*\.\d+)\s+(\d[\d,]*\.\d+)\s+(\d[\d,]*\.\d+)\s+(\d[\d,]*\.\d+)', text)
        if tax_row:
            data.taxable_value = parse_amount(tax_row.group(1))
            data.cgst_amount = parse_amount(tax_row.group(2))
            data.sgst_amount = parse_amount(tax_row.group(3))
            data.igst_amount = parse_amount(tax_row.group(4))
            data.total_amount = parse_amount(tax_row.group(5))
            data.cgst_rate = 2.5 if data.cgst_amount > 0 else 0
            data.sgst_rate = 2.5 if data.sgst_amount > 0 else 0
            data.igst_rate = 5.0 if data.igst_amount > 0 else 0
        
        # Non-taxable value from SAC row (3rd amount column = non-taxable)
        # Pattern: 996425-... 4,593.00 170.00 443.00 0.00 4,763.00 ...
        non_tax_match = re.search(r'996425[^\n]*?\d[\d,]*\.\d{2}\s+[\d,\.]+\s+(\d[\d,]*\.\d{2})\s+[\d,\.]+\s+\d[\d,]*\.\d{2}\s+\d+\s*%', text)
        if non_tax_match:
            non_tax = parse_amount(non_tax_match.group(1))
            if non_tax > 0:
                data.non_taxable_value = non_tax
        
        # Fallback: "Non-taxable fare details: P2 = 236.00; IN = 207.00"
        if data.non_taxable_value == 0:
            non_tax_line = re.search(r'Non-taxable\s*fare\s*details\s*:\s*(.+)', text, re.IGNORECASE)
            if non_tax_line:
                amounts = re.findall(r'(\d[\d,]*\.\d{2})', non_tax_line.group(1))
                if amounts:
                    data.non_taxable_value = sum(parse_amount(a) for a in amounts)
        
        return data


class AirIndiaExpressParser(BaseParser):
    """Parser for Air India Express invoices."""
    
    airline_name = "AIR INDIA EXPRESS"
    
    def can_parse(self, text: str) -> bool:
        return "AIR INDIA EXPRESS" in text.upper()
    
    def extract(self, text: str, invoice_type: str) -> InvoiceData:
        data = InvoiceData(airline=self.airline_name, invoice_type=invoice_type, raw_text=text)
        
        # Invoice Number
        inv_match = re.search(r'Invoice\s*Number\s*[:\s]*([A-Z0-9]+)', text, re.IGNORECASE)
        if inv_match:
            data.invoice_number = inv_match.group(1).strip()
            
        # Vendor GSTIN (Supplier) - AI Express uses "GSTN"
        vendor_match = re.search(r'GSTN\s*[:\s]*(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2})', text, re.IGNORECASE)
        if vendor_match:
            data.vendor_gstin = vendor_match.group(1)
        
        # Invoice Date
        date_match = re.search(r'Invoice\s*Date\s*[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})', text, re.IGNORECASE)
        if date_match:
            data.invoice_date = parse_date_to_standard(date_match.group(1))
        
        # Customer GSTIN
        gstin_match = re.search(r'GSTIN\s*of\s*Customer\s*[:\s]*(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2})', text, re.IGNORECASE)
        if gstin_match:
            data.customer_gstin = gstin_match.group(1)
            data.state_code, data.place_of_supply = self._extract_gstin_state(data.customer_gstin)
        
        # Customer Name
        cust_match = re.search(r'GSTIN\s*Customer\s*Name\s*[:\s]*([A-Za-z][A-Za-z\s]+(?:Pvt|Private)?\s*(?:Ltd|Limited)?)', text, re.IGNORECASE)
        if cust_match:
            data.customer_name = cust_match.group(1).strip()
        
        # PNR
        pnr_match = re.search(r'PNR\s*(?:No)?\s*[:\s]*([A-Z0-9]{6})', text, re.IGNORECASE)
        if pnr_match:
            data.pnr = pnr_match.group(1)
        
        # Passenger Name
        pass_match = re.search(r'Passenger\s*Name\s*[:\s]*([A-Za-z][A-Za-z\s]+)', text, re.IGNORECASE)
        if pass_match:
            data.passenger_name = pass_match.group(1).strip()
        
        # Flight From/To
        from_match = re.search(r'Flight\s*From\s*[:\s]*([A-Z]{3})', text, re.IGNORECASE)
        to_match = re.search(r'Flight\s*To\s*[:\s]*([A-Z]{3})', text, re.IGNORECASE)
        if from_match:
            data.flight_from = from_match.group(1)
        if to_match:
            data.flight_to = to_match.group(1)
        if data.flight_from and data.flight_to:
            data.routing = f"{data.flight_from} TO {data.flight_to}"
        
        # Total from Grand Total line (last amount)
        # Grand Total 31,451.42 1,772.00 33,223.42 1,572.58 34,796.00
        grand_total_line = re.search(r'Grand\s*Total.*', text, re.IGNORECASE)
        if grand_total_line:
            amounts = re.findall(r'(\d[\d,]*\.\d{2})', grand_total_line.group(0))
            if amounts:
                data.total_amount = parse_amount(amounts[-1])  # Last amount = grand total
        
        # Extract from SAC 996425 row:
        # Air Ticket charges 996425 31,451.42 - 31,451.42 5 % 1,572.58 33,024.00
        sac_row = re.search(r'996425\s+(\d[\d,]*\.\d{2})', text)
        if sac_row:
            data.taxable_value = parse_amount(sac_row.group(1))
        
        # IGST from SAC row: "5 % 1,572.58"
        igst_match = re.search(r'996425[^\n]*?(\d+)\s*%\s+(\d[\d,]*\.\d{2})', text)
        if igst_match:
            data.igst_rate = parse_amount(igst_match.group(1))
            data.igst_amount = parse_amount(igst_match.group(2))
        
        # Non-taxable: Airport Taxes-Pass Through
        # Pattern: "Airport Taxes-Pass Through - - 1,772.00 1,772.00 ..."
        airport_match = re.search(r'Airport\s*Taxes[^\n]*?\s(\d[\d,]*\.\d{2})\s+(\d[\d,]*\.\d{2})', text, re.IGNORECASE)
        if airport_match:
            data.non_taxable_value = parse_amount(airport_match.group(1))
        
        # Fallback: look for "Non Taxable" or "Exempt" value in the table
        if data.non_taxable_value == 0:
            non_tax_match = re.search(r'Non\s*Taxable[^\d]*(\d[\d,]*\.?\d*)', text, re.IGNORECASE)
            if non_tax_match:
                val = parse_amount(non_tax_match.group(1))
                if val > 0:
                    data.non_taxable_value = val
        
        return data


class IndiGoParser(BaseParser):
    """Parser for IndiGo (InterGlobe Aviation) invoices."""
    
    airline_name = "INDIGO"
    
    def can_parse(self, text: str) -> bool:
        return "INDIGO" in text.upper() or "INTERGLOBE AVIATION" in text.upper()
    
    def extract(self, text: str, invoice_type: str) -> InvoiceData:
        data = InvoiceData(airline=self.airline_name, invoice_type=invoice_type, raw_text=text)
        
        # Invoice Number (format: KA1252612CR78975)
        inv_match = re.search(r'Number\s*[:\s]*([A-Z]{2}\d+[A-Z]{2}\d+)', text)
        if inv_match:
            data.invoice_number = inv_match.group(1).strip()
        
        # Invoice Date (format:        # Date: 21-Oct-2025 or 07 Apr 2025
        # Support permissive separators (dash, space, dot, etc.)
        # \d{1,2} : 1 or 2 digit day
        # [^\w\d]+ : One or more non-alphanumeric chars as separator
        # [A-Za-z]{3} : 3-letter month
        # \d{4} : 4-digit year
        date_match = re.search(r'Date\s*[:\s]*(\d{1,2}[^\w\d]+[A-Za-z]{3}[^\w\d]+\d{4})', text, re.IGNORECASE)
        if date_match:
            # Normalize to standard format: replace spaces/separators with single dash
            raw_date = re.sub(r'[^\w\d]+', '-', date_match.group(1))
            data.invoice_date = parse_date_to_standard(raw_date)
        
            data.invoice_date = parse_date_to_standard(raw_date)
        
        # Vendor GSTIN (Supplier) - appears before Customer GSTIN
        vendor_match = re.search(r'GSTIN\s*[:\s]*(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2})', text, re.IGNORECASE)
        # Ensure it's not the customer one if they appear close
        if vendor_match and "Customer" not in text[vendor_match.start()-20:vendor_match.start()]: 
             data.vendor_gstin = vendor_match.group(1)
        elif vendor_match:
             # Fallback: Find first GSTIN that is NOT followed by "of Customer" or preceded by "Customer"
             all_matches = re.finditer(r'GSTIN\s*[:\s]*(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2})', text, re.IGNORECASE)
             for m in all_matches:
                 start, end = m.span()
                 context = text[max(0, start-30):end+30]
                 if "Customer" not in context:
                     data.vendor_gstin = m.group(1)
                     break
        
        # Customer GSTIN
        gstin_match = re.search(r'GSTIN\s*of\s*Customer\s*[:\s]*(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2})', text, re.IGNORECASE)
        if gstin_match:
            data.customer_gstin = gstin_match.group(1)
            data.state_code, data.place_of_supply = self._extract_gstin_state(data.customer_gstin)
        
        # Customer Name
        cust_match = re.search(r'GSTIN\s*Customer\s*Name\s*[:\s]*([A-Za-z][A-Za-z\s]+(?:Pvt|Private)?\s*(?:Ltd|Limited)?)', text, re.IGNORECASE)
        if cust_match:
            name = cust_match.group(1).strip()
            data.customer_name = name.split('\n')[0].strip()
        
        # PNR
        pnr_match = re.search(r'PNR\s*[:\s]*([A-Z0-9]{6})', text, re.IGNORECASE)
        if pnr_match:
            data.pnr = pnr_match.group(1)
        
        # Passenger Name - specific to IndiGo format
        pass_match = re.search(r'Passenger\s*Name\s*[:\s]*\n?([A-Za-z][A-Za-z\s]+)', text, re.IGNORECASE)
        if pass_match:
            data.passenger_name = pass_match.group(1).strip()
        
        # From/To
        from_match = re.search(r'From\s*[:\s]*([A-Z]{3})', text, re.IGNORECASE)
        to_match = re.search(r'(?<!From\s)To\s*[:\s]*([A-Z]{3})', text, re.IGNORECASE)
        if from_match:
            data.flight_from = from_match.group(1)
        if to_match:
            data.flight_to = to_match.group(1)
        if data.flight_from and data.flight_to:
            data.routing = f"{data.flight_from} TO {data.flight_to}"
        
        # Grand Total - IndiGo format: Grand Total 0 974.00 0 304.00 0.00 0.00 0.00 7,367.00
        # Need to capture the last number on the line
        total_line = re.search(r'Grand\s*Total.*', text, re.IGNORECASE)
        if total_line:
            amounts = re.findall(r'(\d[\d,]*\.\d{2})', total_line.group(0))
            if amounts:
                data.total_amount = parse_amount(amounts[-1])  # Take last amount
        
        # IndiGo table parsing using line tokens (more robust)
        # Find line starting with 996425
        table_line_match = re.search(r'996425\s+.*', text)
        if table_line_match:
            parts = table_line_match.group(0).split()
            # Basic structure: 0:SAC, 1:Taxable ...
            if len(parts) > 1:
                data.taxable_value = parse_amount(parts[1])
            
            # Format detection based on token count
            # Use negative indexing to be safer against inserted columns
            # Structure ends with: ... CGST_R CGST_A SGST_R SGST_A IGST_R IGST_A Total
            # We see length 13 for 3-pair format. Old format length 7-8.
            
            if len(parts) >= 11:
                # 3 Pairs logic (CGST, SGST, IGST)
                # CGST: -7, -6
                data.cgst_rate = parse_amount(parts[-7])
                data.cgst_amount = parse_amount(parts[-6])
                
                # SGST: -5, -4
                data.sgst_rate = parse_amount(parts[-5])
                data.sgst_amount = parse_amount(parts[-4])
                
                # IGST: -3, -2  (Last item -1 is Total)
                data.igst_rate = parse_amount(parts[-3])
                data.igst_amount = parse_amount(parts[-2])
                
            elif len(parts) >= 6:
                # Old format: ... Rate Amt Total (Last 3)
                # IGST only
                data.igst_rate = parse_amount(parts[-3])
                data.igst_amount = parse_amount(parts[-2])
        
        # Airport Charges (Non-taxable / Exempted)
        # Pattern: "Airport Charges   0.00   974.00   974.00 ..."
        airport_match = re.search(r'Airport\s*Charges\s+[\d,\.]+\s+(\d[\d,]*\.\d{2})', text, re.IGNORECASE)
        if airport_match:
            data.non_taxable_value = parse_amount(airport_match.group(1))
        
        return data


class AkasaAirParser(BaseParser):
    """Parser for Akasa Air (SNV Aviation) invoices."""
    
    airline_name = "AKASA AIR"
    
    def can_parse(self, text: str) -> bool:
        return "AKASA" in text.upper() or "SNV AVIATION" in text.upper()
    
    def extract(self, text: str, invoice_type: str) -> InvoiceData:
        data = InvoiceData(airline=self.airline_name, invoice_type=invoice_type, raw_text=text)
        
        # Invoice/Debit Note Number
        inv_match = re.search(r'(?:Invoice|Debit\s*Note)\s*Number\s*[:\s]*([A-Z0-9]+)', text, re.IGNORECASE)
        if inv_match:
            data.invoice_number = inv_match.group(1).strip()
        
        # Invoice/Debit Note Date (format: 22-Oct-2025)
        date_match = re.search(r'(?:Invoice|Debit\s*Note)\s*Date\s*[:\s]*(\d{1,2}-[A-Za-z]{3}-\d{4})', text, re.IGNORECASE)
        if date_match:
            data.invoice_date = parse_date_to_standard(date_match.group(1))
        
        # Vendor GSTIN (Supplier)
        vendor_match = re.search(r'GSTIN\s*[:\s]*(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2})', text, re.IGNORECASE)
        # Ensure it's not the customer one (Customer one is usually "GSTIN/Unique ID of Customer")
        if vendor_match and "Customer" not in text[vendor_match.start():vendor_match.end()+20]:
             data.vendor_gstin = vendor_match.group(1)
        elif vendor_match:
             # Fallback: check context
             if "Customer" not in text[max(0, vendor_match.start()-20):vendor_match.start()]:
                 data.vendor_gstin = vendor_match.group(1)
        
        # Customer GSTIN
        gstin_match = re.search(r'GSTIN[/\s]*Unique\s*ID\s*of\s*Customer\s*[:\s]*(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2})', text, re.IGNORECASE)
        if gstin_match:
            data.customer_gstin = gstin_match.group(1)
            data.state_code, data.place_of_supply = self._extract_gstin_state(data.customer_gstin)
        
        # Customer Name
        cust_match = re.search(r'Name\s*of\s*Customer\s*[:\s]*([A-Za-z][A-Za-z\s]+(?:Pvt|Private)?\s*(?:Ltd|Limited)?)', text, re.IGNORECASE)
        if cust_match:
            name = cust_match.group(1).strip()
            data.customer_name = name.split('\n')[0].strip()
        
        # PNR
        pnr_match = re.search(r'PNR\s*[:\s]*([A-Z0-9]{6})', text, re.IGNORECASE)
        if pnr_match:
            data.pnr = pnr_match.group(1)
        
        # Flight From
        from_match = re.search(r'Flight\s*From\s*[:\s]*([A-Z]{3})', text, re.IGNORECASE)
        if from_match:
            data.flight_from = from_match.group(1)
            data.routing = f"{data.flight_from}"
        
        # Grand Total - Akasa format: last amount on the line is the grand total
        # Grand Total 10518.00 1018.00 398.00 11138.00 0.00 0.00 506.00 11644.00
        # Columns: [0]Taxable [1]NonTax [2]Discount [3]TaxableTotal [4]CGST [5]SGST [6]IGST [7]GrandTotal
        grand_total_line = re.search(r'Grand\s*Total.*', text, re.IGNORECASE)
        if grand_total_line:
            amounts = re.findall(r'(\d[\d,]*\.\d+)', grand_total_line.group(0))
            if len(amounts) >= 8:
                data.taxable_value = parse_amount(amounts[0])
                data.non_taxable_value = parse_amount(amounts[1])
                data.cgst_amount = parse_amount(amounts[4]) 
                data.sgst_amount = parse_amount(amounts[5])
                data.igst_amount = parse_amount(amounts[6])
                data.total_amount = parse_amount(amounts[7])
                
                # Set rates if amounts exist
                if data.cgst_amount > 0: data.cgst_rate = 2.5
                if data.sgst_amount > 0: data.sgst_rate = 2.5
                if data.igst_amount > 0:
                    # Calculate approximate rate
                    if data.taxable_value > 0:
                        rate = (data.igst_amount / data.taxable_value) * 100
                        data.igst_rate = 5.0 if abs(rate - 5.0) < 1.0 else 18.0 # Default to 5 or 18
                    else:
                        data.igst_rate = 5.0 # Default fallback
            elif amounts:
                data.total_amount = parse_amount(amounts[-1])
        
        # Akasa table: SAC Taxable NonTax Discount Total Rate Amount...
        # Only parse if we didn't get data from Grand Total line
        if data.total_amount == 0:
            akasa_row = re.search(r'996425\s+(\d[\d,]*\.\d+)\s+[\d,\.]+\s+[\d,\.]+\s+(\d[\d,]*\.\d+)[^\d]+\d+%[^\d]+[\d,\.]+[^\d]+\d+%[^\d]+[\d,\.]+[^\d]+5%\s+(\d[\d,]*\.\d+)\s+(\d[\d,]*\.\d+)', text)
            if akasa_row:
                data.taxable_value = parse_amount(akasa_row.group(1))
                # taxable after discount in group 2
                data.igst_amount = parse_amount(akasa_row.group(3))
                # Don't overwrite total_amount here - Grand Total (line 472) has the correct full total
                data.igst_rate = 5.0
            else:
                # Fallback: simpler pattern
                taxable_match = re.search(r'996425\s+(\d[\d,]*\.\d{2})', text)
                if taxable_match:
                    data.taxable_value = parse_amount(taxable_match.group(1))
                igst_match = re.search(r'5%\s+(\d[\d,]*\.\d{2})', text)
                if igst_match:
                    data.igst_amount = parse_amount(igst_match.group(1))
                    data.igst_rate = 5.0
        
        # Airport Charges (Non-taxable)
        # Pattern: "Airport Charges   0.00   443.00   0.00   443.00 ..."
        airport_match = re.search(r'Airport\s*Charges\s+[\d,\.]+\s+(\d[\d,]*\.\d{2})', text, re.IGNORECASE)
        if airport_match:
            data.non_taxable_value = parse_amount(airport_match.group(1))
        
        # CGST/SGST for intra-state (e.g., Maharashtra)
        cgst_match = re.search(r'2\.5%\s+(\d[\d,]*\.\d{2})\s+2\.5%\s+(\d[\d,]*\.\d{2})', text)
        if cgst_match:
            data.cgst_amount = parse_amount(cgst_match.group(1))
            data.sgst_amount = parse_amount(cgst_match.group(2))
            data.cgst_rate = 2.5
            data.sgst_rate = 2.5
            data.igst_amount = 0.0  # Override if CGST/SGST present
            data.igst_rate = 0.0
        
        return data


class GulfAirParser(BaseParser):
    """Parser for Gulf Air invoices."""
    
    airline_name = "GULF AIR"
    
    def can_parse(self, text: str) -> bool:
        return "GULF AIR" in text.upper()
    
    def extract(self, text: str, invoice_type: str) -> InvoiceData:
        data = InvoiceData(airline=self.airline_name, invoice_type=invoice_type, raw_text=text)
        
        # Invoice Number (format: TKMHP/2510/04496)
        inv_match = re.search(r'Invoice\s*No\s*[:\s]*([A-Z0-9/]+)', text, re.IGNORECASE)
        if inv_match:
            data.invoice_number = inv_match.group(1).strip()
        
        # Invoice Date (format: 21-10-2025)
        date_match = re.search(r'Invoice\s*Date\s*[:\s]*(\d{1,2}-\d{1,2}-\d{4})', text, re.IGNORECASE)
        if date_match:
            data.invoice_date = parse_date_to_standard(date_match.group(1))
        
        # Customer GSTIN
        gstin_match = re.search(r'GSTIN\s*of\s*Customer\s*[:\s]*(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2})', text, re.IGNORECASE)
        if gstin_match:
            data.customer_gstin = gstin_match.group(1)
            data.state_code, data.place_of_supply = self._extract_gstin_state(data.customer_gstin)
        
        # Customer Name
        cust_match = re.search(r'Customer\s*Name\s*[:\s]*([A-Z][A-Z\s]+(?:PRIVATE\s+)?(?:LIMITED|LTD)?)', text, re.IGNORECASE)
        if cust_match:
            name = cust_match.group(1).strip()
            data.customer_name = name.split('\n')[0].strip()
        
        # Ticket Number as PNR alternative
        ticket_match = re.search(r'Ticket\s*/\s*Document\s*No\s*[:\s]*(\d+)', text, re.IGNORECASE)
        if ticket_match:
            data.pnr = ticket_match.group(1)
        
        # Taxable Value
        taxable_match = re.search(r'Taxable\s*Value[^\d]*(\d[\d,]*\.?\d*)', text, re.IGNORECASE)
        if taxable_match:
            data.taxable_value = parse_amount(taxable_match.group(1))
        
        # Non-Taxable Value
        non_taxable_match = re.search(r'Non-Taxable\s*Value[^\d]*(\d[\d,]*\.?\d*)', text, re.IGNORECASE)
        if non_taxable_match:
            data.non_taxable_value = parse_amount(non_taxable_match.group(1))
        
        # Total Value
        total_match = re.search(r'Total\s*\(including\s*taxes\)[^\d]*(\d[\d,]*\.?\d*)', text, re.IGNORECASE)
        if total_match:
            data.total_amount = parse_amount(total_match.group(1))
        
        # IGST (Gulf Air typically uses 18% for international)
        igst_match = re.search(r'Integrated\s*Tax\s*\(IGST\)\s*(\d+)%\s*(\d[\d,]*\.?\d*)', text, re.IGNORECASE)
        if igst_match:
            data.igst_rate = parse_amount(igst_match.group(1))
            data.igst_amount = parse_amount(igst_match.group(2))
        
        return data


# List of all parsers in priority order
PARSERS = [
    AirIndiaExpressParser(),  # Check Express before regular Air India
    AirIndiaParser(),
    IndiGoParser(),
    AkasaAirParser(),
    GulfAirParser(),
]


def detect_invoice_type(filename: str) -> str:
    """Detect invoice type from filename."""
    filename_upper = filename.upper()
    if "DEBIT" in filename_upper:
        return "DEBIT"
    elif "TAX_INVOICE" in filename_upper or "INVOICE" in filename_upper:
        return "TAX_INVOICE"
    return "UNKNOWN"


def extract_text_from_pdf(pdf_path: str, page_num: int = 0) -> str:
    """Extract text from a specific page of a PDF file."""
    with pdfplumber.open(pdf_path) as pdf:
        if page_num < len(pdf.pages):
            page = pdf.pages[page_num]
            text = page.extract_text()
            if text:
                # Fix numbers split across lines by PDF extraction
                # e.g., "10,864.0\n0" -> "10,864.00" or "11,838.\n00" -> "11,838.00"
                text = re.sub(r'(\d\.\d)\n(\d)', r'\1\2', text)
                text = re.sub(r'(\d\.)\n(\d)', r'\1\2', text)
                return text
    return ""


def parse_invoice(pdf_path: str) -> InvoiceData:
    """
    Parse an invoice PDF and extract structured data.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        InvoiceData object with extracted information
    """
    import os
    
    filename = os.path.basename(pdf_path)
    invoice_type = detect_invoice_type(filename)
    
    # Skip credit notes
    if "CREDIT" in filename.upper():
        data = InvoiceData()
        data.extraction_errors.append("Credit notes are not supported")
        return data
    
    # Extract text from first page only
    text = extract_text_from_pdf(pdf_path, page_num=0)
    
    if not text:
        data = InvoiceData()
        data.extraction_errors.append("Could not extract text from PDF")
        return data
    
    # Try each parser
    for parser in PARSERS:
        if parser.can_parse(text):
            data = parser.extract(text, invoice_type)
            
            # Validate required fields
            if not data.invoice_number:
                data.extraction_errors.append("Invoice number not found")
            if not data.invoice_date:
                data.extraction_errors.append("Invoice date not found")
            if not data.customer_gstin:
                data.extraction_errors.append("Customer GSTIN not found")
            if data.total_amount == 0:
                data.extraction_errors.append("Total amount not found or is zero")
            
            return data
    
    # No parser matched
    data = InvoiceData(raw_text=text)
    data.extraction_errors.append(f"Unknown invoice format - no parser matched")
    return data


if __name__ == "__main__":
    # Test with sample invoice
    import sys
    import json
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        result = parse_invoice(pdf_path)
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print("Usage: python invoice_parser.py <pdf_path>")
