# Audit hisoboti — Yordamchi Buxgalter AI

**Sana:** 2026-09-28
**Qamrov:** backend (FastAPI), frontend (Next.js 14), parserlar/OCR, integratsiyalar, testlar, CI, Docker
**Usul:** kodni o'qish + jonli tekshiruvlar (`TestClient`, parserlarga to'g'ridan-to'g'ri kirish, `pytest`, `tsc`, `npm audit`)

> Belgilar: ✅ jonli tekshiruv bilan tasdiqlangan · 📖 kod o'qish orqali aniqlangan

## Xulosa

| Daraja | Soni | Asosiy mavzu |
|---|---|---|
| CRITICAL | 6 | Autentifikatsiya yo'qligi, ma'lumotlar buzilishi (sonlar, soxta fakturalar), path traversal |
| HIGH | 9 | Moddiy hisobot formulasi, sanalar, takroriy import, IDOR, Next.js zaifliklari |
| MEDIUM | 10 | O'lik kod/takrorlanish, migratsiyalar, storno semantikasi, Docker |
| LOW | 6 | Uslub, ogohlantirishlar |

**Asosiy xulosa:** loyihani hozirgi holatida real mijoz ma'lumotlari bilan ishlatib bo'lmaydi. Bunga ikki sabab bor:
1. Tizimga kirish nazorati yo'q: istalgan odam istalgan rol bilan ishlay oladi, butun bazani o'chira oladi va serverdagi fayllarni o'qiy oladi.
2. Hisob-kitob natijalari buzilishi mumkin: sonlar 100 baravar oshib yoki 0 bo'lib o'qilishi, soxta Didox fakturalari va noto'g'ri boshlang'ich qoldiq tufayli.

46 ta test o'tadi, lekin topilgan xatolarning birortasini ham ushlamaydi.

---

## CRITICAL

### C1. Autentifikatsiya yo'q — rolni klientning o'zi tanlaydi ✅
- `backend/app/core/rbac.py:21-28`: rol `X-User-Role` header'idan olinadi. Header bo'lmasa, avtomatik **`CHIEF_ACCOUNTANT`** beriladi.
- `frontend/src/lib/api-client.ts:29`: rol `localStorage`dan olinadi, foydalanuvchi uni o'zi o'zgartira oladi.
- `backend/app/core/security.py` (JWT, bcrypt) yozilgan, lekin hech qayerda ishlatilmaydi.
- 43 ta endpoint'dan faqat 14 tasida `require_roles` bor. Qolganlarining (organizations yaratish, OCR commit, AI chat, reports, tasks, system) hech qanday himoyasi yo'q.
- Tekshiruv: `GET /backup/list` so'roviga `X-User-Role: CHIEF_ACCOUNTANT` qo'shildi → `200`, 26 ta zaxira ro'yxati qaytdi.

**Tuzatish:** Foydalanuvchilar jadvali va JWT login qo'shish (mavjud `security.py` asosida). Rol va tashkilot token ichidan olinishi kerak. Header'ni butunlay olib tashlash.

### C2. `/system/factory-reset` va `reset-data` himoyasiz ✅
- `backend/app/api/v1/endpoints/system.py:17-50`: butun bazani o'chirish uchun faqat `{"confirmation":"RESET"}` yuborish yetarli. Rol tekshiruvi yo'q.
- Tekshiruv: noto'g'ri so'z bilan yuborilgan so'rov 400 qaytardi (403 emas). Demak, to'g'ri so'z bilan yuborilsa, baza o'chib ketadi. Bu so'rov ataylab yuborilmadi.

**Tuzatish:** Autentifikatsiya va faqat admin roli. Prod muhitida bu endpoint umuman o'chirilgan bo'lishi kerak. Oldin avtomatik backup olish.

