# Nagarkot Airline Invoice Parser User Guide

## Introduction
The Airline Invoice Parser is a Windows desktop application designed to streamline the accounting process for **Nagarkot Forwarders Pvt Ltd**. It automatically extracts data from airline PDF invoices (Air India, Air India Express, IndiGo, Akasa Air, and Gulf Air) and generates formatted CSV files ready for upload to the **Logisys ERP** system.

## How to Use

### 1. Launching the App
1. Locate the **MMT Flight Invoice Parser.exe** file on your computer.
2. Double-click to launch. The application will open in **full-screen mode** with the Nagarkot branding.

### 2. The Workflow (Step-by-Step)

#### Step 1: Select Invoices
1. Click the **Select Files** button in the "Invoice PDFs" section.
2. A file dialog will appear. Navigate to the folder containing your PDF invoices.
3. Select one or multiple PDF files (hold `Ctrl` or `Shift` to select multiple).
4. Click **Open**. 
   - *Result:* The app will display the count of selected files (e.g., "5 file(s) selected").

#### Step 2: Process & Generate CSV
1. Click the blue **▶ Process & Generate CSV** button.
2. The application will start parsing the files. You will see a progress bar and a "Processing..." status.
   - *Note:* The processing happens in the background, so the app remains responsive.
3. The **Processing Log** will update in real-time:
   - **Green (✓):** Successfully parsed invoice (displays Airline, Invoice No, and Amount).
   - **Red (✗):** Parsing failed (displays the reason).
   - **Orange (⚠):** Warnings or skipped files (e.g., credit notes).

#### Step 3: Save the CSV
1. Once parsing is complete, a "Select Output Directory" dialog will appear.
2. Choose the folder where you want to save the Excel/CSV files.
3. Click **Select Folder**.
4. The app will generate the CSV files and display a "✓ Complete!" message in the log.
   - The files are named automatically: `transport_expenses_[State]_[GSTIN]_[Timestamp].csv`.

---

## Interface Reference

| Control / Input | Description | Expected Format / Behavior |
| :--- | :--- | :--- |
| **Select Files** | Opens file explorer to pick PDFs. | Accepts `.pdf` files only. |
| **Clear Selection** | Removes all currently selected files. | Resets count to "No files selected". |
| **Process & Generate CSV** | Starts the extraction and export process. | Disabled while processing. |
| **Processing Log** | Shows status, errors, and success messages. | Scrollable text area. |
| **Clear Log** | Clears the text from the log window. | - |

---

## Troubleshooting & Validations

If you see an error in the **Processing Log**, check this table:

| Message / Error | Possible Cause | How to Fix |
| :--- | :--- | :--- |
| **"Credit notes are not supported"** | The filename contains "CREDIT" or the document type is detected as a Credit Note. | This tool only processes Tax Invoices and Debit Notes. Remove Credit Notes from selection. |
| **"Could not extract text from PDF"** | The PDF might be a scanned image (non-selectable text) or encrypted. | Use OCR to convert the PDF to text-searchable format, or ensure it's a digital text PDF. |
| **"Invoice number not found"** | The parser couldn't find the invoice number pattern in the text. | Check if the invoice format has changed or if it's a non-standard document. |
| **"Total amount not found or is zero"** | The extraction logic failed to find the "Total" or "Grand Total" line. | Verify the invoice isn't truncated. Open the PDF to ensure the Total is visible. |
| **"Customer GSTIN not found"** | The parser couldn't identify the pattern `\d{2}[A-Z]{5}...` for the customer. | Ensure the invoice is billed to a valid entity with a GSTIN. |
| **"Unknown invoice format"** | The airline is not recognized. | Supported airlines: Air India, AI Express, IndiGo, Akasa, Gulf Air. |

---

## Technical Details (For IT Support)

* **Supported Airlines:** 
  * Air India / AI Express
  * IndiGo (InterGlobe Aviation)
  * Akasa Air (SNV Aviation)
  * Gulf Air
* **Extraction Logic:** Uses text landmarks (Regex) to identify fields. Values are cross-verified (e.g., Taxable + Non-Taxable + Taxes ≈ Total).
* **CSV Output:** 41-column format matching the Logisys "Purchase Upload" template.
* **IGST Logic:** If IGST is present, `Avail Tax Credit` is set to `100`; otherwise `Yes`.
