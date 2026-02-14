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
try:
    from invoice_parser import InvoiceData, GSTIN_STATE_MAP
except ImportError:
    from .invoice_parser import InvoiceData, GSTIN_STATE_MAP


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
    "27AABCA0522B1ZK": "MUMBAI"
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
    dr_cr = "Dr" if invoice.invoice_type == "TAX_INVOICE" else "Cr"
    
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
        "Charge or GL": "TRAVELLING EXPENSES",
        "Charge or GL Name": "TRAVELLING EXPENSES",
        "Charge or GL Amount": str(amount),
        "DR or CR": dr_cr,
        "Cost Center": "",
        "Branch": branch,
        " Charge Narration": "",
        "TaxGroup": "GSTIN" if invoice.customer_gstin and not is_non_taxable else "",
        "Tax Type": "Non-Taxable" if is_non_taxable else "Taxable",
        "SAC or HSN": "996425" if not is_non_taxable else "",  # Air Transport SAC code only for taxable
        "Taxcode1": taxcode1,
        "Taxcode1 Amt": taxcode1_amt,
        "Taxcode2": taxcode2,
        "Taxcode2 Amt": taxcode2_amt,
        "Taxcode3": taxcode3,
        "Taxcode3 Amt": taxcode3_amt,
        "Taxcode4": "",
        "Taxcode4 Amt": "",
        "Avail Tax Credit": "Yes" if not is_non_taxable else "No",
        "LOB": "",
        "Ref Type": "",
        "Ref No": "",
        "Amount": str(invoice.total_amount),  # Total amount for the invoice
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
    
    for gstin, inv_list in groups.items():
        # Get state name for filename
        if gstin != "UNKNOWN" and gstin != "all" and len(gstin) >= 2:
            state = STATE_TO_BRANCH.get(gstin[:2], "Unknown")
        else:
            state = "Unknown"
        
        # Create filename with timestamp to avoid overwriting
        timestamp = datetime.now().strftime("%d%b%Y_%H%M").upper()
        filename = f"{filename_prefix}_{state}_{gstin}_{timestamp}.csv"
        filepath = os.path.join(output_dir, filename)
        
        # Write CSV
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            
            for inv in inv_list:
                if inv.extraction_errors and not inv.invoice_number:
                    continue  # Skip failed extractions
                # Get all rows (may be multiple for taxable + non-taxable split)
                rows = invoice_to_csv_rows(inv, entry_date)
                for row in rows:
                    writer.writerow(row)
        
        generated_files.append(filepath)
        print(f"Generated: {filepath} ({len(inv_list)} invoice(s))")
    
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


if __name__ == "__main__":
    # Test with sample data
    import sys
    from invoice_parser import parse_invoice
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        invoice = parse_invoice(pdf_path)
        
        if invoice.invoice_number:
            row = invoice_to_csv_row(invoice)
            print("CSV Row:")
            for k, v in row.items():
                if v:  # Only print non-empty values
                    print(f"  {k}: {v}")
        else:
            print("Failed to extract invoice data")
            print("Errors:", invoice.extraction_errors)
    else:
        print("Usage: python csv_generator.py <pdf_path>")
