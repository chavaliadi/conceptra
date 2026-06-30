import zipfile
import xml.etree.ElementTree as ET
import os

def read_docx(file_path):
    # Namespace for word processing ML
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    
    with zipfile.ZipFile(file_path) as docx:
        # Read the document xml
        xml_content = docx.read('word/document.xml')
        root = ET.fromstring(xml_content)
        
        # Find all paragraph elements
        paragraphs = []
        for p in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
            texts = [t.text for t in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if t.text]
            if texts:
                paragraphs.append(''.join(texts))
        return '\n'.join(paragraphs)

if __name__ == "__main__":
    file_path = "/Users/srinivasch/Documents/Projects/Conceptra/Conceptra_Blueprint.docx"
    text = read_docx(file_path)
    # Write output to txt
    out_path = "/Users/srinivasch/Documents/Projects/Conceptra/Conceptra_Blueprint_extracted.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Extracted document text saved to {out_path}")
