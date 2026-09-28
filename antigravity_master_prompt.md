# MASTER AGENT BLUEPRINT: "YORDAMCHI BUXGALTER AI" (FINANCIAL ASSISTANT)

> **Role & Persona for Antigravity Agent:**
> You are an Elite Full-Stack Fintech Engineer and Senior Financial Systems Architect with specialized domain expertise in Uzbekistan's accounting and taxation systems (BHMS / NAS, Didox EHF, Soliq.uz integrations, banking statements, and 1C export formats).
>
> **Core Mandate:**
> Build a production-grade, modular, and fault-tolerant financial accounting platform that enables deterministic calculations (never rely on LLMs for arithmetic), dual-mode operations (Simple vs. Professional BHMS), multi-format document parsing (Excel, PDF, CSV, XML), and AI-augmented document mapping and analysis.

---

## 1. PROJECT OBJECTIVES & ARCHITECTURAL PRINCIPLES

1. **Dual-Mode Accounting Engine**:
   - **Mode A (Oddiy / Soddalashtirilgan rejim)**: Designed for small businesses, trade points, and individual entrepreneurs. Focuses on:
     - `Boshlang'ich qoldiq` (Opening Balance)
     - `Kirim` (Inflow / Receipts)
     - `Chiqim` (Outflow / Expenses / Dispatches)
     - `Oxirgi qoldiq` (Closing Balance)
     - Inventory / Material movement (`Moddiy hisobot`) and Counterparty settlement (`Akt Sverka`).
   - **Mode B (Professional BHMS / Buxgalteriya schotlari rejasi)**: Full double-entry ledger with standard Uzbekistan Chart of Accounts (e.g., `1000 - Materiallar`, `2900 - Tovarlar`, `4000 - Xaridorlar`, `5110 - Hisob-kitob schoti`, `6000 - Mol yetkazib beruvchilar`, `9000 - Moliyaviy natijalar`).
   - The user can toggle between these modes per organization in settings without breaking existing historical data.

2. **Deterministic Calculation Integrity**:
   - Math operations (Sum, Average, Debit/Credit balances, VAT/QQS calculations) must strictly run via Python (`pandas`, `decimal.Decimal`, SQL aggregation).
   - LLMs are strictly prohibited from generating raw mathematical answers. LLMs are used **only** for:
     - OCR/Text extraction correction and schema normalization.
     - Column header mapping (matching unstructured user Excel columns to standard schema).
     - Natural language queries over pre-calculated SQL aggregates.

3. **Uzbekistan Ingestion Pipeline**:
   - Out-of-the-box support for:
     - **Didox.uz** EHF Excel/JSON exports.
     - **Soliq.uz** Turnover registries and electronic invoice archives.
     - **Bank-Client** ko'chirmalari (Agrobank, Ipak Yo'li, Kapitalbank, Hamkorbank, etc. formatted in Excel/TXT).
     - **1C (v7.7, v8.3)** exported standard Trial Balance (OSV) and Material reports.

---

## 2. REPOSITORY & PROJECT DIRECTORY STRUCTURE

You must create and organize the project according to the following monorepo structure:

```plaintext
yordamchi-buxgalter-ai/
├── docker-compose.yml
├── .env.example
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── migrations/
│   │   └── env.py
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── core/
│       │   ├── config.py
│       │   ├── database.py
│       │   └── security.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── organization.py
│       │   ├── account.py           # Chart of Accounts (BHMS)
│       │   ├── counterparty.py      # Kontragentlar
│       │   ├── inventory.py         # Tovarlar va materiallar
│       │   └── transaction.py       # Asosiy buxgalteriya provodkalari
│       ├── schemas/
│       │   ├── transaction.py
│       │   ├── report.py
│       │   └── document.py
│       ├── services/
│       │   ├── parsers/
│       │   │   ├── base.py
│       │   │   ├── didox_parser.py
│       │   │   ├── soliq_parser.py
│       │   │   ├── bank_parser.py
│       │   │   └── smart_excel_mapper.py  # LLM-assisted column mapper
│       │   ├── accounting_engine.py       # Oborotka, Qoldiq, Moddiy hisobot logic
│       │   ├── export_engine.py           # OpenPyXL and PDF generators
│       │   └── ai_assistant.py            # LangChain / OpenAI / Gemini client
│       └── api/
│           ├── v1/
│           │   ├── api.py
│           │   ├── endpoints/
│           │   │   ├── documents.py
│           │   │   ├── reports.py
│           │   │   ├── accounts.py
│           │   │   ├── counterparties.py
│           │   │   └── ai_chat.py
│
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── tsconfig.json
    ├── tailwind.config.ts
    ├── next.config.mjs
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx
    │   │   ├── page.tsx
    │   │   ├── documents/
    │   │   ├── reports/
    │   │   │   ├── oborotka/
    │   │   │   ├── materials/
    │   │   │   └── akt-sverka/
    │   │   ├── settings/
    │   │   └── chat/
    │   ├── components/
    │   │   ├── ui/                 # Shadcn UI primitives
    │   │   ├── file-uploader.tsx   # Drag & drop parser with auto-detect
    │   │   ├── column-mapper.tsx   # Interactive Excel mapping modal
    │   │   ├── data-table/         # Virtualized TanStack Table
    │   │   ├── mode-toggle.tsx     # Simple vs BHMS switch
    │   │   └── ai-analyst-panel.tsx
    │   ├── hooks/
    │   ├── lib/
    │   │   ├── utils.ts
    │   │   └── api-client.ts
    │   └── types/
    │       └── accounting.d.ts
```

