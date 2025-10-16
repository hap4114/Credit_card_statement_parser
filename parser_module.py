import pdfplumber
import re
import pandas as pd
from typing import Dict, List
from dataclasses import dataclass
import os
import tempfile

# Import PyPDF2/pypdf for encryption handling
try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.errors import PdfReadError
except ImportError:
    try:
        from PyPDF2 import PdfReader, PdfWriter
        from PyPDF2.errors import PdfReadError
    except ImportError:
        raise ImportError("Neither pypdf nor PyPDF2 is installed. Install with: pip install pypdf")

# Import OCR libraries (optional)
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    pytesseract = None
    Image = None
    OCR_AVAILABLE = False

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 120)
pd.set_option('display.max_colwidth', 200)
pd.set_option('display.max_rows', None)


@dataclass
class CreditCardData:
    """Standardized data structure for all credit card statements"""
    bank_name: str
    cardholder_name: str
    card_last_4: str
    statement_date: str
    payment_due_date: str
    total_amount_due: float
    minimum_amount_due: float
    credit_limit: float
    available_credit: float
    transactions: List[Dict]


class CreditCardParser:
    """Main parser class with bank-specific adapters"""

    def __init__(self, enable_ocr: bool = True):
        self.bank_identifiers = {
            'HDFC': ['HDFC Bank', 'HDFC BANK', 'Paytm HDFC'],
            'ICICI': ['ICICI Bank', 'ICICI BANK', 'ICICI CARD'],
            'Axis': ['AXIS BANK', 'Axis Bank', 'Axis Cards', 'Flipkart Axis Bank'],
            'IDFC First': ['IDFC FIRST', 'IDFC FIRST BANK', 'IDFC Bank'],
            'Indian Bank': ['Indian Bank', 'INDIAN BANK', 'IBGCC']
        }
        self.enable_ocr = enable_ocr and OCR_AVAILABLE
        if enable_ocr and not OCR_AVAILABLE:
            print("⚠️  OCR is enabled but pytesseract/PIL not available. Install with: pip install pytesseract pillow")

    def identify_bank(self, text: str) -> str:
        """Identify which bank issued the statement"""
        text_upper = text.upper()
        for bank, identifiers in self.bank_identifiers.items():
            for identifier in identifiers:
                if identifier.upper() in text_upper:
                    return bank
        return "UNKNOWN"

    def parse_statement(self, pdf_path: str) -> CreditCardData:
        """Main parsing function with encrypted PDF and scanned PDF support"""
        # First, check if PDF is corrupted
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Try to access pages to check if PDF is corrupted
                _ = pdf.pages[0]
        except Exception as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ["corrupt", "cannot read", "invalid", "malformed", "decrypt"]):
                print("corrupt")
                return CreditCardData(
                    bank_name='CORRUPT',
                    cardholder_name="corrupt",
                    card_last_4="corrupt",
                    statement_date="corrupt",
                    payment_due_date="corrupt",
                    total_amount_due=0.0,
                    minimum_amount_due=0.0,
                    credit_limit=0.0,
                    available_credit=0.0,
                    transactions=[]
                )
            else:
                # Re-raise if it's a different error
                raise e
        
        # First, check if PDF is encrypted and handle it
        decrypted_pdf_path = self._check_and_decrypt_pdf(pdf_path)
        
        try:
            # Extract text with OCR fallback for scanned PDFs
            text = self._extract_text_with_ocr_fallback(decrypted_pdf_path)

            if not text.strip():
                raise ValueError("No text found in PDF even with OCR")

            bank_name = self.identify_bank(text)

            # Route to bank-specific parser
            if bank_name == "HDFC":
                return self._parse_hdfc_fixed(text)
            elif bank_name == "ICICI":
                return self._parse_icici_improved(text)
            elif bank_name == "Axis":
                return self._parse_axis(text)
            elif bank_name == "IDFC First":
                return self._parse_idfc(text)
            elif bank_name == "Indian Bank":
                return self._parse_indian_bank(text)
            else:
                return self._parse_generic(text)
        finally:
            # Clean up temporary decrypted file if it was created
            if decrypted_pdf_path != pdf_path and os.path.exists(decrypted_pdf_path):
                os.remove(decrypted_pdf_path)

    def _check_and_decrypt_pdf(self, pdf_path: str) -> str:
        """
        Check if PDF is encrypted and decrypt it if needed.
        Returns path to decrypted PDF (original path if not encrypted).
        """
        try:
            # First, try to open with PyPDF to check encryption
            with open(pdf_path, 'rb') as file:
                reader = PdfReader(file)
                
                if reader.is_encrypted:
                    print("🔐 PDF is encrypted. Attempting decryption...")
                    
                    # Try empty password first
                    try:
                        if reader.decrypt(""):
                            print("✅ PDF decrypted with empty password")
                        else:
                            raise Exception("Empty password failed")
                    except Exception:
                        # Prompt for password
                        password = input("🔐 Enter PDF password: ").strip()
                        if not password:
                            raise ValueError("No password provided for encrypted PDF")
                        
                        # Try with provided password
                        if reader.decrypt(password):
                            print("✅ PDF decrypted successfully with provided password")
                        else:
                            raise ValueError("Failed to decrypt PDF with provided password")
                    
                    # Create decrypted temporary file
                    writer = PdfWriter()
                    
                    for page in reader.pages:
                        writer.add_page(page)
                    
                    # Create temporary file for decrypted PDF
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                    temp_path = temp_file.name
                    temp_file.close()
                    
                    with open(temp_path, 'wb') as output_file:
                        writer.write(output_file)
                    
                    return temp_path
                else:
                    # PDF is not encrypted, return original path
                    return pdf_path
                    
        except Exception as e:
            # If PyPDF fails, try direct pdfplumber (might handle some encrypted PDFs)
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    # If we get here, pdfplumber could open it
                    return pdf_path
            except Exception as pdfplumber_error:
                if "encrypted" in str(pdfplumber_error).lower() or "password" in str(pdfplumber_error).lower():
                    print("🔐 PDF appears to be encrypted but PyPDF couldn't handle it.")
                    password = input("🔐 Enter PDF password: ").strip()
                    if password:
                        # Try to decrypt using alternative method
                        return self._decrypt_with_password(pdf_path, password)
                    else:
                        raise ValueError("No password provided for encrypted PDF")
                else:
                    raise ValueError(f"Error reading PDF: {pdfplumber_error}")

    def _check_and_decrypt_pdf(self, pdf_path: str) -> str:
        """
        Check if PDF is encrypted and decrypt it if needed.
        Returns path to decrypted PDF (original path if not encrypted).
        """
        try:
            # First, try to open with PyPDF to check encryption
            with open(pdf_path, 'rb') as file:
                reader = PdfReader(file)
                
                if reader.is_encrypted:
                    print("🔐 PDF is encrypted. Attempting decryption...")
                    
                    # Try empty password first
                    try:
                        if reader.decrypt(""):
                            print("✅ PDF decrypted with empty password")
                        else:
                            raise Exception("Empty password failed")
                    except Exception:
                        # Prompt for password
                        password = input("🔐 Enter PDF password: ").strip()
                        if not password:
                            raise ValueError("No password provided for encrypted PDF")
                        
                        # Try with provided password
                        if reader.decrypt(password):
                            print("✅ PDF decrypted successfully with provided password")
                        else:
                            raise ValueError("Failed to decrypt PDF with provided password")
                    
                    # Create decrypted temporary file
                    writer = PdfWriter()
                    
                    for page in reader.pages:
                        writer.add_page(page)
                    
                    # Create temporary file for decrypted PDF
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                    temp_path = temp_file.name
                    temp_file.close()
                    
                    with open(temp_path, 'wb') as output_file:
                        writer.write(output_file)
                    
                    return temp_path
                else:
                    # PDF is not encrypted, return original path
                    print("✅ PDF is not encrypted")
                    return pdf_path
                
        except Exception as e:
            print(f"⚠️  PyPDF encryption check failed: {e}")
            # If PyPDF fails, try direct pdfplumber (might handle some encrypted PDFs)
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    # If we get here, pdfplumber could open it
                    print("✅ PDF opened successfully with pdfplumber")
                    return pdf_path
            except Exception as pdfplumber_error:
                error_msg = str(pdfplumber_error).lower()
                if "encrypted" in error_msg or "password" in error_msg:
                    print("🔐 PDF appears to be encrypted but PyPDF couldn't handle it.")
                    password = input("🔐 Enter PDF password: ").strip()
                    if password:
                        # Try to decrypt using alternative method
                        return self._decrypt_with_password(pdf_path, password)
                    else:
                        raise ValueError("No password provided for encrypted PDF")
                else:
                    raise ValueError(f"Error reading PDF: {pdfplumber_error}")

    def _extract_text_with_ocr_fallback(self, pdf_path: str) -> str:
        """
        Extract text from PDF, using OCR if the PDF appears to be scanned/image-based.
        """
        text = ""
        
        try:
            # First attempt: try to extract text directly
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text(layout=True) or page.extract_text() or ""
                    text += page_text + "\n"
                
                # Check if we got meaningful text
                if len(text.strip()) > 100:  # Arbitrary threshold for "enough text"
                    return text
                
                # If we got very little text, try OCR if enabled
                if self.enable_ocr:
                    print("📄 PDF appears to be scanned/image-based. Using OCR...")
                    return self._extract_text_with_ocr(pdf)
                else:
                    print("⚠️  PDF appears to be scanned but OCR is disabled.")
                    return text
                    
        except Exception as e:
            print(f"⚠️  Error in text extraction: {e}")
            if self.enable_ocr:
                print("🔄 Falling back to OCR...")
                try:
                    with pdfplumber.open(pdf_path) as pdf:
                        return self._extract_text_with_ocr(pdf)
                except Exception as ocr_error:
                    raise ValueError(f"Both text extraction and OCR failed: {ocr_error}")
            else:
                raise ValueError(f"Text extraction failed and OCR is disabled: {e}")

    def _extract_text_with_ocr(self, pdf) -> str:
        """
        Extract text from PDF using OCR for scanned/image-based PDFs.
        """
        if not OCR_AVAILABLE:
            raise ValueError("OCR is not available. Install pytesseract and pillow.")
        
        text = ""
        total_pages = len(pdf.pages)
        
        print(f"🔍 Processing {total_pages} page(s) with OCR...")
        
        for i, page in enumerate(pdf.pages, 1):
            try:
                # Convert page to image
                image = page.to_image(resolution=300)
                
                # Use pytesseract to extract text from the image
                page_text = pytesseract.image_to_string(image.original, config='--psm 6')
                
                if page_text.strip():
                    text += f"--- Page {i} ---\n{page_text}\n"
                    print(f"✅ Processed page {i}/{total_pages}")
                else:
                    print(f"⚠️  No text found on page {i}/{total_pages}")
                    
            except Exception as e:
                print(f"❌ Error processing page {i} with OCR: {e}")
                continue
        
        if not text.strip():
            raise ValueError("OCR could not extract any text from the PDF")
        
        print(f"✅ OCR completed. Extracted {len(text)} characters.")
        return text

    # ========== HDFC PARSER (Fixed) ==========
    def _parse_hdfc_fixed(self, text: str) -> CreditCardData:
        cardholder_name = self._extract_hdfc_name_fixed(text)
        card_last_4 = self._extract_hdfc_card_last_4_fixed(text)
        statement_date = self._extract_hdfc_statement_date_fixed(text)
        payment_due_date = self._extract_hdfc_due_date_fixed(text)
        total_amount_due = self._extract_hdfc_total_due_fixed(text)
        minimum_amount_due = self._extract_hdfc_min_due_fixed(text)
        credit_limit = self._extract_hdfc_credit_limit_fixed(text)
        available_credit = self._extract_hdfc_available_credit_fixed(text)
        transactions = self._extract_hdfc_transactions_fixed(text)

        return CreditCardData(
            bank_name='HDFC',
            cardholder_name=cardholder_name,
            card_last_4=card_last_4,
            statement_date=statement_date,
            payment_due_date=payment_due_date,
            total_amount_due=total_amount_due,
            minimum_amount_due=minimum_amount_due,
            credit_limit=credit_limit,
            available_credit=available_credit,
            transactions=transactions
        )

    def _extract_hdfc_name_fixed(self, text: str) -> str:
        match = re.search(r'Name\s*:\s*([A-Z][A-Za-z\s]+?)(?:\n|Email)', text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            name = re.sub(r'[^A-Za-z\s]+$', '', name).strip()
            if name and len(name) > 2:
                return name
        match = re.search(r'Name\s*:\s*([A-Z\s]+)\s*\n\s*000', text)
        if match:
            name = match.group(1).strip()
            name = re.sub(r'[^A-Za-z\s]+$', '', name).strip()
            if name and len(name) > 2:
                return name
        match = re.search(r'Domestic Transactions\s+Date\s+Transaction Description\s+Amount.*?\n\s*([A-Z][A-Z\s]+[A-Z])\s*\n\s*\d{2}/\d{2}/\d{4}', text, re.DOTALL)
        if match:
            name = match.group(1).strip()
            if name and len(name.split()) >= 2 and not any(word in name for word in ['PAYTM', 'TRANSACTION', 'AMOUNT', 'DATE', 'NOIDA', 'DELHI']):
                return name
        return "Not Found"

    def _extract_hdfc_card_last_4_fixed(self, text: str) -> str:
        pattern1 = r'Card No:\s*\d{4}\s*\d{2}XX\s*XXXX\s*(\d{4})'
        match = re.search(pattern1, text)
        if match:
            return match.group(1)
        pattern2 = r'\d{4}\s+\d{2}X+\s+X+\s+(\d{4})'
        match = re.search(pattern2, text)
        if match:
            return match.group(1)
        return "Not Found"

    def _extract_hdfc_statement_date_fixed(self, text: str) -> str:
        pattern = r'Statement Date:\s*(\d{2}/\d{2}/\d{4})'
        match = re.search(pattern, text)
        if match:
            return match.group(1)
        return "Not Found"

    def _extract_hdfc_due_date_fixed(self, text: str) -> str:
        pattern1 = r'Payment Due Date\s+Total Dues.*?\n(\d{2}/\d{2}/\d{4})'
        match = re.search(pattern1, text, re.DOTALL)
        if match:
            return match.group(1)
        pattern2 = r'(\d{2}/\d{2}/\d{4})\s+[\d,]+\.[\d]{2}\s+[\d,]+\.[\d]{2}'
        match = re.search(pattern2, text)
        if match:
            return match.group(1)
        return "Not Found"

    def _extract_hdfc_total_due_fixed(self, text: str) -> float:
        pattern1 = r'(\d{2}/\d{2}/\d{4})\s+([\d,]+\.[\d]{2})\s+([\d,]+\.[\d]{2})'
        match = re.search(pattern1, text)
        if match:
            amount_str = match.group(2).replace(',', '')
            try:
                return float(amount_str)
            except ValueError:
                pass
        pattern2 = r'Total Dues[^\d]+([\d,]+\.[\d]{2})'
        match = re.search(pattern2, text)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                return float(amount_str)
            except ValueError:
                pass
        return 0.0

    def _extract_hdfc_min_due_fixed(self, text: str) -> float:
        pattern1 = r'(\d{2}/\d{2}/\d{4})\s+([\d,]+\.[\d]{2})\s+([\d,]+\.[\d]{2})'
        match = re.search(pattern1, text)
        if match:
            amount_str = match.group(3).replace(',', '')
            try:
                return float(amount_str)
            except ValueError:
                pass
        pattern2 = r'Minimum Amount Due[^\d]+([\d,]+\.[\d]{2})'
        match = re.search(pattern2, text)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                return float(amount_str)
            except ValueError:
                pass
        return 0.0

    def _extract_hdfc_credit_limit_fixed(self, text: str) -> float:
        match = re.search(r'Credit Limit\s+Available Credit Limit\s+Available Cash Limit\s*\n\s*([\d,]+)', text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                return float(amount_str)
            except ValueError:
                pass
        match = re.search(r'Credit Limit\s*\|\s*([\d,]+)', text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                return float(amount_str)
            except ValueError:
                pass
        match = re.search(r'Credit Limit[^\d\n]*([\d,]+)', text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                amount = float(amount_str)
                if 1000 <= amount <= 1000000000:
                    return amount
            except ValueError:
                pass
        return 0.0

    def _extract_hdfc_available_credit_fixed(self, text: str) -> float:
        match = re.search(r'Credit Limit\s+Available Credit Limit\s+Available Cash Limit\s*\n\s*([\d,]+)(?:\.[\d]+)?\s+([\d,]+\.[\d]+)', text, re.IGNORECASE)
        if match:
            amount_str = match.group(2).replace(',', '')
            try:
                return float(amount_str)
            except ValueError:
                pass
        match = re.search(r'Credit Limit\s+Available Credit Limit.*?\n\s*[\d,]+(?:\.\d+)?\s+([\d,]+\.\d+)', text, re.IGNORECASE | re.DOTALL)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                return float(amount_str)
            except ValueError:
                pass
        match = re.search(r'Available Credit Limit\s*\|\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                return float(amount_str)
            except ValueError:
                pass
        return 0.0

    def _extract_hdfc_transactions_fixed(self, text: str) -> List[Dict]:
        transactions = []
        pattern = r'Domestic Transactions\s+Date\s+Transaction Description\s+Amount.*?(?=Reward Points|$)'
        domestic_match = re.search(pattern, text, re.DOTALL)
        if not domestic_match:
            return transactions
        transaction_text = domestic_match.group(0)
        lines = transaction_text.split('\n')
        excluded_keywords = ['Domestic Transactions', 'Date', 'Transaction Description', 'Amount']
        for line in lines:
            line = line.strip()
            if not line or any(keyword in line for keyword in excluded_keywords):
                continue
            if re.match(r'^[A-Z][A-Za-z\s]+[A-Z]$', line):
                continue
            tx_pattern = r'(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([\d,]+\.[\d]{2})(\s+Cr)?$'
            match = re.match(tx_pattern, line)
            if match:
                date = match.group(1)
                description = match.group(2).strip()
                amount_str = match.group(3).replace(',', '')
                is_credit = match.group(4) is not None
                try:
                    amount = float(amount_str)
                    if is_credit:
                        amount = -amount
                    transactions.append({'date': date, 'description': description, 'amount': amount})
                except ValueError:
                    continue
        return transactions

    # ========== ICICI PARSER ==========
    def _parse_icici_improved(self, text: str) -> CreditCardData:
        cardholder_name = self._extract_icici_name(text)
        card_last_4 = self._extract_icici_card_last_4(text)
        statement_date = self._extract_icici_statement_date(text)
        payment_due_date = self._extract_icici_due_date(text)
        total_amount_due = self._extract_icici_total_due(text)
        minimum_amount_due = self._extract_icici_min_due(text)
        credit_limit = self._extract_icici_credit_limit(text)
        available_credit = self._extract_icici_available_credit(text)
        transactions = self._extract_icici_transactions(text)

        return CreditCardData(
            bank_name='ICICI',
            cardholder_name=cardholder_name,
            card_last_4=card_last_4,
            statement_date=statement_date,
            payment_due_date=payment_due_date,
            total_amount_due=total_amount_due,
            minimum_amount_due=minimum_amount_due,
            credit_limit=credit_limit,
            available_credit=available_credit,
            transactions=transactions
        )

    def _extract_icici_name(self, text: str) -> str:
        match = re.search(r'((?:MR|MS|MRS|DR)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*\n\s*(?:AT/PO|FLAT|HOUSE|[A-Z\s,/]+\n)', text)
        if match:
            return match.group(1).strip()
        return "Not Found"

    def _extract_icici_card_last_4(self, text: str) -> str:
        match = re.search(r'\d{4}X+(\d{4})', text)
        if match:
            return match.group(1)
        return "Not Found"

    def _extract_icici_statement_date(self, text: str) -> str:
        match = re.search(r'STATEMENT DATE.*?([A-Z][a-z]+\s+\d{1,2},\s+\d{4})', text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1)
        match = re.search(r'Statement period\s*:\s*[A-Za-z]+\s+\d{1,2},\s+\d{4}\s+to\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})', text)
        if match:
            return match.group(1)
        return "Not Found"

    def _extract_icici_due_date(self, text: str) -> str:
        match = re.search(r'PAYMENT DUE DATE.*?([A-Z][a-z]+\s+\d{1,2},\s+\d{4})', text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        dates = re.findall(r'([A-Z][a-z]+\s+\d{1,2},\s+\d{4})', text[:1000])
        if len(dates) >= 2:
            return dates[1]
        return "Not Found"

    def _extract_icici_total_due(self, text: str) -> float:
        match = re.search(r'Total Amount due\s+[`₹]?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '').replace('`', '')
            try:
                return float(amount_str)
            except ValueError:
                pass
        return 0.0

    def _extract_icici_min_due(self, text: str) -> float:
        patterns = [
            r'Minimum\s+Amount\s+due\s*[:\-]?\s*[`₹]?\s*([\d,]+\.?\d*)',
            r'Minimum\s+Amount\s*[:\-]?\s*[`₹]?\s*([\d,]+\.?\d*)',
            r'Minimum\s+Amount\s+Payable\s*[:\-]?\s*[`₹]?\s*([\d,]+\.?\d*)',
            r'Amount\s+Due\s+\(Minimum\)\s*[`₹]?\s*([\d,]+\.?\d*)'
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '').replace('`', '')
                try:
                    return float(amount_str)
                except ValueError:
                    continue

        label_match = re.search(r'Minimum\s+Amount\s+due', text, re.IGNORECASE)
        if label_match:
            lines = text.splitlines()
            char_index = 0
            found_line_idx = None
            for idx, ln in enumerate(lines):
                start = char_index
                end = char_index + len(ln) + 1
                if start <= label_match.start() < end:
                    found_line_idx = idx
                    break
                char_index = end
            if found_line_idx is not None:
                for offset in range(0, 4):
                    li = found_line_idx + offset
                    if li >= len(lines):
                        break
                    line = lines[li].strip()
                    nums = re.findall(r'[`₹]?\s*([\d,]+\.?\d*)', line)
                    for n in nums:
                        try:
                            val = float(n.replace(',', '').replace('`', ''))
                            if val > 0:
                                return val
                        except ValueError:
                            continue

        total = None
        total_match = re.search(r'Total\s+Amount\s+due\s*[`₹]?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if total_match:
            try:
                total = float(total_match.group(1).replace(',', '').replace('`', ''))
            except ValueError:
                total = None

        anchor_pos = None
        m2 = re.search(r'Minimum\s+Amount\s+due', text, re.IGNORECASE)
        if m2:
            anchor_pos = m2.end()
        elif total_match:
            anchor_pos = total_match.end()

        if anchor_pos is not None:
            window_start = max(0, anchor_pos - 200)
            window_end = min(len(text), anchor_pos + 400)
            window = text[window_start:window_end]
            nums = re.findall(r'[`₹]?\s*([\d,]+\.?\d*)', window)
            cleaned = []
            for n in nums:
                try:
                    cleaned.append(float(n.replace(',', '').replace('`', '')))
                except ValueError:
                    continue
            if cleaned:
                for v in cleaned:
                    if v > 0 and (total is None or v <= total):
                        return v

        for line in text.splitlines():
            if 'MINIMUM' in line.upper() or 'MIN DUE' in line.upper():
                nums = re.findall(r'[`₹]?\s*([\d,]+\.?\d*)', line)
                for n in nums:
                    try:
                        val = float(n.replace(',', '').replace('`', ''))
                        if val > 0:
                            return val
                    except ValueError:
                        continue
        return 0.0

    def _extract_icici_credit_limit(self, text: str) -> float:
        match = re.search(
            r"Credit Limit \(Including cash\)\s+Available Credit.*?[`₹]\s*([\d,]+\.?\d*)",
            text,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                return float(amount_str)
            except ValueError:
                pass
        return 0.0

    def _extract_icici_available_credit(self, text: str) -> float:
        match = re.search(
            r"Credit Limit \(Including cash\)\s+Available Credit \(Including cash\).*?[`₹]\s*[\d,]+\.?\d*\s+[`₹]\s*([\d,]+\.?\d*)",
            text,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                return float(amount_str)
            except ValueError:
                pass
        return 0.0

    def _extract_icici_transactions(self, text: str) -> List[Dict]:
        transactions = []
        pattern = re.compile(
            r'(\d{2}/\d{2}/\d{4})\s+'  # Date
            r'(\d+)\s+'  # Serial number
            r'(.+?)\s+'  # Description
            r'(?:IN\s+)?'  # Optional "IN"
            r'([\d,]+\.?\d*)\s*'  # Amount
            r'(CR)?'  # Optional CR
            r'(?:\s*$)',  # End of line
            re.MULTILINE
        )
        matches = pattern.findall(text)
        for match in matches:
            date, serial, description, amount_str, is_credit = match
            description = description.strip()
            description = re.sub(r'\s+', ' ', description)
            if any(keyword in description.upper() for keyword in ['TRANSACTION DETAILS', 'DATE', 'SERNO', 'AMOUNT', 'INTL', 'STATEMENT']):
                continue
            try:
                amount = float(amount_str.replace(',', ''))
                if is_credit:
                    amount = -amount
                transactions.append({'date': date, 'description': description, 'amount': amount})
            except ValueError:
                continue
        seen = set()
        unique_transactions = []
        for tx in transactions:
            key = (tx['date'], tx['description'], tx['amount'])
            if key not in seen:
                seen.add(key)
                unique_transactions.append(tx)
        return unique_transactions

    # ========== AXIS PARSER ==========
    def _parse_axis(self, text: str) -> CreditCardData:
        cardholder_name = self._extract_axis_name(text)
        card_last_4 = self._extract_axis_card_last_4(text)
        statement_date, payment_due_date, total_amount_due, minimum_amount_due = self._extract_axis_payment_summary(text)
        credit_limit, available_credit = self._extract_axis_limits(text)
        transactions = self._extract_axis_transactions(text)

        return CreditCardData(
            bank_name='Axis Bank',
            cardholder_name=cardholder_name,
            card_last_4=card_last_4,
            statement_date=statement_date or "Not Found",
            payment_due_date=payment_due_date or "Not Found",
            total_amount_due=total_amount_due,
            minimum_amount_due=minimum_amount_due,
            credit_limit=credit_limit,
            available_credit=available_credit,
            transactions=transactions
        )

    def _extract_axis_name(self, text: str) -> str:
        match = re.search(r'\n([A-Z][A-Z\s,.-]+)\nB/', text)
        if match:
            name = re.sub(r'\s+', ' ', match.group(1).strip())
            return name
        for line in text.splitlines():
            ln = line.strip()
            if ln.isupper() and len(ln.split()) >= 2 and len(ln) < 60:
                if not any(k in ln for k in ['AXIS', 'STATEMENT', 'PAYMENT', 'SUMMARY']):
                    return re.sub(r'\s+', ' ', ln)
        return "Not Found"

    def _extract_axis_card_last_4(self, text: str) -> str:
        match = re.search(r'(\d{6}\*{6}(\d{4}))|(\*{6}(\d{4}))', text)
        if match:
            for g in match.groups():
                if g and re.fullmatch(r'\d{4}', g):
                    return g
        return "Not Found"

    def _extract_axis_payment_summary(self, text: str):
        section = text.upper()
        start = section.find('PAYMENT SUMMARY')
        end = section.find('AUTO-DEBIT')
        if start != -1 and end != -1:
            section = text[start:end + 300]
        else:
            section = text
        dates = re.findall(r'(\d{2}/\d{2}/\d{4})', section)
        amounts = re.findall(r'([\d\s,]+\.\d{2})\s*Dr', section, re.IGNORECASE)
        statement_date = None
        payment_due_date = None
        total_due = 0.0
        min_due = 0.0
        if len(dates) >= 2:
            statement_date = dates[1]
        if len(dates) >= 3:
            payment_due_date = dates[2]
        if amounts:
            total_due = self._clean_amount_to_float(amounts[0])
            if len(amounts) > 1:
                min_due = self._clean_amount_to_float(amounts[1])
            else:
                min_due = total_due
        return statement_date, payment_due_date, total_due, min_due

    def _extract_axis_limits(self, text: str):
        match = re.search(r'\*{4,}\d{4}\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})', text)
        if match:
            credit_limit = self._clean_amount_to_float(match.group(1))
            available_credit = self._clean_amount_to_float(match.group(2))
            return credit_limit, available_credit
        return 0.0, 0.0

    def _clean_amount_to_float(self, s: str) -> float:
        if not s:
            return 0.0
        cleaned = re.sub(r'[^\d.\-]', '', s)
        try:
            return float(cleaned)
        except:
            return 0.0

    def _extract_axis_transactions(self, text: str) -> List[Dict]:
        transactions = []
        text = text.replace('\r', '').replace('\t', ' ')
        text = re.sub(r' {2,}', ' ', text)
        tx_pattern = re.compile(
            r'(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([\d\s,]+\.\d{2})\s*(Dr|Cr)\b',
            re.MULTILINE | re.IGNORECASE
        )
        for match in tx_pattern.finditer(text):
            date, desc, amt_str, drcr = match.groups()
            amount = self._clean_amount_to_float(amt_str)
            if drcr.lower() == 'cr':
                amount = -amount
            transactions.append({'date': date, 'description': desc.strip(), 'amount': amount})
        last_date = None
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            m_date = re.match(r'(\d{2}/\d{2}/\d{4})', line)
            if m_date:
                last_date = m_date.group(1)
                continue
            m_amount = re.search(r'([\d\s,]+\.\d{2})\s*(Dr|Cr)\b', line, re.IGNORECASE)
            if m_amount and last_date:
                amt = self._clean_amount_to_float(m_amount.group(1))
                if m_amount.group(2).lower() == 'cr':
                    amt = -amt
                desc = re.sub(r'([\d\s,]+\.\d{2})\s*(Dr|Cr)\b', '', line).strip()
                if desc:
                    transactions.append({'date': last_date, 'description': desc, 'amount': amt})
        seen = set()
        unique = []
        for tx in transactions:
            key = (tx['date'], tx['description'][:30], tx['amount'])
            if key not in seen:
                seen.add(key)
                unique.append(tx)
        return unique

    # ========== IDFC FIRST PARSER ==========
    def _parse_idfc(self, text: str) -> CreditCardData:
        cardholder_name = self._extract_idfc_name(text)
        card_last_4 = self._extract_idfc_card_last_4(text)
        statement_date, payment_due_date = self._extract_idfc_dates(text)
        total_amount_due, minimum_amount_due = self._extract_idfc_dues(text)
        credit_limit, available_credit, cash_limit = self._extract_idfc_limits(text)
        transactions = self._extract_idfc_transactions(text)

        return CreditCardData(
            bank_name='IDFC First',
            cardholder_name=cardholder_name,
            card_last_4=card_last_4,
            statement_date=statement_date,
            payment_due_date=payment_due_date,
            total_amount_due=total_amount_due,
            minimum_amount_due=minimum_amount_due,
            credit_limit=credit_limit,
            available_credit=available_credit,
            transactions=transactions
        )

    def _extract_idfc_name(self, text: str) -> str:
        match = re.search(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*\n\s*Credit Card Statement', text, re.MULTILINE)
        if match:
            return match.group(1).strip()
        match = re.search(r'Customer Name\s*:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', text)
        if match:
            name = match.group(1).strip()
            name = re.sub(r'\s+Card\s+Number.*$', '', name, flags=re.IGNORECASE)
            return name
        match = re.search(r'\n([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){1,3})\s*\n.*?Credit Card Statement', text, re.DOTALL)
        if match:
            name = match.group(1).strip()
            if not any(kw in name.upper() for kw in ['ALWAYS', 'FIRST', 'BANK', 'STATEMENT', 'CARD NUMBER']):
                return name
        return "Not Found"

    def _extract_idfc_card_last_4(self, text: str) -> str:
        match = re.search(r'(\d{6}\*{6}(\d{4}))|(\*{6}(\d{4}))', text)
        if match:
            for g in match.groups():
                if g and re.fullmatch(r'\d{4}', g):
                    return g
        match = re.search(r'Card Number\s*:?\s*\d+\*+(\d{4})', text)
        if match:
            return match.group(1)
        return "Not Found"

    def _extract_idfc_dates(self, text: str) -> tuple:
        match = re.search(r'Statement\s+Date\s*\n\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        if match:
            return match.group(1), match.group(2)
        stmt_match = re.search(r'Statement\s+Date\s*\n\s*(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        due_match = re.search(r'Payment\s+Due\s+Date\s*\n\s*(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        s_date = stmt_match.group(1) if stmt_match else "Not Found"
        d_date = due_match.group(1) if due_match else "Not Found"
        if s_date != "Not Found" or d_date != "Not Found":
            return s_date, d_date
        match = re.search(r'(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})', text)
        if match:
            return match.group(1), match.group(2)
        return "Not Found", "Not Found"

    def _extract_idfc_dues(self, text: str) -> tuple:
        match = re.search(
            r'Total\s+Amount\s+Due\s+Minimum\s+Amount\s+Due\s*\n\s*r?\s*([\d,]+\.?\d*)\s+r?\s*([\d,]+\.?\d*)',
            text, re.IGNORECASE
        )
        if match:
            try:
                total = float(match.group(1).replace(',', ''))
                minimum = float(match.group(2).replace(',', ''))
                return total, minimum
            except ValueError:
                pass
        match = re.search(
            r'Total\s+Amount\s+Due.*?Minimum\s+Amount\s+Due.*?\n.*?[r₹]\s*([\d,]+\.?\d*).*?[r₹]\s*([\d,]+\.?\d*)',
            text, re.IGNORECASE | re.DOTALL
        )
        if match:
            try:
                total = float(match.group(1).replace(',', ''))
                minimum = float(match.group(2).replace(',', ''))
                return total, minimum
            except ValueError:
                pass
        total = 0.0
        minimum = 0.0
        total_match = re.search(r'Total\s+Amount\s+Due\s*:?\s*[r₹]?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if total_match:
            try:
                total = float(total_match.group(1).replace(',', ''))
            except ValueError:
                pass
        min_match = re.search(r'Minimum\s+Amount\s+Due\s*:?\s*[r₹]?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if min_match:
            try:
                minimum = float(min_match.group(1).replace(',', ''))
            except ValueError:
                pass
        if total > 0 or minimum > 0:
            return total, minimum
        return 0.0, 0.0

    def _extract_idfc_limits(self, text: str) -> tuple:
        credit = 0.0
        available = 0.0
        cash = 0.0
        limits_block = re.search(
            r'Credit\s+Limit\s+Available\s+Credit\s+Limit.*?Cash\s+Limit',
            text, re.IGNORECASE | re.DOTALL
        )
        if limits_block:
            block_text = limits_block.group(0)
            amounts = re.findall(r'r\s*([\d,]+(?:\.\d+)?)', block_text, re.IGNORECASE)
            if len(amounts) >= 3:
                try:
                    credit = float(amounts[0].replace(',', ''))
                    available = float(amounts[1].replace(',', ''))
                    cash = float(amounts[2].replace(',', ''))
                    return credit, available, cash
                except (ValueError, IndexError):
                    pass
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if 'Credit Limit' in line and 'Available Credit Limit' in line and i + 1 < len(lines):
                next_line = lines[i + 1]
                nums = re.findall(r'r?\s*([\d,]+(?:\.\d+)?)', next_line)
                if len(nums) >= 2:
                    try:
                        credit = float(nums[0].replace(',', ''))
                        available = float(nums[1].replace(',', ''))
                    except ValueError:
                        pass
            if 'Cash Limit' in line and i + 1 < len(lines):
                next_line = lines[i + 1]
                nums = re.findall(r'r?\s*([\d,]+(?:\.\d+)?)', next_line)
                if nums:
                    try:
                        cash = float(nums[0].replace(',', ''))
                    except ValueError:
                        pass
        if credit == 0.0:
            credit_section = re.search(
                r'Credit\s+Limit.*?(?:Available|Cash|\n\n)',
                text, re.IGNORECASE | re.DOTALL
            )
            if credit_section:
                nums = re.findall(r'(?:r|₹)?\s*([\d,]+(?:\.\d+)?)', credit_section.group(0))
                for n in nums:
                    try:
                        val = float(n.replace(',', ''))
                        if 10000 <= val <= 10000000:
                            credit = val
                            break
                    except ValueError:
                        continue
        if available == 0.0:
            avail_section = re.search(
                r'Available\s+Credit\s+Limit.*?(?:Cash|\n\n)',
                text, re.IGNORECASE | re.DOTALL
            )
            if avail_section:
                nums = re.findall(r'(?:r|₹)?\s*([\d,]+(?:\.\d+)?)', avail_section.group(0))
                for n in nums:
                    try:
                        val = float(n.replace(',', ''))
                        if 0 < val <= 10000000:
                            available = val
                            break
                    except ValueError:
                        continue
        if cash == 0.0:
            cash_section = re.search(
                r'Cash\s+Limit.*?(?:\n\n|STATEMENT)',
                text, re.IGNORECASE | re.DOTALL
            )
            if cash_section:
                nums = re.findall(r'(?:r|₹)?\s*([\d,]+(?:\.\d+)?)', cash_section.group(0))
                for n in nums:
                    try:
                        val = float(n.replace(',', ''))
                        if 1000 <= val <= 1000000:
                            cash = val
                            break
                    except ValueError:
                        continue
        return credit, available, cash

    def _extract_idfc_transactions(self, text: str) -> List[Dict]:
        transactions = []
        tx_section_match = re.search(r'YOUR\s+TRANSACTIONS.*?(?=KEY\s+OFFERS|Page\s+\d+|$)', text, re.IGNORECASE | re.DOTALL)
        if not tx_section_match:
            return transactions
        tx_text = tx_section_match.group(0)
        tx_pattern = re.compile(
            r'(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([\d,]+\.?\d*)\s*(CR)?(?:\s*\n|$)',
            re.MULTILINE | re.IGNORECASE
        )
        for match in tx_pattern.finditer(tx_text):
            date = match.group(1)
            desc = match.group(2).strip()
            amt_str = match.group(3)
            is_credit = match.group(4) is not None
            if any(kw in desc.upper() for kw in ['TRANSACTION', 'DATE', 'DETAILS', 'AMOUNT', 'CUSTOMER NAME', 'CARD NUMBER']):
                continue
            try:
                amt = float(amt_str.replace(',', ''))
                if is_credit:
                    amt = -amt
                transactions.append({'date': date, 'description': desc, 'amount': amt})
            except ValueError:
                continue
        seen = set()
        unique_transactions = []
        for tx in transactions:
            key = (tx['date'], tx['description'][:30], tx['amount'])
            if key not in seen:
                seen.add(key)
                unique_transactions.append(tx)
        return unique_transactions

    # ========== INDIAN BANK PARSER ==========
    def _parse_indian_bank(self, text: str) -> CreditCardData:
        cardholder_name = self._extract_indian_name(text)
        card_last_4 = self._extract_indian_card_last_4(text)
        statement_date, statement_period, payment_due_date = self._extract_indian_dates(text)
        total_amount_due, minimum_amount_due = self._extract_indian_dues(text)
        credit_limit, available_credit, cash_limit = self._extract_indian_limits(text)
        transactions = self._extract_indian_transactions(text)

        return CreditCardData(
            bank_name='Indian Bank',
            cardholder_name=cardholder_name,
            card_last_4=card_last_4,
            statement_date=statement_date or "Not Found",
            payment_due_date=payment_due_date or "Not Found",
            total_amount_due=total_amount_due,
            minimum_amount_due=minimum_amount_due,
            credit_limit=credit_limit,
            available_credit=available_credit,
            transactions=transactions
        )

    def _extract_indian_name(self, text: str) -> str:
        match = re.search(r'Mr\.?\s+([A-Z][A-Za-z\s]+)', text)
        if match:
            return match.group(1).strip()
        for line in text.splitlines():
            if line.strip().isupper() and len(line.strip().split()) >= 2:
                return line.strip()
        return "Not Found"

    def _extract_indian_card_last_4(self, text: str) -> str:
        match = re.search(r'(\d{4})\s*\d{2}XX\s*XXXX\s*(\d{4})', text)
        if match:
            return match.group(2)
        match = re.search(r'XXXX\s*(\d{4})', text)
        if match:
            return match.group(1)
        return "Not Found"

    def _extract_indian_dates(self, text: str) -> tuple:
        match = re.search(r'(\d{2}-\d{2}-\d{2})\s+(\d{2}-\d{2}-\d{2})\s*-\s*(\d{2}-\d{2}-\d{2})\s+(\d{2}-\d{2}-\d{2})', text)
        if match:
            statement_date = match.group(1)
            statement_period = f"{match.group(2)} - {match.group(3)}"
            due_date = match.group(4)
            return statement_date, statement_period, due_date
        return "Not Found", "Not Found", "Not Found"

    def _extract_indian_dues(self, text: str) -> tuple:
        pattern_primary = r'\d{4}\s+\d{2}XX\s+XXXX\s+\d{4}.*?\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})'
        match = re.search(pattern_primary, text)
        if match:
            try:
                total = float(match.group(1).replace(',', ''))
                minimum = float(match.group(2).replace(',', ''))
                return total, minimum
            except ValueError:
                pass
        matches = re.findall(r'([\d,]+\.\d{2})\s+([\d,]+\.\d{2})', text)
        if matches:
            last_pair = matches[-1]
            try:
                total = float(last_pair[0].replace(',', ''))
                minimum = float(last_pair[1].replace(',', ''))
                return total, minimum
            except ValueError:
                pass
        return 0.0, 0.0

    def _extract_indian_limits(self, text: str) -> tuple:
        match = re.search(r'([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})', text)
        if match:
            try:
                credit_limit = float(match.group(1).replace(',', ''))
                available_credit = float(match.group(2).replace(',', ''))
                cash_limit = float(match.group(3).replace(',', ''))
                return credit_limit, available_credit, cash_limit
            except ValueError:
                pass
        return 0.0, 0.0, 0.0

    def _extract_indian_transactions(self, text: str) -> List[Dict]:
        transactions = []
        match = re.search(r'Txn\.\s*Date\s*Transaction Particulars.*?(?=CONTACT|Mr\.|Page|\Z)', text, re.DOTALL | re.IGNORECASE)
        if not match:
            # fallback: try to find lines that look like DD-MMM-YY followed by description and amount
            tx_lines = re.findall(r'(\d{2}-[A-Z]{3}-\d{2})\s+(.+?)\s+(Cr|Dr)\s+([\d,]+\.\d{2})', text, re.IGNORECASE)
            for m in tx_lines:
                date, desc, crdr, amount_str = m
                amt = float(amount_str.replace(',', ''))
                if crdr.lower() == 'cr':
                    amt = -amt
                transactions.append({'date': date, 'description': desc.strip(), 'amount': amt})
            return transactions
        tx_text = match.group(0)
        tx_pattern = re.compile(r'(\d{2}-[A-Z]{3}-\d{2})\s+(.+?)\s+(Cr|Dr)\s+([\d,]+\.\d{2})', re.IGNORECASE)
        for m in tx_pattern.finditer(tx_text):
            date = m.group(1)
            desc = m.group(2).strip()
            crdr = m.group(3).strip().lower()
            amount = float(m.group(4).replace(',', ''))
            if crdr == 'cr':
                amount = -amount
            transactions.append({'date': date, 'description': desc, 'amount': amount})
        return transactions

    # ========== Generic Parser ==========
    def _parse_generic(self, text: str) -> CreditCardData:
        return CreditCardData(
            bank_name='UNKNOWN',
            cardholder_name="Not Found",
            card_last_4="Not Found",
            statement_date="Not Found",
            payment_due_date="Not Found",
            total_amount_due=0.0,
            minimum_amount_due=0.0,
            credit_limit=0.0,
            available_credit=0.0,
            transactions=[]
        )


class StatementAnalyzer:
    """Analyze and display parsed statement data"""

    @staticmethod
    def display_summary(data: CreditCardData):
        print("\n" + "=" * 60)
        print("CREDIT CARD STATEMENT SUMMARY")
        print("=" * 60)
        print(f"Bank: {data.bank_name}")
        print(f"Cardholder: {data.cardholder_name}")
        print(f"Card Ending: **** **** **** {data.card_last_4}")
        print(f"Statement Date: {data.statement_date}")
        print(f"Payment Due Date: {data.payment_due_date}")
        print(f"Total Amount Due: ₹{data.total_amount_due:,.2f}")
        print(f"Minimum Amount Due: ₹{data.minimum_amount_due:,.2f}")
        print(f"Credit Limit: ₹{data.credit_limit:,.2f}")
        print(f"Available Credit: ₹{data.available_credit:,.2f}")
        print(f"Transactions Count: {len(data.transactions)}")
        print("=" * 60)


def main():
    """Standalone parser for VS Code"""
    import pandas as pd
    import os
    import traceback
    import sys

    parser = CreditCardParser(enable_ocr=True)
    analyzer = StatementAnalyzer()

    print("🚀 CREDIT CARD STATEMENT PARSER")
    print("✅ Supports: Encrypted PDFs, Scanned PDFs (OCR), Regular PDFs")
    print("🏦 Supported Banks: HDFC, ICICI, Axis, IDFC First, Indian Bank")
    
    if OCR_AVAILABLE:
        print("🔍 OCR: Enabled (pytesseract available)")
    else:
        print("⚠️  OCR: Disabled (install pytesseract and pillow for scanned PDFs)")
    
    print("=" * 60)
    pdf_path = input("📂 Enter the full path to your PDF: ").strip()

    if not os.path.exists(pdf_path):
        print("❌ File not found!")
        return

    try:
        print(f"🔍 Processing: {pdf_path}")
        data = parser.parse_statement(pdf_path)
        
        # Check if PDF was corrupt
        if data.bank_name == 'CORRUPT':
            return
            
        analyzer.display_summary(data)

        # === Transaction Table ===
        if data.transactions:
            print("\n" + "=" * 60)
            print("TRANSACTIONS:")
            print("=" * 60)

            df = pd.DataFrame(data.transactions)

            # Format amount nicely
            df["amount_str"] = df["amount"].apply(
                lambda x: f"₹{x:,.2f}" if x >= 0 else f"-₹{abs(x):,.2f}"
            )

            # Calculate column widths dynamically
            date_width = max(df["date"].map(len).max(), len("Date"))
            desc_width = max(df["description"].map(len).max(), len("Description"))
            amt_width = max(df["amount_str"].map(len).max(), len("Amount"))

            # Print header
            print(f"{'Date':<{date_width}}  {'Description':<{desc_width}}  {'Amount':>{amt_width}}")
            print("-" * (date_width + desc_width + amt_width + 4))

            # Print each transaction
            for _, row in df.iterrows():
                print(
                    f"{row['date']:<{date_width}}  "
                    f"{row['description']:<{desc_width}}  "
                    f"{row['amount_str']:>{amt_width}}"
                )

        else:
            print("\n(No transactions found in this statement.)")

    except Exception as e:
        print(f"❌ Error processing file!")
        print(f"🔍 Error type: {type(e).__name__}")
        print(f"📋 Error message: {str(e)}")
        print("\n📋 Full traceback:")
        traceback.print_exc()
        print(f"\n💡 Python version: {sys.version}")


if __name__ == "__main__":
    main()