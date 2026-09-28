# ==============================================================================
# MASTER EXECUTION PLAN: YORDAMCHI BUXGALTER AI
# ==============================================================================
# Target System: Uzbekistan Accounting & Tax Ecosystem (Didox, Soliq.uz, BHMS)
# Architecture: Modular Monolith (FastAPI + PostgreSQL + Redis + Next.js 14)
# Mode: Full Autonomous Execution (Zero-Confirmation / Self-Correcting)
# ==============================================================================

## 0. AGENT AUTONOMOUS DIRECTIVE (CORE INSTRUCTIONS)
You are the Lead Autonomous Systems Architect & Full-Stack Engineer.
Execute all phases sequentially from Phase 1 through Phase 7 without asking the user for confirmation.
- If dependencies fail, automatically resolve version constraints.
- If database migrations or scripts crash, inspect stderr/logs, apply fixes, and re-run.
- Mathematical integrity is non-negotiable: all financial numbers must be Decimal, not float.
- Never place business logic inside API routers; enforce the 3-Layer Pattern (Router -> Service -> Repository).
- Complete every phase and run automated verification tests before declaring completion.

---

## 1. PROJECT STRUCTURE BLUEPRINT (MODULAR MONOLITH)
Ensure the root directory contains the following modular layout:

```text
yordamchi-buxgalter-ai/
├── .antigravity/
│   └── config.json
├── docker-compose.yml
├── Makefile
├── run_antigravity.sh
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/
│   └── app/
│       ├── main.py
│       ├── core/
│       │   ├── config.py
│       │   ├── database.py
│       │   └── security.py
│       ├── modules/
│       │   ├── accounting/         # BHMS & Simple Mode engine
│       │   │   ├── models.py
│       │   │   ├── schemas.py
│       │   │   ├── repositories.py
│       │   │   ├── services.py
│       │   │   └── router.py
│       │   ├── documents/          # Parsers (Didox, Soliq, Bank)
│       │   │   ├── models.py
│       │   │   ├── schemas.py
│       │   │   ├── parsers/
│       │   │   │   ├── didox_parser.py
│       │   │   │   ├── soliq_parser.py
│       │   │   │   └── bank_parser.py
│       │   │   ├── services.py
│       │   │   └── router.py
│       │   ├── ocr/                # Degraded/Blurry Scan Engine
│       │   │   ├── image_enhancer.py
│       │   │   ├── ocr_extractor.py
│       │   │   ├── ocr_validator.py
│       │   │   └── router.py
│       │   └── reports/            # OSV, Material Report, Akt Sverka
│       │       ├── services.py
│       │       ├── excel_export.py
│       │       ├── pdf_export.py
│       │       └── router.py
│       └── tests/
│           ├── conftest.py
│           ├── test_accounting_math.py
│           ├── test_ocr_pipeline.py
│           └── test_parsers.py
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── tsconfig.json
    ├── tailwind.config.js
    └── src/
        ├── app/
        │   ├── layout.tsx
        │   ├── page.tsx
        │   ├── documents/page.tsx
        │   ├── ocr-verify/page.tsx
        │   ├── osv/page.tsx
        │   ├── materials/page.tsx
        │   └── akt-sverka/page.tsx
        ├── components/
        │   ├── layout/Sidebar.tsx
        │   ├── ocr/VerificationWorkspace.tsx
        │   ├── reports/VirtualizedDataTable.tsx
        │   └── ui/
        └── lib/
            ├── api-client.ts
            └── utils.ts
```

---

## 2. STEP-BY-STEP IMPLEMENTATION ROADMAP

### PHASE 1: INFRASTRUCTURE & BACKEND SCAFFOLDING
1. **docker-compose.yml**:
   - PostgreSQL 16 (Port 5432, db: `buxgalter_db`, user: `postgres`, password: `postgres_password`).
   - Redis 7 Alpine (Port 6379) for caching and background tasks.
2. **Backend Dependencies (`backend/requirements.txt`)**:
   ```txt
   fastapi>=0.110.0
   uvicorn[standard]>=0.28.0
   pydantic>=2.6.4
   pydantic-settings>=2.2.1
   sqlalchemy[asyncio]>=2.0.28
   asyncpg>=0.29.0
   alembic>=1.13.1
   pandas>=2.2.1
   openpyxl>=3.1.2
   python-multipart>=0.0.9
   opencv-python-headless>=4.9.0.80
   PyMuPDF>=1.24.0
   Pillow>=10.2.0
   openai>=1.14.0
   redis>=5.0.3
   pytest>=8.1.1
   pytest-asyncio>=0.23.5
   httpx>=0.27.0
   reportlab>=4.1.0
   ```
