import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from credit_card_parser import CreditCardParser, StatementAnalyzer
import pdfplumber
import tempfile
import os
from datetime import datetime

# ===== PAGE CONFIG =====
st.set_page_config(
    page_title="💳 Credit Card Analyzer",
    layout="wide",
    page_icon="💰"
)

# ===== CUSTOM STYLING =====
st.markdown("""
<style>
.main {
    background: linear-gradient(135deg, #f9f9f9 30%, #e1f0ff 100%);
    font-family: 'Segoe UI', sans-serif;
}
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] {color: black !important;}
div[data-testid="stMetric"] {
    background: white; padding: 15px; border-radius: 15px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1); color: black !important;
}
section[data-testid="stFileUploader"] div div div div {display: none !important;}
.upload-button {
    display:inline-block; background:white; color:#0072ff; font-weight:600;
    padding:10px 20px; border-radius:12px; border:2px solid #0072ff;
    box-shadow:0 3px 8px rgba(0,0,0,0.1); cursor:pointer; transition:all .3s ease;
}
.upload-button:hover {background:#0072ff; color:white; transform:scale(1.03);}
.stButton button, .stDownloadButton button {
    background-color:#0072ff!important; color:white!important; border-radius:10px;
    font-weight:600; padding:.6em 1.2em; border:none;
}
.stButton button:hover, .stDownloadButton button:hover {background-color:#005ce6!important;}
.stDataFrame div {color:#000!important;}
.warning-box {
    background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 10px;
    padding: 15px; margin: 10px 0; color: #856404;
}
.scanned-warning {
    background-color: #f8d7da; border: 1px solid #f5c6cb; border-radius: 10px;
    padding: 15px; margin: 10px 0; color: #721c24;
}
.success-box {
    background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 10px;
    padding: 15px; margin: 10px 0; color: #155724;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}
.stTabs [data-baseweb="tab"] {
    background-color: white;
    border-radius: 10px;
    padding: 10px 20px;
    color: #0072ff;
    font-weight: 600;
}
.stTabs [aria-selected="true"] {
    background-color: #0072ff;
    color: white;
}
</style>
""", unsafe_allow_html=True)

# ===== TITLE =====
st.title("💳 Multi-Bank Credit Card Statement Analyzer")
st.caption("Analyze Axis, HDFC, ICICI, IDFC, and Indian Bank statements easily 📈")

# ===== CUSTOM UPLOAD BUTTON =====
st.markdown('<label class="upload-button">📤 Upload Credit Card Statement (PDF)</label>', unsafe_allow_html=True)
uploaded_file = st.file_uploader("", type=["pdf"], label_visibility="collapsed")