---

## 3. DATABASE SCHEMA SPECIFICATION (PostgreSQL + SQLAlchemy 2.0 Async)

Ensure exact table types and decimal scales to prevent financial truncation errors.

```python
# backend/app/models/account.py
from sqlalchemy import Column, String, Boolean, ForeignKey, Numeric, Date, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum
from app.core.database import Base

class AccountingMode(str, enum.Enum):
    SIMPLE = "SIMPLE"
    BHMS = "BHMS"

class AccountType(str, enum.Enum):
    ASSET = "ASSET"          # Aktiv
    LIABILITY = "LIABILITY"  # Passiv
    EQUITY = "EQUITY"        # Kapital
    REVENUE = "REVENUE"      # Daromad
    EXPENSE = "EXPENSE"      # Xarajat

class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    inn = Column(String(9), unique=True, nullable=False, index=True) # STIR
    mode = Column(Enum(AccountingMode), default=AccountingMode.SIMPLE, nullable=False)
    vat_payer = Column(Boolean, default=False) # QQS to'lovchisi
    created_at = Column(Date)

class ChartOfAccount(Base):
    __tablename__ = "chart_of_accounts"
    
    code = Column(String(10), primary_key=True) # e.g., '1010', '2910', '4010', '5110'
    name = Column(String(255), nullable=False)  # Materiallar, Tovarlar, etc.
    account_type = Column(Enum(AccountType), nullable=False)
    is_active = Column(Boolean, default=True)

class Counterparty(Base):
    __tablename__ = "counterparties"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False, index=True)
    inn = Column(String(9), index=True) # STIR
    mfo = Column(String(5))
    bank_account = Column(String(20))
    is_supplier = Column(Boolean, default=True)
    is_client = Column(Boolean, default=True)

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False, index=True)
    ikpu_code = Column(String(50), index=True) # MXIK kodi (17 ta raqam)
    package_code = Column(String(50))           # Qadoq kodi
    unit = Column(String(50), default="dona")   # O'lchov birligi
    min_stock_alert = Column(Numeric(15, 3), default=0)

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    doc_number = Column(String(100), index=True)
    doc_date = Column(Date, nullable=False, index=True)
    doc_type = Column(String(50), nullable=False) # 'EHF', 'BANK', 'STOCK', 'MANUAL'
    
    # Dual-mode support: Accounts are optional in SIMPLE mode, required in BHMS
    debit_account = Column(String(10), ForeignKey("chart_of_accounts.code"), nullable=True)
    credit_account = Column(String(10), ForeignKey("chart_of_accounts.code"), nullable=True)
    
    counterparty_id = Column(UUID(as_uuid=True), ForeignKey("counterparties.id"), nullable=True)
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=True)
    
    # Financial metrics (always stored with precise decimals)
    quantity = Column(Numeric(15, 3), default=0)
    price = Column(Numeric(18, 2), default=0)
    total_amount = Column(Numeric(18, 2), nullable=False) # Jami summa
    vat_rate = Column(Numeric(5, 2), default=0)           # 0% or 12%
    vat_amount = Column(Numeric(18, 2), default=0)         # QQS summasi
    
    description = Column(Text)
    raw_payload = Column(Text, nullable=True) # Store JSON of original row if ingested
```

---

## 4. DETERMINISTIC FINANCIAL CALCULATIONS (ENGINE LOGIC)

The agent must implement the calculation engine using the exact formulas below.

### 4.1. Trial Balance (Oborotno-Saldo Vedomost - OSV)
For any target date range $[T_{start}, T_{end}]$:

1. **Boshlang'ich qoldiq (Opening Balance at $T_{start}$)**:
   $$\text{Initial\_Debit} = \sum_{t < T_{start}, \text{Acc}=Debit} \text{amount} - \sum_{t < T_{start}, \text{Acc}=Credit} \text{amount}$$
   - If account is an **Asset** (`1000`, `2900`, `5000`, `5110`):
     - Positive result $\implies$ Debit balance.
   - If account is a **Liability** (`6000`, `6800`):
     - Positive result $\implies$ Credit balance.

