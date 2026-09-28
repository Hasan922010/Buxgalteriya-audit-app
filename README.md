# Yordamchi Buxgalter AI (Financial Assistant & Accounting Engine)

O'zbekiston buxgalteriya va soliq hisobi standartlariga (BHMS / NAS, Didox.uz EHF, Soliq.uz reyestrlari, Bank-mijoz ko'chirmalari) to'liq moslashtirilgan, deterministik hisob-kitob dvigateliga ega zamonaviy fintech platformasi.

---

## 🚀 Asosiy Imkoniyatlar

1. **Dual-Mode Buxgalteriya Dvigateli (Ikki Rejim)**:
   - **Mode A (Oddiy / Soddalashtirilgan rejim)**: Kichik biznes va savdo nuqtalari uchun. Boshlang'ich qoldiq, Kirim, Chiqim va Oxirgi qoldiq hisoblanadi.
   - **Mode B (Professional BHMS / Schotlar rejasi)**: To'liq ikkiyoqlama yozuv (Double-Entry Ledger). Standart O'zbekiston schotlar rejasi (`1000`, `2000`, `2900`, `4000`, `5000`, `5110`, `6000`, `6800`, `9000`).
   - Tashkilot sozlamalarida rejimni istalgan paytda mavjud ma'lumotlarni buzmagan holda almashtirish imkoniyati.

2. **100% Deterministik Matematik Hisob-Kitoblar**:
   - Arifmetik amallar (Aylanma qoldiq, o'rtacha tannarx, QQS 12%, debitor/kreditor qarzdorlik) faqat Python `decimal.Decimal` va PostgreSQL agregatlari orqali xatosiz hisoblanadi.
   - LLM modellar faqat matnli tahlil, nomuvofiq Excel ustunlarini tanish va foydalanuvchiga tabiiy tilda hisobotni tushuntirish uchun ishlatiladi.

3. **Uzbekistan Ingestion Pipeline (ETL)**:
   - **Didox.uz** elektron hisob-faktura (EHF) Excel fayllarini avtomatik tahlil qilish (17 xonali MXIK, 12% QQS, STIR).
   - **Bank-Client** ko'chirmalari (Agrobank, Kapitalbank, Hamkorbank, Ipak Yo'li va 1C TXT formati).
   - **Smart Fallback Mapper**: Tartibsiz yoki nostandart ustun nomlariga ega fayllarni AI orqali aniqlash va 1-bosqichli tasdiqlash oynasi (Modal).

4. **Yuqori Unumdorlikdagi Hisobotlar (Next.js 14 + Virtualized Table)**:
   - **Aylanma Qoldiq Vedomosti (OSV - Oborotka)**
   - **Moddiy Hisobot (Ombor va mahsulotlar harakati - O'rtacha tannarx bo'yicha)**
   - **Akt Sverka (Kontragentlar bilan o'zaro hisob-kitoblar solishtirmasi)**
   - Chiroyli formatlangan **Excel (.xlsx)** va chop etishga tayyor **PDF** eksportlari.

---

## 🛠 Texnologiyalar Steki

- **Backend**: Python 3.13, FastAPI, SQLAlchemy 2.0 Async, PostgreSQL 18, Alembic, Pandas, OpenPyXL, ReportLab.
- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, Lucide Icons, TanStack Table v8, TanStack Virtual.
- **AI Tahlilchi**: Google Gemini API (`gemini-2.5-flash`) / OpenAI API, maxsus O'zbek tili buxgalteriya tahlilchisi.

---

## 📦 O'rnatish va Ishga Tushirish

### 1. Backend ni ishga tushirish

```bash
cd backend

# Virtual muhitni faollashtirish (Windows)
.\.venv\Scripts\activate

# Ma'lumotlar bazasini initsializatsiya qilish va BHMS schotlarini kiritish (Seed)
python -m app.db.seed

# FastAPI serverini ishga tushirish
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend Swagger interaktiv hujjatlari: `http://127.0.0.1:8000/docs`

#### Tizimga kirish (majburiy sozlamalar)

- `.env` da kamida 32 belgili tasodifiy `SECRET_KEY` bo'lishi shart, aks holda backend ishga tushmaydi:
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- Birinchi administrator: `.env` ga `BOOTSTRAP_ADMIN_USERNAME` va `BOOTSTRAP_ADMIN_PASSWORD` yozing (faqat foydalanuvchilar jadvali bo'sh bo'lganda yaratiladi) yoki `python -m app.core.create_user admin --superuser` buyrug'idan foydalaning.
- Boshqa foydalanuvchilar va ularning tashkilotlarga kirish huquqlari administrator tomonidan `/api/v1/auth/users` orqali boshqariladi.
- Xavfli amallar standart holatda o'chiq: `ALLOW_SYSTEM_RESET` (bazani tozalash) va `INTEGRATIONS_DEMO_MODE` (soxta Didox/Soliq hujjatlari).

### 2. Frontend ni ishga tushirish

```bash
cd frontend

# Bog'liqliklarni o'rnatish
npm install

# Dev serverni ishga tushirish
npm run dev
```

Brauzerda ochish: `http://localhost:3000`

---

## 🧪 Avtomatlashtirilgan Sinovlar (Unit & Integration Tests)

Barcha matematik formulalar va parserlarni avtomatik tekshirish uchun:

```bash
cd backend
.\.venv\Scripts\pytest.exe -v
```

Natijalar:
- Balans tengligi: $\text{Bosh_qoldiq} + \text{Kirim} - \text{Chiqim} == \text{Oxirgi_qoldiq}$ (PASSED)
- Didox EHF parseri va QQS 12% hisobi (PASSED)
- Bank to'lov topshirnomalari va provodkalari (PASSED)
- Moddiy hisobot o'rtacha tannarx formulasi (PASSED)
- Akt sverka yakuniy debitor/kreditor qarzdorligi (PASSED)
- Barcha REST API endpointlari va tashkilot rejimlari (PASSED)
