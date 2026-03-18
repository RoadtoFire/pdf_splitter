import os
import sys
import json
import re
from PyPDF2 import PdfReader, PdfWriter

def get_chapter_mapping(pdf_path):
    """
    Recursively flattens the PDF outline into a sorted list of unique chapters.
    Handles nested (Rook's) and container-style (Bolognia) PDF outlines.
    """
    reader = PdfReader(pdf_path)
    raw_bookmarks = []

    def crawl(items):
        for item in items:
            if isinstance(item, list):
                crawl(item)
            else:
                try:
                    page_num = reader.get_destination_page_number(item)
                    if page_num is not None:
                        raw_bookmarks.append({"title": item.title, "page": page_num})
                except Exception:
                    continue

    print(f"[*] Analyzing PDF structure for: {os.path.basename(pdf_path)}...")
    crawl(reader.outline)

    # Sort by page number to ensure logical sequence
    raw_bookmarks.sort(key=lambda x: x['page'])

    # Filter for actual chapters and remove duplicate page entries
    unique_chapters = []
    seen_pages = set()
    
    for b in raw_bookmarks:
        # Check if it looks like a chapter (starts with a number)
        if any(char.isdigit() for char in b['title'].strip()[:4]):
            if b['page'] not in seen_pages:
                unique_chapters.append(b)
                seen_pages.add(b['page'])

    # Create ranges (Start -> Next Chapter Start)
    final_mapping = []
    total_pages = len(reader.pages)
    for i in range(len(unique_chapters)):
        start = unique_chapters[i]['page']
        end = unique_chapters[i+1]['page'] if i+1 < len(unique_chapters) else total_pages
        
        if end > start:
            final_mapping.append({
                "name": unique_chapters[i]['title'],
                "start": start,
                "end": end
            })
    
    return final_mapping

def export_to_react_json(chapters_list, output_filename):
    """
    Transforms the chapter metadata into a React-friendly JSON array.
    Uses regex to cleanly strip leading numbers and whitespace.
    """
    react_data = []
    
    # Regex: Start of string (^), one or more digits (\d+), zero or more spaces (\s*)
    # Also handles cases like "1. Introduction" by adding an optional dot and space
    pattern = r'^\d+\.?\s*'
    
    for index, ch in enumerate(chapters_list, start=1):
        raw_title = ch["name"].strip()
        
        # Strip the prefix safely
        clean_title = re.sub(pattern, '', raw_title)
        
        chapter_obj = {
            "id": index,
            "title": clean_title,
            "description": "",
            "image": ""
        }
        react_data.append(chapter_obj)
        
    with open(output_filename, 'w', encoding='utf-8') as json_file:
        json.dump(react_data, json_file, indent=4)
        
    print(f"[SUCCESS] Cleaned React JSON data generated: {output_filename}")

def split_pdf(pdf_path, output_folder, chapters):
    """
    Physically splits the PDF into separate chapter files using memory-efficient loops.
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    reader = PdfReader(pdf_path)
    total = len(chapters)
    print(f"\n[#] Starting PDF extraction for {total} files...\n")

    for idx, ch in enumerate(chapters, 1):
        # We use the raw name for the PDF file to maintain the original number mapping if needed, 
        # or you can use the cleaned name. Here we use raw for the file system.
        clean_filename = "".join(c for c in ch["name"] if c.isalnum() or c in (' ', '_')).strip()
        clean_filename = clean_filename[:100] 
        output_path = os.path.join(output_folder, f"{clean_filename}.pdf")

        print(f"[{idx}/{total}] Writing: {clean_filename}.pdf...", end="", flush=True)

        writer = PdfWriter()
        for page_num in range(ch["start"], ch["end"]):
            writer.add_page(reader.pages[page_num])

        with open(output_path, "wb") as f:
            writer.write(f)
        
        print(" DONE")

if __name__ == "__main__":
    # --- CONFIGURATION ---
    SOURCE_PDF = "Rooks.pdf"           
    OUTPUT_DIR = "Rooks_Chapters"      
    JSON_OUTPUT = "rooksChapters.json" 
    
    # Set to False if you only want to generate the JSON for the frontend right now
    GENERATE_PDFS = False                  
    
    try:
        # 1. Map the Data
        chapters_data = get_chapter_mapping(SOURCE_PDF)
        
        if not chapters_data:
            print("[ERROR] No chapters identified. Check your PDF's outline.")
            sys.exit(1)
            
        # 2. Export the structured JSON
        export_to_react_json(chapters_data, JSON_OUTPUT)
        
        # 3. Split the physical files
        if GENERATE_PDFS:
            split_pdf(SOURCE_PDF, OUTPUT_DIR, chapters_data)
            print("\n[SUCCESS] All physical chapters extracted successfully.")
            
    except FileNotFoundError:
        print(f"[ERROR] Could not find file: {SOURCE_PDF}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[STOPPED] Process interrupted by user.")
        sys.exit(0)