# Consolidated Invoice Processor
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
    filename: str = "" # Added to track source file
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
    
    # Remove currency symbols, commas, percent, and whitespace
    cleaned = re.sub(r'[₹$,%\s]', '', str(amount_str))
    
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
        lines = text.split('\n')
        parts = []
        header_text = ""
        for i, line in enumerate(lines):
            if '996425' in line:
                raw_parts = line.split()
                # Find index of 996425
                try:
                    start_idx = [k for k, p in enumerate(raw_parts) if '996425' in p][0]
                    candidate = raw_parts[start_idx:]
                    while candidate and not re.search(r'\d', candidate[-1]):
                        candidate.pop()
                except IndexError:
                    continue
                
                # Heuristic: Prefer more tokens, then more content (non-zero digits)
                is_better = False
                if len(candidate) > len(parts):
                    is_better = True
                elif len(candidate) == len(parts) and len(candidate) >= 2:
                    # Prefer row with higher Tax Amount (at index -2)
                    try:
                        cand_tax = parse_amount(candidate[-2])
                        part_tax = parse_amount(parts[-2]) if len(parts) >= 2 else -1.0
                        if cand_tax > part_tax:
                            is_better = True
                    except:
                        pass
                
                if is_better:
                    parts = candidate
                    # Header scan for this candidate
                    for j in range(i-1, max(-1, i-6), -1):
                        if "Taxable" in lines[j] or "GST" in lines[j] or "Code" in lines[j]:
                            header_text = lines[j]
                            break

        
        if parts:
            # Total is always the last numeric token
            data.total_amount = parse_amount(parts[-1]) if len(parts) > 1 else 0.0

            # Basic structure: 0:SAC, 1:Taxable (or GrossTaxable) ...
            if len(parts) > 1:
                data.taxable_value = parse_amount(parts[1])
            
            # Discount Logic: Check header for "Discount" or "Disc"
            if header_text and ("Discount" in header_text or "Disc" in header_text) and len(parts) > 2:
                discount = parse_amount(parts[2])
                data.taxable_value -= discount
            
            # Smart tax extraction: scan all numeric tokens after taxable
            # for rate-amount pairs. Rates are small (<=18), amounts are larger.
            # Tokens layout: SAC, [Gross], [Disc], NetTaxable, R1, A1, R2, A2, R3, A3, ..., Total
            # We skip index 0 (SAC) and the last token (Total).
            # We look for pairs starting from index 2 onward.
            
            # Collect all numeric values from index 2 to second-to-last
            nums = []
            for idx in range(2, len(parts) - 1):
                nums.append((idx, parse_amount(parts[idx])))
            
            # Find rate-amount pairs: a rate is a value <= 18 followed by a non-zero amount
            # Also collect zero-rate + zero-amount pairs for completeness
            tax_pairs = []  # list of (rate, amount)
            i = 0
            while i < len(nums) - 1:
                val = nums[i][1]
                next_val = nums[i + 1][1]
                # Check if this looks like a rate (0-18 range, typical GST rates)
                if val <= 18.0:
                    tax_pairs.append((val, next_val))
                    i += 2  # skip the pair
                else:
                    i += 1  # skip non-rate value (like net taxable repeating)
            
            # Assign tax pairs: find non-zero pairs first
            non_zero_pairs = [(r, a) for r, a in tax_pairs if a > 0]
            zero_pairs = [(r, a) for r, a in tax_pairs if a == 0]
            
            # Determine tax type from non-zero pairs
            # IndiGo: IGST if interstate (rate typically 5% or 12% or 18%)
            #          CGST+SGST if intrastate (rate typically 2.5% or 6% or 9%)
            for rate, amt in non_zero_pairs:
                if rate in (2.5, 6.0, 9.0):
                    # CGST/SGST rate - assign to whichever is empty first
                    if data.cgst_amount == 0:
                        data.cgst_rate = rate
                        data.cgst_amount = amt
                    else:
                        data.sgst_rate = rate
                        data.sgst_amount = amt
                else:
                    # IGST rate (5, 12, 18, or any other)
                    data.igst_rate = rate
                    data.igst_amount = amt
        
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
                # With Discount column: [0]Gross [1]NonTax [2]Discount [3]NetTotal [4]CGST [5]SGST [6]IGST [7]GrandTotal
                data.non_taxable_value = parse_amount(amounts[1])
                net_total = parse_amount(amounts[3])
                # Calculate taxable from Net Total (Col 3) to account for discount
                data.taxable_value = net_total - data.non_taxable_value
                
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


