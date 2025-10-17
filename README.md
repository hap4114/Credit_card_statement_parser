# 💳 Multi-Bank Credit Card Statement Parser

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-square&logo=Streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-square&logo=python&logoColor=white)
![Railway](https://img.shields.io/badge/Railway-0B0D0E?style=for-square&logo=railway&logoColor=white)

A powerful web application that automatically parses and analyzes credit card statements from multiple Indian banks. Extract transaction data, visualize spending patterns, and export financial insights with ease.

## 🌟 Live Demo

**Live Application:** [https://creditcardstatementparser-production.up.railway.app/](https://creditcardstatementparser-production.up.railway.app/)

## 📋 Table of Contents
- [Features](#-features)
- [Quick Start](#-quick-start)
- [Supported Banks](#-supported-banks)
- [Installation](#-installation)
- [Usage Guide](#-usage-guide)
- [API Documentation](#-api-documentation)
- [Deployment](#-deployment)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

## ✨ Features

### Multi-Bank Support
- **HDFC Bank** - Complete statement parsing
- **ICICI Bank** - Advanced transaction analysis
- **Axis Bank** - Full credit limit tracking
- **IDFC First Bank** - Comprehensive support
- **Indian Bank** - Detailed transaction parsing
- **Generic Parser** - Basic support for other banks

### 🏦 Supported Banks

| Bank | Digital PDF | Scanned PDF | Encrypted PDF | Transaction Parsing |
|------|-------------|-------------|---------------|---------------------|
| HDFC | ✅ | ✅ | ✅ | ✅ |
| ICICI | ✅ | ✅ | ✅ | ✅ |
| Axis | ✅ | ✅ | ✅ | ✅ |
| IDFC First | ✅ | ✅ | ✅ | ✅ |
| Indian Bank | ✅ | ✅ | ✅ | ✅ |
| Other Banks | ✅ | ✅ | ✅ | ⚠️ Basic |


### Advanced Capabilities
- **Digital PDF Processing** - Text-based statement analysis
- **OCR Integration** - Scanned PDF support via Tesseract
- **Encrypted PDF Support** - Password-protected statement handling
- **Visual Analytics** - Interactive charts and spending insights
- **Transaction Categorization** - Automatic spending classification
- **CSV Export** - Download parsed data for analysis
- **Responsive Design** - Works on desktop and mobile

## 🚀 Quick Start

### Use Live App (Recommended)
1. Visit [Live App](https://creditcardstatementparser-production.up.railway.app/)
2. Upload your credit card statement PDF
3. View parsed data and analytics instantly

### Local Installation
```bash
# Clone repository
git clone https://github.com/hap4114/Credit_card_statement_parser.git
cd Credit_card_statement_parser

# Install dependencies
pip install -r requirements.txt

# Run application
streamlit run app.py