3. Initialize FastAPI in `backend/app/main.py` with CORS configured for `http://localhost:3000`.

---

### PHASE 2: DATABASE SCHEMA & BHMS SEEDING (ACCOUNTING CORE)
1. **Models (`backend/app/modules/accounting/models.py`)**:
   - `Organization`: ID, name, INN (STIR: 9 digits), vat_payer (bool), accounting_mode (`SIMPLE` | `BHMS`).
   - `ChartOfAccount`: code (PK, e.g., '1000', '2900', '4000', '5000', '5110', '6000', '9000'), name, account_type (`ASSET`, `LIABILITY`, `EQUITY`, `REVENUE`, `EXPENSE`).
   - `Counterparty`: ID, organization_id, name, INN (9 digits), is_client, is_supplier, phone.
   - `InventoryItem`: ID, organization_id, name, ikpu_code (MXIK: 17 digits), unit, min_stock_alert.
   - `Transaction`: ID, organization_id, doc_number, doc_date, doc_type (`EHF`, `BANK_PAYMENT`, `CASH`, `STOCK`), debit_account, credit_account, counterparty_id, item_id, quantity (Decimal), price (Decimal), vat_rate (Decimal), vat_amount (Decimal), total_amount (Decimal), description.
2. **BHMS Seeding Script (`backend/app/core/seed_bhms.py`)**:
   Pre-populate standard Uzbekistan BHMS accounts:
   - `1000`: Materiallar (Asset)
   - `2900`: Tovarlar (Asset)
   - `4000`: Xaridorlar va buyurtmachilar bilan hisob-kitoblar (Asset)
   - `5000`: Milliy valyutadagi pul mablag'lari / Kassa (Asset)
   - `5110`: Hisob-kitob schoti / Bank (Asset)
   - `6000`: Mol yetkazib beruvchilar bilan hisob-kitoblar (Liability)
   - `9000`: Asosiy faoliyatdan olingan daromadlar (Revenue)
   - `9400`: Davr xarajatlari (Expense)

---

### PHASE 3: BLURRY & DEGRADED SCAN OCR PIPELINE
1. **`backend/app/modules/ocr/image_enhancer.py`**:
   - `pdf_to_enhanced_images(pdf_bytes, dpi=300)` using PyMuPDF.
   - Grayscale conversion -> Deskewing via `cv2.minAreaRect` -> Denoising via `cv2.fastNlMeansDenoising` -> CLAHE adaptive contrast (`clipLimit=2.2`) -> Unsharp Masking filter for faded numbers.
2. **`backend/app/modules/ocr/ocr_extractor.py`**:
   - Strict Pydantic schemas: `ExtractedDocument`, `ExtractedLineItem`.
   - Send cleaned image to Vision LLM with structured output prompt enforcing Uzbekistan tax norms:
     - STIR is 9 digits (`^\d{9}$`).
     - MXIK/IKPU is 17 digits (`^\d{17}$`).
     - Standard VAT is 12% or 0%.
     - Return field-level `confidence` score (0.0 to 1.0).
3. **`backend/app/modules/ocr/ocr_validator.py`**:
   - Mathematical check: `abs((qty * price + vat) - total) < 0.05`.
   - Set row status to `WARNING` if math deviates or confidence < 0.85.
   - Verify STIR validity.
4. **Endpoints (`backend/app/modules/ocr/router.py`)**:
   - `POST /api/v1/ocr/upload-and-parse`
   - `POST /api/v1/ocr/commit`

---

### PHASE 4: DOCUMENT PARSERS & IMPORTERS
1. **Didox Parser (`backend/app/modules/documents/parsers/didox_parser.py`)**:
   - Read Didox standard Excel (.xlsx) exports. Extract Invoice ID, Date, Contract Number, Supplier INN, Buyer INN, IKPU, Item Name, Units, Quantity, Price, VAT amount, and Total sum.