def extract_text_from_pdf(pdf_path: str, page_num: int = None) -> str:
    """Extract text from PDF. If page_num is None, extracts all pages."""
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        if page_num is not None:
            if page_num < len(pdf.pages):
                pages = [pdf.pages[page_num]]
            else:
                pages = []
        else:
            pages = pdf.pages
            
        for page in pages:
            t = page.extract_text(x_tolerance=1)
            if t:
                # Fix numbers split across lines by PDF extraction
                # e.g., "10,864.0\n0" -> "10,864.00" or "11,838.\n00" -> "11,838.00"
                t = re.sub(r'(\d\.\d)\n(\d)', r'\1\2', t)
                t = re.sub(r'(\d\.)\n(\d)', r'\1\2', t)
                text += t + "\n"
    return text


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
    
    # Extract text from all pages to handle duplicates/split content
    text = extract_text_from_pdf(pdf_path, page_num=None)
    
    if not text:
        data = InvoiceData()
        data.extraction_errors.append("Could not extract text from PDF")
        return data
    
    # Try each parser
    for parser in PARSERS:
        if parser.can_parse(text):
            data = parser.extract(text, invoice_type)
            data.filename = filename # Set filename
            
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
    data.filename = filename # Set filename
    data.extraction_errors.append(f"Unknown invoice format - no parser matched")
    return data
 


# ============================================================
# CSV GENERATOR SECTION
# ============================================================
"""
CSV Generator Module for Logisys Portal Upload
Generates CSV files matching the 41-column template format.
"""

import csv
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Import from invoice_parser


# Map state codes to branch names for the template
STATE_TO_BRANCH = {
    "01": "JAMMU AND KASHMIR", "02": "HIMACHAL PRADESH", "03": "PUNJAB",
    "04": "CHANDIGARH", "05": "UTTARAKHAND", "06": "HARYANA", "07": "DELHI",
    "08": "RAJASTHAN", "09": "UTTAR PRADESH", "10": "BIHAR", "11": "SIKKIM",
    "12": "ARUNACHAL PRADESH", "13": "NAGALAND", "14": "MANIPUR", "15": "MIZORAM",
    "16": "TRIPURA", "17": "MEGHALAYA", "18": "ASSAM", "19": "WEST BENGAL",
    "20": "JHARKHAND", "21": "ODISHA", "22": "CHATTISGARH", "23": "MADHYA PRADESH",
    "24": "GUJARAT", "26": "DADRA AND NAGAR HAVELI", "27": "MAHARASHTRA", "28": "ANDHRA PRADESH",
    "29": "KARNATAKA", "30": "GOA", "31": "LAKSHADWEEP", "32": "KERALA",
    "33": "TAMIL NADU", "34": "PUDUCHERRY", "35": "ANDAMAN AND NICOBAR ISLANDS",
    "36": "TELANGANA", "37": "ANDHRA PRADESH", "38": "LADAKH"
}

# Map Vendor GSTIN to Organization Branch
VENDOR_GSTIN_MAP = {
    "27ABECS9580P1ZC": "MUMBAI",
    "24AABCI2726B1Z8": "VADODRA",
    "27AABCI2726B1Z2": "SANTACRUZ",
    "32AABCI2726B1ZB": "COCHIN",
    "05AABCI2726B1Z8": "UTTARAKHAND",
    "03AABCI2726B1ZC": "PUNJAB",
    "07AABCI2726B1Z4": "NEW DELHI",
    "08AABCI2726B1Z2": "RAJASTHAN",
    "30AABCI2726B1ZF": "GOA",
    "36AABCI2726B1Z3": "TELANGANA",
    "07AACCN6194P2ZQ": "NEW DELHI",
    "27AACCN6194P1ZP": "MUMBAI",
    "24AACCN6194P1ZV": "GUJARAT",
    "03AACCN6194P1ZZ": "PUNJAB",
    "27AABCA0522B1ZK": "MUMBAI",
    "29AABCI2726B1ZY": "KARNATAKA",
    "08AACCN6194P1ZP": "RAJASTHAN",
    "30AACCN6194P1Z2": "GOA",
    "09AABCI2726B1Z0": "UTTAR PRADESH",
    "23AABCI2726B1ZA": "MADHYA PRADESH",
    "29ABECS9580P1Z8": "KARNATAKA",
    "27AAACG2368J1ZI": "MAHARASHTRA"
}

# Map Customer GSTIN to Branch
CUSTOMER_GSTIN_MAP = {
    "27AACCN5739J1Z4": "HO",
    "06AACCN5739J1Z8": "HARYANA",
    "33AACCN5739J1ZB": "CHENNAI",
    "24AACCN5739J1ZA": "GUJARAT",
    "27AACCN5739J2Z3": "ISD"
}

# 41 CSV Headers matching the template
CSV_HEADERS = [
    "Entry Date",           # 1
    "Posting Date",         # 2
    "Organization",         # 3
    "Organization Branch",  # 4
    "Vendor Inv No",        # 5
    "Vendor Inv Date",      # 6
    "Currency",             # 7
    "ExchRate",             # 8
    "Narration",            # 9
    "Due Date",             # 10
    "Charge or GL",         # 11
    "Charge or GL Name",    # 12
    "Charge or GL Amount",  # 13
    "DR or CR",             # 14
    "Cost Center",          # 15
    "Branch",               # 16
    " Charge Narration",    # 17
    "TaxGroup",             # 18
    "Tax Type",             # 19
    "SAC or HSN",           # 20
    "Taxcode1",             # 21
    "Taxcode1 Amt",         # 22
    "Taxcode2",             # 23
    "Taxcode2 Amt",         # 24
    "Taxcode3",             # 25
    "Taxcode3 Amt",         # 26
    "Taxcode4",             # 27
    "Taxcode4 Amt",         # 28
    "Avail Tax Credit",     # 29
    "LOB",                  # 30
    "Ref Type",             # 31
    "Ref No",               # 32
    "Amount",               # 33
    "Start Date",           # 34
    "End Date",             # 35
    "WH Tax Code",          # 36
    "WH Tax Percentage",    # 37
    "WH Tax Taxable",       # 38
    "WH Tax Amount",        # 39
    "Round Off",            # 40
    "CC Code",              # 41
]


