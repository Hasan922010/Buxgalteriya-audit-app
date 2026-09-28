import io
from decimal import Decimal
from typing import Any, List
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.schemas.report import TrialBalanceReport, MaterialReport, AktSverkaReport

class PDFExportEngine:
    """
    Generates styled PDF exports for financial reports using ReportLab.
    """

    @classmethod
    def export_generic_pdf(cls, title: str, subtitle: str, headers: List[str], rows: List[List[Any]]) -> io.BytesIO:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=20,
            leftMargin=20,
            topMargin=20,
            bottomMargin=20
        )
        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            name="ReportTitle",
            parent=styles["Heading1"],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#1E3A8A")
        )
        sub_style = ParagraphStyle(
            name="ReportSubtitle",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#4B5563")
        )

        elements.append(Paragraph(title, title_style))
        if subtitle:
            elements.append(Paragraph(subtitle, sub_style))
        elements.append(Spacer(1, 10))

        table_data = [headers] + rows
        t = Table(table_data, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
            ("TOPPADDING", (0, 0), (-1, 0), 5),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ]))
        elements.append(t)
        doc.build(elements)
        buffer.seek(0)
        return buffer

    @classmethod
    def export_trial_balance(cls, report: TrialBalanceReport) -> io.BytesIO:
        title = f"Aylanma Qoldiq Vedomosti (OSV) - {report.organization_name}"
        subtitle = f"Davr: {report.from_date.strftime('%d.%m.%Y')} dan {report.to_date.strftime('%d.%m.%Y')} gacha | Jami saldo: {report.total_final_debit:,.2f} UZS"

        headers = [
            "Schot", "Schot nomi", "Bosh. Dt", "Bosh. Kt", "Davr Dt", "Davr Kt", "Yakun Dt", "Yakun Kt"
        ]
        rows = []
        for it in report.items:
            rows.append([
                it.account_code,
                it.account_name[:30],
                f"{float(it.initial_debit):,.2f}",
                f"{float(it.initial_credit):,.2f}",
                f"{float(it.period_debit):,.2f}",
                f"{float(it.period_credit):,.2f}",
                f"{float(it.final_debit):,.2f}",
                f"{float(it.final_credit):,.2f}"
            ])
        rows.append([
            "JAMI",
            "Jami hisob-kitoblar",
            f"{float(report.total_initial_debit):,.2f}",
            f"{float(report.total_initial_credit):,.2f}",
            f"{float(report.total_period_debit):,.2f}",
            f"{float(report.total_period_credit):,.2f}",
            f"{float(report.total_final_debit):,.2f}",
            f"{float(report.total_final_credit):,.2f}"
        ])
        return cls.export_generic_pdf(title, subtitle, headers, rows)

    @classmethod
    def export_material_report(cls, report: MaterialReport) -> io.BytesIO:
        title = f"Moddiy Hisobot (Stock Report) - {report.organization_name}"
        subtitle = f"Davr: {report.from_date.strftime('%d.%m.%Y')} dan {report.to_date.strftime('%d.%m.%Y')} gacha"

        headers = ["Nomi", "Birlik", "Bosh. Qoldiq", "Bosh. Summa", "Kirim Qty", "Kirim Summa", "Chiqim Qty", "Chiqim Summa", "Oxirgi Qoldiq", "Oxirgi Summa"]
        rows = []
        for it in report.items:
            rows.append([
                it.item_name[:25],
                it.unit,
                f"{float(it.opening_qty):,.2f}",
                f"{float(it.opening_sum):,.2f}",
                f"{float(it.inflow_qty):,.2f}",
                f"{float(it.inflow_sum):,.2f}",
                f"{float(it.outflow_qty):,.2f}",
                f"{float(it.outflow_sum):,.2f}",
                f"{float(it.closing_qty):,.2f}",
                f"{float(it.closing_sum):,.2f}"
            ])
        rows.append([
            "JAMI", "", "",
            f"{float(report.total_opening_sum):,.2f}", "",
            f"{float(report.total_inflow_sum):,.2f}", "",
            f"{float(report.total_outflow_sum):,.2f}", "",
            f"{float(report.total_closing_sum):,.2f}"
        ])
        return cls.export_generic_pdf(title, subtitle, headers, rows)

    @classmethod
    def export_akt_sverka(cls, report: AktSverkaReport) -> io.BytesIO:
        title = f"Solishuv Dalolatnomasi (Akt Sverka)"
        subtitle = f"{report.organization_name} va {report.counterparty_name} o'rtasida | Davr: {report.from_date.strftime('%d.%m.%Y')} - {report.to_date.strftime('%d.%m.%Y')}"

        headers = ["Sana", "Hujjat №", "Turi", "Operatsiya", "Debet (Dt)", "Kredit (Kt)", "Running Saldo"]
        rows = []
        rows.append([
            report.from_date.strftime("%d.%m.%Y"), "-", "Boshlang'ich", "Davr boshiga qoldiq", "", "", f"{float(report.initial_balance):,.2f}"
        ])
        for it in report.items:
            rows.append([
                it.doc_date.strftime("%d.%m.%Y"),
                it.doc_number or "-",
                it.doc_type,
                (it.description or "")[:30],
                f"{float(it.debit):,.2f}" if it.debit > 0 else "-",
                f"{float(it.credit):,.2f}" if it.credit > 0 else "-",
                f"{float(it.running_balance):,.2f}"
            ])
        rows.append([
            "JAMI", "", "", "Davr aylanmasi va yakuniy saldo",
            f"{float(report.total_debit):,.2f}",
            f"{float(report.total_credit):,.2f}",
            f"{float(report.final_balance):,.2f}"
        ])
        return cls.export_generic_pdf(title, subtitle, headers, rows)