### C3. Path traversal — serverdagi istalgan xlsx/csv/pdf faylni o'qish mumkin ✅
- `backend/app/api/v1/endpoints/documents.py:124,148,511`: `os.path.join(UPLOAD_DIR, file_id)` qatorida `file_id` foydalanuvchidan keladi va tekshirilmaydi.
- Tekshiruv: `POST /documents/preview-mapping` ga `file_id=../../tests/sample_data/sample_bank.xlsx` yuborildi → `200`, fayl ustunlari va birinchi 5 qatori qaytdi. Shu yo'l bilan boshqa tashkilotlarning `uploads/` fayllarini yoki diskdagi har qanday Excel faylni o'qish mumkin.
- `backend/app/services/backup_engine.py:217` (`verify_backup`) da ham `basename` qo'llanmagan.

**Tuzatish:** `file_id` ni UUID formatiga tekshirish. Fayllarni DB orqali `(file_id → path, organization_id)` shaklida saqlash. Qo'shimcha `realpath(...).startswith(UPLOAD_DIR)` tekshiruvi.

### C4. Sonlarni o'qishda ma'lumot buziladi ✅
Ikkala Didox parser'ning `_get_decimal` funksiyasi sinovdan o'tkazildi:

| Kirish | `modules/documents/parsers` | `services/parsers` |
|---|---|---|
| `1 234 567,89` | **123456789** ❌ (100×) | 1234567.89 |
| `1,234,567.89` | 1234567.89 | **0** ❌ |
| `1.234.567,89` | **0** ❌ | **0** ❌ |

Excel'dagi raqamli yacheykalar to'g'ri o'qiladi. Xato matn ko'rinishidagi summalarda chiqadi (CSV, Didox/1C eksportlari). Summa 0 bo'lib qolsa, `total <= 0: continue` sharti bu qatorni **ogohlantirishsiz tashlab yuboradi**.

**Tuzatish:** Bitta umumiy `parse_amount()` funksiyasi yozib, uzb/rus/en formatlari bo'yicha testlar qo'shish. O'qib bo'lmaydigan qiymat 0 emas, xato sifatida qaytishi kerak.

### C5. "Didox/Soliq sinxronlash" buxgalteriyaga soxta fakturalarni yozadi ✅📖
- `backend/app/services/integrations/didox_adapter.py:57+`: `mock_invoices` ro'yxati tasodifiy `DIDOX-2026-XXXXXX` raqamlari bilan yaratiladi va `Transaction` sifatida **haqiqiy tashkilot balansiga** yoziladi. `soliq_adapter.py` ham xuddi shunday ishlaydi.
- `test_connection` token bor-yo'qligidan qat'i nazar har doim "muvaffaqiyatli ulandi" deb javob beradi.
- UI'dagi tugma `/integrations/didox/sync` ni chaqiradi. Har bir bosishda kitobga yangi soxta yozuvlar qo'shiladi.

**Tuzatish:** Haqiqiy API ulanmaguncha endpoint'ni o'chirib qo'yish yoki faqat `ENVIRONMENT=demo` rejimida ishlashiga ruxsat berish. UI'da "Demo" belgisini ko'rsatish.

