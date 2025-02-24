import google.generativeai as genai
import json

genai.configure(api_key="AIzaSyCM766BeiiDRjOCzIrXt9kh4dyXpOmhyiA")
model = genai.GenerativeModel("gemini-1.5-flash")
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
    print(course_outline)
    prompt = f"""
    You are a helpful assistant. The user gives you a course outline.
    Please extract:
      1) The due dates for all exams
      2) The due dates for all assignments
      3) The class schedule (days/times)

    Return the result as valid JSON in the following structure:

    {{
      "exams": [
        {{
          "name": "Midterm Exam",
          "due_date": "YYYY-MM-DD"
        }}
      ],
      "assignments": [
        {{
          "name": "Assignment 1",
          "due_date": "YYYY-MM-DD"
        }}
      ],
      "schedule": [
        {{
          "day_of_week": "Monday",
          "time": "10:00am - 11:30am"
        }}
      ]
    }}

    If any of these are missing from the outline, you can provide an empty array for that field.

    Here is the course outline:
    -----------------------
    {course_outline}
    -----------------------
    """

    response = model.generate_content(prompt)
    return response.text