2. **Davr Oboroti (Turnover during period $[T_{start}, T_{end}]$)**:
   $$\text{Debit\_Turnover (Kirim/Oborot Dt)} = \sum_{t \in [T_{start}, T_{end}], \text{Acc}=Debit} \text{amount}$$
   $$\text{Credit\_Turnover (Chiqim/Oborot Kt)} = \sum_{t \in [T_{start}, T_{end}], \text{Acc}=Credit} \text{amount}$$

3. **Oxirgi qoldiq (Closing Balance at $T_{end}$)**:
   - For Asset accounts:
     $$\text{Final\_Debit} = \text{Initial\_Debit} + \text{Debit\_Turnover} - \text{Credit\_Turnover}$$
   - For Liability accounts:
     $$\text{Final\_Credit} = \text{Initial\_Credit} + \text{Credit\_Turnover} - \text{Debit\_Turnover}$$

### 4.2. Material Stock Movement (Moddiy Hisobot)
For inventory items over $[T_{start}, T_{end}]$:
- **Boshlang'ich qoldiq**: Soni ($Q_0$) va Summasi ($S_0$)
- **Kirim**: Xarid qilingan yoki ishlab chiqarilgan soni ($Q_{in}$) va summasi ($S_{in}$)
- **Chiqim**: Sotilgan yoki hisobdan chiqarilgan soni ($Q_{out}$)
- **O'rtacha tannarx (Weighted Average Cost)**:
  $$\bar{P} = \frac{S_0 + S_{in}}{Q_0 + Q_{in}}$$
- **Chiqim summasi**:
  $$S_{out} = Q_{out} \times \bar{P}$$
- **Oxirgi qoldiq**:
  $$Q_{end} = Q_0 + Q_{in} - Q_{out}$$
  $$S_{end} = S_0 + S_{in} - S_{out}$$

---

## 5. DOCUMENT PARSER & ETL ADAPTERS

Create modular adapters in `backend/app/services/parsers/`:

### 5.1. Didox EHF Ingestion
Target table columns standard in Didox Excel exports:
- `№`, `Hujjat raqami` (Doc Number), `Sana` (Date)
- `Yetkazib beruvchi STIR / Nomi` (Supplier TIN/Name)
- `Xaridor STIR / Nomi` (Buyer TIN/Name)
- `Tovarlar (xizmatlar) nomi` (Item Description)
- `IKPU / MXIK kodi` (17-digit code)
- `O'lchov birligi` (Unit)
- `Miqdori` (Quantity), `Narxi` (Unit Price)
- `Yetkazib berish qiymati` (Cost without VAT)
- `QQS stavkasi` (VAT Rate - 12% or 0%), `QQS summasi` (VAT amount)
- `Jami qiymat` (Total Amount with VAT)

### 5.2. Smart AI Column Auto-Detection (Fallback Parser)
When a user uploads an irregular Excel or PDF file:
1. Extract the first 10 rows and header line using `pandas.read_excel()` or `pdfplumber`.
2. Construct a prompt to the LLM with a strict JSON Schema output:
   ```json
   {
     "date_col": "Sanasi",
     "doc_num_col": "Hujjat #",
     "item_name_col": "Mahsulot",
     "counterparty_col": "Hamkor",
     "inflow_qty_col": "Kirim miqdori",
     "inflow_sum_col": "Kirim summasi",
     "outflow_qty_col": "Chiqim miqdori",
     "outflow_sum_col": "Chiqim summasi",
     "balance_col": "Qoldiq"
   }
   ```
3. Return the mapped schema to the user on the frontend for 1-click confirmation before inserting transactions into the database.

---

## 6. BACKEND API ENDPOINTS

The FastAPI application must expose the following REST endpoints:

- `POST /api/v1/documents/upload`: Accepts `.xlsx`, `.xls`, `.pdf`, `.csv`. Saves file, auto-detects source type (Didox, Bank, Soliq, Generic).
- `POST /api/v1/documents/preview-mapping`: Returns parsed headers and proposed mappings.
- `POST /api/v1/documents/commit`: Saves mapped data as valid transactions in PostgreSQL.
- `GET /api/v1/reports/oborotka`:
  - Query parameters: `organization_id`, `from_date`, `to_date`, `account_filter` (optional).
  - Returns complete Trial Balance structure.
- `GET /api/v1/reports/material-report`:
  - Query parameters: `organization_id`, `from_date`, `to_date`, `item_id` (optional).
  - Returns Opening Stock, Inflow, Outflow, Closing Stock by item and total.
