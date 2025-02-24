import google.generativeai as genai
import json
from dotenv import load_dotenv
import os

load_dotenv()


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure the Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Instantiate the Gemini model
model = genai.GenerativeModel("gemini-1.5-flash")

def extract_course_info(course_outline: str) -> str:
    """
    Given a course outline (as text), prompt the Gemini model to extract:
      - All due dates for exams
      - All due dates for assignments
      - Class schedule (days/times)
    Return the result as text, ideally valid JSON if the model follows instructions.
    """
    
    prompt = """
    You are a helpful assistant. The user gives you a course outline.
    Please extract:
      1) The due dates for all exams
      2) The due dates for all assignments
      3) The class schedule (days/times)

    Return the result as valid JSON in the following structure:

    {
      "exams": [
        {
          "name": "Midterm Exam",
          "due_date": "YYYY-MM-DD"
        }
      ],
      "assignments": [
        {
          "name": "Assignment 1",
          "due_date": "YYYY-MM-DD"
        }
      ],
      "schedule": [
        {
          "day_of_week": "Monday",
          "time": "10:00am - 11:30am"
        }
      ]
    }

    If any of these are missing from the outline, you can provide an empty array for that field.

    Here is the course outline:
    -----------------------
    {course_outline}
    -----------------------
    """

    # Generate response from the Gemini model
    response = model.generate_content(prompt)
    
    # Validate the JSON structure (optional but recommended)
    try:
        result = json.loads(response.text)
        return json.dumps(result, indent=2)  # Pretty print the JSON for readability
    except json.JSONDecodeError:
        return "Error: The model did not return valid JSON.\n" + response.text

# Example usage
if __name__ == "__main__":
    course_outline = """
    Assignment 1 is due on October 20.
    Assignment 2 is due on November 15 by 11:59 PM.
    Quiz 1 is scheduled for September 30.
    The midterm exam will be held on October 25.
    Final Exam is scheduled during the December exam period.
    Classes are held on Tuesdays and Thursdays from 11:30 AM to 12:50 PM, and Fridays from 2:30 PM to 3:20 PM.
    """

    extracted_info = extract_course_info(course_outline)
    print(extracted_info)