### C6. Secret'lar, real ma'lumotlar va git gigiyenasi 📖
- `.gitignore` yo'q. Git repo ildizi — `C:\Users\ASUS` (butun home papka), birorta ham commit yo'q.
- Birinchi `git add .` qilinsa, `.env` (haqiqiy `SECRET_KEY`), `.venv`, `node_modules`, `.next`, `backend/app/uploads/` (40+ real buxgalteriya fayli: kassa, "шароб база" va boshqalar), `backend/backups/*.json` (24 ta to'liq DB dump) repoga tushib ketadi.
- `backend/app/core/config.py:15-30`: standart qiymatlar kodda yozilgan: `POSTGRES_PASSWORD="12345"`, `SECRET_KEY="super-secret-key-..."`, `DEBUG=True`.
- `core/database.py:9`: `echo=settings.DEBUG` sozlamasi DEBUG rejimida barcha SQL so'rovlarni va ulardagi moliyaviy qiymatlarni logga yozadi.

**Tuzatish:** Loyiha uchun alohida `git init` va `.gitignore` (`.env`, `.venv`, `node_modules`, `.next`, `uploads/`, `backups/`, `*.png` skrinshotlar). Secret'lar uchun standart qiymat bo'lmasligi va ular yo'q bo'lsa ilova ishga tushmasligi kerak. `DEBUG=False` standart bo'lsin. `uploads` va `backups` papkalarini loyihadan tashqariga ko'chirish.

---

## HIGH

### H1. Moddiy hisobot: boshlang'ich qoldiqda chiqim kirimga qo'shilib ketadi 📖
`backend/app/services/accounting_engine.py:255`:
```python
if t.doc_type == "INITIAL_STOCK" or t.debit_account in [...] or t.doc_type == "EHF" or amt > 0:
    init_q += qty   # kirim
```
`amt > 0` sharti deyarli har bir chiqim uchun ham bajariladi, chunki chiqim summasi ham musbat. Natijada `from_date` dan oldingi sotuvlar ombor qoldig'ini **oshiradi**. Bundan tashqari, chiqimlar tannarx bilan emas, sotuv summasi bilan hisoblanadi. Manfiy qoldiq ogohlantirishsiz 0 ga tenglashtiriladi (`:259-262`, `:294-297`), shuning uchun xato ko'rinmay qoladi.

**Tuzatish:** Kirim yoki chiqim ekanini faqat schot yo'nalishiga qarab aniqlash. Oldingi davrni ham o'rtacha tannarx bilan qayta hisoblash. Manfiy qoldiqni 0 ga tushirmasdan "ogohlantirish" sifatida qaytarish. Sotuvdan oldin kirim bo'lgan va bo'lmagan holatlar uchun regression testlar yozish.

### H2. Sanalarni o'qish: `03.04.2025` 4-mart deb o'qiladi ✅
`pd.to_datetime('03.04.2025')` → `2025-03-04`. Bu xato quyidagi joylarda bor:
- `modules/documents/parsers/didox_parser.py:179`, `bank_parser.py:112`, `soliq_parser.py:90`
- `services/parsers/soliq_parser.py:59`

Kun 12 dan katta bo'lsa, sana to'g'ri o'qiladi. Shuning uchun xato faqat ba'zi qatorlarda chiqadi, bu esa uni topishni ayniqsa qiyinlashtiradi. Sanani o'qib bo'lmasa, `None` yoki `date.today()` qo'yiladi, ya'ni yozuv ogohlantirishsiz boshqa davrga tushib qoladi.

**Tuzatish:** `dayfirst=True` yoki aniq formatlar (`%d.%m.%Y`, `%Y-%m-%d`). Sanani o'qib bo'lmasa, qator xato sifatida qaytarilishi kerak.

### H3. Takroriy importdan himoya yo'q 📖
Bitta fayl yoki bitta faktura ikki marta commit qilinsa, barcha yozuvlar ikki baravar ko'payadi: faylning hash'i ham, `(organization_id, doc_number, doc_type)` bo'yicha tekshiruv ham, unique cheklov ham yo'q (`models/*`).

**Tuzatish:** Fayl SHA256 qiymatini `document_ingestion_logs` jadvaliga yozish, hujjat raqami bo'yicha dublikatni aniqlash va UI'da ogohlantirish ko'rsatish.

### H4. Multi-tenancy / IDOR 📖
Barcha endpoint'larda `organization_id` so'rovning query yoki body qismidan olinadi va foydalanuvchiga tegishli ekani tekshirilmaydi (`reports.py`, `counterparties.py`, `organizations.py`, `ocr/router.py`). `GET /tasks` endpoint'i barcha tashkilotlarning fon vazifalarini qaytaradi (`tasks.py:20`).
**Tuzatish:** C1 bilan birga hal qilinadi: tashkilot token'dan olinadi va har bir so'rovda filtrlanadi.

### H5. Fayl yuklashda cheklovlar yo'q 📖
- `/documents/upload` faylni to'liq diskka yozadi (`shutil.copyfileobj`). OCR endpoint'lari esa faylni to'liq xotiraga o'qiydi. Hajm chegarasi yo'q.
- Kengaytma faqat nom bo'yicha tekshiriladi, MIME yoki magic bytes tekshirilmaydi.
- `uploads/` hech qachon tozalanmaydi.

**Tuzatish:** Hajm limiti (masalan, 20 MB), kontentni tekshirish, TTL bo'yicha tozalash, upload endpoint'lari uchun rate limiting.

### H6. Excel eksportda formula injection 📖
Kontragent yoki mahsulot nomlari (ular foydalanuvchi yuklagan fayllardan keladi) `ws.append(...)` orqali tozalanmasdan yoziladi (`modules/reports/excel_export.py`, `services/export_engine.py`, `modules/ocr/*exporter*`). `=`, `+`, `-`, `@` bilan boshlanadigan nom Excel'da formula sifatida ishga tushadi.
**Tuzatish:** Matn qiymatlari oldiga `'` qo'shish yoki `cell.data_type='s'` belgilash.

### H7. Frontend: 3 ta sahifa mavjud bo'lmagan endpoint'larni chaqiradi ✅
- `app/osv/page.tsx`, `app/materials/page.tsx`, `app/akt-sverka/page.tsx` quyidagi manzillarni chaqiradi: `/reports/materials`, `/reports/*/export/excel|pdf`.
- Bu endpoint'lar `modules/reports/router.py` da yozilgan, lekin router **ulanmagan** (`api.py` da yo'q). Shuning uchun 404 qaytadi. OpenAPI'da ular yo'qligi tasdiqlandi.
- ~~Bu sahifalarga faqat ishlatilmayotgan `components/layout/Sidebar.tsx` dan havola bor.~~ **Tuzatish (2026-09-28):** bu xulosa noto'g'ri edi. `components/sidebar.tsx` aslida `layout/Sidebar.tsx` ni qayta eksport qiladi, ya'ni **asosiy menyu** aynan shu buzilgan sahifalarga olib borardi. Oborotka, Moddiy hisobot va Akt sverka menyudan ochilganda ishlamasdi. Sahifalardagi 12 joyda URL `http://localhost:8000` qattiq yozilgan edi.

