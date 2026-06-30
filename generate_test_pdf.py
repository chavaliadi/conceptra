from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

def create_pdf():
    pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_syllabus.pdf")
    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont("Helvetica-Bold", 20)
    c.drawString(100, height - 100, "Data Communication and Networking Syllabus")
    
    # Body text
    c.setFont("Helvetica", 12)
    text = [
        "Course Description:",
        "This course introduces the fundamental concepts of data communication and computer networks.",
        "Topics include physical layer transmission, data link layer protocols, medium access control,",
        "routing algorithms (IP), congestion control, transport protocols (TCP/UDP), and application layer services (HTTP, DNS).",
        "",
        "Syllabus Concepts to Study:",
        "1. Physical Layer and Signal Encoding",
        "2. Data Link Layer and Error Correction",
        "3. Network Layer Protocols and IP Routing",
        "4. Transport Layer TCP UDP Flow Control",
        "5. Application Layer DNS HTTP and Security"
    ]
    
    y = height - 150
    for line in text:
        c.drawString(100, y, line)
        y -= 20
        
    c.save()
    print(f"Created PDF: {pdf_path}")

if __name__ == "__main__":
    create_pdf()