- `GET /api/v1/reports/akt-sverka`:
  - Query parameters: `organization_id`, `counterparty_id`, `from_date`, `to_date`.
  - Returns side-by-side reconciliation statement with final debt status.
- `POST /api/v1/reports/export/{format}`: Accepts report type and filters; streams styled Excel file (`.xlsx` formatted with currency and headers) or PDF.
- `POST /api/v1/ai/chat`: Interactive streaming LLM endpoint aware of the currently viewed report context.

---

## 7. FRONTEND SPECIFICATION (Next.js 14 + Shadcn UI + TanStack Table)

### Key Screens & User Experiences:

1. **Dashboard & Metric Cards**:
   - Monthly Kirim (Total Income/Receipts).
   - Monthly Chiqim (Total Outflows/Expenses).
   - Net Cash / Inventory Value.
   - Quick Mode Switcher (`Soddalashtirilgan rejim` vs `BHMS Schotlar rejasi`).

2. **Universal Ingestion Zone (`/documents`)**:
   - Big Drag-and-Drop dropzone supporting multi-file uploads.
   - Live visual parser: Detects "Didox EHF", "Bank Ko'chirmasi", or "Noma'lum format".
   - If format is unknown, pop up the **Smart Mapper Modal** displaying extracted sample rows and dropdown selectors for each required field.

3. **High-Performance Reporting View (`/reports/oborotka`, `/reports/materials`)**:
   - Built using `@tanstack/react-table` with row virtualization to seamlessly handle 20,000+ transaction rows without browser lag.
   - Multi-criteria filter bar: Date Range Picker (Davr oralig'i), Kontragent qidirish, Mahsulot qidirish.
   - Floating summary bar at the bottom: Jami Boshlang'ich Qoldiq, Jami Kirim, Jami Chiqim, Jami Oxirgi Qoldiq.
   - Export buttons: "Excel ga yuklab olish" (green), "PDF chop etish" (slate).

4. **Context-Aware AI Assistant Drawer**:
   - Right-side slide-over panel.
   - Passes the current active report view summary to the assistant.
   - Pre-built quick action buttons:
     - *"Eng ko'p xarid qilingan 5 ta tovar"*
     - *"Qaysi kontragentdan qarzimiz ko'p?"*
     - *"Ushbu oydagi QQS majburiyatini hisobla"*

---

## 8. STEP-BY-STEP AUTONOMOUS BUILD SEQUENCE

When executing this project, execute the following steps in exact order:

### Step 1: Environment & Project Scaffolding
- Initialize the directory tree as specified in Section 2.
- Configure `docker-compose.yml` with:
  - `postgres:16-alpine` (Exposed on `5432`)
  - `redis:7-alpine` (Exposed on `6379`)
  - `backend` (FastAPI running on `8000`)
  - `frontend` (Next.js running on `3000`)

### Step 2: Backend Core & Database Setup
- Install dependencies: `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic`, `pandas`, `openpyxl`, `pdfplumber`, `weasyprint`, `langchain`, `openai`.
- Implement models in `app/models/`.
- Generate and run Alembic migrations.
- Create a seeder script (`app/db/seed.py`) that populates the standard Uzbekistan BHMS Chart of Accounts:
  - `1000` (Materiallar)
  - `2000` (Asosiy ishlab chiqarish)
  - `2900` (Tovarlar)
  - `4000` (Xaridorlar va buyurtmachilar)
  - `5000` (Kassa)
  - `5110` (Hisob-kitob schoti)
  - `6000` (Mol yetkazib beruvchilar)
  - `6800` (Soliqlar bo'yicha qarzlar)
  - `9000` (Asosiy faoliyat daromadlari)

### Step 3: Implement Parsers & Calculation Engine
- Implement `didox_parser.py` parsing raw Excel EHF files into standard transaction objects.
- Implement `bank_parser.py` for standard payment orders.
- Implement `accounting_engine.py` with pure Pandas/SQL formulas for:
  - `calculate_oborotka(org_id, start_date, end_date)`
  - `calculate_material_report(org_id, start_date, end_date)`
  - `calculate_akt_sverka(org_id, counterparty_id, start_date, end_date)`

### Step 4: Frontend Development
- Initialize Next.js 14 app with TypeScript, Tailwind, Lucide Icons, and Shadcn UI.
- Implement the responsive navigation layout with sidebar.
- Implement the interactive file uploader with drag & drop preview.
- Implement TanStack Table with sticky headers and footer aggregates.
- Connect API calls via typed client in `src/lib/api-client.ts`.

### Step 5: Verification & End-to-End Testing
- Write sample test files:
  - A mock Didox Excel file (`sample_didox.xlsx`).
  - A mock 1C Oborotka file (`sample_oborotka.xlsx`).
- Execute integration tests verifying that `Initial_Balance + Inflow - Outflow == Final_Balance` across all generated reports.