**Tuzatish:** Takroriy sahifalarni o'chirish (`/reports/*` qoldiriladi) yoki router'ni ulash. Barcha so'rovlar `api-client.ts` orqali o'tsin.

### H8. Next.js 14.2.35 — kritik zaifliklar ✅
`npm audit` natijasi: 1 critical (next, 20+ advisory: SSRF, cache poisoning, DoS, XSS) va 1 high (postcss).
**Tuzatish:** Next.js'ni tuzatilgan versiyaga yangilash (15.x yoki 16.x; migratsiya talab qiladi, chunki bu breaking change).

### H9. Davr qulfi va ma'lumot yaxlitligi zaif 📖
- Didox/Soliq sinxronlashda qulf faqat `from_date` bo'yicha tekshiriladi, yozuvlarning o'z sanalari bo'yicha emas (`didox_adapter.py:52`).
- `Transaction.created_at` turi `Date`, timestamp emas. Audit izi (kim va qachon kiritgan) aniq emas.

---

## MEDIUM

| # | Topilma | Joyi |
|---|---|---|
| M1 | **Ikki xil arxitektura:** `api/v1/endpoints` va `modules/*`. `modules/accounting/router.py` (13 endpoint) va `modules/reports/router.py` (9 endpoint) ulanmagan, ya'ni o'lik kod | `backend/app/api/v1/api.py` |
| M2 | Parserlar ikki joyda (`services/parsers` va `modules/documents/parsers`) va ular **turlicha natija beradi** (C4 ga qarang) | backend |
| M3 | `app/tests/` papkasi `tests/` ning aynan nusxasi va ishga tushmaydi (5 ta collection error) | `backend/app/tests` |
| M4 | Sxema Alembic orqali emas, startup'da `create_all` va `ALTER TABLE ... IF NOT EXISTS` orqali boshqariladi. Migratsiya bitta (`001`), unda `audit_logs` va `document_ingestion_logs` jadvallari yo'q | `backend/app/db/seed.py:51-58` |
| M5 | Startup xatosi yutib yuboriladi: DB ishlamasa ham ilova "sog'lom" holatda ko'tariladi | `backend/app/main.py:17-21` |
| M6 | Storno asl yozuvni ham, qaytarish yozuvini ham `is_reversed=True` qilib belgilaydi, hisobotlar esa ikkalasini ham chiqarib tashlaydi. Bu klassik "qizil storno" emas, balki o'tgan davrni o'chirib yuborish. Natijada storno qilingandan keyin ochiq o'tgan davrlarning hisobotlari o'zgaradi | `backend/app/services/accounting_engine.py:628-651` |
| M7 | `docker-compose` ishlamaydi: backend `.env` dagi `localhost:5433` ga ulanmoqchi bo'ladi, lekin konteyner ichida DB `postgres:5432` da. Frontend Dockerfile `npm run dev` bilan ishga tushadi. Konteynerlar root foydalanuvchi ostida ishlaydi | `docker-compose.yml`, `frontend/Dockerfile` |
| M8 | CI: `pip install -r requirements.txt \|\| pip install ...` qatori o'rnatish xatosini yashiradi. Python 3.12 ishlatiladi, lokal va Docker'da esa 3.13 | `.github/workflows/ci.yml` |
| M9 | Juda katta fayllar: `VerificationWorkspace.tsx` (1386 qator), `settings/page.tsx` (1013 qator), `documents.py` (606 qator, `execute_document_import` funksiyasi 300 qatordan uzun) | frontend va backend |
| M10 | Xatolarni yutish: 55 ta `except Exception`, 16 joyda `except: pass/continue`. Masalan, `documents.py:101` da format aniqlanmasa `UNKNOWN` qaytadi, sababi esa hech qayerga yozilmaydi | backend |