def get_current_date_formatted() -> str:
    """Get current date in DD-MMM-YYYY format."""
    return datetime.now().strftime("%d-%b-%Y") # Title Case


def map_airline_to_organization(airline: str) -> str:
    """Map airline name to organization name for the template."""
    airline_upper = airline.upper()
    if "AIR INDIA EXPRESS" in airline_upper:
        return "AIR INDIA EXPRESS LIMITED"
    elif "AIR INDIA" in airline_upper:
        return "AIR INDIA LTD"
    elif "INDIGO" in airline_upper:
        return "InterGlobe Aviation Limited"
    elif "AKASA" in airline_upper:
        return "SNV Aviation Private Limited"
    elif "GULF" in airline_upper:
        return "Gulf Air B.S.C. (c)"
    return airline_upper


def generate_narration(airline: str, routing: str, pnr: str = "", passenger: str = "") -> str:
    """Generate narration text for the CSV."""
    org = map_airline_to_organization(airline)
    
    if routing:
        route_text = routing.replace(" TO ", " TO ")
    else:
        route_text = ""
    
    narration = f"BEING AMOUNT PAYABLE TO {org}"
    if route_text:
        narration += f" FROM {route_text}"
    if pnr:
        narration += f" PNR:{pnr}"
    if passenger:
        narration += f" PAX:{passenger}"
    
    return narration


def invoice_to_csv_row(
    invoice: InvoiceData, 
    entry_date: Optional[str] = None,
    is_non_taxable: bool = False,
    charge_amount: Optional[float] = None
) -> Dict[str, Any]:
    """Convert InvoiceData to a CSV row dictionary.
    
    Args:
        invoice: InvoiceData object
        entry_date: Entry date in DD-MMM-YYYY format
        is_non_taxable: If True, creates a non-taxable entry (for airport charges)
        charge_amount: Override for charge amount (used for split entries)
    """
    
    if entry_date is None:
        entry_date = get_current_date_formatted()
    
    # Determine Branch (Customer GSTIN based)
    branch = ""
    if invoice.customer_gstin:
        branch = CUSTOMER_GSTIN_MAP.get(invoice.customer_gstin)
        if not branch:
            # Fallback to state code map
            state_code = invoice.customer_gstin[:2]
            branch = STATE_TO_BRANCH.get(state_code, "")
            
    if not branch and invoice.state_code:
        branch = STATE_TO_BRANCH.get(invoice.state_code, "GUJARAT")
    if not branch:
        branch = "GUJARAT"

    # Determine Organization Branch (Vendor GSTIN based)
    org_branch = ""
    if invoice.vendor_gstin:
        org_branch = VENDOR_GSTIN_MAP.get(invoice.vendor_gstin)
        if not org_branch:
             # Fallback to state logic if extracted
             state_code = invoice.vendor_gstin[:2]
             org_branch = STATE_TO_BRANCH.get(state_code, "")
    
    # Determine DR or CR based on invoice type
    # Since Credit Notes are filtered out, both Tax Invoices and Debit Notes are Dr entries
    dr_cr = "Dr"
    
    # Generate narration
    narration = generate_narration(
        invoice.airline,
        invoice.routing,
        invoice.pnr,
        invoice.passenger_name
    )
    
    # Determine amount to use
    if charge_amount is not None:
        amount = charge_amount
    elif is_non_taxable:
        amount = invoice.non_taxable_value
    else:
        amount = invoice.taxable_value if invoice.taxable_value > 0 else invoice.total_amount
    
    # Tax codes - only for taxable entries
    taxcode1 = ""
    taxcode1_amt = ""
    taxcode2 = ""
    taxcode2_amt = ""
    taxcode3 = ""
    taxcode3_amt = ""
    
    if not is_non_taxable:
        if invoice.igst_amount > 0:
            taxcode1 = "IGST"
            taxcode1_amt = str(invoice.igst_amount)
        elif invoice.cgst_amount > 0:
            taxcode1 = "CGST"
            taxcode1_amt = str(invoice.cgst_amount)
            if invoice.sgst_amount > 0:
                taxcode2 = "SGST"
                taxcode2_amt = str(invoice.sgst_amount)
        # Fallback for weird cases (e.g. only SGST? Unlikely)
        elif invoice.sgst_amount > 0:
            taxcode1 = "SGST"
            taxcode1_amt = str(invoice.sgst_amount)
    
    # Determine Expense Head and SAC Code   
    expense_head = "TRAVELLING EXPENSES"
    sac_code = "996425"
    
    # If IGST is 18%, likely misc charges
    if invoice.igst_rate == 18.0 and not is_non_taxable:
        expense_head = "TRAVELLING EXP. (AIRLINE MISC CHARGES)"
        sac_code = "996429"

    # Build the row
    row = {
        "Entry Date": entry_date,
        "Posting Date": entry_date,
        "Organization": map_airline_to_organization(invoice.airline),
        "Organization Branch": org_branch,
        "Vendor Inv No": invoice.invoice_number,
        "Vendor Inv Date": invoice.invoice_date,
        "Currency": invoice.currency,
        "ExchRate": "1",
        "Narration": narration,
        "Due Date": entry_date,
        "Charge or GL": expense_head,
        "Charge or GL Name": expense_head,
        "Charge or GL Amount": str(amount),
        "DR or CR": dr_cr,
        "Cost Center": "",
        "Branch": branch,
        " Charge Narration": "AIRPORT CHARGES" if is_non_taxable else "BASE FARE",
        "TaxGroup": "GSTIN" if invoice.customer_gstin and not is_non_taxable else "",
        "Tax Type": "Non-Taxable" if is_non_taxable else "Taxable",
        "SAC or HSN": sac_code if not is_non_taxable else "",  # Air Transport SAC code only for taxable
        "Taxcode1": taxcode1,
        "Taxcode1 Amt": taxcode1_amt,
        "Taxcode2": taxcode2,
        "Taxcode2 Amt": taxcode2_amt,
        "Taxcode3": taxcode3,
        "Taxcode3 Amt": taxcode3_amt,
        "Taxcode4": "",
        "Taxcode4 Amt": "",
        "Avail Tax Credit": "100" if (invoice.igst_amount > 0 or invoice.cgst_amount > 0 or invoice.sgst_amount > 0) else "Yes",
        "LOB": "",
        "Ref Type": "",
        "Ref No": "",
        "Amount": str(invoice.taxable_value + invoice.non_taxable_value + invoice.igst_amount + invoice.cgst_amount + invoice.sgst_amount),  # Grand total for the invoice
        "Start Date": "",
        "End Date": "",
        "WH Tax Code": "",
        "WH Tax Percentage": "",
        "WH Tax Taxable": "",
        "WH Tax Amount": "",
        "Round Off": "Yes",
        "CC Code": "",
    }
    
    return row


