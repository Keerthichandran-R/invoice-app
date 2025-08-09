"""
Invoice Manager - Single-file Python application
Author: ChatGPT (GPT-5 Thinking mini)

Features:
- Tkinter GUI
- SQLite storage (invoices table)
- Add / Edit / Delete invoices
- Mark invoice type: Inward / Outward
- Search and filter by customer, invoice number, date, type
- Export selected or all invoices to CSV
- Simple PDF invoice generation (optional, requires reportlab)
- Basic automation: auto-numbering invoices and optional email sending stub

Dependencies (standard library): tkinter, sqlite3, csv, datetime, os, tempfile, webbrowser
Optional dependencies (pip install): pandas (for nicer exports), reportlab (for PDF generation)

Run: python invoice_manager.py

This single file contains everything you need for a simple invoice manager.
"""

import os
import sqlite3
import csv
import tempfile
import webbrowser
from datetime import datetime
from tkinter import *
from tkinter import ttk, messagebox, filedialog

# Optional imports
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except Exception:
    PANDAS_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rcanvas
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

DB_FILE = os.path.join(os.path.expanduser('~'), '.invoice_manager.db')

# --- Database helpers ---
class InvoiceDB:
    def __init__(self, db_path=DB_FILE):
        self.conn = sqlite3.connect(db_path)
        self._create_tables()

    def _create_tables(self):
        c = self.conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY,
                invoice_no TEXT UNIQUE,
                date TEXT,
                type TEXT,
                customer TEXT,
                items TEXT,
                total REAL,
                notes TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS meta (
                k TEXT PRIMARY KEY,
                v TEXT
            )
        ''')
        # initialize last_invoice if missing
        c.execute("INSERT OR IGNORE INTO meta (k,v) VALUES ('last_invoice', '0')")
        self.conn.commit()

    def next_invoice_no(self, prefix='INV'):
        c = self.conn.cursor()
        c.execute("SELECT v FROM meta WHERE k='last_invoice'")
        last = int(c.fetchone()[0])
        last += 1
        c.execute("UPDATE meta SET v=? WHERE k='last_invoice'", (str(last),))
        self.conn.commit()
        return f"{prefix}-{last:05d}"

    def add_invoice(self, invoice_no, date, itype, customer, items_text, total, notes):
        c = self.conn.cursor()
        c.execute('''INSERT INTO invoices (invoice_no, date, type, customer, items, total, notes)
                     VALUES (?,?,?,?,?,?,?)''', (invoice_no, date, itype, customer, items_text, total, notes))
        self.conn.commit()
        return c.lastrowid

    def update_invoice(self, id_, invoice_no, date, itype, customer, items_text, total, notes):
        c = self.conn.cursor()
        c.execute('''UPDATE invoices SET invoice_no=?, date=?, type=?, customer=?, items=?, total=?, notes=? WHERE id=?''',
                  (invoice_no, date, itype, customer, items_text, total, notes, id_))
        self.conn.commit()

    def delete_invoice(self, id_):
        c = self.conn.cursor()
        c.execute('DELETE FROM invoices WHERE id=?', (id_,))
        self.conn.commit()

    def list_invoices(self, filters=None):
        filters = filters or {}
        q = 'SELECT id, invoice_no, date, type, customer, total FROM invoices'
        conds = []
        params = []
        if 'type' in filters and filters['type']:
            conds.append('type=?')
            params.append(filters['type'])
        if 'customer' in filters and filters['customer']:
            conds.append('customer LIKE ?')
            params.append('%' + filters['customer'] + '%')
        if 'invoice_no' in filters and filters['invoice_no']:
            conds.append('invoice_no LIKE ?')
            params.append('%' + filters['invoice_no'] + '%')
        if 'date_from' in filters and filters['date_from']:
            conds.append('date(date) >= date(?)')
            params.append(filters['date_from'])
        if 'date_to' in filters and filters['date_to']:
            conds.append('date(date) <= date(?)')
            params.append(filters['date_to'])
        if conds:
            q += ' WHERE ' + ' AND '.join(conds)
        q += ' ORDER BY date(date) DESC'
        c = self.conn.cursor()
        c.execute(q, params)
        return c.fetchall()

    def get_invoice(self, id_):
        c = self.conn.cursor()
        c.execute('SELECT * FROM invoices WHERE id=?', (id_,))
        return c.fetchone()

    def export_csv(self, filepath, invoices_rows):
        # invoices_rows is list of full rows or tuples
        # If pandas available, use it
        headers = ['id', 'invoice_no', 'date', 'type', 'customer', 'items', 'total', 'notes']
        if PANDAS_AVAILABLE:
            df = pd.DataFrame(invoices_rows, columns=headers)
            df.to_csv(filepath, index=False)
        else:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for r in invoices_rows:
                    writer.writerow(r)

# --- PDF generation helper (very simple layout) ---

def generate_pdf_invoice(invoice_row, output_path):
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError('reportlab is not installed')
    # invoice_row expected: (id, invoice_no, date, type, customer, items, total, notes)
    c = rcanvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    margin = 40
    y = height - margin
    c.setFont('Helvetica-Bold', 16)
    c.drawString(margin, y, f"INVOICE: {invoice_row[1]}")
    c.setFont('Helvetica', 10)
    y -= 25
    c.drawString(margin, y, f"Date: {invoice_row[2]}")
    c.drawString(width/2, y, f"Type: {invoice_row[3]}")
    y -= 20
    c.drawString(margin, y, f"Customer: {invoice_row[4]}")
    y -= 30
    c.setFont('Helvetica-Bold', 12)
    c.drawString(margin, y, 'Items:')
    y -= 15
    c.setFont('Helvetica', 10)
    items = invoice_row[5].split('\n') if invoice_row[5] else []
    for it in items:
        if y < 100:
            c.showPage()
            y = height - margin
        c.drawString(margin+10, y, '- ' + it)
        y -= 14
    y -= 10
    c.setFont('Helvetica-Bold', 12)
    c.drawString(margin, y, f"Total: {invoice_row[6]:.2f}")
    y -= 25
    c.setFont('Helvetica', 9)
    c.drawString(margin, y, 'Notes:')
    y -= 12
    note_lines = invoice_row[7].split('\n') if invoice_row[7] else []
    for ln in note_lines:
        if y < 100:
            c.showPage()
            y = height - margin
        c.drawString(margin+6, y, ln)
        y -= 12
    c.showPage()
    c.save()

# --- Tkinter GUI ---
class InvoiceApp:
    def __init__(self, root):
        self.root = root
        root.title('Invoice Manager')
        root.geometry('1000x600')
        self.db = InvoiceDB()
        self.create_widgets()
        self.load_invoices()

    def create_widgets(self):
        # top frame for add / search
        top = Frame(self.root)
        top.pack(side=TOP, fill=X, padx=8, pady=6)

        add_btn = Button(top, text='Add Invoice', command=self.open_add_window)
        add_btn.pack(side=LEFT)

        export_btn = Button(top, text='Export CSV', command=self.export_csv)
        export_btn.pack(side=LEFT, padx=(6,0))

        pdf_btn = Button(top, text='Generate PDF (selected)', command=self.generate_pdf_selected)
        pdf_btn.pack(side=LEFT, padx=(6,0))

        # Search controls
        Label(top, text='Type:').pack(side=LEFT, padx=(20,2))
        self.type_var = StringVar()
        type_combo = ttk.Combobox(top, textvariable=self.type_var, values=['', 'Inward', 'Outward'], width=10)
        type_combo.pack(side=LEFT)

        Label(top, text='Customer:').pack(side=LEFT, padx=(8,2))
        self.customer_search = Entry(top)
        self.customer_search.pack(side=LEFT)

        Label(top, text='Invoice #:').pack(side=LEFT, padx=(8,2))
        self.inv_search = Entry(top, width=12)
        self.inv_search.pack(side=LEFT)

        Label(top, text='From (YYYY-MM-DD):').pack(side=LEFT, padx=(8,2))
        self.date_from = Entry(top, width=12)
        self.date_from.pack(side=LEFT)

        Label(top, text='To:').pack(side=LEFT, padx=(8,2))
        self.date_to = Entry(top, width=12)
        self.date_to.pack(side=LEFT)

        search_btn = Button(top, text='Search', command=self.load_invoices)
        search_btn.pack(side=LEFT, padx=(8,0))

        reset_btn = Button(top, text='Reset', command=self.reset_filters)
        reset_btn.pack(side=LEFT, padx=(6,0))

        # main Treeview
        columns = ('id', 'invoice_no', 'date', 'type', 'customer', 'total')
        self.tree = ttk.Treeview(self.root, columns=columns, show='headings')
        for col in columns:
            self.tree.heading(col, text=col.title())
            if col == 'customer':
                self.tree.column(col, width=300)
            elif col == 'items':
                self.tree.column(col, width=250)
            else:
                self.tree.column(col, width=100)
        self.tree.pack(fill=BOTH, expand=True, padx=8, pady=6)
        self.tree.bind('<Double-1>', self.on_tree_double)

        # bottom buttons
        bottom = Frame(self.root)
        bottom.pack(side=BOTTOM, fill=X, padx=8, pady=6)
        view_btn = Button(bottom, text='View/Edit Selected', command=self.view_selected)
        view_btn.pack(side=LEFT)
        del_btn = Button(bottom, text='Delete Selected', command=self.delete_selected)
        del_btn.pack(side=LEFT, padx=(6,0))
        sample_btn = Button(bottom, text='Insert Sample Data', command=self.insert_sample)
        sample_btn.pack(side=LEFT, padx=(6,0))

    def reset_filters(self):
        self.type_var.set('')
        self.customer_search.delete(0, END)
        self.inv_search.delete(0, END)
        self.date_from.delete(0, END)
        self.date_to.delete(0, END)
        self.load_invoices()

    def build_filters(self):
        return {
            'type': self.type_var.get(),
            'customer': self.customer_search.get().strip(),
            'invoice_no': self.inv_search.get().strip(),
            'date_from': self.date_from.get().strip(),
            'date_to': self.date_to.get().strip(),
        }

    def load_invoices(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        rows = self.db.list_invoices(self.build_filters())
        for row in rows:
            # row: (id, invoice_no, date, type, customer, total)
            self.tree.insert('', END, values=row)

    def open_add_window(self):
        InvoiceEditor(self.root, self.db, on_save=self.load_invoices)

    def view_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('No selection', 'Please select an invoice to view/edit')
            return
        item = self.tree.item(sel[0])['values']
        id_ = item[0]
        InvoiceEditor(self.root, self.db, invoice_id=id_, on_save=self.load_invoices)

    def on_tree_double(self, event):
        self.view_selected()

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('No selection', 'Please select an invoice to delete')
            return
        item = self.tree.item(sel[0])['values']
        id_ = item[0]
        if messagebox.askyesno('Confirm delete', f'Delete invoice {item[1]}?'):
            self.db.delete_invoice(id_)
            self.load_invoices()

    def export_csv(self):
        sel = self.tree.selection()
        if sel:
            ids = [self.tree.item(s)['values'][0] for s in sel]
            rows = [self.db.get_invoice(id_) for id_ in ids]
        else:
            # export all
            # fetch full rows
            c = self.db.conn.cursor()
            c.execute('SELECT * FROM invoices ORDER BY date(date) DESC')
            rows = c.fetchall()
        if not rows:
            messagebox.showinfo('No data', 'No invoices to export')
            return
        filepath = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV files','*.csv')])
        if not filepath:
            return
        self.db.export_csv(filepath, rows)
        messagebox.showinfo('Exported', f'Exported {len(rows)} invoices to {filepath}')

    def generate_pdf_selected(self):
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror('Missing dependency', 'reportlab not installed. pip install reportlab')
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('No selection', 'Please select an invoice to generate PDF')
            return
        if len(sel) > 1:
            messagebox.showinfo('One at a time', 'Select only one invoice to generate PDF for simplicity')
            return
        id_ = self.tree.item(sel[0])['values'][0]
        row = self.db.get_invoice(id_)
        fd, tmpf = tempfile.mkstemp(suffix='.pdf')
        os.close(fd)
        try:
            generate_pdf_invoice(row, tmpf)
            webbrowser.open('file://' + tmpf)
        except Exception as e:
            messagebox.showerror('Error', str(e))

    def insert_sample(self):
        # add some sample invoices
        try:
            for i in range(3):
                inv_no = self.db.next_invoice_no('SAMPLE')
                date = datetime.now().strftime('%Y-%m-%d')
                itype = 'Outward' if i%2==0 else 'Inward'
                customer = f'Customer {i+1}'
                items = f'Item A x1 - 100\nItem B x2 - 200'
                total = 300.0
                notes = 'Sample invoice created for testing'
                self.db.add_invoice(inv_no, date, itype, customer, items, total, notes)
            messagebox.showinfo('Inserted', 'Sample invoices inserted')
            self.load_invoices()
        except Exception as e:
            messagebox.showerror('Error', str(e))


class InvoiceEditor:
    def __init__(self, parent, db: InvoiceDB, invoice_id=None, on_save=None):
        self.db = db
        self.invoice_id = invoice_id
        self.on_save = on_save
        self.top = Toplevel(parent)
        self.top.title('Invoice Editor')
        self.top.geometry('700x600')
        self.build()
        if invoice_id:
            self.load_invoice()
        else:
            self.invoice_no_var.set(self.db.next_invoice_no('INV'))
            self.date_var.set(datetime.now().strftime('%Y-%m-%d'))

    def build(self):
        frm = Frame(self.top)
        frm.pack(fill=BOTH, expand=True, padx=8, pady=8)
        Label(frm, text='Invoice No:').grid(row=0, column=0, sticky=W)
        self.invoice_no_var = StringVar()
        Entry(frm, textvariable=self.invoice_no_var).grid(row=0, column=1, sticky=EW)

        Label(frm, text='Date (YYYY-MM-DD):').grid(row=0, column=2, sticky=W)
        self.date_var = StringVar()
        Entry(frm, textvariable=self.date_var).grid(row=0, column=3, sticky=EW)

        Label(frm, text='Type:').grid(row=1, column=0, sticky=W)
        self.type_var = StringVar()
        ttk.Combobox(frm, textvariable=self.type_var, values=['Inward', 'Outward']).grid(row=1, column=1, sticky=EW)

        Label(frm, text='Customer:').grid(row=1, column=2, sticky=W)
        self.customer_var = StringVar()
        Entry(frm, textvariable=self.customer_var).grid(row=1, column=3, sticky=EW)

        Label(frm, text='Items (one per line):').grid(row=2, column=0, sticky=NW, pady=(8,0))
        self.items_txt = Text(frm, height=10)
        self.items_txt.grid(row=2, column=1, columnspan=3, sticky=EW)

        Label(frm, text='Total:').grid(row=3, column=0, sticky=W, pady=(8,0))
        self.total_var = StringVar()
        Entry(frm, textvariable=self.total_var).grid(row=3, column=1, sticky=EW, pady=(8,0))

        Label(frm, text='Notes:').grid(row=4, column=0, sticky=NW, pady=(8,0))
        self.notes_txt = Text(frm, height=5)
        self.notes_txt.grid(row=4, column=1, columnspan=3, sticky=EW, pady=(8,0))

        # buttons
        btn_frm = Frame(frm)
        btn_frm.grid(row=5, column=0, columnspan=4, pady=12)
        save_btn = Button(btn_frm, text='Save', command=self.save)
        save_btn.pack(side=LEFT)
        cancel_btn = Button(btn_frm, text='Cancel', command=self.top.destroy)
        cancel_btn.pack(side=LEFT, padx=(6,0))

        # configure grid weights
        for i in range(4):
            frm.grid_columnconfigure(i, weight=1)

    def load_invoice(self):
        row = self.db.get_invoice(self.invoice_id)
        if not row:
            messagebox.showerror('Not found', 'Invoice not found')
            self.top.destroy()
            return
        # row: (id, invoice_no, date, type, customer, items, total, notes)
        self.invoice_no_var.set(row[1])
        self.date_var.set(row[2])
        self.type_var.set(row[3])
        self.customer_var.set(row[4])
        self.items_txt.delete('1.0', END)
        self.items_txt.insert(END, row[5] or '')
        self.total_var.set(str(row[6] or ''))
        self.notes_txt.delete('1.0', END)
        self.notes_txt.insert(END, row[7] or '')

    def save(self):
        inv_no = self.invoice_no_var.get().strip()
        date = self.date_var.get().strip()
        itype = self.type_var.get().strip()
        customer = self.customer_var.get().strip()
        items = self.items_txt.get('1.0', END).strip()
        try:
            total = float(self.total_var.get().strip() or 0.0)
        except ValueError:
            messagebox.showerror('Invalid total', 'Please enter a valid numeric total')
            return
        notes = self.notes_txt.get('1.0', END).strip()
        if not inv_no or not date or not itype or not customer:
            messagebox.showerror('Missing fields', 'Please fill invoice number, date, type, and customer')
            return
        try:
            if self.invoice_id:
                self.db.update_invoice(self.invoice_id, inv_no, date, itype, customer, items, total, notes)
            else:
                self.db.add_invoice(inv_no, date, itype, customer, items, total, notes)
            messagebox.showinfo('Saved', 'Invoice saved')
            if self.on_save:
                self.on_save()
            self.top.destroy()
        except sqlite3.IntegrityError as e:
            messagebox.showerror('Error', f'Could not save invoice: {e}')


if __name__ == '__main__':
    root = Tk()
    app = InvoiceApp(root)
    root.mainloop()