2. **Soliq.uz Turnover Parser (`backend/app/modules/documents/parsers/soliq_parser.py`)**:
   - Parse official turnover statements, fiscal receipt aggregates.
3. **Bank Statement Parser (`backend/app/modules/documents/parsers/bank_parser.py`)**:
   - Read Uzbek bank client extracts (.xlsx, .csv). Map Debit/Credit columns to account `5110` entries.
4. **Interactive Ingestion Pipeline (`POST /api/v1/documents/parse-preview`)**:
   - Returns extracted rows and column mapping candidates for user confirmation before saving to `transactions`.

---

### PHASE 5: DETERMINISTIC FINANCIAL REPORTING ENGINES
1. **Trial Balance / Oborotka (`backend/app/modules/reports/services.py`)**:
   - Query: Filter by `organization_id`, `start_date`, and `end_date`.
   - Calculate per account:
     - `boshlangich_saldo_debit`, `boshlangich_saldo_kredit` (transactions before `start_date`).
     - `davr_oborot_debit`, `davr_oborot_kredit` (transactions between dates).
     - `oxirgi_saldo_debit`, `oxirgi_saldo_kredit`.
   - Enforce trial balance equality: $\sum \text{Debit} == \sum \text{Credit}$.
2. **Material Stock Report (Moddiy Hisobot)**:
   - Group by `inventory_item_id`.
   - Calculate: Opening quantity/value, Incoming purchases (Kirim), Outgoing usages/sales (Chiqim), Closing balance (Qoldiq).
3. **Reconciliation Act (Akt Sverka)**:
   - Filter by `counterparty_id` and date range.
   - Generate chronological ledger of mutual invoices, payments, and running balance (Debitor / Kreditor).
4. **Excel Export Engine (`backend/app/modules/reports/excel_export.py`)**:
   - Styled `.xlsx` generator with frozen headers, formatted currency cells (`#,##0.00`), bold total summaries, and auto-fitted columns.

---

### PHASE 6: FRONTEND APPLICATION (NEXT.JS 14 + REACT + TAILWIND)
1. **Dashboard & Layout**:
   - Navigation: Dashboard, Hujjat yuklash (Upload), Xira hujjatlar tekshiruvi (OCR Review), Oborotka (OSV), Moddiy hisobot (Stock), Akt sverka.
   - Dual-mode switch: "Soddalashtirilgan rejim" vs "BHMS professional rejim".
2. **Split-Screen Verification Workspace (`components/ocr/VerificationWorkspace.tsx`)**:
   - Left side (50%): Image / PDF preview with interactive pan, zoom, and page switcher.
   - Right side (50%): TanStack Table with inline cell editing:
     - Yellow highlight (`bg-amber-50 text-amber-900 border-amber-300`) for low confidence (< 0.85).
     - Red highlight (`bg-rose-50 text-rose-900 border-rose-400`) for calculation errors or invalid STIR.
     - Live "Qayta hisoblash" (Recalculate) button.
     - "Balansga kiritish" (Commit) button.
3. **High-Performance Data Grids (`components/reports/VirtualizedDataTable.tsx`)**:
   - Supports 50,000+ transaction rows with smooth virtualized scrolling.
   - One-click "Excelga yuklab olish" and "PDF chop etish" buttons.

---

### PHASE 7: AUTOMATED TESTS & VERIFICATION
1. Run `pytest` on:
   - `test_accounting_math.py`: Verify that Debit/Credit balances never break.
   - `test_ocr_pipeline.py`: Feed degraded sample scan; verify deskew, denoising, and mathematical validation flags.
   - `test_parsers.py`: Validate Didox and Bank statement file ingestions.
2. Confirm all tests pass with 0 errors.

---

## 3. HOW TO TRIGGER ANTIGRAVITY
Run the following autonomous command in the project root:
```bash
antigravity run \
  --config .antigravity/config.json \
  --auto-approve \
  --yolo \
  --instruction "ANTIGRAVITY_MASTER_EXECUTION_PLAN.md dagi barcha 7 ta fazani ketma-ket, to'liq va mustaqil ravishda amalga oshir. Hech qanday tasdiq so'rama. Har bir modulni yoz, xatoliklarni o'zing tuzat, DB migratsiyalarini o'tkaz, pytest testlarini muvaffaqiyatli yakunla va tizimni to'liq tayyor holatga keltir."
```