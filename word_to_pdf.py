import sys
import os
import win32com.client

def word_to_pdf(word_path):
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    
    pdf_path = os.path.splitext(word_path)[0] + ".pdf"
    print(f"Converting {word_path} to {pdf_path}...")
    
    doc = word.Documents.Open(os.path.abspath(word_path))
    doc.SaveAs(os.path.abspath(pdf_path), FileFormat=17) # 17 is wdFormatPDF
    doc.Close()
    word.Quit()
    print("Done!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        word_to_pdf(sys.argv[1])
