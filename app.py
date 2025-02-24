from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import secrets
import json
from datetime import datetime
from preprocess import extract_academic_dates, format_results

# Import your LLM extraction function from the separate script
from llm import extract_course_info

app = FastAPI()

# ------------------------------------------------------------------------------
#  GOOGLE CALENDAR OAUTH CONFIG
# ------------------------------------------------------------------------------
GOOGLE_CLIENT_ID = "660092035334-la4adf80u92fegr8bkompqn6tb3mlm30.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"
REDIRECT_URI = "http://localhost:8000/oauth2callback"
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# In-memory token storage (demo only)
user_tokens = {}

def get_flow(state=None):
    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        state=state
    )

# ------------------------------------------------------------------------------
#  HOME: Show "Login with Google" button if not logged in
#        or "Create Event" button if user is authenticated.
# ------------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    user_id = "demo_user"
    if user_id not in user_tokens:
        html_content = """
        <html>
          <head><title>Google Calendar OAuth Demo</title></head>
          <body>
            <h1>Welcome to the Google Calendar OAuth Demo!</h1>
            <p>You are not logged in. Please log in with Google:</p>
            <form action="/login" method="get">
                <button type="submit">Login with Google</button>
            </form>
          </body>
        </html>
        """
    else:
        html_content = """
        <html>
          <head><title>Google Calendar OAuth Demo</title></head>
          <body>
            <h1>You are logged in!</h1>
            <p>Click the button below to create a sample event in your Google Calendar.</p>
            <form action="/create_event" method="post">
                <button type="submit">Create Event</button>
            </form>
            <p>Or <a href="/extract-dates-ui">Extract & Create Multiple Events</a> from your text.</p>
          </body>
        </html>
        """
    return HTMLResponse(content=html_content)

# ------------------------------------------------------------------------------
#  LOGIN: Step 1 - Redirect user to Google's OAuth 2.0 server
# ------------------------------------------------------------------------------
@app.get("/login")
def login():
    state = secrets.token_hex(16)
    flow = get_flow(state)
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    return RedirectResponse(authorization_url)

# ------------------------------------------------------------------------------
#  OAUTH2 CALLBACK: Step 2 - Exchange code for tokens
# ------------------------------------------------------------------------------
@app.get("/oauth2callback")
def oauth2callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="No code parameter returned by Google")

    state = request.query_params.get("state")
    flow = get_flow(state)
    flow.fetch_token(code=code)
    creds = flow.credentials

    user_id = "demo_user"
    user_tokens[user_id] = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
        "expiry": creds.expiry.isoformat() if creds.expiry else None
    }

    return RedirectResponse(url="/")

# ------------------------------------------------------------------------------
#  CREATE A SAMPLE EVENT
# ------------------------------------------------------------------------------
@app.post("/create_event")
def create_event():
    user_id = "demo_user"
    if user_id not in user_tokens:
        raise HTTPException(status_code=401, detail="User not authenticated")

    creds = rebuild_credentials(user_tokens[user_id])
    service = build("calendar", "v3", credentials=creds)

    event_body = {
        "summary": "FastAPI Test Event",
        "start": {
            "dateTime": "2025-01-15T09:00:00-05:00",
            "timeZone": "America/New_York",
        },
        "end": {
            "dateTime": "2025-01-15T10:00:00-05:00",
            "timeZone": "America/New_York",
        },
        "description": "Created from FastAPI!",
    }

    created_event = service.events().insert(calendarId="primary", body=event_body).execute()

    return {
        "message": "Event created successfully!",
        "event_link": created_event.get("htmlLink")
    }

# ------------------------------------------------------------------------------
#  ADDITIONAL HELPERS
# ------------------------------------------------------------------------------
def rebuild_credentials(token_data: dict) -> Credentials:
    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data["refresh_token"],
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data["scopes"]
    )
    if not creds.valid and creds.refresh_token:
        creds.refresh(requests=None)
    return creds

# ------------------------------------------------------------------------------
#  UI FORM to input course outline text
# ------------------------------------------------------------------------------
@app.get("/extract-dates-ui", response_class=HTMLResponse)
def extract_dates_ui():
    user_id = "demo_user"
    if user_id not in user_tokens:
        return HTMLResponse("""
        <html>
          <body>
            <h2>Please <a href='/'>log in</a> first to use this feature.</h2>
          </body>
        </html>
        """)

    # Updated form with enctype
    html_form = """
<html>
  <head>
    <title>Extract Course Dates</title>
  </head>
  <body>
    <h1>Extract Course Dates & Create Calendar Events</h1>
    <form action="/extract-and-create-events" method="post" enctype="text/plain">
      <textarea 
        name="course_outline" 
        rows="10" 
        cols="60" 
        placeholder="Paste your course outline here..." 
        style="white-space: pre-wrap; overflow-wrap: break-word;">
      </textarea><br><br>
      <input type="submit" value="Extract & Create Events">
    </form>
  </body>
</html>

    """
    return HTMLResponse(html_form)


# ------------------------------------------------------------------------------
#  EXTRACT & CREATE EVENTS ENDPOINT
# ------------------------------------------------------------------------------
@app.post("/extract-and-create-events")
def extract_and_create_events(course_outline: str = Body(..., embed=False)):
    """
    1) Takes 'course_outline' text from user
    2) Calls LLM (extract_course_info) to parse dates
    3) Tries to parse returned JSON
    4) Creates Google Calendar events (exams, assignments)
    5) Returns success with details
    """
    print(f"Received course outline: {course_outline}")
    user_id = "demo_user"
    if user_id not in user_tokens:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    
    #smaller_outline = extract_academic_dates(course_outline)
    #print(smaller_outline)
    #formated_outline = format_results(smaller_outline)
    #print(formated_outline)
    import re
    llm_response = extract_course_info(course_outline)
    cleaned_json_string = re.sub(r"^``json\\s*|\\s*```$", "", llm_response, flags=re.MULTILINE)
    print(cleaned_json_string)
    print('test',type(cleaned_json_string))
    parsed_data = [llm_response]

    # Create calendar events for extracted items
    creds = rebuild_credentials(user_tokens[user_id])
    service = build("calendar", "v3", credentials=creds)

    creation_details = []

    # Exams
    exams = parsed_data.get("exams", [])
    for exam in exams:
        event = create_calendar_event(service, exam, "Exam")
        if event:
            creation_details.append(event)

    # Assignments
    assignments = parsed_data.get("assignments", [])
    for assignment in assignments:
        event = create_calendar_event(service, assignment, "Assignment")
        if event:
            creation_details.append(event)

    return {
        "success": True,
        "parsed_data": parsed_data,
        "calendar_events": creation_details
    }

def create_calendar_event(service, item_dict, item_type: str):
    """
    Example: item_dict = { "name": "Midterm Exam", "due_date": "2025-10-10" }
    Create an all-day event on 'due_date'.
    """
    name = item_dict.get("name")
    due_date_str = item_dict.get("due_date")
    if not (name and due_date_str):
        return None

    # parse date
    try:
        dt = datetime.strptime(due_date_str, "%Y-%m-%d")
    except ValueError:
        return None

    event_body = {
        "summary": f"{item_type}: {name}",
        "description": f"Auto-generated from LLM.\n{item_dict}",
        "start": {
            "date": dt.strftime("%Y-%m-%d"),  # all-day event
        },
        "end": {
            "date": dt.strftime("%Y-%m-%d"),
        },
    }

    created_event = service.events().insert(calendarId="primary", body=event_body).execute()
    return {
        "type": item_type,
        "name": name,
        "due_date": due_date_str,
        "event_link": created_event.get("htmlLink")
    }
