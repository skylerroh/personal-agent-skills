#!/usr/bin/env python3
"""Render a checked volleyball plan as printable court cards."""

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape


SCHEMA = """JSON object with a "sheets" list. Each sheet has:
  title       Team and set label, e.g. "Blue team | Sets 1 and 3"
  rules       Rule mode and assumptions, e.g. "House rules | Fixed rows"
  rotations   Six objects in order, with:
    zones     Six names in zone order 1, 2, 3, 4, 5, 6 (null for vacant)
    server    Player serving when the team has service
    setter    Active setter and row, e.g. "Alex (back row)"
    note      Optional alignment or switch cue
  notes       List of bench assignments, substitution triggers, or other cues
Use additional sheets for other sets, teams, or steps of a longer cycle.
For a continuation sheet, set optional "first_step" and supply 1–6 steps.
The renderer checks card structure. Check rules and substitutions separately.
"""


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, epilog=SCHEMA,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--paper", choices=["letter", "a4"], default="letter")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    render(plan["sheets"], args.output, args.paper)


def render(sheets, output, paper):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
        TableStyle,
    )

    if not sheets:
        raise ValueError("Supply at least one rotation sheet.")

    ink = colors.HexColor("#142632")
    muted = colors.HexColor("#455863")
    line = colors.HexColor("#A8B6BF")
    tint = colors.HexColor("#EDF2F5")
    styles = {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=20,
                                leading=24, textColor=ink),
        "label": ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=10,
                                leading=13, textColor=ink),
        "body": ParagraphStyle("body", fontSize=9, leading=12, textColor=ink),
        "small": ParagraphStyle("small", fontSize=8, leading=11, textColor=muted),
    }
    doc = SimpleDocTemplate(
        str(output), pagesize=letter if paper == "letter" else A4,
        leftMargin=36, rightMargin=36, topMargin=34, bottomMargin=40,
        title="Volleyball rotation schedule",
    )
    width = doc.width - 12  # ReportLab frame padding
    card_width = (width - 14) / 2

    def paragraph(value, style="body"):
        return Paragraph(escape(value), styles[style])

    def card(step, rotation):
        zones = rotation["zones"]
        names = [name for name in zones if name is not None]
        if len(zones) != 6 or len(names) != len(set(names)):
            raise ValueError(f"Rotation {step} needs six zones and unique players.")
        court_rows = [
            [Paragraph(f'<font size="8">{zone}</font><br/>{escape(zones[zone - 1] or "Vacant")}',
                       styles["body"]) for zone in row]
            for row in ((4, 3, 2), (5, 6, 1))
        ]
        court = Table(court_rows, colWidths=[card_width / 3] * 3)
        court.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), tint),
            ("GRID", (0, 0), (-1, -1), 0.5, line),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        contents = [
            paragraph(f"R{step}", "label"), paragraph("NET", "small"), court,
            Spacer(1, 4),
            paragraph(f"Server  {rotation['server']}"),
            paragraph(f"Setter  {rotation['setter']}"),
        ]
        if rotation.get("note"):
            contents.append(paragraph(rotation["note"], "small"))
        return contents

    story = []
    for index, sheet in enumerate(sheets):
        if index:
            story.append(PageBreak())
        rotations = sheet["rotations"]
        first_step = sheet.get("first_step", 1)
        if not (1 <= len(rotations) <= 6 and first_step >= 1):
            raise ValueError("Each sheet needs 1–6 steps and a positive first step.")
        if first_step == 1 and len(rotations) != 6:
            raise ValueError("The opening sheet needs six steps.")

        story.extend([
            paragraph("VOLLEYBALL ROTATIONS", "small"),
            paragraph(sheet["title"], "title"), Spacer(1, 4),
            paragraph(sheet["rules"]),
            paragraph("View from your end line facing the net. Shaded row is front.", "small"),
            Spacer(1, 14),
        ])
        cards = [card(step, rotation)
                 for step, rotation in enumerate(rotations, first_step)]
        for left in range(0, len(cards), 2):
            right = cards[left + 1] if left + 1 < len(cards) else ""
            pair = Table([[cards[left], "", right]],
                         colWidths=[card_width, 14, card_width])
            pair.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.extend([pair, Spacer(1, 13)])
        notes = sheet.get("notes", [])
        if notes:
            story.append(KeepTogether([
                paragraph(f"Bench and instructions | {sheet['title']}", "label"),
                *[paragraph(note) for note in notes],
            ]))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFillColor(muted)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(document.pagesize[0] - 36, 23, str(document.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    main()
