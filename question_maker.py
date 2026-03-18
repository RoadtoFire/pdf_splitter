import os
import json
import time
from PyPDF2 import PdfReader
from google import genai
from google.genai import types

# Initialize the modern Gemini Client
client = genai.Client(api_key="")

def extract_text_from_pdf(pdf_path):
    """Extracts raw text from a PDF file."""
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text

def generate_chapter_quiz(chapter_id, pdf_path):
    """Sends chapter text to Gemini and returns a structured JSON list of MCQs."""
    print(f"[*] Reading {os.path.basename(pdf_path)}...")
    chapter_text = extract_text_from_pdf(pdf_path)
    
    # Failsafe for empty PDFs
    if not chapter_text.strip():
        print(f"[ERROR] No text extracted from {pdf_path}")
        return []

    prompt = f"""
    You are an expert medical educator. Based ONLY on the following textbook chapter text, 
    generate exactly 30 multiple-choice questions (MCQs) for a doctor's board exam.
    
    The chapterId for these questions is: {chapter_id}
    
    Return the output strictly as a JSON array of objects. Do not include markdown formatting like ```json.
    Each object must exactly match this structure:
    {{
        "id": <incremental_number>,
        "chapterId": {chapter_id},
        "question": "<The question string>",
        "options": ["<Option A>", "<Option B>", "<Option C>", "<Option D>"],
        "correctIndex": <Integer 0-3 corresponding to the correct option array index>,
        "explanation": "<A concise explanation of why the answer is correct>"
    }}
    
    TEXT:
    {chapter_text}
    """

    print(f"[*] Sending {len(chapter_text)} characters to Gemini for Chapter {chapter_id}...")
    
    try:

        # PIVOT: Use Flash-Lite to access the 1,000 RPD free tier limit
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite', 
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        
        
        # Parse the string response into a Python list of dictionaries
        quiz_data = json.loads(response.text)
        print(f"[SUCCESS] Generated {len(quiz_data)} questions.")
        return quiz_data

    except Exception as e:
        print(f"[FAILED] Error on Chapter {chapter_id}: {e}")
        return []

def build_master_quiz_db(chapters_dir, output_file):
    """Iterates through all chapter PDFs, generates quizzes, and stitches them together."""
    master_quiz_list = []
    global_question_id = 1
    
    # Sort files to ensure chapters are processed in order
    pdf_files = sorted([f for f in os.listdir(chapters_dir) if f.endswith('.pdf')])
    
    for index, filename in enumerate(pdf_files, start=1):
        pdf_path = os.path.join(chapters_dir, filename)
        
        # 1. Generate the quiz data for this specific chapter
        chapter_mcqs = generate_chapter_quiz(chapter_id=index, pdf_path=pdf_path)
        
        # 2. Correct the global IDs sequentially
        for mcq in chapter_mcqs:
            mcq["id"] = global_question_id
            master_quiz_list.append(mcq)
            global_question_id += 1
            
        # 3. Save progress iteratively to prevent data loss on crashes
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(master_quiz_list, f, indent=4)
            
        # 4. Strict Rate Limiting for the Free Tier
        print("[*] Sleeping for 15 seconds to respect rate limits...\n")
        time.sleep(15)
        
    print(f"\n[FINISHED] Master quiz database saved to {output_file} with {len(master_quiz_list)} total questions.")

if __name__ == "__main__":
    # Point this to the folder containing your split PDFs
    CHAPTERS_FOLDER = "./Rooks_Chapters" 
    MASTER_OUTPUT = "./rooksQuestions.json"
    
    build_master_quiz_db(CHAPTERS_FOLDER, MASTER_OUTPUT)