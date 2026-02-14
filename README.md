# Nagarkot Invoice Processor

GUI application to parse airline PDF invoices (IndiGo, Air India, Akasa Air, etc.) and generate Logisys-compatible CSV files.

## Tech Stack
- Python 3.11+
- pdfplumber
- Tkinter (Built-in)
- Pillow

> 📖 **See [USER_GUIDE.md](USER_GUIDE.md) for detailed usage instructions.**

---

## Installation

### 1. Create Virtual Environment (MANDATORY)

You **must** use a virtual environment for this project.

```bash
python -m venv venv
```

### 2. Activate Virtual Environment

**Windows:**
```cmd
venv\Scripts\activate
```

**Mac/Linux:**
```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Usage

### Run Application

Ensure the virtual environment is active:

```bash
python invoice_processor.py
```

1. Select PDF invoices via the GUI.
2. Click **Process & Generate CSV**.
3. Files will be saved to your chosen directory.

---

## Build Executable (exe)

To generate a standalone `.exe` file for distribution:

1. **Ensure all dependencies are installed** inside the active venv.
2. **Install PyInstaller**:
   ```bash
   pip install pyinstaller
   ```
3. **Build using the Spec file**:
   ```bash
   pyinstaller InvoiceParser.spec
   ```
   *(Running directly on `invoice_processor.py` may miss assets like the logo)*

4. **Locate Executable**:
   The `MMT Flight Invoice Parser.exe` will be in the `dist/` folder.

---

## Project Structure

- `invoice_processor.py`: Main application code (Logic + GUI).
- `requirements.txt`: Python dependencies.
- `logo.png` / `logo.ico`: Application branding assets.
- `InvoiceParser.spec`: PyInstaller build configuration.

---

## Notes
- **Always confirm venv is active** before running python commands.
- Do not commit `venv`, `dist`, or `build` folders.
