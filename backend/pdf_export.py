"""One-page PDF brief export styled like an EP committee memo.

Uses ReportLab if available; otherwise falls back to a minimal hand-written
PDF so the demo never crashes when ReportLab is missing in the environment.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import List, Optional


def _build_with_reportlab(
    item_id: str,
    headline: str,
    narrative: str,
    threat_level: str,
    disinfo_pct: int,
    deepfake_pct: int,
    coordination_pct: int,
    legal_flags: List[str],
    recommended_actions: List[str],
    qr_url: Optional[str],
) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Flowable,
    )

    try:
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics import renderPDF
    except Exception:
        QrCodeWidget = None

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=14 * mm,
        title=f"PDIP Brief {item_id[:8]}",
        author="PDIP - Parliamentary Disinformation Intelligence Platform",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="EPHeader",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=colors.HexColor("#0a1c40"),
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="EPSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.HexColor("#4a5872"),
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="EPHeadline",
        parent=styles["Heading1"],
        fontName="Times-Roman",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#0a1c40"),
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="EPSection",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=colors.HexColor("#0a1c40"),
        spaceBefore=10,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="EPBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1f2b3c"),
    ))
    styles.add(ParagraphStyle(
        name="EPSmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#3a4a66"),
    ))

    story = []

    header_table = Table(
        [[
            Paragraph(
                "<b>PDIP</b> &nbsp; Parliamentary Disinformation Intelligence Platform",
                styles["EPHeader"],
            ),
            Paragraph(
                f"BRIEF ID {item_id[:8].upper()}<br/>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                ParagraphStyle("right", parent=styles["EPSmall"], alignment=2),
            ),
        ]],
        colWidths=[120 * mm, 50 * mm],
    )
    header_table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.6, colors.HexColor("#0a1c40")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "INTELLIGENCE BRIEF &middot; ARTICLE 50 TRANSPARENCY NOTICE: AI-ASSISTED ANALYSIS",
        styles["EPSub"],
    ))
    story.append(Paragraph(headline or "Dossier headline pending", styles["EPHeadline"]))

    badge_color = colors.HexColor("#dc2626") if disinfo_pct >= 65 else (
        colors.HexColor("#d97706") if disinfo_pct >= 45 else colors.HexColor("#0f5fa6")
    )
    metrics = [[
        Paragraph(f"<b>Threat Level</b><br/><font size=10>{threat_level or 'Pending'}</font>", styles["EPBody"]),
        Paragraph(f"<b>Mislead-Citizens Risk</b><br/><font size=10 color='{badge_color.hexval()[2:]}'>{disinfo_pct}%</font>", styles["EPBody"]),
        Paragraph(f"<b>Synthetic Media</b><br/><font size=10>{deepfake_pct}%</font>", styles["EPBody"]),
        Paragraph(f"<b>Coordination</b><br/><font size=10>{coordination_pct}%</font>", styles["EPBody"]),
    ]]
    table = Table(metrics, colWidths=[42 * mm, 42 * mm, 42 * mm, 42 * mm])
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cad6ee")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e1e9f8")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f6f9ff")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)

    story.append(Paragraph("Situation overview", styles["EPSection"]))
    story.append(Paragraph(narrative or "Narrative pending model output.", styles["EPBody"]))

    story.append(Paragraph("Regulatory exposure", styles["EPSection"]))
    if legal_flags:
        for flag in legal_flags[:6]:
            story.append(Paragraph(f"&bull; {flag}", styles["EPSmall"]))
    else:
        story.append(Paragraph("No regulatory exposure identified.", styles["EPSmall"]))

    story.append(Paragraph("Recommended action", styles["EPSection"]))
    if recommended_actions:
        for idx, action in enumerate(recommended_actions[:5], start=1):
            story.append(Paragraph(f"{idx}. {action}", styles["EPSmall"]))
    else:
        story.append(Paragraph("No actions recommended.", styles["EPSmall"]))

    story.append(Spacer(1, 8))
    footer_left = Paragraph(
        "Issued by: PDIP duty desk &middot; Human reviewer required before public use &middot; "
        "Legal basis: Regulation (EU) 2024/1689 Art. 14 (human oversight) &amp; Art. 50 (transparency).",
        styles["EPSmall"],
    )

    qr_flowable: Optional[Flowable] = None
    if qr_url and QrCodeWidget is not None:
        qr_widget = QrCodeWidget(qr_url, barLevel="M")
        bounds = qr_widget.getBounds()
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        target = 24 * mm
        drawing = Drawing(target, target, transform=[target / width, 0, 0, target / height, 0, 0])
        drawing.add(qr_widget)
        qr_flowable = drawing

    if qr_flowable is not None:
        footer_table = Table(
            [[footer_left, qr_flowable]],
            colWidths=[140 * mm, 30 * mm],
        )
        footer_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEABOVE", (0, 0), (-1, -1), 0.3, colors.HexColor("#cad6ee")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(footer_table)
    else:
        story.append(footer_left)

    doc.build(story)
    return buffer.getvalue()


def _fallback_pdf(item_id: str, headline: str, narrative: str) -> bytes:
    """Minimal valid PDF if ReportLab is unavailable."""

    body_lines = [
        "PDIP - Parliamentary Disinformation Intelligence Platform",
        f"Brief ID: {item_id[:8]}",
        f"Generated: {datetime.utcnow().isoformat()}Z",
        "",
        headline or "Dossier headline pending",
        "",
        narrative[:500] if narrative else "Narrative pending.",
        "",
        "Article 50 transparency notice: AI-assisted analysis. Human review required.",
    ]
    body_text = "\n".join(body_lines)

    escaped = body_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream_lines = ["BT", "/F1 11 Tf", "1 0 0 1 50 760 Tm", "14 TL"]
    for idx, line in enumerate(escaped.split("\n")):
        if idx == 0:
            stream_lines.append(f"({line}) Tj")
        else:
            stream_lines.append("T*")
            stream_lines.append(f"({line}) Tj")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines).encode("latin-1", errors="replace")

    objects = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
    )
    objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    output = io.BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(output.tell())
        output.write(f"{idx} 0 obj\n".encode())
        output.write(obj)
        output.write(b"\nendobj\n")
    xref_offset = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n".encode())
    output.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        output.write(f"{off:010d} 00000 n \n".encode())
    output.write(b"trailer\n")
    output.write(f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode())
    output.write(b"startxref\n")
    output.write(f"{xref_offset}\n".encode())
    output.write(b"%%EOF\n")
    return output.getvalue()


def render_brief(
    item_id: str,
    headline: str,
    narrative: str,
    threat_level: str,
    disinfo_pct: int,
    deepfake_pct: int,
    coordination_pct: int,
    legal_flags: List[str],
    recommended_actions: List[str],
    qr_url: Optional[str],
) -> bytes:
    try:
        return _build_with_reportlab(
            item_id, headline, narrative, threat_level,
            disinfo_pct, deepfake_pct, coordination_pct,
            legal_flags, recommended_actions, qr_url,
        )
    except Exception:
        return _fallback_pdf(item_id, headline, narrative)