## LOW

- Uzbekistonda QQS 2019-10-01 gacha 20% bo'lgan. `TaxEngine` bu sanadan oldingi yozuvlar uchun 12% qaytaradi (`backend/app/services/tax_engine.py:55`).
- OCR va tax-audit ekstraktorlarida QQS 12% qattiq yozilgan (`TaxEngine` ishlatilmaydi): `pdf_table_extractor.py:175,202`, `tax_audit_extractor.py:47`, `didox_adapter.py:79,93`.
- Eksportda `float(...)` ishlatilgan (`export_engine.py`). Hozircha amaliy xatoga olib kelmaydi, lekin `Decimal`dan to'g'ridan-to'g'ri yozish to'g'riroq.
- `python-jose` va `passlib` kutubxonalari ishlatilmaydi va faol qo'llab-quvvatlanmaydi.
- `datetime.utcnow()` eskirgan; frontend'da 11 ta `console.*` qolgan; ESLint konfiguratsiyasi yo'q.
- Ildiz papkada 10 ta PNG skrinshot, 3 ta katta prompt yoki reja `.md` fayli va `scratch/` papkasi bor.

---

## Testlar va sifat holati

| Tekshiruv | Natija |
|---|---|
| `pytest tests` | ✅ 46 passed (SQLite in-memory) |
| `pytest app/tests` | ❌ 5 collection error (takroriy nusxa) |
| Coverage | o'lchanmadi, chunki `pytest-cov` o'rnatilmagan |
| `tsc --noEmit` | ✅ 0 xato |
| `next build` | ishga tushirilmadi, chunki dev `.next` papkasini ustidan yozib yuborardi. CI'da tekshiriladi |
| `npm audit` | ❌ 1 critical, 1 high |
| `pip-audit` | o'rnatilmagan, tekshirilmadi |

Mavjud testlar C4, H1, H2, H3, C3 xatolarining birortasini ham ushlamaydi.

---

## Tuzatish holati

### 1-bosqich (2026-09-28)

