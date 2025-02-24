from fastapi import FastAPI, Request, HTTPException, Body, Form
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json
import os
from dotenv import load_dotenv
from datetime import datetime
import logging
import uuid

# Import the LLM script
from llm import extract_course_info

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    logger.warning("GOOGLE_API_KEY not found in environment variables")

# FastAPI app
app = FastAPI(title="Course Calendar Assistant")

# ------------------------------------------------------------------------------
#  HOME: Show form for user input
# ------------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    html_form = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Extract Course Dates & Add to Google Calendar</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
          body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
          }
          h1 {
            color: #333;
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
          }
          .form-group {
            margin-bottom: 15px;
          }
          label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
          }
          input[type="text"], textarea {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
          }
          textarea {
            min-height: 200px;
          }
          button {
            background-color: #4285f4;
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
          }
          button:hover {
            background-color: #3367d6;
          }
          .loading {
            display: none;
            margin-top: 20px;
          }
          .results {
            display: none;
            margin-top: 20px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 4px;
          }
          .event-link {
            color: #4285f4;
            text-decoration: none;
          }
          .event-link:hover {
            text-decoration: underline;
          }
          .error {
            color: #d32f2f;
            background-color: #ffebee;
            padding: 10px;
            border-radius: 4px;
            margin-top: 10px;
            display: none;
          }
        </style>
      </head>
      <body>
        <h1>Course Calendar Assistant</h1>
        <p>
          This tool extracts important dates from your course outline and adds them to your Google Calendar.
        </p>
        
        <div class="form-group">
          <label for="calendar_id">Google Calendar ID:</label>
          <input 
            type="text" 
            id="calendar_id" 
            name="calendar_id" 
            placeholder="your-calendar-id@group.calendar.google.com" 
            required
          >
          <small>Find this in your Google Calendar settings under "Integrate calendar"</small>
        </div>
        
        <div class="form-group">
          <label for="course_outline">Paste your course outline:</label>
          <textarea 
            id="course_outline" 
            name="course_outline" 
            placeholder="Paste your course outline or syllabus here..."
            required
          ></textarea>
        </div>
        
        <button id="submitBtn" type="button">Extract & Create Events</button>
        <button id="downloadIcsBtn" type="button" style="margin-left:10px;">Download ICS</button>
        
        <div class="loading" id="loadingIndicator">
          Processing your request... This may take a few seconds.
        </div>
        
        <div class="error" id="errorMessage"></div>
        
        <div class="results" id="resultsContainer">
          <h2>Results</h2>
          <div id="extractedDataContainer">
            <h3>Extracted Information</h3>
            <pre id="extractedData"></pre>
          </div>
          <div id="eventsContainer">
            <h3>Created Calendar Events</h3>
            <ul id="eventsList"></ul>
          </div>
        </div>
        
        <script>
          document.getElementById('submitBtn').addEventListener('click', async function() {
            const calendarId = document.getElementById('calendar_id').value;
            const courseOutline = document.getElementById('course_outline').value;
            
            // Validation
            if (!calendarId || !courseOutline) {
              document.getElementById('errorMessage').textContent = 'Please fill in all fields';
              document.getElementById('errorMessage').style.display = 'block';
              return;
            }
            
            // Show loading indicator
            document.getElementById('loadingIndicator').style.display = 'block';
            document.getElementById('errorMessage').style.display = 'none';
            document.getElementById('resultsContainer').style.display = 'none';
            
            try {
              const response = await fetch('/extract-and-create-events', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                  calendar_id: calendarId,
                  course_outline: courseOutline
                })
              });
              
              const result = await response.json();
              
              if (!response.ok) {
                throw new Error(result.detail || 'Something went wrong');
              }
              
              // Display results
              document.getElementById('extractedData').textContent = JSON.stringify(result.parsed_data, null, 2);
              
              const eventsList = document.getElementById('eventsList');
              eventsList.innerHTML = '';
              
              if (result.calendar_events && result.calendar_events.length > 0) {
                result.calendar_events.forEach(event => {
                  const li = document.createElement('li');
                  li.innerHTML = `<strong>${event.type}:</strong> ${event.name} (${event.due_date}) - <a href="${event.event_link}" target="_blank" class="event-link">View in Calendar</a>`;
                  eventsList.appendChild(li);
                });
              } else {
                eventsList.innerHTML = '<li>No events were created. Check the extracted data for any issues.</li>';
              }
              
              document.getElementById('resultsContainer').style.display = 'block';
            } catch (error) {
              document.getElementById('errorMessage').textContent = error.message;
              document.getElementById('errorMessage').style.display = 'block';
            } finally {
              document.getElementById('loadingIndicator').style.display = 'none';
            }
          });

          document.getElementById('downloadIcsBtn').addEventListener('click', async function() {
            const courseOutline = document.getElementById('course_outline').value;
            
            // Validation
            if (!courseOutline) {
              document.getElementById('errorMessage').textContent = 'Please enter your course outline';
              document.getElementById('errorMessage').style.display = 'block';
              return;
            }
            
            // Show loading indicator
            document.getElementById('loadingIndicator').style.display = 'block';
            document.getElementById('errorMessage').style.display = 'none';
            
            try {
              const response = await fetch('/generate-ics', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                  course_outline: courseOutline
                })
              });
              
              if (!response.ok) {
                const result = await response.json();
                throw new Error(result.detail || 'Something went wrong');
              }
              
              // Convert the response to blob and trigger download
              const blob = await response.blob();
              const url = window.URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = 'events.ics';
              document.body.appendChild(a);
              a.click();
              a.remove();
            } catch (error) {
              document.getElementById('errorMessage').textContent = error.message;
              document.getElementById('errorMessage').style.display = 'block';
            } finally {
              document.getElementById('loadingIndicator').style.display = 'none';
            }
          });
        </script>
      </body>
    </html>
    """
    return HTMLResponse(html_form)

# ------------------------------------------------------------------------------
#  EXTRACT & CREATE EVENTS ENDPOINT (Google Calendar API approach)
# ------------------------------------------------------------------------------
@app.post("/extract-and-create-events")
async def extract_and_create_events(request: Request):
    """
    1) Takes 'course_outline' text and 'calendar_id' from user.
    2) Calls LLM to extract dates.
    3) Creates Google Calendar events in the specified calendar.
    4) Returns success message with event links.
    """
    try:
        data = await request.json()
        course_outline = data.get("course_outline")
        calendar_id = data.get("calendar_id")
        
        if not course_outline or not calendar_id:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Log input but mask calendar ID for privacy
        masked_id = calendar_id[:3] + "***" + calendar_id[-5:] if len(calendar_id) > 8 else "***"
        logger.info(f"Processing calendar ID: {masked_id}")
        logger.info(f"Course outline length: {len(course_outline)} characters")
        
        # 1️⃣ Call LLM to extract structured data
        llm_response = extract_course_info(course_outline)
        try:
            parsed_data = json.loads(llm_response)  # Convert string to JSON
        except json.JSONDecodeError:
            logger.error(f"Invalid LLM response: {llm_response[:200]}...")
            raise HTTPException(status_code=400, detail="Could not parse LLM response as valid JSON")
        
        # Check if Google API key is available
        if not GOOGLE_API_KEY:
            raise HTTPException(status_code=500, detail="Google API key not configured")
            
        # 2️⃣ Use Google API key (for public calendar access)
        try:
            service = build("calendar", "v3", developerKey=GOOGLE_API_KEY)
        except Exception as e:
            logger.error(f"Error building Google Calendar service: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to connect to Google Calendar API: {str(e)}")
        
        # 3️⃣ Create events for extracted items
        creation_details = []
        
        # Create events for exams
        for exam in parsed_data.get("exams", []):
            event = create_calendar_event(service, exam, "Exam", calendar_id)
            if event:
                creation_details.append(event)
        
        # Create events for assignments
        for assignment in parsed_data.get("assignments", []):
            event = create_calendar_event(service, assignment, "Assignment", calendar_id)
            if event:
                creation_details.append(event)
        
        logger.info(f"Created {len(creation_details)} calendar events")
        
        return {
            "success": True,
            "parsed_data": parsed_data,
            "calendar_events": creation_details
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# ------------------------------------------------------------------------------
#  CREATE GOOGLE CALENDAR EVENT FUNCTION
# ------------------------------------------------------------------------------
def create_calendar_event(service, item_dict, item_type: str, calendar_id: str):
    """
    Creates an event in the specified Google Calendar.
    Example:
      item_dict = { "name": "Midterm Exam", "due_date": "2025-10-10" }
    """
    name = item_dict.get("name")
    due_date_str = item_dict.get("due_date")
    
    if not (name and due_date_str):
        logger.warning(f"Missing name or due_date in {item_type} data: {item_dict}")
        return None
    
    # Parse date
    try:
        dt = datetime.strptime(due_date_str, "%Y-%m-%d")
    except ValueError:
        logger.warning(f"Invalid date format: {due_date_str}")
        return None
    
    description = item_dict.get("description", "")
    
    event_body = {
        "summary": f"{item_type}: {name}",
        "description": f"Auto-generated from course outline.\n\n{description}",
        "start": {"date": dt.strftime("%Y-%m-%d")},  # All-day event
        "end": {"date": dt.strftime("%Y-%m-%d")},
        "colorId": "5" if item_type == "Exam" else "10"  # Red for exams, green for assignments
    }
    
    try:
        created_event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
        logger.info(f"Created {item_type} event: {name} on {due_date_str}")
        return {
            "type": item_type,
            "name": name,
            "due_date": due_date_str,
            "event_link": created_event.get("htmlLink")
        }
    except HttpError as e:
        error_content = json.loads(e.content.decode())
        error_message = error_content.get("error", {}).get("message", str(e))
        logger.error(f"Google Calendar API error: {error_message}")
        
        if "calendarNotFound" in error_message:
            raise HTTPException(status_code=400, detail=f"Calendar not found: {calendar_id}. Make sure it's public and the ID is correct.")
        elif "forbidden" in error_message.lower():
            raise HTTPException(status_code=403, detail="Access denied. Make sure the calendar is public and the API key has proper permissions.")
        else:
            raise HTTPException(status_code=500, detail=f"Calendar API error: {error_message}")
    except Exception as e:
        logger.error(f"Error creating event: {str(e)}")
        return None

# ------------------------------------------------------------------------------
#  iCalendar (ICS) GENERATION FUNCTIONS & ENDPOINT
# ------------------------------------------------------------------------------
def create_ics_event(event: dict) -> str:
    """
    Generates a single ICS event string for an event dictionary.
    The event dict should have keys: type, name, due_date, and optionally description.
    """
    uid = str(uuid.uuid4())
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    # For all-day events, use date format YYYYMMDD
    try:
        dtstart = datetime.strptime(event["due_date"], "%Y-%m-%d").strftime("%Y%m%d")
    except ValueError:
        dtstart = ""
    summary = f"{event.get('type', '')}: {event.get('name', '')}"
    description = event.get("description", "")
    ics_event = (
        "BEGIN:VEVENT\n"
        f"UID:{uid}\n"
        f"DTSTAMP:{dtstamp}\n"
        f"DTSTART;VALUE=DATE:{dtstart}\n"
        f"DTEND;VALUE=DATE:{dtstart}\n"
        f"SUMMARY:{summary}\n"
        f"DESCRIPTION:{description}\n"
        "END:VEVENT"
    )
    return ics_event

def create_ics_calendar(events: list) -> str:
    """
    Combines multiple ICS events into a full calendar string.
    """
    header = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Course Calendar Assistant//EN"
    footer = "END:VCALENDAR"
    events_str = "\n".join(create_ics_event(event) for event in events)
    return f"{header}\n{events_str}\n{footer}"

@app.post("/generate-ics")
async def generate_ics(request: Request):
    """
    1) Takes 'course_outline' text from user.
    2) Calls LLM to extract events.
    3) Generates an iCalendar (.ics) file with the events.
    4) Returns the .ics file for download.
    """
    try:
        data = await request.json()
        course_outline = data.get("course_outline")
        
        if not course_outline:
            raise HTTPException(status_code=400, detail="Missing course outline")
        
        logger.info(f"Generating ICS for course outline length: {len(course_outline)} characters")
        
        # Call LLM to extract structured data
        llm_response = extract_course_info(course_outline)
        try:
            parsed_data = json.loads(llm_response)
        except json.JSONDecodeError:
            logger.error("Could not parse LLM response as valid JSON")
            raise HTTPException(status_code=400, detail="Invalid LLM response format")
        
        # Combine events from exams and assignments
        events = []
        for exam in parsed_data.get("exams", []):
            if exam.get("name") and exam.get("due_date"):
                events.append({
                    "type": "Exam",
                    "name": exam.get("name"),
                    "due_date": exam.get("due_date"),
                    "description": exam.get("description", "")
                })
        for assignment in parsed_data.get("assignments", []):
            if assignment.get("name") and assignment.get("due_date"):
                events.append({
                    "type": "Assignment",
                    "name": assignment.get("name"),
                    "due_date": assignment.get("due_date"),
                    "description": assignment.get("description", "")
                })
                
        ics_content = create_ics_calendar(events)
        
        return Response(
            content=ics_content,
            media_type="text/calendar",
            headers={"Content-Disposition": "attachment; filename=events.ics"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in generate_ics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# ------------------------------------------------------------------------------
#  STATIC FILES & TEMPLATES


# ------------------------------------------------------------------------------
#  MAIN - For running with "python main.py"
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
