"""
translations.py — Bilingual UI dictionary (English / Bahasa Melayu).

All user-facing labels, titles, and messages are defined here so the rest of the
app can switch languages with a single session-state variable.
"""

TRANSLATIONS = {
    "en": {
        # ---- Language toggle ----
        "language": "Language",
        "bahasa": "Bahasa Melayu",
        "english": "English",

        # ---- Sidebar: Upload ----
        "upload_title": "📂 Upload Your Data",
        "upload_label": "Choose a CSV or Excel (.xlsx) file",
        "upload_help": "Upload your sales data exported from your POS / accounting system. Note: Only .xlsx files are supported.",
        "column_mapping": "🎯 Column Mapping",
        "column_mapping_hint": "If the auto-detected columns look wrong, select the correct ones from the dropdowns below.",
        "date_col_label": "📅 Date / Transaction Date column",
        "amount_col_label": "💰 Sales / Amount column",
        "product_col_label": "📦 Product / Item column  (optional)",
        "category_col_label": "🏷️ Category / Segment column  (optional)",
        "generate_btn": "🚀 Generate Dashboard",
        "generating": "Cleaning data & building dashboard...",
        "dashboard_ready": "Dashboard ready!",
        "reading_file": "Reading file...",

        # ---- Sidebar: API Key ----
        "api_key_title": "🔑 Gemini API Key",
        "api_key_help": "Enter your Google AI Studio API key. Get one at https://aistudio.google.com/",
        "api_key_placeholder": "Paste your API key here",
        "api_key_secured": "✅ API Key secured via {source}",
        "api_key_source_secrets": ".streamlit/secrets.toml",
        "api_key_source_env": "environment variable (GEMINI_API_KEY)",
        "api_key_remove_btn": "🗑️ Remove Key",
        "api_key_security_note": "🔒 Your key is sent only to Google's Gemini API. It stays in your browser session and is never saved to disk.",
        "api_key_not_configured": "⏸️ No API key configured — AI chat disabled",
        "api_key_configure_help": "Set your key via: (1) secrets.toml, (2) GEMINI_API_KEY env var, or (3) paste below",

        # ---- Filters ----
        "filter_title": "🔍 Filters",
        "filter_year_label": "📅 Year",
        "filter_month_label": "📅 Month",
        "filter_product_label": "📦 Product",
        "filter_category_label": "🏷️ Category",
        "filter_amount_label": "💰 Amount Range (RM)",
        "filter_showing": "Showing",

        # ---- Sidebar: Errors ----
        "file_error": "❌ Could not read the file. Please check that it is a valid CSV or Excel (.xlsx) file and try again.\n\nNote: Old-format .xls files are not supported — save as .xlsx in Excel first.",

        # ---- Empty state ----
        "empty_eyebrow": "Upload · Map · Analyse",
        "empty_title": "Your Business Dashboard Awaits",
        "empty_desc": "Upload a CSV or Excel file with your sales data in the sidebar to get an instant dashboard with KPIs, trends, and product breakdowns — no account or configuration needed.",
        "empty_features": "✅ Supports CSV &amp; Excel (.xlsx)<br>✅ Auto-detects date &amp; amount columns<br>✅ Bilingual column names (English / Bahasa Melayu)",

        # ---- Dashboard ----
        "transactions": "transactions",
        "total_sales_label": "Total sales",
        "no_data_warning": "⚠️ No usable data remained after cleaning. This could mean:\n\n1. The date column couldn't be parsed — check the format\n2. The amount column couldn't be read as numbers\n3. All rows were empty\n\nTry uploading a different file or re-check the column mapping in the sidebar.",

        # ---- KPI cards ----
        "total_sales": "Total Sales",
        "transactions_kpi": "Transactions",
        "avg_order_value": "Avg Order Value",
        "best_day": "Best Day",

        # ---- Charts ----
        "sales_trend_title": "📈 Sales Trend Over Time",
        "sales_trend_x": "Date",
        "sales_trend_y": "Sales (RM)",
        "top_products_title": "Top {n} Products / Items by Sales",
        "top_products_x": "Total Sales (RM)",
        "category_title": "Sales by Category / Segment",

        # ---- Chart info messages ----
        "trend_no_data": "Could not determine date or amount columns for the trend chart.",
        "trend_col_missing": "Date or amount column not found in the cleaned data.",
        "trend_no_parse": "Date column could not be parsed.  Trend chart unavailable.",
        "products_no_col": "Product column not detected. Upload data with a product/item column to see this chart.",
        "products_no_data": "No product data available.",

        # ---- Raw data expander ----
        "raw_data": "📄 View Raw Data (first 100 rows)",

        # ---- PDF export ----
        "pdf_btn": "DOWNLOAD PDF",
        "pdf_title": "Sigma — Business Insight Report",
        "pdf_file": "File analyzed",
        "pdf_date_range": "Date range",
        "pdf_generated": "Generated at",
        "pdf_scope_note": "Filtered view - this report reflects the active filters, not the full dataset. Filters:",
        "pdf_section_kpis": "Key Performance Indicators",
        "pdf_section_trend": "Sales Trend Over Time",
        "pdf_section_products": "Top Products / Items by Sales",
        "pdf_section_category": "Sales by Category / Segment",
        "pdf_section_insights": "Insights & Recommendations",
        "pdf_col_product": "Product",
        "pdf_col_sales": "Sales (RM)",
        "pdf_col_share": "Share",
        "pdf_col_category": "Category",
        "pdf_footer_generated": "Generated by Sigma",
        "pdf_footer_snapshot": "This report reflects a snapshot of the dashboard at the time of generation.",
        "pdf_f_year": "Year",
        "pdf_f_month": "Month",
        "pdf_f_product": "Product",
        "pdf_f_category": "Category",
        "pdf_f_amount": "Amount",

        # ---- Chat section ----
        "chat_title": "💬 Ask the AI Agent",
        "chat_desc": "Ask questions about your sales data in English or Bahasa Melayu.",
        "chat_input_placeholder": "Ask about your data...",
        "chat_welcome": "👋 Hi! I'm your **Business Insight Agent**. Ask me anything about your sales data — in English or Bahasa Melayu!\n\nTry asking:\n- \"What were my best selling items?\"\n- \"Bandingkan jualan minggu ini dengan minggu lepas\"\n- \"Give me a business insight\"",
        "chat_thinking": "Thinking...",
        "chat_error": "Sorry, I encountered an error. Please check your API key and try again.",
        "chat_no_data": "Please upload and generate a dashboard first before asking questions.",
        "chat_no_api_key": "⚠️ Please enter your **Gemini API Key** in the sidebar to enable the AI chat assistant.",

        # ---- Quick Insights ----
        "quick_insights_btn": "🚀 Quick Insights",
        "quick_insights_btn_hint": "Run all 4 analysis tools instantly and get a complete report",
        "quick_insights_running": "Generating comprehensive report...",
        "quick_insights_title": "📋 Comprehensive Business Report",
        "quick_insights_summary_title": "📊 Sales Summary",
        "quick_insights_products_title": "🏆 Top Products",
        "quick_insights_comparison_title": "📈 Period Comparison",
        "quick_insights_insights_title": "💡 Insights & Recommendations",
        "quick_insights_no_products": "No product column detected. Upload data with a product column to see top products.",
        "quick_insights_no_comparison": "Insufficient data for period comparison (need at least 2 days of data).",
        "quick_insights_ready": "✅ Quick Insights ready!",

        # ---- Footer ----
        "footer": "Business Insight Agent &mdash; AI-Powered Sales Analytics for Malaysian Small Businesses",
    },

    "bm": {
        # ---- Language toggle ----
        "language": "Bahasa",
        "bahasa": "Bahasa Melayu",
        "english": "English",

        # ---- Sidebar: Upload ----
        "upload_title": "📂 Muat Naik Data Anda",
        "upload_label": "Pilih fail CSV atau Excel (.xlsx)",
        "upload_help": "Muat naik data jualan yang dieksport daripada sistem POS / perakaunan anda. Nota: Hanya fail .xlsx disokong.",
        "column_mapping": "🎯 Pemetaan Lajur",
        "column_mapping_hint": "Jika lajur yang dikesan automatik tidak tepat, pilih lajur yang betul dari menu lungsur di bawah.",
        "date_col_label": "📅 Tarikh / Lajur Tarikh Transaksi",
        "amount_col_label": "💰 Jualan / Lajur Jumlah",
        "product_col_label": "📦 Produk / Barangan  (pilihan)",
        "category_col_label": "🏷️ Kategori / Segmen  (pilihan)",
        "generate_btn": "🚀 Jana Dashboard",
        "generating": "Membersihkan data & membina dashboard...",
        "dashboard_ready": "Dashboard sedia!",
        "reading_file": "Membaca fail...",

        # ---- Sidebar: API Key ----
        "api_key_title": "🔑 Kunci API Gemini",
        "api_key_help": "Masukkan kunci API Google AI Studio anda. Dapatkannya di https://aistudio.google.com/",
        "api_key_placeholder": "Tampal kunci API anda di sini",
        "api_key_secured": "✅ Kunci API dijamin melalui {source}",
        "api_key_source_secrets": "fail rahsia (.streamlit/secrets.toml)",
        "api_key_source_env": "pembolehubah persekitaran (GEMINI_API_KEY)",
        "api_key_remove_btn": "🗑️ Padam Kunci",
        "api_key_security_note": "🔒 Kunci anda dihantar hanya ke API Gemini Google. Ia kekal dalam sesi pelayar anda dan tidak pernah disimpan ke cakera.",
        "api_key_not_configured": "⏸️ Tiada kunci API dikonfigurasi — chat AI dilumpuhkan",
        "api_key_configure_help": "Tetapkan kunci anda melalui: (1) secrets.toml, (2) pembolehubah persekitaran GEMINI_API_KEY, atau (3) tampal di bawah",

        # ---- Filters ----
        "filter_title": "🔍 Tapisan",
        "filter_year_label": "📅 Tahun",
        "filter_month_label": "📅 Bulan",
        "filter_product_label": "📦 Produk",
        "filter_category_label": "🏷️ Kategori",
        "filter_amount_label": "💰 Julat Jumlah (RM)",
        "filter_showing": "Menunjukkan",

        # ---- Sidebar: Errors ----
        "file_error": "❌ Gagal membaca fail. Sila pastikan fail adalah CSV atau Excel (.xlsx) yang sah dan cuba lagi.\n\nNota: Format .xls lama tidak disokong — simpan sebagai .xlsx dalam Excel terlebih dahulu.",

        # ---- Empty state ----
        "empty_eyebrow": "Muat Naik · Peta · Analisis",
        "empty_title": "Dashboard Perniagaan Anda Menanti",
        "empty_desc": "Muat naik fail CSV atau Excel dengan data jualan anda di bar sisi untuk mendapatkan dashboard segera dengan KPI, trend, dan pecahan produk — tanpa akaun atau konfigurasi diperlukan.",
        "empty_features": "✅ Menyokong CSV &amp; Excel (.xlsx)<br>✅ Mengesan lajur tarikh &amp; jumlah secara automatik<br>✅ Nama lajur dwibahasa (English / Bahasa Melayu)",

        # ---- Dashboard ----
        "transactions": "transaksi",
        "total_sales_label": "Jumlah jualan",
        "no_data_warning": "⚠️ Tiada data yang boleh digunakan selepas pembersihan. Ini mungkin bermaksud:\n\n1. Lajur tarikh tidak dapat dibaca — periksa format\n2. Lajur jumlah tidak dapat dibaca sebagai nombor\n3. Semua baris kosong\n\nCuba muat naik fail yang berbeza atau semak semula pemetaan lajur di bar sisi.",

        # ---- KPI cards ----
        "total_sales": "Jumlah Jualan",
        "transactions_kpi": "Transaksi",
        "avg_order_value": "Nilai Purata Pesanan",
        "best_day": "Hari Terbaik",

        # ---- Charts ----
        "sales_trend_title": "📈 Trend Jualan Mengikut Masa",
        "sales_trend_x": "Tarikh",
        "sales_trend_y": "Jualan (RM)",
        "top_products_title": "{n} Produk / Item Teratas mengikut Jualan",
        "top_products_x": "Jumlah Jualan (RM)",
        "category_title": "Jualan mengikut Kategori / Segmen",

        # ---- Chart info messages ----
        "trend_no_data": "Lajur tarikh atau jumlah tidak dapat ditentukan untuk carta trend.",
        "trend_col_missing": "Lajur tarikh atau jumlah tidak ditemui dalam data yang dibersihkan.",
        "trend_no_parse": "Lajur tarikh tidak dapat dibaca. Carta trend tidak tersedia.",
        "products_no_col": "Lajur produk tidak dikesan. Muat naik data dengan lajur produk/item untuk melihat carta ini.",
        "products_no_data": "Tiada data produk tersedia.",

        # ---- Raw data expander ----
        "raw_data": "📄 Lihat Data Mentah (100 baris pertama)",

        # ---- PDF export ----
        "pdf_btn": "DOWNLOAD PDF",
        "pdf_title": "Sigma — Laporan Cerapan Perniagaan",
        "pdf_file": "Fail dianalisis",
        "pdf_date_range": "Julat tarikh",
        "pdf_generated": "Dijana pada",
        "pdf_scope_note": "Paparan ditapis - laporan ini mencerminkan tapisan aktif, bukan keseluruhan data. Tapisan:",
        "pdf_section_kpis": "Petunjuk Prestasi Utama",
        "pdf_section_trend": "Trend Jualan Mengikut Masa",
        "pdf_section_products": "Produk / Item Teratas mengikut Jualan",
        "pdf_section_category": "Jualan mengikut Kategori / Segmen",
        "pdf_section_insights": "Cerapan & Cadangan",
        "pdf_col_product": "Produk",
        "pdf_col_sales": "Jualan (RM)",
        "pdf_col_share": "Bahagian",
        "pdf_col_category": "Kategori",
        "pdf_footer_generated": "Dijana oleh Sigma",
        "pdf_footer_snapshot": "Laporan ini mencerminkan gambaran dashboard pada masa penjanaan.",
        "pdf_f_year": "Tahun",
        "pdf_f_month": "Bulan",
        "pdf_f_product": "Produk",
        "pdf_f_category": "Kategori",
        "pdf_f_amount": "Jumlah",

        # ---- Chat section ----
        "chat_title": "💬 Tanya AI Agent",
        "chat_desc": "Tanya soalan tentang data jualan anda dalam Bahasa Melayu atau English.",
        "chat_input_placeholder": "Tanya tentang data anda...",
        "chat_welcome": "👋 Hai! Saya **Ejen Cerapan Perniagaan** anda. Tanya apa sahaja tentang data jualan anda — dalam Bahasa Melayu atau English!\n\nCuba tanya:\n- \"Apa item paling laris?\"\n- \"Bandingkan jualan minggu ini dengan minggu lepas\"\n- \"Beri saya cerapan perniagaan\"",
        "chat_thinking": "Berfikir...",
        "chat_error": "Maaf, ralat berlaku. Sila periksa kunci API anda dan cuba lagi.",
        "chat_no_data": "Sila muat naik data dan jana dashboard terlebih dahulu sebelum bertanya soalan.",
        "chat_no_api_key": "⚠️ Sila masukkan **Kunci API Gemini** di bar sisi untuk membolehkan pembantu AI.",

        # ---- Quick Insights ----
        "quick_insights_btn": "🚀 Cerapan Pantas",
        "quick_insights_btn_hint": "Jalankan semua 4 alat analisis serta-merta dan dapatkan laporan lengkap",
        "quick_insights_running": "Menjana laporan komprehensif...",
        "quick_insights_title": "📋 Laporan Perniagaan Komprehensif",
        "quick_insights_summary_title": "📊 Ringkasan Jualan",
        "quick_insights_products_title": "🏆 Produk Teratas",
        "quick_insights_comparison_title": "📈 Perbandingan Tempoh",
        "quick_insights_insights_title": "💡 Cerapan & Cadangan",
        "quick_insights_no_products": "Lajur produk tidak dikesan. Muat naik data dengan lajur produk untuk melihat produk teratas.",
        "quick_insights_no_comparison": "Data tidak mencukupi untuk perbandingan tempoh (perlukan sekurang-kurangnya 2 hari data).",
        "quick_insights_ready": "✅ Cerapan Pantas sedia!",

        # ---- Footer ----
        "footer": "Business Insight Agent &mdash; Analitis Jualan Dikuasakan AI untuk Perniagaan Kecil Malaysia",
    },
}


def t(key: str, lang: str = "en") -> str:
    """Translate a key into the given language.

    Falls back to English, then to the key itself if neither has a value.
    Keys ending with '_label', '_title', etc. are supported.
    """
    return TRANSLATIONS.get(lang, {}).get(key, TRANSLATIONS["en"].get(key, key))