def invoice_to_csv_rows(invoice: InvoiceData, entry_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Convert InvoiceData to one or more CSV row dictionaries.
    Creates separate rows for taxable and non-taxable amounts (e.g., Akasa airport charges).
    
    Args:
        invoice: InvoiceData object
        entry_date: Entry date in DD-MMM-YYYY format
        
    Returns:
        List of row dictionaries
    """
    if entry_date is None:
        entry_date = get_current_date_formatted()
    
    rows = []
    
    # Main taxable entry
    if invoice.taxable_value > 0:
        rows.append(invoice_to_csv_row(invoice, entry_date, is_non_taxable=False))
    elif invoice.total_amount > 0 and invoice.non_taxable_value == 0:
        # No taxable value but has total - use total as taxable
        rows.append(invoice_to_csv_row(invoice, entry_date, is_non_taxable=False))
    
    # Non-taxable entry (airport charges, etc.) - separate row with same invoice number
    if invoice.non_taxable_value > 0:
        rows.append(invoice_to_csv_row(invoice, entry_date, is_non_taxable=True))
    
    # If no rows created (edge case), create at least one
    if not rows:
        rows.append(invoice_to_csv_row(invoice, entry_date, is_non_taxable=False))
    
    return rows


def generate_summary_report(
    summary_data: List[Dict[str, Any]],
    output_dir: str
) -> str:
    """
    Generate a summary CSV report with validation status.
    Helps users identify why uploads might fail (e.g. unmapped branches).
    """
    filename = f"Processing_Summary_{datetime.now().strftime('%d%b_%H%M')}.csv"
    filepath = os.path.join(output_dir, filename)
    
    headers = [
        "Status", "Issues", "File Name", "Invoice No", "Airline", 
        "Vendor GSTIN", "Mapped Org Branch", "In Vendor Map?", 
        "Customer GSTIN", "Mapped Cust Branch", "Amount"
    ]
    
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in summary_data:
                writer.writerow(row)
        return filepath
    except Exception as e:
        print(f"Failed to write summary report: {e}")
        return ""


def group_invoices_by_gstin(invoices: List[InvoiceData]) -> Dict[str, List[InvoiceData]]:
    """Group invoices by customer GSTIN for separate output files."""
    groups = {}
    for inv in invoices:
        key = inv.customer_gstin if inv.customer_gstin else "UNKNOWN"
        if key not in groups:
            groups[key] = []
        groups[key].append(inv)
    return groups


def generate_csv(
    invoices: List[InvoiceData],
    output_dir: str,
    group_by_gstin: bool = True,
    filename_prefix: str = "transport_expenses"
) -> List[str]:
    """
    Generate CSV file(s) from a list of InvoiceData objects.
    
    Args:
        invoices: List of InvoiceData objects
        output_dir: Directory to write CSV files to
        group_by_gstin: If True, creates separate CSV for each GSTIN
        filename_prefix: Prefix for output filenames
        
    Returns:
        List of generated file paths
    """
    os.makedirs(output_dir, exist_ok=True)
    generated_files = []
    
    if group_by_gstin:
        groups = group_invoices_by_gstin(invoices)
    else:
        groups = {"all": invoices}
    
    entry_date = get_current_date_formatted()
    
    summary_data = [] # Collect data for validation report

    for gstin, inv_list in groups.items():
        # Get state name for filename
        if gstin != "UNKNOWN" and gstin != "all" and len(gstin) >= 2:
            state = STATE_TO_BRANCH.get(gstin[:2], "Unknown")
        else:
            state = "Unknown"
        
        # Create filename with timestamp to avoid overwriting
        timestamp = datetime.now().strftime("%d%b").upper() # 14FEB
        gstin_suffix = gstin[-4:] if len(gstin) >= 4 else gstin
        
        # Format: Flight_Exp_Maharashtra_J1Z4_14FEB.csv
        state_clean = state.replace(" ", "")
        filename = f"Flight_Exp_{state_clean}_{gstin_suffix}_{timestamp}.csv"
        filepath = os.path.join(output_dir, filename)
        
        # Write CSV
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            
            for inv in inv_list:
                # Validation Logic for Summary
                file_basename = inv.filename if inv.filename else "Unknown"
                
                status = "Success"
                issues = []
                
                if inv.extraction_errors and not inv.invoice_number:
                    status = "Failed"
                    issues = "; ".join(inv.extraction_errors)
                    # Add to summary even if skipped
                    summary_data.append({
                        "Status": status,
                        "Issues": issues,
                        "File Name": file_basename,
                        "Invoice No": inv.invoice_number or "N/A",
                        "Airline": inv.airline,
                        "Vendor GSTIN": inv.vendor_gstin,
                        "Mapped Org Branch": "N/A",
                        "In Vendor Map?": "N/A",
                        "Customer GSTIN": inv.customer_gstin,
                        "Mapped Cust Branch": "N/A",
                        "Amount": str(inv.total_amount)
                    })
                    continue  # Skip failed extractions
                
                # Get mapped rows
                rows = invoice_to_csv_rows(inv, entry_date)
                
                # Check mapping for the first row (representative)
                if rows:
                    first_row = rows[0]
                    org_branch = first_row.get("Organization Branch", "")
                    cust_branch = first_row.get("Branch", "")
                    
                    # Check 1: Org Branch Empty
                    if not org_branch:
                        status = "Warning"
                        issues.append("Org Branch Empty")
                    
                    # Check 2: Vendor Mapping
                    in_map = "Yes"
                    if inv.vendor_gstin and inv.vendor_gstin not in VENDOR_GSTIN_MAP:
                        in_map = "No"
                        if status != "Warning": status = "Warning" # Downgrade if not already
                        issues.append("Vendor GSTIN not in Map (State Fallback used)")
                    
                    # Check 3: Cust Branch
                    if not cust_branch:
                        status = "Warning"
                        issues.append("Customer Branch Empty")

                    summary_data.append({
                        "Status": status,
                        "Issues": "; ".join(issues),
                        "File Name": file_basename,
                        "Invoice No": inv.invoice_number,
                        "Airline": inv.airline,
                        "Vendor GSTIN": inv.vendor_gstin,
                        "Mapped Org Branch": org_branch,
                        "In Vendor Map?": in_map,
                        "Customer GSTIN": inv.customer_gstin,
                        "Mapped Cust Branch": cust_branch,
                        "Amount": first_row.get("Amount", "0")
                    })

                for row in rows:
                    writer.writerow(row)
        
        generated_files.append(filepath)
        print(f"Generated: {filepath} ({len(inv_list)} invoice(s))")
    
    # Generate Summary Report
    summary_path = generate_summary_report(summary_data, output_dir)
    if summary_path:
        generated_files.append(summary_path)

    return generated_files


def generate_single_csv(
    invoices: List[InvoiceData],
    output_path: str
) -> str:
    """
    Generate a single CSV file from a list of InvoiceData objects.
    
    Args:
        invoices: List of InvoiceData objects
        output_path: Full path for the output CSV file
        
    Returns:
        Path to generated file
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    entry_date = get_current_date_formatted()
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        
        for inv in invoices:
            if inv.extraction_errors and not inv.invoice_number:
                continue  # Skip failed extractions
            # Get all rows (may be multiple for taxable + non-taxable split)
            rows = invoice_to_csv_rows(inv, entry_date)
            for row in rows:
                writer.writerow(row)
    
    print(f"Generated: {output_path} ({len(invoices)} invoice(s))")
    return output_path




# ============================================================
# GUI APP SECTION
# ============================================================
"""
Invoice Parser GUI Application
Tkinter-based GUI for parsing airline invoices and generating Logisys CSV files.
"""

import os
import sys
import threading
import queue
from datetime import datetime
from pathlib import Path
from tkinter import (
    Tk, Frame, Label, Button, Entry, Text, Scrollbar, Canvas,
    filedialog, messagebox, StringVar, IntVar, BooleanVar,
    ttk, END, WORD, VERTICAL, RIGHT, LEFT, BOTH, Y, X, TOP, BOTTOM, NW, W, E, N, S
)
from typing import List, Optional

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Add current directory to path for imports


# --- Color Palette ---
BG_COLOR = "#F4F6F8"  # Nagarkot Light Background
CARD_BG = "#FFFFFF"   # Panel White
ACCENT = "#1F3F6E"    # Nagarkot Primary Blue
ACCENT_HOVER = "#2A528F" # Hover Blue
ACCENT_LIGHT = "#E3F2FD" # Light Blue
TEXT_PRIMARY = "#1E1E1E" # Dark Text
TEXT_SECONDARY = "#6B7280" # Muted Gray
BORDER_COLOR = "#E5E7EB" # Border Gray
SUCCESS_GREEN = "#1F3F6E" # Blue for success (Brand Rule)
ERROR_RED = "#D8232A"     # Nagarkot Red for errors
LOG_BG = "#FAFBFC"
LOG_FG = "#1E1E1E"


class LogRedirector:
    """Redirect print statements to the GUI log."""
    
    def __init__(self, text_widget, queue):
        self.text_widget = text_widget
        self.queue = queue
    
    def write(self, message):
        self.queue.put(message)
    
    def flush(self):
        pass


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)