| Topilma | Holat | Nima qilindi |
|---|---|---|
| Testlar dev bazani tozalardi | ✅ | `tests/conftest.py` app import qilinishidan oldin vaqtinchalik SQLite baza hamda `UPLOAD_DIR` va `BACKUP_DIR` papkalarini belgilaydi. Test Postgres'ga ulanmoqchi bo'lsa, `pytest.exit` bilan darhol to'xtaydi |
| C6 git gigiyenasi | ✅ qisman | Loyiha uchun alohida `git init` qilindi va `.gitignore` qo'shildi (`.env`, `uploads/`, `backups/`, `.venv`, `node_modules`, `.next`). Commit qilinmadi. `SECRET_KEY` va boshqa standart qiymatlar hali kodda turibdi (2-bosqich) |
| C3 path traversal | ✅ | Yangi `app/core/storage.py`: `resolve_upload_path` va `resolve_backup_path` fayl nomlarini tekshiradi, upload fayl nomi `build_upload_filename` orqali tozalanadi. Traversal urinishi 400 qaytaradi |
| C2 reset endpoint'lari | ✅ | `ALLOW_SYSTEM_RESET` sozlamasi (standart holatda `False`), rol tekshiruvi, tozalashdan oldin avtomatik backup (`pre_reset_backup`). Rol hali header'dan olinadi (C1 bilan birga to'liq hal bo'ladi) |
| C5 soxta Didox/Soliq | ✅ | `INTEGRATIONS_DEMO_MODE` sozlamasi (standart holatda `False`): sinxronlash 503 qaytaradi va hech narsa yozmaydi. Status endpoint'i `NOT_CONFIGURED` ko'rsatadi |
| C4 summalar | ✅ | Yangi `app/services/parsers/normalize.py:parse_amount`. 7 ta parser va `documents.py` shu funksiyaga o'tkazildi |
| H2 sanalar | ✅ | `parse_date` doim kun birinchi o'qiydi va Excel serial sanalarini ham tushunadi |
| Summa/sana o'qilmasa jimgina 0 yoki bugungi sana qo'yiladi | ⏳ | O'qish to'g'rilandi, lekin fallback xatti-harakati o'zgartirilmadi. Qatorga xato belgilash 3-bosqichda |

**Code review natijalari (1-bosqichdan keyin):**

| Review topilmasi | Holat |
|---|---|
| CRITICAL: demo tekshiruvi faqat endpoint'da edi, adapterni to'g'ridan-to'g'ri chaqirsa soxta yozuvlar baribir yozilardi | ✅ `ensure_demo_mode()` endi `DidoxAdapter` va `SoliqAdapter` ning `sync_documents` metodi ichida |
| CRITICAL: `documents.py` dagi qaytarish summasi va soni hali eski usulda o'qilardi (`"12 500,50"` → 1 250 050) | ✅ `parse_amount` ga o'tkazildi va end-to-end test qo'shildi. Shu turdagi xato OCR ekstraktorlarida (`clean_decimal`) ham topilib, tuzatildi |
| HIGH: factory reset yarim yo'lda yiqilsa, ma'lumot qisman o'chib qoladi va xabar bo'lmaydi | ✅ qisman: endi 500 javobida qaysi backup fayldan tiklash kerakligi aytiladi. ⏳ Tozalashni atomar qilish va **backup'dan tiklash (restore) endpoint'i hali yo'q** (3-bosqich) |
| MEDIUM: `BackupEngine` papkani import paytida qotirib qo'yardi | ✅ endi `settings.BACKUP_DIR` har chaqiruvda o'qiladi |
| MEDIUM: `/documents/commit-parsed` davr qulfini tekshirmaydi | ⏳ 3-bosqich (H9 bilan birga) |
| LOW: `app/tests` takroriy nusxa | ⏳ 4-bosqich (M3) |

