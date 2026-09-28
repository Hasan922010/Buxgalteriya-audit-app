import json
import logging
from typing import Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger("ai_assistant")

class AIAssistantService:
    """
    Context-aware financial assistant that analyzes pre-calculated accounting figures.
    Never calculates raw numbers itself; operates strictly on provided report aggregates.
    """

    @classmethod
    async def answer_query(cls, query: str, context_data: Dict[str, Any]) -> str:
        # 1. Attempt Gemini if configured
        if settings.GEMINI_API_KEY:
            try:
                return await cls._ask_gemini(query, context_data)
            except Exception as e:
                logger.warning(f"Gemini AI Assistant failed: {e}")

        # 2. Attempt OpenAI if configured
        if settings.OPENAI_API_KEY:
            try:
                return await cls._ask_openai(query, context_data)
            except Exception as e:
                logger.warning(f"OpenAI Assistant failed: {e}")

        # 3. Fallback: Local rule-based Uzbek analyst
        return cls._local_analyst(query, context_data)

    @classmethod
    async def _ask_gemini(cls, query: str, context_data: Dict[str, Any]) -> str:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        prompt = f"""Siz O'zbekiston hisob-kitob va soliq qonunchiligi (BHMS / Soliq kodeksi) bo'yicha professional bosh buxgalter va moliyaviy maslahatchisiz.
Quyida foydalanuvchi ko'rib turgan buxgalteriya hisoboti ma'lumotlari keltirilgan:

{json.dumps(context_data, ensure_ascii=False, indent=2)}

Foydalanuvchi savoli: "{query}"

QOIDALAR:
1. Faqat berilgan aniq raqamlarga asoslaning, yangi raqam to'qimang.
2. Javobni sof o'zbek tilida, professional va lo'nda bayon qiling.
3. Raqamlarni chiroyli formatda (masalan: 15,200,000.00 so'm) ko'rsating.
4. Agar soliq (QQS 12%, Foyda solig'i) yoki schotlar bo'yicha maslahat so'ralsa, O'zbekiston BHMS schotlari (1000, 2900, 4000, 5110, 6000, 6800) asosida tushuntiring."""

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text.strip()

    @classmethod
    async def _ask_openai(cls, query: str, context_data: Dict[str, Any]) -> str:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        prompt = f"""Siz O'zbekiston BHMS buxgalteriya tizimi bo'yicha maslahatchisiz.
Hisobot konteksti:
{json.dumps(context_data, ensure_ascii=False, indent=2)}

Foydalanuvchi savoli: "{query}"
Javobni o'zbek tilida, aniq va ixcham shaklda bering."""

        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Siz O'zbekiston buxgalteriya AI assistentisiz."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        return resp.choices[0].message.content.strip()

    @classmethod
    def _local_analyst(cls, query: str, context_data: Dict[str, Any]) -> str:
        """Intelligent local heuristic summarizer in Uzbek."""
        q = query.lower()
        if "qqs" in q or "soliq" in q:
            inflow = context_data.get("monthly_inflow", "0")
            vat_val = float(str(inflow).replace(",", "")) * 0.12 if inflow else 0
            return f"Joriy oylik tushum ({inflow} so'm) bo'yicha hisoblangan taxminiy 12% QQS majburiyati: {vat_val:,.2f} so'mni tashkil etadi. (O'zbekiston Respublikasi Soliq Kodeksiga asosan)."
        elif "qarz" in q or "kontragent" in q:
            payables = context_data.get("total_payables", context_data.get("final_debt", "0"))
            return f"Hisobot bo'yicha joriy qarz majburiyatlari: {payables} so'm. O'z vaqtida to'lovlarni amalga oshirish tavsiya etiladi."
        elif "tovar" in q or "mahsulot" in q:
            inv = context_data.get("inventory_valuation", "0")
            return f"Ombordagi mavjud tovar va moddiy boyliklarning jami baholangan qiymati: {inv} so'mni tashkil etadi."
        else:
            return f"Hisobot tahlili: Joriy oylik kirim {context_data.get('monthly_inflow', '0')} so'm, chiqim {context_data.get('monthly_outflow', '0')} so'm, sof kassa/bank qoldig'i: {context_data.get('net_cash_balance', '0')} so'm."
