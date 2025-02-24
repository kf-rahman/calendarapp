import google.generativeai as genai
import json
from dotenv import load_dotenv
import os
import re
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not found in environment variables")

# Configure the Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Instantiate the Gemini model
model = genai.GenerativeModel("gemini-1.5-flash")

def extract_json_from_text(text):
    """
    Attempts to extract JSON from text that might contain markdown or other formatting.
    """
    # Try to find JSON block in markdown
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_match:
        potential_json = json_match.group(1).strip()
        try:
            return json.loads(potential_json)
        except json.JSONDecodeError:
            pass  # Continue with other methods if this fails
    
    # Try to find anything that looks like a JSON object
    json_pattern = r'(\{[\s\S]*\})'
    matches = re.findall(json_pattern, text)
    
    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue
    
    return None

def extract_course_info(course_outline: str) -> str:
    """
    Given a course outline (as text), prompt the Gemini model to extract:
    - All due dates for exams
    - All due dates for assignments
    - Class schedule (days/times)
    Return the result as text, ideally valid JSON if the model follows instructions.
    """
    prompt = f"""
    You are a helpful assistant that extracts course information. The user gives you a course outline.

    TASK:
    Extract the following information:
    1) The due dates for all exams
    2) The due dates for all assignments
    3) The class schedule (days/times)

    RESPONSE FORMAT:
    You must respond ONLY with valid JSON in the exact format below, with no additional text:
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

    Use empty arrays if information is not found. All dates must be in YYYY-MM-DD format.
    Do not include any explanations, only the JSON object.

    COURSE OUTLINE:
    {course_outline}
    """
    
    # First attempt with explicit JSON instructions
    try:
        logger.info("Attempting to extract course information with Gemini")
        response = model.generate_content(prompt)
        
        # Try to get text from response
        response_text = None
        try:
            response_text = response.text
        except AttributeError:
            try:
                response_text = response.parts[0].text
            except (AttributeError, IndexError):
                response_text = str(response)
        
        logger.info(f"Received response from Gemini: {response_text[:100]}...")
        
        # Try to parse JSON directly
        try:
            result = json.loads(response_text)
            return json.dumps(result, indent=2)
        except json.JSONDecodeError:
            # If direct parsing fails, try to extract JSON from text
            extracted_json = extract_json_from_text(response_text)
            if extracted_json:
                return json.dumps(extracted_json, indent=2)
            
            # If extraction fails, try a second attempt with a simpler prompt
            logger.warning("Failed to parse JSON from response, trying again with simplified prompt")
            return second_attempt_extract(course_outline)
    
    except Exception as e:
        logger.error(f"Error in first attempt to extract course info: {str(e)}")
        return second_attempt_extract(course_outline)

def second_attempt_extract(course_outline: str) -> str:
    """
    A second attempt with a simpler prompt if the first one fails.
    """
    prompt = f"""
    Extract exam dates, assignment due dates, and class schedules from this course outline.
    Respond with ONLY a JSON object in this exact format:
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
      "schedule": []
    }}
    
    Course outline:
    {course_outline}
    """
    
    try:
        response = model.generate_content(prompt)
        
        # Try to get text from response
        response_text = None
        try:
            response_text = response.text
        except AttributeError:
            try:
                response_text = response.parts[0].text
            except (AttributeError, IndexError):
                response_text = str(response)
        
        # Try to parse JSON
        try:
            result = json.loads(response_text)
            return json.dumps(result, indent=2)
        except json.JSONDecodeError:
            # Try to extract JSON from text
            extracted_json = extract_json_from_text(response_text)
            if extracted_json:
                return json.dumps(extracted_json, indent=2)
            
            # If all else fails, create a basic structure with the raw response as a note
            logger.error("Failed to extract JSON even with simplified prompt")
            fallback_json = {
                "exams": [],
                "assignments": [],
                "schedule": [],
                "raw_response": response_text[:500]  # Include part of the raw response for debugging
            }
            return json.dumps(fallback_json, indent=2)
    
    except Exception as e:
        logger.error(f"Error in second attempt to extract course info: {str(e)}")
        # Return a minimal valid JSON as fallback
        fallback_json = {
            "exams": [],
            "assignments": [],
            "schedule": [],
            "error": str(e)
        }
        return json.dumps(fallback_json, indent=2)

# Example usage
if __name__ == "__main__":
    course_outline = """
    Assignment 1 is due on October 20, 2025.
    Assignment 2 is due on November 15, 2025 by 11:59 PM.
    Quiz 1 is scheduled for September 30, 2025.
    The midterm exam will be held on October 25, 2025.
    Final Exam is scheduled during the December exam period (December 15, 2025).
    Classes are held on Tuesdays and Thursdays from 11:30 AM to 12:50 PM, and Fridays from 2:30 PM to 3:20 PM.
    """
    extracted_info = extract_course_info(course_outline)
    print(extracted_info)