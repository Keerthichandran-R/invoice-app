# invoice-app
# Invoice Manager

A simple Python-based application to manage and automate **inward** and **outward** invoices.

## Features
- Add, edit, delete invoices
- Separate inward and outward invoice tracking
- Search and filter by type, customer, invoice number, and date range
- Automatic invoice numbering
- Export invoice data to CSV
- Optional PDF invoice generation
- Stores data in a local SQLite database

---

## Requirements
- **Python 3.8+**
- **Tkinter** (for GUI)
- **SQLite** (comes built-in with Python)
- Optional:
  - `pandas` for improved CSV export
  - `reportlab` for PDF generation

---

## Installation

1. **Clone or download** this repository.
2. Install dependencies:
   ```bash
   pip install pandas reportlab