class InvoiceParserApp:
    """Main application class for the Invoice Parser GUI."""
    
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("Invoice Parser for Logisys Upload")
        try:
            self.root.state("zoomed")
        except:
            self.root.attributes("-fullscreen", True)
        self.root.configure(bg=BG_COLOR)
        
        # Variables
        self.selected_files: List[str] = []
        self.output_dir = StringVar(value=os.getcwd())
        self.group_by_gstin = BooleanVar(value=True)
        self.is_processing = False
        self.log_queue = queue.Queue()
        
        # Configure ttk styles
        self._setup_styles()
        
        # Build UI
        self._create_widgets()
        self._start_log_polling()

    def _setup_styles(self):
        """Configure modern ttk styles."""
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Card-style LabelFrame
        style.configure(
            "Card.TLabelframe",
            background=CARD_BG,
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=CARD_BG,
            foreground=TEXT_PRIMARY,
            font=("Segoe UI", 10, "bold"),
        )

        # Regular buttons
        style.configure(
            "Modern.TButton",
            font=("Segoe UI", 9),
            padding=(14, 6),
            background="#FFFFFF",
            borderwidth=1,
            relief="solid",
        )
        style.map(
            "Modern.TButton",
            background=[("active", "#F5F5F5"), ("pressed", "#EEEEEE")],
        )

        # Accent (primary) button
        style.configure(
            "Accent.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(20, 8),
            foreground="#FFFFFF",
            background=ACCENT,
            borderwidth=0,
        )
        style.map(
            "Accent.TButton",
            background=[("active", ACCENT_HOVER), ("pressed", ACCENT_HOVER), ("disabled", "#90CAF9")],
            foreground=[("disabled", "#FFFFFF")],
        )

        # Progressbar
        style.configure(
            "blue.Horizontal.TProgressbar",
            troughcolor=BORDER_COLOR,
            background=ACCENT,
            thickness=8,
            borderwidth=0,
        )

        # Checkbutton
        style.configure(
            "Modern.TCheckbutton",
            background=CARD_BG,
            foreground=TEXT_PRIMARY,
            font=("Segoe UI", 9),
        )


    def _create_widgets(self):
        """Create all GUI widgets following Nagarkot Brand Standard."""
        
        # -------- Top-level container --------
        # Full screen root
        main_frame = Frame(self.root, bg=BG_COLOR)
        main_frame.pack(fill=BOTH, expand=True)

        # ================= HEADER =================
        # Dynamic height (driven by content padding), white background
        header_frame = Frame(main_frame, bg=CARD_BG, pady=16, padx=24)
        header_frame.pack(fill=X)
        
        # Bottom border/accent line
        Frame(main_frame, bg=BORDER_COLOR, height=1).pack(fill=X)

        # Logo (Left)
        # Use resource_path for PyInstaller compatibility
        logo_path = resource_path("logo.png")
        self._logo_image = None
        if HAS_PIL and os.path.isfile(logo_path):
            try:
                img = Image.open(logo_path)
                # Fixed height: 20 units (Workflow Rule)
                h = 40
                w = int(img.width * h / img.height)
                img = img.resize((w, h), Image.LANCZOS)
                self._logo_image = ImageTk.PhotoImage(img)
            except Exception:
                pass

        if self._logo_image:
            logo_label = Label(header_frame, image=self._logo_image, bg=CARD_BG)
            logo_label.pack(side=LEFT)
        else:
            # Fallback if no logo
            Label(header_frame, text="NAGARKOT", font=("Segoe UI", 12, "bold"), fg=ACCENT, bg=CARD_BG).pack(side=LEFT)

        # Title Block (Absolute Center)
        # We use a frame that expands to fill space, but content is centered?
        # A clearer way in pack/place mix:
        # We can place the title label at relx=0.5 of header_frame
        
        title_label = Label(
            header_frame,
            text="Airline Invoice Parser",
            font=("Segoe UI", 16, "bold"),
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
        )
        title_label.place(relx=0.5, rely=0.3, anchor="center")

        subtitle_label = Label(
            header_frame,
            text="Extract invoice data  \u2192  Generate Logisys CSV",
            font=("Segoe UI", 9),
            bg=CARD_BG,
            fg=TEXT_SECONDARY,
        )
        subtitle_label.place(relx=0.5, rely=0.75, anchor="center")

        # Ensure header frame has minimum height to accommodate title stacking
        # Logo is 20px + pady 16*2 = 52px total?
        # Title 16pt ~ 21px. Subtitle 9pt ~ 12px. Spacing 5px. Total ~38px text.
        # It fits nicely.

        # ================= BODY =================
        body = Frame(main_frame, bg=BG_COLOR, padx=40, pady=30)
        body.pack(fill=BOTH, expand=True)

        # --- File Selection Card ---
        file_card = ttk.LabelFrame(body, text="  Invoice PDFs  ", style="Card.TLabelframe", padding=20)
        file_card.pack(fill=X, pady=(0, 20))
        
        file_inner = Frame(file_card, bg=CARD_BG)
        file_inner.pack(fill=BOTH, expand=True)

        self.file_count_label = Label(
            file_inner, text="No files selected",
            fg=TEXT_SECONDARY, bg=CARD_BG, font=("Segoe UI", 11),
        )
        self.file_count_label.pack(anchor=W, pady=(0, 15))

        btn_frame = Frame(file_inner, bg=CARD_BG)
        btn_frame.pack(fill=X)

        ttk.Button(btn_frame, text="Select Files", command=self._select_files, style="Modern.TButton").pack(side=LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="Clear Selection", command=self._clear_files, style="Modern.TButton").pack(side=LEFT)

        # --- Action Row ---
        action_frame = Frame(body, bg=BG_COLOR)
        action_frame.pack(fill=X, pady=(0, 20))

        self.process_btn = ttk.Button(
            action_frame,
            text="\u25B6  Process & Generate CSV",
            command=self._start_processing,
            style="Accent.TButton",
        )
        self.process_btn.pack(side=LEFT, padx=(0, 20))

        self.progress = ttk.Progressbar(
            action_frame, mode="indeterminate", length=300,
            style="blue.Horizontal.TProgressbar",
        )
        self.progress.pack(side=LEFT, padx=(0, 15))

        self.status_label = Label(action_frame, text="Ready", fg=TEXT_SECONDARY, bg=BG_COLOR, font=("Segoe UI", 9))
        self.status_label.pack(side=LEFT)

        # --- Log Section Card ---
        # Occupy remaining space
        log_card = ttk.LabelFrame(body, text="  Processing Log  ", style="Card.TLabelframe", padding=15)
        log_card.pack(fill=BOTH, expand=True)
        
        log_inner = Frame(log_card, bg=CARD_BG)
        log_inner.pack(fill=BOTH, expand=True)

        self.log_text = Text(
            log_inner, height=10, wrap=WORD, state="disabled",
            bg=LOG_BG, fg=LOG_FG, font=("Consolas", 9),
            relief="flat", padx=10, pady=10,
        )
        log_scrollbar = Scrollbar(log_inner, orient=VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)
        log_scrollbar.pack(side=RIGHT, fill=Y)

        # Log tags (Using Nagarkot Brand Colors)
        self.log_text.tag_configure("success", foreground=SUCCESS_GREEN)
        self.log_text.tag_configure("error", foreground=ERROR_RED)
        self.log_text.tag_configure("info", foreground=ACCENT)
        self.log_text.tag_configure("warning", foreground="#E65100") # Keep warning orange for visibility

        # ================= FOOTER =================
        # Fixed at bottom, minimal
        footer_frame = Frame(main_frame, bg=CARD_BG, padx=24, pady=10)
        footer_frame.pack(fill=X, side=BOTTOM)
        
        # Top border for footer
        Frame(main_frame, bg=BORDER_COLOR, height=1).pack(fill=X, side=BOTTOM)

        Label(
            footer_frame,
            text="Nagarkot Forwarders Pvt. Ltd. \u00A9",
            fg=TEXT_SECONDARY, bg=CARD_BG, font=("Segoe UI", 8),
        ).pack(side=LEFT)

        clear_log_btn = ttk.Button(footer_frame, text="Clear Log", command=self._clear_log, style="Modern.TButton")
        clear_log_btn.pack(side=RIGHT)
    
    def _log(self, message: str, tag: str = None):
        """Add a message to the log text widget (Thread-safe)."""
        self.root.after(0, lambda: self._log_internal(message, tag))

    def _log_internal(self, message: str, tag: str = None):
        """Internal method to update log widget in main thread."""
        self.log_text.configure(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}\n"
        
        if tag:
            self.log_text.insert(END, formatted, tag)
        else:
            self.log_text.insert(END, formatted)
        
        self.log_text.see(END)
        self.log_text.configure(state="disabled")
    
    def _start_log_polling(self):
        """Poll the log queue and update the text widget."""
        try:
            while True:
                message = self.log_queue.get_nowait()
                if message.strip():
                    self._log(message.strip())
        except queue.Empty:
            pass
        self.root.after(100, self._start_log_polling)
    
    def _select_files(self):
        """Open file dialog to select PDF files."""
        files = filedialog.askopenfilenames(
            title="Select Invoice PDFs",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if files:
            self.selected_files = list(files)
            self._update_file_list()
    
    def _clear_files(self):
        """Clear the file selection."""
        self.selected_files = []
        self._update_file_list()
    
    def _update_file_list(self):
        """Update the file count label."""
        count = len(self.selected_files)
        if count == 0:
            self.file_count_label.configure(text="No files selected", fg=TEXT_SECONDARY)
        else:
            self.file_count_label.configure(text=f"{count} file(s) selected", fg=TEXT_PRIMARY)
    
    def _clear_log(self):
        """Clear the log text widget."""
        self.log_text.configure(state="normal")
        self.log_text.delete(1.0, END)
        self.log_text.configure(state="disabled")
    
    def _start_processing(self):
        """Start processing invoices in a background thread."""
        if not self.selected_files:
            messagebox.showwarning("No Files", "Please select at least one PDF file.")
            return
        
        if self.is_processing:
            return
        
        self.is_processing = True
        self.process_btn.configure(state="disabled")
        self.progress.start(10)
        self.status_label.configure(text="Processing...", fg=ACCENT)
        
        # Start background thread
        thread = threading.Thread(target=self._process_invoices, daemon=True)
        thread.start()
    
    def _process_invoices(self):
        """Process all selected invoices (runs in background thread)."""
        try:
            parsed_invoices: List[InvoiceData] = []
            total = len(self.selected_files)
            success_count = 0
            failed_count = 0
            
            self._log(f"Starting to process {total} file(s)...", "info")
            
            for i, pdf_path in enumerate(self.selected_files, 1):
                filename = os.path.basename(pdf_path)
                
                try:
                    self._log(f"[{i}/{total}] Parsing: {filename}")
                    invoice = parse_invoice(pdf_path)
                    
                    if invoice.invoice_number:
                        parsed_invoices.append(invoice)
                        self._log(f"  ✓ {invoice.airline}: {invoice.invoice_number} | Total: ₹{invoice.total_amount}", "success")
                        success_count += 1
                    else:
                        errors = ", ".join(invoice.extraction_errors) if invoice.extraction_errors else "Unknown error"
                        self._log(f"  ✗ Failed: {errors}", "error")
                        failed_count += 1
                        
                except Exception as e:
                    self._log(f"  ✗ Error processing {filename}: {str(e)}", "error")
                    failed_count += 1
            
            # Generate CSV
            if parsed_invoices:
                self._log(f"\nGenerating CSV file(s)...", "info")

                # Ask user where to save
                output_dir = filedialog.askdirectory(
                    title="Select Output Directory for CSV",
                    initialdir=os.getcwd(),
                )
                if not output_dir:
                    self._log("CSV generation cancelled by user.", "warning")
                    return

                self.output_dir.set(output_dir)
                
                try:
                    generated_files = generate_csv(
                        parsed_invoices,
                        output_dir,
                        group_by_gstin=self.group_by_gstin.get()
                    )
                    
                    self._log(f"Successfully generated {len(generated_files)} file(s).", "success")
                    has_summary = any("Processing_Summary" in f for f in generated_files)
                    
                    for f in generated_files:
                        if "Processing_Summary" in f:
                            self._log(f"  ⚠ Validation Report: {os.path.basename(f)}", "warning")
                        else:
                            self._log(f"  - {os.path.basename(f)}", "success")
                    
                    if has_summary:
                        self._log("Check the Validation Report for any missing mappings.", "info")
                    
                    self._log(f"\n✓ Complete! Processed {success_count}/{total} invoices.", "success")
                    self._log(f"  Output directory: {output_dir}", "info")
                    
                except Exception as e:
                    self._log(f"  ✗ CSV generation error: {str(e)}", "error")
            else:
                self._log("No invoices were successfully parsed.", "warning")
            
            if failed_count > 0:
                self._log(f"  ⚠ {failed_count} file(s) failed to parse", "warning")
                
        except Exception as e:
            self._log(f"Processing error: {str(e)}", "error")
        
        finally:
            # Update UI in main thread
            self.root.after(0, self._processing_complete)
    
    def _processing_complete(self):
        """Called when processing is complete."""
        self.is_processing = False
        self.process_btn.configure(state="normal")
        self.progress.stop()
        self.status_label.configure(text="Complete", fg=SUCCESS_GREEN)


def main():
    """Main entry point."""
    root = Tk()
    app = InvoiceParserApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
