"""
views.py ga qo'shish kerak bo'lgan kod:
- XaridorUmumiyChekView: tanlangan sotuvlar bo'yicha PDF chek generatsiyasi
"""

import io
from decimal import Decimal
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseBadRequest
from django.views import View
from django.shortcuts import get_object_or_404
from django.db.models import Sum

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import date, datetime

# models import — o'z loyihangizga moslang
from crm import models as m

def mkstyle(name, **kw):
    return ParagraphStyle(name, **kw)

def to_int(val):
    """Har qanday val ni xavfsiz int ga aylantiradi"""
    try:
        return int(val) if val is not None else 0
    except (TypeError, ValueError):
        return 0


def fmt(val):
    try:
        return f"{int(val):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"
    
def format_sum(val):
    """Raqamni guruhlash bilan formatlash: 1,234,567"""
    try:
        return f"{int(val):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


class XaridorUmumiyChekView(LoginRequiredMixin, View):
    """
    Xaridor sahifasidan tanlangan sotuvlar bo'yicha umumiy PDF chek.

    URL: /xaridorlar/<pk>/umumiy-chek/
    POST params: sotuv_ids = "1,2,3"  (vergul bilan ajratilgan)
    """
    login_url = 'account_login'

    def post(self, request, pk):
        xaridor = get_object_or_404(m.Xaridor, pk=pk)

        # Tanlangan sotuv IDlarini olish
        ids_raw = request.POST.get('sotuv_ids', '')
        try:
            sotuv_ids = [int(i.strip()) for i in ids_raw.split(',') if i.strip()]
        except ValueError:
            return HttpResponseBadRequest("Noto'g'ri sotuv IDs")

        if not sotuv_ids:
            return HttpResponseBadRequest("Hech qanday sotuv tanlanmagan")

        sotuvlar = m.Sotuv.objects.filter(
            id__in=sotuv_ids,
            xaridor=xaridor
        ).prefetch_related('items__mahsulot', 'items__variant').order_by('sana')

        if not sotuvlar.exists():
            return HttpResponseBadRequest("Sotuvlar topilmadi")

        # PDF generatsiya
        buffer = io.BytesIO()
        pdf = self._generate_pdf(buffer, xaridor, sotuvlar)
        buffer.seek(0)

        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="xaridor_{xaridor.id}_umumiy_chek.pdf"'
        )
        return response

    def _generate_pdf(self, buffer, xaridor, sotuvlar):
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=15 * mm,
            leftMargin=15 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
        )

        # Ranglar
        BLUE_DARK  = colors.HexColor('#1d4ed8')
        BLUE_LIGHT = colors.HexColor('#eff6ff')
        GREEN      = colors.HexColor('#059669')
        GREEN_LIGHT= colors.HexColor('#f0fdf4')
        RED        = colors.HexColor('#dc2626')
        RED_LIGHT  = colors.HexColor('#fef2f2')
        YELLOW_BG  = colors.HexColor('#fef3c7')
        YELLOW_BD  = colors.HexColor('#fcd34d')
        GRAY_BG    = colors.HexColor('#f8fafc')
        GRAY_TEXT  = colors.HexColor('#64748b')
        BORDER     = colors.HexColor('#e2e8f0')
        BLACK      = colors.HexColor('#0f172a')

        styles = getSampleStyleSheet()

        def style(name, **kw):
            return ParagraphStyle(name, **kw)

        s_title = style('title',
            fontSize=18, fontName='Helvetica-Bold',
            textColor=colors.white, alignment=TA_CENTER)
        s_subtitle = style('subtitle',
            fontSize=9, fontName='Helvetica',
            textColor=colors.HexColor('#bfdbfe'), alignment=TA_CENTER)
        s_label = style('label',
            fontSize=8, fontName='Helvetica',
            textColor=GRAY_TEXT)
        s_value = style('value',
            fontSize=10, fontName='Helvetica-Bold',
            textColor=BLACK)
        s_section = style('section',
            fontSize=10, fontName='Helvetica-Bold',
            textColor=BLUE_DARK)
        s_small = style('small',
            fontSize=8, fontName='Helvetica',
            textColor=GRAY_TEXT)
        s_amount_red = style('amt_red',
            fontSize=13, fontName='Helvetica-Bold',
            textColor=RED, alignment=TA_RIGHT)
        s_amount_green = style('amt_green',
            fontSize=11, fontName='Helvetica-Bold',
            textColor=GREEN, alignment=TA_RIGHT)
        s_normal = style('normal_c',
            fontSize=9, fontName='Helvetica',
            textColor=BLACK)
        s_bold = style('bold_c',
            fontSize=9, fontName='Helvetica-Bold',
            textColor=BLACK)
        s_center = style('center_c',
            fontSize=9, fontName='Helvetica',
            textColor=BLACK, alignment=TA_CENTER)

        story = []

        # ─── HEADER ───
        header_data = [[
            Paragraph(f"UMUMIY SOTUV CHEKI", s_title),
        ]]
        header_table = Table(header_data, colWidths=[180 * mm])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), BLUE_DARK),
            ('ROUNDEDCORNERS', [8]),
            ('TOPPADDING', (0, 0), (-1, -1), 14),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 20),
            ('RIGHTPADDING', (0, 0), (-1, -1), 20),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 4 * mm))

        # Sotuvlar raqamlari
        ids_text = ', '.join([f"#{s.id}" for s in sotuvlar])
        sub_data = [[Paragraph(f"Sotuvlar: {ids_text}", s_subtitle)]]
        sub_table = Table(sub_data, colWidths=[180 * mm])
        sub_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), BLUE_DARK),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
        ]))

        # ─── XARIDOR MA'LUMOTLARI ───
        from datetime import date
        info_data = [
            [
                Paragraph("Xaridor", s_label),
                Paragraph("Telefon", s_label),
                Paragraph("Manzil", s_label),
                Paragraph("Chek sanasi", s_label),
            ],
            [
                Paragraph(xaridor.ism, s_value),
                Paragraph(xaridor.telefon or '—', s_value),
                Paragraph(xaridor.manzil or '—', s_value),
                Paragraph(date.today().strftime('%d.%m.%Y'), s_value),
            ],
        ]
        info_table = Table(info_data, colWidths=[45 * mm, 45 * mm, 50 * mm, 40 * mm])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), GRAY_BG),
            ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('ROUNDEDCORNERS', [6]),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 5 * mm))

        # ─── HAR BIR SOTUV ───
        for sotuv in sotuvlar:
            # Sotuv header
            holat_map = {
                'tolandi': ('✓ Tolandi', GREEN, GREEN_LIGHT),
                'qisman': ('◐ Qisman', colors.HexColor('#d97706'), YELLOW_BG),
                'tolanmadi': ('● Tolanmagan', RED, RED_LIGHT),
            }
            holat_text, holat_color, holat_bg = holat_map.get(
                sotuv.tolov_holati,
                (sotuv.tolov_holati, GRAY_TEXT, GRAY_BG)
            )

            sotuv_header = Table([[
                Paragraph(f"Sotuv #{sotuv.id}", style('sh',
                    fontSize=10, fontName='Helvetica-Bold', textColor=BLUE_DARK)),
                Paragraph(sotuv.sana.strftime('%d.%m.%Y %H:%M'), s_small),
                Paragraph(holat_text, style('ht',
                    fontSize=9, fontName='Helvetica-Bold',
                    textColor=holat_color, alignment=TA_RIGHT)),
            ]], colWidths=[60 * mm, 60 * mm, 60 * mm])
            sotuv_header.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), BLUE_LIGHT),
                ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (0, -1), 10),
                ('RIGHTPADDING', (-1, 0), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(sotuv_header)

            # Mahsulotlar jadvali
            items_header = [
                Paragraph('#', s_small),
                Paragraph('Mahsulot', s_small),
                Paragraph('Miqdor', s_small),
                Paragraph('Narx (so\'m)', s_small),
                Paragraph('Jami (so\'m)', s_small),
            ]
            items_rows = [items_header]

            for idx, item in enumerate(sotuv.items.all(), 1):
                variant_text = ''
                if hasattr(item, 'variant') and item.variant:
                    variant_text = f"\n{item.variant}"
                name = f"{item.mahsulot.nomi}{variant_text}"

                items_rows.append([
                    Paragraph(str(idx), s_center),
                    Paragraph(name, s_normal),
                    Paragraph(f"{item.miqdor} ta", s_center),
                    Paragraph(f"{format_sum(item.narx)}", style('r',
                        fontSize=9, fontName='Helvetica', alignment=TA_RIGHT)),
                    Paragraph(f"{format_sum(item.jami)}", style('r2',
                        fontSize=9, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
                ])

            items_table = Table(
                items_rows,
                colWidths=[10 * mm, 85 * mm, 22 * mm, 32 * mm, 31 * mm]
            )
            items_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
                ('TEXTCOLOR', (0, 0), (-1, 0), GRAY_TEXT),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
                ('LINEBELOW', (0, 0), (-1, 0), 0.5, BORDER),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRAY_BG]),
                ('LINEBELOW', (0, 1), (-1, -2), 0.3, BORDER),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(items_table)

            # Sotuv mini-xulosasi
            qarz = getattr(sotuv, 'qarz_summa', sotuv.yakuniy_summa - sotuv.tolangan_summa)
            mini_rows = [
                [
                    Paragraph('Jami:', s_small),
                    Paragraph(f"{format_sum(sotuv.yakuniy_summa)} so'm", style('mv',
                        fontSize=9, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
                    Paragraph("To'langan:", s_small),
                    Paragraph(f"{format_sum(sotuv.tolangan_summa)} so'm", style('mv2',
                        fontSize=9, fontName='Helvetica-Bold',
                        textColor=GREEN, alignment=TA_RIGHT)),
                    Paragraph("Qarz:", s_small),
                    Paragraph(f"{format_sum(qarz)} so'm", style('mv3',
                        fontSize=9, fontName='Helvetica-Bold',
                        textColor=RED if qarz > 0 else GREEN, alignment=TA_RIGHT)),
                ]
            ]
            mini_table = Table(mini_rows, colWidths=[15*mm, 35*mm, 20*mm, 35*mm, 15*mm, 60*mm])
            mini_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), GRAY_BG),
                ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(mini_table)
            story.append(Spacer(1, 4 * mm))

        # ─── KIRIMLAR TARIXI ───
        kirimlar = m.Kirim.objects.filter(
            xaridor=xaridor,
            sotuv__id__in=[s.id for s in sotuvlar]
        ).order_by('sana')

        if kirimlar.exists():
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph("TO'LOVLAR TARIXI", style('kh',
                fontSize=10, fontName='Helvetica-Bold', textColor=GREEN)))
            story.append(Spacer(1, 2 * mm))

            k_rows = [[
                Paragraph('#', s_small),
                Paragraph('Sana', s_small),
                Paragraph("Sotuv", s_small),
                Paragraph("Valyuta", s_small),
                Paragraph("Summa (so'm)", s_small),
                Paragraph("Summa (USD)", s_small),
            ]]
            for idx, k in enumerate(kirimlar, 1):
                k_rows.append([
                    Paragraph(str(idx), s_center),
                    Paragraph(k.sana.strftime('%d.%m.%Y %H:%M'), s_normal),
                    Paragraph(f"#{k.sotuv.id}" if k.sotuv else '—', s_center),
                    Paragraph(k.valyuta.upper() if hasattr(k, 'valyuta') else 'UZS', s_center),
                    Paragraph(format_sum(k.summa), style('r3',
                        fontSize=9, fontName='Helvetica-Bold',
                        textColor=GREEN, alignment=TA_RIGHT)),
                    Paragraph(
                        f"${k.summa_usd:.2f}" if hasattr(k, 'summa_usd') and k.summa_usd else '—',
                        style('r4', fontSize=9, fontName='Helvetica', alignment=TA_RIGHT)
                    ),
                ])

            k_table = Table(k_rows, colWidths=[10*mm, 35*mm, 20*mm, 20*mm, 50*mm, 45*mm])
            k_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0fdf4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), GREEN),
                ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
                ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.HexColor('#86efac')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRAY_BG]),
                ('LINEBELOW', (0, 1), (-1, -2), 0.3, BORDER),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(k_table)
            story.append(Spacer(1, 4 * mm))

        # ─── UMUMIY XULOSA ───
        agg = sotuvlar.aggregate(
            jami=Sum('yakuniy_summa'),
            tolangan=Sum('tolangan_summa'),
        )
        total_jami    = agg['jami']    or 0
        total_tolandi = agg['tolangan'] or 0
        total_qarz    = total_jami - total_tolandi

        # Umumiy USD
        total_usd_tolangan = kirimlar.aggregate(
            s=Sum('summa_usd')
        )['s'] or Decimal('0') if kirimlar.exists() else 0

        # Qarz banner
        qarz_color = RED if total_qarz > 0 else GREEN
        qarz_bg = RED_LIGHT if total_qarz > 0 else GREEN_LIGHT

        summary_data = [
            [
                Paragraph("UMUMIY XULOSA", style('ux',
                    fontSize=11, fontName='Helvetica-Bold',
                    textColor=BLUE_DARK)),
                '', '', '',
            ],
            [
                Paragraph("Jami sotuvlar:", s_label),
                Paragraph(f"{format_sum(total_jami)} so'm", style('sj',
                    fontSize=11, fontName='Helvetica-Bold',
                    textColor=BLACK, alignment=TA_RIGHT)),
                Paragraph("To'langan:", s_label),
                Paragraph(f"{format_sum(total_tolandi)} so'm", style('st',
                    fontSize=11, fontName='Helvetica-Bold',
                    textColor=GREEN, alignment=TA_RIGHT)),
            ],
            [
                Paragraph("Umumiy qarz:", style('ql',
                    fontSize=10, fontName='Helvetica-Bold',
                    textColor=qarz_color)),
                Paragraph(f"{format_sum(total_qarz)} so'm", style('qa',
                    fontSize=14, fontName='Helvetica-Bold',
                    textColor=qarz_color, alignment=TA_RIGHT)),
                Paragraph("To'langan (USD):", s_label),
                Paragraph(
                    f"${float(total_usd_tolangan):.2f}" if total_usd_tolangan else '—',
                    style('ua', fontSize=11, fontName='Helvetica-Bold',
                          textColor=GREEN, alignment=TA_RIGHT)
                ),
            ],
        ]

        summary_table = Table(summary_data, colWidths=[40*mm, 65*mm, 40*mm, 35*mm])
        summary_table.setStyle(TableStyle([
            ('SPAN', (0, 0), (-1, 0)),
            ('BACKGROUND', (0, 0), (-1, 0), BLUE_LIGHT),
            ('BACKGROUND', (0, 1), (-1, 1), GRAY_BG),
            ('BACKGROUND', (0, 2), (-1, 2), qarz_bg),
            ('BOX', (0, 0), (-1, -1), 1.5, BLUE_DARK),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, BORDER),
            ('LINEBELOW', (0, 1), (-1, 1), 0.5, BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(summary_table)

        # Footer
        story.append(Spacer(1, 5 * mm))
        from datetime import datetime
        story.append(Paragraph(
            f"Chek yaratildi: {datetime.now().strftime('%d.%m.%Y %H:%M')} · "
            f"Sotuvlar soni: {sotuvlar.count()} ta",
            style('footer', fontSize=8, fontName='Helvetica',
                  textColor=GRAY_TEXT, alignment=TA_CENTER)
        ))

        doc.build(story)
        return buffer
    
class IshchiChekView(LoginRequiredMixin, View):
    login_url = 'account_login'
 
    def get(self, request, pk):
        ishchi = get_object_or_404(m.Ishchi, pk=pk)
 
        ishlar   = list(ishchi.ishlar.filter(status='yangi')
                        .select_related('mahsulot').order_by('sana'))
        avanslar = list(m.Avans.objects.filter(ishchi=ishchi, is_active=True)
                        .order_by('created'))
 
        total_summa = sum(to_int(ish.narxi) for ish in ishlar)
        total_avans = sum(to_int(av.amount)  for av in avanslar)
        total_soni  = sum(to_int(ish.soni)   for ish in ishlar)
 
        buf = io.BytesIO()
        self._build(buf, ishchi, ishlar, avanslar, total_summa, total_avans, total_soni)
        buf.seek(0)
 
        resp = HttpResponse(buf, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="chek_{ishchi.id}.pdf"'
        return resp
 
    def _build(self, buf, ishchi, ishlar, avanslar,
               total_summa, total_avans, total_soni):
 
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            rightMargin=12*mm, leftMargin=12*mm,
            topMargin=10*mm,   bottomMargin=10*mm,
        )
 
        BD  = colors.HexColor('#1d4ed8')
        BL  = colors.HexColor('#eff6ff')
        GR  = colors.HexColor('#059669')
        GRL = colors.HexColor('#f0fdf4')
        RD  = colors.HexColor('#dc2626')
        RDL = colors.HexColor('#fef2f2')
        GB  = colors.HexColor('#f8fafc')
        GT  = colors.HexColor('#64748b')
        BR  = colors.HexColor('#e2e8f0')
        BK  = colors.HexColor('#0f172a')
        PU  = colors.HexColor('#7c3aed')
        PUL = colors.HexColor('#f5f3ff')
 
        # Sahifa umumiy kengligi: 210 - 12 - 12 = 186mm
        W = 186
 
        _sid = [0]
        def p(text, fs=9, fn='Helvetica', tc=None, al=TA_LEFT):
            _sid[0] += 1
            st = mkstyle(f'_s{_sid[0]}',
                         fontSize=fs, fontName=fn,
                         textColor=tc or BK,
                         alignment=al)
            return Paragraph(str(text), st)
 
        story = []
 
        # ── 1. HEADER ──────────────────────────────────────────────
        hdr = Table([[
            p(f"{ishchi.ism} {ishchi.familiya}",
              fs=13, fn='Helvetica-Bold', tc=colors.white),
            p("OYLIK CHEK",
              fs=13, fn='Helvetica-Bold', tc=colors.white, al=TA_CENTER),
            p(f"{ishchi.turi.nomi if ishchi.turi else ''}  "
              f"<font size=8 color='#bfdbfe'>{date.today().strftime('%d.%m.%Y')}</font>",
              fs=9, fn='Helvetica-Bold', tc=colors.white, al=TA_RIGHT),
        ]], colWidths=[70*mm, 76*mm, 40*mm])
        hdr.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,-1), BD),
            ('TOPPADDING',    (0,0),(-1,-1), 8),
            ('BOTTOMPADDING', (0,0),(-1,-1), 8),
            ('LEFTPADDING',   (0,0),(-1,-1), 10),
            ('RIGHTPADDING',  (0,0),(-1,-1), 10),
            ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ]))
        story.append(hdr)
        story.append(Spacer(1, 3*mm))
 
        # ── 2. ISHLAR JADVALI ──────────────────────────────────────
        # Ustun kengliklari jami: 8+22+104+18+34 = 186mm
        COL_ISH = [8*mm, 22*mm, 104*mm, 18*mm, 34*mm]
 
        rows = [[
            p('#',            fs=7, tc=GT),
            p('Sana',         fs=7, tc=GT),
            p('Mahsulot',     fs=7, tc=GT),
            p('Soni',         fs=7, tc=GT),
            p("Summa (so'm)", fs=7, tc=GT, al=TA_RIGHT),
        ]]
 
        for i, ish in enumerate(ishlar, 1):
            narxi = to_int(ish.narxi)
            soni  = to_int(ish.soni)
            rows.append([
                p(str(i),                                              fs=8, al=TA_CENTER),
                p(ish.sana.strftime('%d.%m.%y') if ish.sana else '—', fs=8),
                p(ish.mahsulot.nomi,                                   fs=8),
                p(str(soni),                                           fs=8, al=TA_CENTER),
                p(fmt(narxi), fs=8, fn='Helvetica-Bold',               al=TA_RIGHT),
            ])
 
        last_i = len(rows)
        rows.append([
            p('', fs=7), p('', fs=7),
            p('JAMI:', fs=8, fn='Helvetica-Bold', tc=BD, al=TA_RIGHT),
            p(f"{total_soni} ta", fs=8, fn='Helvetica-Bold', tc=BD, al=TA_CENTER),
            p(f"{fmt(total_summa)} so'm", fs=9, fn='Helvetica-Bold', tc=BD, al=TA_RIGHT),
        ])
 
        ish_t = Table(rows, colWidths=COL_ISH)
        ish_t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),      (-1,0),        colors.HexColor('#f1f5f9')),
            ('BOX',           (0,0),      (-1,-1),       0.5, BR),
            ('LINEBELOW',     (0,0),      (-1,0),        0.5, BR),
            ('LINEBELOW',     (0,1),      (-1,last_i-1), 0.3, BR),
            ('ROWBACKGROUNDS',(0,1),      (-1,last_i-1), [colors.white, GB]),
            ('BACKGROUND',    (0,last_i), (-1,last_i),   BL),
            ('LINEABOVE',     (0,last_i), (-1,last_i),   1, BD),
            ('TOPPADDING',    (0,0),(-1,-1), 3),
            ('BOTTOMPADDING', (0,0),(-1,-1), 3),
            ('LEFTPADDING',   (0,0),(-1,-1), 4),
            ('RIGHTPADDING',  (0,0),(-1,-1), 4),
            ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ]))
        story.append(ish_t)
        story.append(Spacer(1, 3*mm))
 
        # ── 3. AVANSLAR (chap, 110mm) + XULOSA (o'ng, 72mm) ───────
        # Jami: 110 + 4 (gap) + 72 = 186mm
 
        AV_W  = 110   # avans jadval kengligi (mm)
        GAP_W = 4     # oradagi bo'shliq
        XU_W  = 72    # xulosa kengligi
        # AV_W ichidagi ustunlar: 8 + 32 + 70 = 110
        COL_AV = [8*mm, 32*mm, 70*mm]
 
        av_rows = [[
            p('#',             fs=7, tc=GT),
            p('Berilgan sana', fs=7, tc=GT),
            p("Summa (so'm)",  fs=7, tc=GT, al=TA_RIGHT),
        ]]
        for i, av in enumerate(avanslar, 1):
            av_rows.append([
                p(str(i), fs=8, al=TA_CENTER),
                p(av.created.strftime('%d.%m.%y') if av.created else '—', fs=8),
                p(fmt(av.amount), fs=8, fn='Helvetica-Bold', tc=PU, al=TA_RIGHT),
            ])
 
        av_last = len(av_rows)
        av_rows.append([
            p('', fs=7),
            p('JAMI:', fs=8, fn='Helvetica-Bold', tc=PU, al=TA_RIGHT),
            p(f"{fmt(total_avans)} so'm", fs=9, fn='Helvetica-Bold', tc=PU, al=TA_RIGHT),
        ])
 
        av_t = Table(av_rows, colWidths=COL_AV)
        av_t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),       (-1,0),        PUL),
            ('BOX',           (0,0),       (-1,-1),       0.5, BR),
            ('LINEBELOW',     (0,0),       (-1,0),        0.5, BR),
            ('LINEBELOW',     (0,1),       (-1,av_last-1),0.3, BR),
            ('ROWBACKGROUNDS',(0,1),       (-1,av_last-1),[colors.white, GB]),
            ('BACKGROUND',    (0,av_last), (-1,av_last),  PUL),
            ('LINEABOVE',     (0,av_last), (-1,av_last),  1, PU),
            ('TOPPADDING',    (0,0),(-1,-1), 3),
            ('BOTTOMPADDING', (0,0),(-1,-1), 3),
            ('LEFTPADDING',   (0,0),(-1,-1), 4),
            ('RIGHTPADDING',  (0,0),(-1,-1), 4),
            ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ]))
 
        # Xulosa — XU_W mm ichiga sig'adi: 36 + 36 = 72mm
        qoldi   = total_summa - total_avans
        q_color = GR  if qoldi >= 0 else RD
        q_bg    = GRL if qoldi >= 0 else RDL
        q_label = "Berilishi kerak:" if qoldi >= 0 else "Ortiqcha olgan:"
 
        xulosa = Table([
            [p("HISOB-KITOB", fs=8, fn='Helvetica-Bold', tc=BD), ''],
            [p("Ishlagan:",   fs=7, tc=GT),
             p(f"{fmt(total_summa)} so'm", fs=9, fn='Helvetica-Bold', tc=BK, al=TA_RIGHT)],
            [p("Avans:",      fs=7, tc=GT),
             p(f"{fmt(total_avans)} so'm", fs=9, fn='Helvetica-Bold', tc=PU, al=TA_RIGHT)],
            [p(q_label,       fs=8, fn='Helvetica-Bold', tc=q_color),
             p(f"{fmt(abs(qoldi))} so'm", fs=12, fn='Helvetica-Bold', tc=q_color, al=TA_RIGHT)],
        ], colWidths=[36*mm, 36*mm])   # 36+36 = 72mm = XU_W
        xulosa.setStyle(TableStyle([
            ('SPAN',          (0,0),(-1,0)),
            ('BACKGROUND',    (0,0),(-1,0),  BL),
            ('BACKGROUND',    (0,1),(-1,2),  GB),
            ('BACKGROUND',    (0,3),(-1,3),  q_bg),
            ('BOX',           (0,0),(-1,-1), 1.2, BD),
            ('LINEBELOW',     (0,0),(-1,0),  0.5, BR),
            ('LINEBELOW',     (0,1),(-1,1),  0.3, BR),
            ('LINEBELOW',     (0,2),(-1,2),  0.3, BR),
            ('TOPPADDING',    (0,0),(-1,-1), 5),
            ('BOTTOMPADDING', (0,0),(-1,-1), 5),
            ('LEFTPADDING',   (0,0),(-1,-1), 6),
            ('RIGHTPADDING',  (0,0),(-1,-1), 6),
            ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ]))
 
        # Combo: avans | bo'shliq | xulosa
        combo = Table(
            [[av_t, '', xulosa]],
            colWidths=[AV_W*mm, GAP_W*mm, XU_W*mm]
        )
        combo.setStyle(TableStyle([
            ('VALIGN',        (0,0),(-1,-1), 'TOP'),
            ('TOPPADDING',    (0,0),(-1,-1), 0),
            ('BOTTOMPADDING', (0,0),(-1,-1), 0),
            ('LEFTPADDING',   (0,0),(-1,-1), 0),
            ('RIGHTPADDING',  (0,0),(-1,-1), 0),
        ]))
        story.append(combo)
        story.append(Spacer(1, 4*mm))
 
        # ── 4. IMZO ────────────────────────────────────────────────
        # Jami: 93 + 93 = 186mm
        imzo = Table([[
            Table([
                [p("Ishchi:", fs=8, fn='Helvetica-Bold')],
                [p(f"{ishchi.ism} {ishchi.familiya}", fs=9, fn='Helvetica-Bold')],
                [Spacer(1, 6*mm)],
                [p("Imzo: _______________________", fs=8, tc=GT)],
            ], colWidths=[89*mm]),
            Table([
                [p("Mas'ul:", fs=8, fn='Helvetica-Bold')],
                [p("_______________________", fs=9, fn='Helvetica-Bold')],
                [Spacer(1, 6*mm)],
                [p("Imzo: _______________________", fs=8, tc=GT)],
            ], colWidths=[89*mm]),
        ]], colWidths=[93*mm, 93*mm])
        imzo.setStyle(TableStyle([
            ('BOX',           (0,0),(-1,-1), 0.5, BR),
            ('LINEAFTER',     (0,0),(0,-1),  0.5, BR),
            ('BACKGROUND',    (0,0),(-1,-1), GB),
            ('TOPPADDING',    (0,0),(-1,-1), 8),
            ('BOTTOMPADDING', (0,0),(-1,-1), 10),
            ('LEFTPADDING',   (0,0),(-1,-1), 10),
            ('RIGHTPADDING',  (0,0),(-1,-1), 10),
            ('VALIGN',        (0,0),(-1,-1), 'TOP'),
        ]))
        story.append(imzo)
 
        # ── 5. SANA ────────────────────────────────────────────────
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph(
            "Sana: _______________________",
            mkstyle('_sana', fontSize=9, fontName='Helvetica',
                    textColor=GT, alignment=TA_LEFT)
        ))
 
        doc.build(story)
 