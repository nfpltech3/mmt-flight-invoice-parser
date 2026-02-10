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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from invoice_parser import parse_invoice, InvoiceData
from csv_generator import generate_csv, generate_single_csv, CSV_HEADERS

# --- Color Palette ---
BG_COLOR = "#F0F2F5"
CARD_BG = "#FFFFFF"
ACCENT = "#1565C0"
ACCENT_HOVER = "#0D47A1"
ACCENT_LIGHT = "#E3F2FD"
TEXT_PRIMARY = "#212121"
TEXT_SECONDARY = "#757575"
BORDER_COLOR = "#E0E0E0"
SUCCESS_GREEN = "#2E7D32"
LOG_BG = "#FAFBFC"
LOG_FG = "#333333"


class LogRedirector:
    """Redirect print statements to the GUI log."""
    
    def __init__(self, text_widget, queue):
        self.text_widget = text_widget
        self.queue = queue
    
    def write(self, message):
        self.queue.put(message)
    
    def flush(self):
        pass


class InvoiceParserApp:
    """Main application class for the Invoice Parser GUI."""
    
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("Invoice Parser for Logisys Upload")
        self.root.geometry("960x740")
        self.root.minsize(850, 650)
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
        """Create all GUI widgets."""
        
        # -------- Top-level scrollable container --------
        main_frame = Frame(self.root, bg=BG_COLOR)
        main_frame.pack(fill=BOTH, expand=True)

        # ================= HEADER =================
        header_frame = Frame(main_frame, bg=CARD_BG, pady=12, padx=20)
        header_frame.pack(fill=X)
        # thin accent line under header
        Frame(main_frame, bg=ACCENT, height=3).pack(fill=X)

        # Logo
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
        self._logo_image = None
        if HAS_PIL and os.path.isfile(logo_path):
            try:
                img = Image.open(logo_path)
                # scale to 40px height keeping aspect ratio
                h = 40
                w = int(img.width * h / img.height)
                img = img.resize((w, h), Image.LANCZOS)
                self._logo_image = ImageTk.PhotoImage(img)
            except Exception:
                pass

        if self._logo_image:
            logo_label = Label(header_frame, image=self._logo_image, bg=CARD_BG)
            logo_label.pack(side=LEFT, padx=(0, 12))

        title_block = Frame(header_frame, bg=CARD_BG)
        title_block.pack(side=LEFT)

        Label(
            title_block,
            text="Airline Invoice Parser",
            font=("Segoe UI", 17, "bold"),
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
        ).pack(anchor=W)

        Label(
            title_block,
            text="Extract invoice data  \u2192  Generate Logisys CSV",
            font=("Segoe UI", 10),
            bg=CARD_BG,
            fg=ACCENT,
        ).pack(anchor=W)

        # ================= BODY =================
        body = Frame(main_frame, bg=BG_COLOR, padx=20, pady=14)
        body.pack(fill=BOTH, expand=True)

        # --- File Selection Card ---
        file_card = ttk.LabelFrame(body, text="  Invoice PDFs  ", style="Card.TLabelframe", padding=14)
        file_card.pack(fill=X, pady=(0, 12))
        file_inner = Frame(file_card, bg=CARD_BG)
        file_inner.pack(fill=BOTH, expand=True)

        self.file_count_label = Label(
            file_inner, text="No files selected",
            fg=TEXT_SECONDARY, bg=CARD_BG, font=("Segoe UI", 11),
        )
        self.file_count_label.pack(anchor=W, pady=(0, 10))

        btn_frame = Frame(file_inner, bg=CARD_BG)
        btn_frame.pack(fill=X)

        ttk.Button(btn_frame, text="Select", command=self._select_files, style="Modern.TButton").pack(side=LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="Clear", command=self._clear_files, style="Modern.TButton").pack(side=LEFT)

        # --- Action Row ---
        action_frame = Frame(body, bg=BG_COLOR)
        action_frame.pack(fill=X, pady=(0, 10))

        self.process_btn = ttk.Button(
            action_frame,
            text="\u25B6  Process Invoices",
            command=self._start_processing,
            style="Accent.TButton",
        )
        self.process_btn.pack(side=LEFT, padx=(0, 14))

        self.progress = ttk.Progressbar(
            action_frame, mode="indeterminate", length=260,
            style="blue.Horizontal.TProgressbar",
        )
        self.progress.pack(side=LEFT, padx=(0, 12))

        self.status_label = Label(action_frame, text="Ready", fg=TEXT_SECONDARY, bg=BG_COLOR, font=("Segoe UI", 9))
        self.status_label.pack(side=LEFT)

        # --- Log Section Card ---
        log_card = ttk.LabelFrame(body, text="  Processing Log  ", style="Card.TLabelframe", padding=10)
        log_card.pack(fill=BOTH, expand=True)
        log_inner = Frame(log_card, bg=CARD_BG)
        log_inner.pack(fill=BOTH, expand=True)

        self.log_text = Text(
            log_inner, height=10, wrap=WORD, state="disabled",
            bg=LOG_BG, fg=LOG_FG, font=("Consolas", 9),
            relief="solid", borderwidth=1, highlightthickness=0,
            insertbackground=LOG_FG, padx=8, pady=6,
        )
        log_scrollbar = Scrollbar(log_inner, orient=VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)
        log_scrollbar.pack(side=RIGHT, fill=Y)

        # Log tags (light-friendly colors)
        self.log_text.tag_configure("success", foreground="#2E7D32")
        self.log_text.tag_configure("error", foreground="#C62828")
        self.log_text.tag_configure("info", foreground="#1565C0")
        self.log_text.tag_configure("warning", foreground="#E65100")

        # ================= FOOTER =================
        footer_frame = Frame(main_frame, bg=CARD_BG, padx=20, pady=8)
        footer_frame.pack(fill=X, side=BOTTOM)
        # thin line above footer
        Frame(main_frame, bg=BORDER_COLOR, height=1).pack(fill=X, side=BOTTOM)

        Label(
            footer_frame,
            text="\u00A9 Nagarkot Forwarders Pvt Ltd | Supported Air India, Air India Express, IndiGo, Akasa Air, Gulf Air",
            fg=TEXT_SECONDARY, bg=CARD_BG, font=("Segoe UI", 8),
        ).pack(side=LEFT)

        # Generate CSV blue button (bottom-right like BLR tool)
        self.gen_csv_btn = Button(
            footer_frame, text="  \U0001F4CB  Generate CSV  ",
            command=self._start_processing,
            font=("Segoe UI", 10, "bold"),
            bg=ACCENT, fg="white", activebackground=ACCENT_HOVER, activeforeground="white",
            relief="flat", cursor="hand2", padx=16, pady=6,
        )
        self.gen_csv_btn.pack(side=RIGHT)

        clear_log_btn = ttk.Button(footer_frame, text="Clear Log", command=self._clear_log, style="Modern.TButton")
        clear_log_btn.pack(side=RIGHT, padx=(0, 10))
    
    def _log(self, message: str, tag: str = None):
        """Add a message to the log text widget."""
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
        self.gen_csv_btn.configure(state="disabled")
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
                    
                    for f in generated_files:
                        self._log(f"  ✓ Created: {os.path.basename(f)}", "success")
                    
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
        self.gen_csv_btn.configure(state="normal")
        self.progress.stop()
        self.status_label.configure(text="Complete", fg=SUCCESS_GREEN)


def main():
    """Main entry point."""
    root = Tk()
    app = InvoiceParserApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