# ===== PROCESS FILE =====
if uploaded_file:
    # Save temp file
    temp_path = "temp.pdf"
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Initialize parser with OCR enabled
    parser = CreditCardParser(enable_ocr=True)
    
    # Check OCR availability and show status
    ocr_available = False
    try:
        import pytesseract
        from PIL import Image
        pytesseract.get_tesseract_version()
        ocr_available = True
        st.success("🔍 OCR Available - Scanned PDFs can be processed")
    except Exception as ocr_error:
        ocr_available = False
        error_str = str(ocr_error).lower()
        if "tesseract" in error_str or "not installed" in error_str:
            st.warning("⚠️ Tesseract OCR Not Installed - Scanned PDFs cannot be processed")
            with st.expander("📖 How to Install Tesseract OCR"):
                st.markdown("""
                **Windows:**
                1. Download from: https://github.com/UB-Mannheim/tesseract/wiki
                2. Install and add to PATH
                3. Run: `pip install pytesseract pillow`
                
                **Mac:**
                ```bash
                brew install tesseract
                pip install pytesseract pillow
                ```
                
                **Linux:**
                ```bash
                sudo apt-get install tesseract-ocr
                pip install pytesseract pillow
                ```
                
                After installation, restart the Streamlit app.
                """)
        else:
            st.info(f"ℹ️ OCR Status: {str(ocr_error)}")
    
    # Check if PDF is encrypted using PyPDF2/pypdf (same method as parser)
    is_encrypted = False
    password = None
    
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            st.error("❌ PyPDF2 or pypdf library not found. Please install it: pip install pypdf")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            st.stop()
    
    try:
        with open(temp_path, 'rb') as file:
            reader = PdfReader(file)
            is_encrypted = reader.is_encrypted
    except Exception as e:
        st.error(f"❌ Error reading PDF: {str(e)}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        st.stop()

    # Handle encrypted PDFs
    if is_encrypted:
        st.warning("🔒 This PDF is password-protected.")
        password = st.text_input("Please enter the PDF password:", type="password", key="pdf_password")
        
        if not password:
            st.info("🔑 Please enter the password to continue.")
            st.stop()

    try:
        # Parse the statement with optional password
        status_container = st.empty()
        
        with st.spinner("🔎 Analyzing your statement... Please wait..."):
            # Pass password only if it exists and is not empty
            if password:
                data = parser.parse_statement(temp_path, password=password)
            else:
                data = parser.parse_statement(temp_path)
        
        # Show OCR success message if OCR was used
        if hasattr(parser, '_ocr_used') and parser._ocr_used:
            st.markdown("""
            <div class="success-box">
            <strong>✅ Scanned PDF Processed Successfully</strong><br>
            OCR was used to extract text from the scanned document.
            </div>
            """, unsafe_allow_html=True)
        
        # ===== DISPLAY RESULTS =====
        st.success("✅ Statement parsed successfully!")
        
        st.markdown("### 📊 Quick Summary")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("🏦 Bank", data.bank_name)
            st.metric("👤 Cardholder", data.cardholder_name)
        with c2:
            st.metric("💳 Last 4 Digits", data.card_last_4)
            st.metric("📅 Payment Due Date", data.payment_due_date)
        with c3:
            st.metric("💰 Total Amount Due", f"₹{data.total_amount_due:,.2f}")
            st.metric("💸 Minimum Due", f"₹{data.minimum_amount_due:,.2f}")

        st.markdown("---")

        # ===== FULL DETAILS SECTION =====
        st.subheader("📋 Full Statement Information")

        d1, d2 = st.columns(2)
        with d1:
            st.write(f"**Statement Date:** {data.statement_date}")
            st.write(f"**Credit Limit:** ₹{data.credit_limit:,.2f}")
            st.write(f"**Available Credit:** ₹{data.available_credit:,.2f}")
        with d2:
            st.write(f"**Card Number (Last 4):** {data.card_last_4}")
            st.write(f"**Total Transactions:** {len(data.transactions)}")

        # Display credit utilization if available
        if data.credit_limit > 0:
            utilization = ((data.credit_limit - data.available_credit) / data.credit_limit) * 100
            st.write(f"**Credit Utilization:** {utilization:.1f}%")
            
            # Progress bar for utilization
            st.progress(min(utilization / 100, 1.0))
            
            # Color code based on utilization
            if utilization > 80:
                st.warning("⚠️ High credit utilization detected (above 80%)")
            elif utilization > 50:
                st.info("ℹ️ Moderate credit utilization (above 50%)")
            else:
                st.success("✅ Healthy credit utilization (below 50%)")

        st.markdown("---")

        # ===== TRANSACTIONS SECTION WITH TABS =====
        if data.transactions:
            st.markdown("### 💳 Transactions Analysis")
            
            # Create transactions dataframe
            transactions_df = pd.DataFrame(data.transactions)
            
            # Format amount with ₹ symbol and proper formatting
            def format_amount(amount):
                if amount >= 0:
                    return f"₹{amount:,.2f}"
                else:
                    return f"-₹{abs(amount):,.2f}"
            
            transactions_df["Formatted Amount"] = transactions_df["amount"].apply(format_amount)
            transactions_df['type'] = transactions_df['amount'].apply(lambda x: 'Credit' if x < 0 else 'Debit')
            
            # Display summary statistics
            st.markdown("#### 📈 Transaction Summary")
            col1, col2, col3, col4 = st.columns(4)
            
            total_spent = transactions_df[transactions_df["amount"] > 0]["amount"].sum()
            total_credits = transactions_df[transactions_df["amount"] < 0]["amount"].sum()
            transaction_count = len(transactions_df)
            avg_transaction = transactions_df[transactions_df["amount"] > 0]["amount"].mean() if len(transactions_df[transactions_df["amount"] > 0]) > 0 else 0
            
            with col1:
                st.metric("💸 Total Spent", f"₹{total_spent:,.2f}")
            with col2:
                st.metric("💚 Total Credits", f"₹{abs(total_credits):,.2f}")
            with col3:
                st.metric("🔢 Transaction Count", transaction_count)
            with col4:
                st.metric("📊 Avg Transaction", f"₹{avg_transaction:,.2f}")
            
            st.markdown("---")
            
            # ===== TABS FOR DIFFERENT VIEWS =====
            tab1, tab2, tab3, tab4 = st.tabs(["📋 Transaction List", "📊 Spending Analysis", "📈 Timeline", "💾 Export Data"])
            
            with tab1:
                st.markdown("#### 🔍 Filter Transactions")
                
                col1, col2 = st.columns(2)
                with col1:
                    filter_type = st.multiselect(
                        "Filter by Type",
                        options=['Debit', 'Credit'],
                        default=['Debit', 'Credit']
                    )
                with col2:
                    search_term = st.text_input("Search in descriptions:", "")
                
                # Apply filters
                display_df = transactions_df[["date", "description", "Formatted Amount", "type"]].copy()
                display_df.columns = ["Date", "Description", "Amount", "Type"]
                
                filtered_df = display_df[display_df['Type'].isin(filter_type)]
                
                if search_term:
                    filtered_df = filtered_df[
                        filtered_df["Description"].str.contains(search_term, case=False, na=False)
                    ]
                    st.write(f"Found {len(filtered_df)} transactions matching '{search_term}'")
                
                # Display transactions table
                st.dataframe(
                    filtered_df[["Date", "Description", "Amount"]],
                    use_container_width=True,
                    height=400
                )
            
            with tab2:
                st.markdown("#### 📊 Spending by Category")
                
                # Enhanced categorization based on actual transaction patterns
                categories = {
                    'Shopping & E-commerce': [
                        'AMAZON', 'FLIPKART', 'MYNTRA', 'SHOP', 'MALL', 'STORE', 
                        'PAYTM', 'DREAMPLUG', 'CLOTH', 'SILKS', 'READYM', 'COTTON',
                        'CLOTHINGS', 'GRASP', 'RAMRAJ', 'URVASI'
                    ],
                    'Food & Dining': [
                        'SWIGGY', 'ZOMATO', 'RESTAURANT', 'CAFE', 'FOOD', 'KITCHEN',
                        'FAMILY BAZAR'
                    ],
                    'Travel & Transportation': [
                        'UBER', 'OLA', 'IRCTC', 'AIRLINE', 'FLIGHT', 'HOTEL', 'RAILWAY',
                        'MAKEMYTRIP', 'BUS', 'TOLL', 'ELECTRONIC TOLL'
                    ],
                    'Fuel & Vehicle': [
                        'PETROL', 'DIESEL', 'FUEL', 'HP', 'SHELL', 'BPCL', 'HPCL',
                        'FILLING', 'SERVICE STAT', 'ENERGY STAT', 'PETROLEUM',
                        'AUTOMOBILES', 'ACCURATE FILLING', 'CHAKRA PETROL',
                        'ESSAR', 'MANAV SERVICE', 'AGARWAL', 'GREEN GAS'
                    ],
                    'Bills & Utilities': [
                        'ELECTRICITY', 'WATER', 'BROADBAND', 'MOBILE', 'RECHARGE',
                        'GAS', 'PHONEPE', 'BILLDESK', 'BILL PAYMENT', 'ONE97',
                        'MOBIKWIK'
                    ],
                    'Entertainment': [
                        'NETFLIX', 'PRIME', 'MOVIE', 'HOTSTAR', 'SPOTIFY', 'YOUTUBE',
                        'BIGTREE ENTERTAINMENT'
                    ],
                    'Insurance & Finance': [
                        'INSURANCE', 'SHRIRAM LIFE', 'EMI', 'LOAN'
                    ],
                    'Healthcare': [
                        'MEDICAL', 'HOSPITAL', 'PHARMACY', 'CLINIC', 'DOCTOR',
                        'SHALBY HOSPITALS', 'NURSING'
                    ],
                    'Fees & Charges': [
                        'FEE', 'CHARGE', 'OVERLIMIT', 'GST', 'INTEREST',
                        'SURCHARGE'
                    ],
                    'Other': []
                }
                
                def categorize(desc):
                    desc_upper = desc.upper()
                    for cat, keywords in categories.items():
                        if any(kw in desc_upper for kw in keywords):
                            return cat
                    return 'Other'
                
                transactions_df['category'] = transactions_df['description'].apply(categorize)
                
                # Only include debits for spending analysis
                spending_df = transactions_df[transactions_df['type'] == 'Debit'].groupby('category')['amount'].sum().reset_index()
                spending_df = spending_df.sort_values('amount', ascending=False)
                
                if len(spending_df) > 0:
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        fig = px.pie(spending_df, values='amount', names='category', 
                                     title='Spending Distribution',
                                     color_discrete_sequence=px.colors.qualitative.Set3)
                        fig.update_traces(textposition='inside', textinfo='percent+label')
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        st.markdown("##### Top Categories")
                        for idx, row in spending_df.head(5).iterrows():
                            st.write(f"**{row['category']}:** ₹{row['amount']:,.2f}")
                else:
                    st.info("No spending data available to visualize")
            
            with tab3:
                st.markdown("#### 📈 Transaction Timeline")
                
                if len(transactions_df) > 0:
                    fig = go.Figure()
                    
                    # Add debit transactions
                    debit_df = transactions_df[transactions_df['type'] == 'Debit']
                    if len(debit_df) > 0:
                        fig.add_trace(go.Scatter(
                            x=debit_df['date'],
                            y=debit_df['amount'],
                            mode='markers',
                            name='Debit',
                            marker=dict(size=10, color='red', opacity=0.6),
                            text=debit_df['description'],
                            hovertemplate='<b>%{text}</b><br>Date: %{x}<br>Amount: ₹%{y:,.2f}<extra></extra>'
                        ))
                    
                    # Add credit transactions
                    credit_df = transactions_df[transactions_df['type'] == 'Credit']
                    if len(credit_df) > 0:
                        fig.add_trace(go.Scatter(
                            x=credit_df['date'],
                            y=credit_df['amount'].abs(),
                            mode='markers',
                            name='Credit',
                            marker=dict(size=10, color='green', opacity=0.6),
                            text=credit_df['description'],
                            hovertemplate='<b>%{text}</b><br>Date: %{x}<br>Amount: ₹%{y:,.2f}<extra></extra>'
                        ))
                    
                    fig.update_layout(
                        title='Transaction Timeline',
                        xaxis_title='Date',
                        yaxis_title='Amount (₹)',
                        hovermode='closest',
                        height=500
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No timeline data to visualize")
            
            with tab4:
                st.markdown("### 📂 Export Statement Data")
                
                # Create comprehensive CSV data
                summary_data = {
                    "Field": [
                        "Bank Name", "Cardholder Name", "Card Last 4 Digits", 
                        "Statement Date", "Payment Due Date", "Total Amount Due",
                        "Minimum Amount Due", "Credit Limit", "Available Credit",
                        "Total Transactions", "Credit Utilization %"
                    ],
                    "Value": [
                        data.bank_name, data.cardholder_name, data.card_last_4,
                        data.statement_date, data.payment_due_date, f"₹{data.total_amount_due:,.2f}",
                        f"₹{data.minimum_amount_due:,.2f}", f"₹{data.credit_limit:,.2f}", 
                        f"₹{data.available_credit:,.2f}", len(data.transactions),
                        f"{((data.credit_limit - data.available_credit) / data.credit_limit * 100):.1f}%" if data.credit_limit > 0 else "N/A"
                    ]
                }
                summary_df = pd.DataFrame(summary_data)
                
                # Transactions section
                transactions_export_df = pd.DataFrame(data.transactions)
                transactions_export_df["Formatted Amount"] = transactions_export_df["amount"].apply(
                    lambda x: f"₹{x:,.2f}" if x >= 0 else f"-₹{abs(x):,.2f}"
                )
                transactions_export_df = transactions_export_df[["date", "description", "Formatted Amount", "amount"]]
                transactions_export_df.columns = ["Date", "Description", "Formatted Amount", "Numeric Amount"]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Combine for download
                    combined_data = pd.concat([
                        summary_df, 
                        pd.DataFrame([{"Field": "---TRANSACTIONS---", "Value": ""}]),
                        transactions_export_df
                    ], ignore_index=True)
                    
                    csv_data = combined_data.to_csv(index=False).encode("utf-8")
                    
                    st.download_button(
                        "📥 Download Full Statement (CSV)",
                        csv_data,
                        f"{data.bank_name}_statement_{data.statement_date.replace('/', '-')}.csv",
                        "text/csv",
                        help="Download complete statement data including summary and transactions",
                        use_container_width=True
                    )
                
                with col2:
                    # Quick transactions-only download
                    transactions_csv = transactions_export_df[["Date", "Description", "Formatted Amount"]].to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "📥 Download Transactions Only (CSV)",
                        transactions_csv,
                        f"{data.bank_name}_transactions_{data.statement_date.replace('/', '-')}.csv",
                        "text/csv",
                        help="Download only transactions data",
                        use_container_width=True
                    )
                
                st.markdown("---")
                st.info("💡 Export your data to CSV format for further analysis in Excel or other tools.")
        
        else:
            st.info("No transactions found in this statement.")

    except ValueError as e:
        error_msg = str(e)
        if "encrypted" in error_msg.lower() or "password" in error_msg.lower():
            st.error("❌ Incorrect password or unable to decrypt PDF. Please try again with the correct password.")
        elif "ocr" in error_msg.lower() or "no text" in error_msg.lower() or "scanned" in error_msg.lower():
            st.markdown("""
            <div class="scanned-warning">
            <strong>⚠️ Scanned PDF Detected</strong><br>
            This appears to be a scanned PDF or image-based document.
            </div>
            """, unsafe_allow_html=True)
            
            if not ocr_available:
                st.error("❌ OCR is not installed. Cannot process scanned PDFs.")
                
                st.markdown("### 📋 How to Enable OCR:")
                
                tab1, tab2, tab3 = st.tabs(["Windows", "Mac", "Linux"])
                
                with tab1:
                    st.markdown("""
                    **Step 1: Download Tesseract**
                    1. Go to: https://github.com/UB-Mannheim/tesseract/wiki
                    2. Download the latest installer (e.g., `tesseract-ocr-w64-setup-5.3.x.exe`)
                    3. Run the installer and note the installation path (default: `C:\\Program Files\\Tesseract-OCR`)
                    
                    **Step 2: Install Python packages**
                    ```bash
                    pip install pytesseract pillow
                    ```
                    
                    **Step 3: Configure path (if needed)**
                    If Tesseract is not in your PATH, add this to `credit_card_parser.py` after imports:
                    ```python
                    import pytesseract
                    pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
                    ```
                    
                    **Step 4: Restart the Streamlit app**
                    ```bash
                    streamlit run app.py
                    ```
                    """)
                
                with tab2:
                    st.markdown("""
                    **Step 1: Install Tesseract via Homebrew**
                    ```bash
                    brew install tesseract
                    ```
                    
                    **Step 2: Install Python packages**
                    ```bash
                    pip install pytesseract pillow
                    ```
                    
                    **Step 3: Verify installation**
                    ```bash
                    tesseract --version
                    ```
                    
                    **Step 4: Restart the Streamlit app**
                    ```bash
                    streamlit run app.py
                    ```
                    """)
                
                with tab3:
                    st.markdown("""
                    **Step 1: Install Tesseract**
                    ```bash
                    sudo apt-get update
                    sudo apt-get install tesseract-ocr
                    sudo apt-get install libtesseract-dev
                    ```
                    
                    **Step 2: Install Python packages**
                    ```bash
                    pip install pytesseract pillow
                    ```
                    
                    **Step 3: Verify installation**
                    ```bash
                    tesseract --version
                    ```
                    
                    **Step 4: Restart the Streamlit app**
                    ```bash
                    streamlit run app.py
                    ```
                    """)
                
                st.info("💡 **Alternative:** Download a fresh digital (non-scanned) copy from your bank's website or mobile app.")
            else:
                st.error(f"❌ {error_msg}")
                st.info("💡 **Tips:**\n- The scan quality might be too low\n- Try a higher resolution scan (300 DPI minimum)\n- Download a digital copy from your bank if possible")
        else:
            st.error(f"❌ Error: {error_msg}")
    except Exception as e:
        error_msg = str(e)
        st.error(f"❌ Unexpected error: {error_msg}")
        
        # Provide helpful tips
        if "text" not in error_msg.lower():
            st.info("💡 Tips for better results:")
            st.write("- Ensure the PDF is a valid credit card statement from supported banks")
            st.write("- For encrypted PDFs, make sure you entered the correct password")
            st.write("- Try with a different statement if available")

    finally:
        # Clean up temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)

else:
    # Show instructions when no file is uploaded
    st.info("👆 Upload your PDF credit card statement to get started.")
    
    st.markdown("---")
    st.markdown("### 📋 Supported Banks")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("🏦 **HDFC Bank**")
        st.write("🏦 **ICICI Bank**")
    with col2:
        st.write("🏦 **Axis Bank**")
        st.write("🏦 **IDFC First Bank**")
    with col3:
        st.write("🏦 **Indian Bank**")
        st.write("🔍 **Other banks (basic support)**")
    
    st.markdown("---")
    
    # Add warning about scanned PDFs
    st.markdown("""
    <div class="warning-box">
    <strong>⚠️ Important Note:</strong> This tool works best with <strong>digital PDFs</strong> (text-based) from bank statements.<br><br>
    <strong>📄 Scanned PDFs:</strong> Supported with OCR (requires Tesseract installation)<br>
    <strong>How to check:</strong> Try selecting text in your PDF. If you can highlight/copy text, it's digital. If not, it's scanned.<br><br>
    <strong>For scanned PDFs, install Tesseract OCR:</strong><br>
    • Windows: <a href="https://github.com/UB-Mannheim/tesseract/wiki" target="_blank">Download installer</a><br>
    • Mac: <code>brew install tesseract</code><br>
    • Linux: <code>sudo apt-get install tesseract-ocr</code><br>
    • Python: <code>pip install pytesseract pillow</code>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 🛡️ Privacy Note")
    st.info("""
    Your financial data is processed locally and never stored on our servers. 
    All processing happens in your browser and temporary files are deleted immediately after analysis.
    """)
    
    st.markdown("### 💡 Features")
    features_col1, features_col2 = st.columns(2)
    
    with features_col1:
        st.write("✅ **Encrypted PDF support**")
        st.write("✅ **Transaction analysis**")
        st.write("✅ **Credit utilization tracking**")
        st.write("✅ **Spending categorization**")
        st.write("✅ **OCR for scanned PDFs** (requires Tesseract)")
    
    with features_col2:
        st.write("✅ **Multi-bank compatibility**")
        st.write("✅ **CSV export**")
        st.write("✅ **Real-time filtering**")
        st.write("✅ **Visual analytics**")

# ===== FOOTER =====
st.markdown("---")
st.caption("Built with ❤️ using Streamlit | Your financial privacy is our priority")