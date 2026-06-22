import io
from datetime import datetime, timedelta
from uuid import UUID
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_study_guide_pdf(plan) -> bytes:
    """Generate a high-quality printable PDF study guide from a study plan."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styled palettes
    primary_color = colors.HexColor("#6D28D9")   # Violet-700
    secondary_color = colors.HexColor("#4F46E5") # Indigo-600
    text_color = colors.HexColor("#1F2937")      # Gray-800
    bg_light = colors.HexColor("#F3F4F6")        # Gray-100
    border_color = colors.HexColor("#E5E7EB")    # Gray-200
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=24,
        leading=28,
        textColor=primary_color,
        spaceAfter=15
    )
    
    h1_style = ParagraphStyle(
        'HeadingSection',
        parent=styles['Heading2'],
        fontSize=16,
        leading=20,
        textColor=primary_color,
        spaceBefore=15,
        spaceAfter=10,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'HeadingConcept',
        parent=styles['Heading3'],
        fontSize=13,
        leading=16,
        textColor=secondary_color,
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=text_color,
        spaceAfter=8
    )
    
    meta_label_style = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#4B5563"),
        fontName="Helvetica-Bold"
    )
    
    meta_val_style = ParagraphStyle(
        'MetaVal',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=text_color
    )

    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#B91C1C"),
        spaceAfter=4
    )
    
    story = []
    
    # Title
    story.append(Paragraph(f"Conceptra Study Guide: {plan.topic}", title_style))
    story.append(Spacer(1, 10))
    
    # Metadata Box
    created_str = plan.created_at.strftime("%B %d, %Y") if hasattr(plan, 'created_at') and plan.created_at else datetime.now().strftime("%B %d, %Y")
    exam_str = plan.exam_date.strftime("%B %d, %Y") if plan.exam_date else "N/A"
    
    meta_data = [
        [Paragraph("Topic:", meta_label_style), Paragraph(plan.topic, meta_val_style),
         Paragraph("Created On:", meta_label_style), Paragraph(created_str, meta_val_style)],
        [Paragraph("Exam Date:", meta_label_style), Paragraph(exam_str, meta_val_style),
         Paragraph("Study Velocity:", meta_label_style), Paragraph(f"{plan.hours_per_day} hours / day", meta_val_style)],
        [Paragraph("Total Modules:", meta_label_style), Paragraph(f"{len(plan.concepts)} core concepts", meta_val_style),
         Paragraph("Est. Prep Duration:", meta_label_style), Paragraph(f"{len(plan.schedule)} sessions", meta_val_style)]
    ]
    
    meta_table = Table(meta_data, colWidths=[90, 160, 90, 160])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg_light),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('BOX', (0,0), (-1,-1), 1, border_color),
        ('LINEBELOW', (0,0), (-1,-2), 0.5, border_color),
    ]))
    
    story.append(meta_table)
    story.append(Spacer(1, 20))
    
    # 1. Study Calendar Table
    story.append(Paragraph("Study Schedule & Timeline", h1_style))
    story.append(Paragraph("Following a topological study calendar to respect prerequisite dependencies. Skip weeks/days with no items.", body_style))
    story.append(Spacer(1, 8))
    
    # Group schedule items
    sched_header = [
        Paragraph("<b>Week / Day</b>", meta_label_style),
        Paragraph("<b>Concept Module Name</b>", meta_label_style),
        Paragraph("<b>Priority</b>", meta_label_style)
    ]
    sched_rows = [sched_header]
    
    # Sorting schedule items chronologically
    sorted_schedule = sorted(plan.schedule, key=lambda x: (x.week, x.day, x.priority))
    concepts_by_id = {c.id: c for c in plan.concepts}
    
    for item in sorted_schedule:
        concept = concepts_by_id.get(item.concept_id)
        concept_name = concept.name if concept else "Unknown Concept"
        priority_label = "High" if item.priority == "high" else ("Medium" if item.priority == "medium" else "Low")
        sched_rows.append([
            Paragraph(f"Week {item.week}, Day {item.day}", body_style),
            Paragraph(concept_name, body_style),
            Paragraph(priority_label, body_style)
        ])
        
    sched_table = Table(sched_rows, colWidths=[120, 280, 100])
    sched_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BACKGROUND', (0,0), (-1,0), border_color),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
    ]))
    
    story.append(sched_table)
    story.append(PageBreak())
    
    # 2. Concept Detail Sheets
    story.append(Paragraph("Concept Detail Sheets", h1_style))
    story.append(Spacer(1, 10))
    
    for concept in plan.concepts:
        concept_elements = []
        
        # Concept name & description
        concept_elements.append(Paragraph(concept.name, h2_style))
        concept_elements.append(Paragraph(f"<b>Description:</b> {concept.description or 'No description provided.'}", body_style))
        
        content = concept.content
        if content:
            # Explanation
            if content.explanation:
                concept_elements.append(Paragraph("<b>Explanation:</b>", meta_label_style))
                concept_elements.append(Paragraph(content.explanation, body_style))
                concept_elements.append(Spacer(1, 4))
                
            # Quiz Questions
            if content.quiz:
                concept_elements.append(Paragraph("<b>Practice Quiz:</b>", meta_label_style))
                for idx, q in enumerate(content.quiz, 1):
                    q_text = f"Q{idx}. {q.get('question', '')}"
                    if q.get("type") == "mcq" and q.get("options"):
                        opts = ", ".join(f"({chr(97 + i)}) {opt}" for i, opt in enumerate(q.get("options", [])))
                        q_text += f"<br/><i>Options: {opts}</i>"
                    q_text += f"<br/><b>Correct Answer:</b> {q.get('answer', '')}"
                    concept_elements.append(Paragraph(q_text, body_style))
                    concept_elements.append(Spacer(1, 4))
            
            # Resources
            if content.resources:
                concept_elements.append(Paragraph("<b>Recommended Resources:</b>", meta_label_style))
                for r in content.resources:
                    res_text = f"• [{r.get('type', 'link').upper()}] <b>{r.get('title', 'Resource')}</b> - {r.get('url', '')}"
                    concept_elements.append(Paragraph(res_text, body_style))
                    
        concept_elements.append(Spacer(1, 15))
        story.append(KeepTogether(concept_elements))
        
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_study_schedule_ics(plan) -> str:
    """Generate an iCalendar (.ics) string representing the study calendar."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Conceptra//Study Planner//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH"
    ]
    
    start_date = datetime.now().date()
    if hasattr(plan, 'created_at') and plan.created_at:
        start_date = plan.created_at.date()
        
    concepts_by_id = {c.id: c for c in plan.concepts}
    
    for item in plan.schedule:
        concept = concepts_by_id.get(item.concept_id)
        if not concept:
            continue
            
        # Compute exact study day
        # Assumes 5 study days per week, mapping week W, day D directly:
        # Week 1, Day 1 -> offset 0
        # Week 1, Day 5 -> offset 4
        # Week 2, Day 1 -> offset 7
        days_offset = (item.week - 1) * 7 + (item.day - 1)
        event_date = start_date + timedelta(days=days_offset)
        
        # Unique identifier
        uid = f"conceptra-{plan.id}-{concept.id}@conceptra.app"
        
        # Timestamps
        now_str = datetime.now().strftime("%Y%m%dT%H%M%SZ")
        dtstart = event_date.strftime("%Y%m%d")
        dtend = (event_date + timedelta(days=1)).strftime("%Y%m%d")
        
        # Summary and description
        summary = f"Conceptra Study: {concept.name}"
        
        desc_parts = []
        if concept.description:
            desc_parts.append(concept.description)
        if concept.content and concept.content.explanation:
            desc_parts.append(f"Explanation: {concept.content.explanation}")
        if concept.content and concept.content.resources:
            desc_parts.append("Resources:")
            for r in concept.content.resources:
                desc_parts.append(f"- [{r.get('type')}] {r.get('title')}: {r.get('url')}")
                
        # Clean description text for ICS format (no newlines without escaping, keep simple)
        description = "\\n".join(desc_parts).replace(",", "\\,").replace(";", "\\;")
        
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_str}",
            f"DTSTART;VALUE=DATE:{dtstart}",
            f"DTEND;VALUE=DATE:{dtend}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
            "STATUS:CONFIRMED",
            "END:VEVENT"
        ])
        
    lines.append("END:VCALENDAR")
    return "\n".join(lines)