Testlar soni: 46 → 161 (hammasi o'tadi).

### 2-bosqich (2026-09-28): autentifikatsiya va tenancy

| Topilma | Holat | Nima qilindi |
|---|---|---|
| C1 autentifikatsiya yo'q | ✅ | `users` va `user_organizations` jadvallari, bcrypt parol, JWT (`/auth/login`, `/auth/me`, `/auth/change-password`, superuser uchun `/auth/users`). `/auth/login` dan tashqari barcha endpoint'lar token talab qiladi. Rol faqat token egasining DB yozuvidan olinadi, `X-User-Role` header'i butunlay olib tashlandi. Login'da brute-force himoyasi bor (5 xato urinish / 5 daqiqa → 429) |
| H4 IDOR / tenancy | ✅ | Barcha `organization_id` (path, query, body) tekshiriladi. Begona tashkilot uchun 404 qaytadi. Tashkilotlar ro'yxati, backup'lar va fon vazifalari egasi bo'yicha filtrlanadi. Factory reset faqat superuser uchun |
| C6 `SECRET_KEY` | ✅ | Kodda standart qiymat yo'q, kamida 32 belgi talab qilinadi, aks holda ilova ishga tushmaydi. `.env` dagi **ochiq standart kalit** yangi tasodifiy kalitga almashtirildi |
| DEBUG'da SQL echo parol hash'larini logga yozardi | ✅ | Alohida `SQL_ECHO` sozlamasi, standart holatda `False` |
| H7 menyudagi 3 ta hisobot sahifasi ishlamasdi | ✅ | Menyu `/reports/*` sahifalariga yo'naltirildi, buzilgan `/osv`, `/materials`, `/akt-sverka` o'chirildi |
| Frontend | ✅ | Login sahifasi, `AuthGate`, 401 kelsa avtomatik chiqish, eksport va backup token bilan yuklanadi (`AuthDownloadLink`), rol tanlash menyusi o'rniga foydalanuvchi menyusi |

**Security review natijalari:** CRITICAL topilma yo'q.
- ✅ HIGH: Akt sverka o'z tashkilotining ID'si bilan boshqa tashkilot kontragentining nomi va STIR'ini ko'rsatib qo'yardi. Kontragent endi tashkilot bo'yicha filtrlanadi, regression test qo'shildi.
- ✅ MEDIUM: superuser huquqini API orqali olib tashlab bo'lmasdi. Endi `PATCH /auth/users/{id}` bilan mumkin (o'zini-o'zi pasaytirish taqiqlangan).
- ⏳ MEDIUM: bir nechta worker bir vaqtda ishga tushganda boshlang'ich admin yaratishda poyga holati (race) bo'lishi mumkin. Hozir bitta worker ishlatilgani uchun amaliy xavf past.

Tekshiruv: 193 backend test o'tdi. Ular orasida barcha endpoint'lar tokensiz 401 qaytarishini tekshiradigan test va mutatsiya bilan tekshirilgan tenancy testlari bor. `tsc` xatosiz. Brauzerda sinaldi: tokensiz → `/login`, noto'g'ri parol → xato xabari, login → dashboard, OSV, Excel eksport, chiqish.

## Tuzatish yo'l xaritasi

**1-bosqich — Bloklovchi xatolar (1–2 kun)**
1. Alohida git repo va `.gitignore`. `uploads/` va `backups/` papkalarini repodan tashqariga chiqarish (C6).
2. `file_id` validatsiyasi, backup `basename` (C3).
3. `factory-reset` va `reset-data` ni o'chirish yoki faqat admin roliga ochish (C2).
4. Didox/Soliq mock sinxronlashni o'chirish (C5).
5. Bitta `parse_amount` va `parse_date` funksiyasi hamda ularning testlari (C4, H2).

**2-bosqich — Autentifikatsiya va tenancy (3–4 kun)**
6. User modeli, JWT login, rol va tashkilotni token'dan olish; frontend login sahifasi (C1, H4).
7. Upload limitlari va rate limiting (H5).

**3-bosqich — Hisob-kitob to'g'riligi (2–3 kun)**
8. Moddiy hisobot formulasini qayta yozish va regression testlar (H1).
9. Dublikat importdan himoya (H3); storno semantikasi (M6); davr qulfi (H9).
10. Excel formula injection (H6).

**4-bosqich — Tozalash va infratuzilma (2–3 kun)**
11. Bitta arxitekturani tanlash, o'lik router, parserlar va `app/tests` ni o'chirish (M1–M3).
12. Alembic migratsiyalari (M4), startup xatolari (M5).
13. Next.js'ni yangilash (H8), takroriy sahifalarni o'chirish (H7), katta komponentlarni bo'lish (M9).
14. Docker va CI tuzatishlari (M7, M8), coverage o'lchovi.
