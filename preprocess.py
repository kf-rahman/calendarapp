import re

def extract_contact_info(text):
    """
    Extracts instructor and TA information up until the specified cutoff text.
    
    Args:
        text (str): Input text to process
        
    Returns:
        str: Extracted contact information
    """
    # The cutoff text
    cutoff = "Contact for questions regarding verification of illness or"
    
    # Pattern to find instructor and contact info section
    pattern = re.compile(
        r'Instructor & TA \(Teaching Assistant\) Information(.*?)' + re.escape(cutoff),
        re.DOTALL | re.IGNORECASE
    )
    
    match = pattern.search(text)
    if match:
        return match.group(1).strip()
    return ""

def preprocess_text(text):
    """
    Preprocesses the input text by replacing '+' with spaces and decoding any percent-encoded characters.
    
    Args:
        text (str): Input text to preprocess
        
    Returns:
        str: Cleaned and decoded text
    """
    # Replace '+' with spaces
    text = text.replace('+', ' ')
    
    # Decode percent-encoded characters
    text = re.sub(r'%([0-9A-Fa-f]{2})', lambda m: chr(int(m.group(1), 16)), text)
    
    return text

def extract_academic_dates(text):
    """
    Extracts academic schedule information including assignments, tests, exams,
    and their associated dates from the text.
    
    Args:
        text (str): Input text to process
        
    Returns:
        list: List of dictionaries containing found items and their dates
    """
    text = preprocess_text(text)
    
    # Month names for pattern matching
    months = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    
    # Patterns to match different types of academic dates
    patterns = [
        # Pattern for "Assignment X" followed by date
        rf"Assignment\\s+(\\d+).*?(?:Due|Date|due|date)?\\s*(?:by|on|:)?\\s*({months}\\s+\\d{{1,2}})",
        
        # Pattern for assignments with just dates
        rf"Assignment\\s+(\\d+).*?(\\d{{1,2}}(?::\\d{{2}})?\\s*(?:a\\.m\\.|p\\.m\\.|AM|PM))",
        
        # Pattern for quiz dates
        rf"Quiz\\s+(\\d+).*?(?:Date|date)?\\s*({months}\\s+\\d{{1,2}})",
        
        # Pattern for exam dates
        rf"(?:Final\\s+)?Exam.*?(?:Date|date)?\\s*({months}\\s+\\d{{1,2}})",
        
        # Pattern for month and day combinations
        rf"(?:Due|Date|due|date)\\s*(?:by|on|:)?\\s*({months}\\s+\\d{{1,2}})"
    ]
    
    results = []
    
    # Process each pattern
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            item = {}
            groups = match.groups()
            
            # Handle different pattern matches
            if len(groups) == 2 and groups[0]:  # Assignment or Quiz number + date
                item_type = "Assignment" if "Assignment" in match.group(0) else "Quiz"
                item['type'] = item_type
                item['number'] = groups[0]
                item['date'] = groups[1]
            elif "Exam" in match.group(0):  # Exam date
                item['type'] = "Exam"
                item['date'] = groups[0]
            else:  # General due date
                item['type'] = "Due Date"
                item['date'] = groups[0]
            
            results.append(item)
    
    return results

def format_results(results):
    """
    Formats the extracted results into a readable string.
    
    Args:
        results (list): List of dictionaries containing academic dates
        
    Returns:
        str: Formatted string of results
    """
    if not results:
        return "No academic dates found in the text."
    
    formatted = []
    for item in results:
        if 'number' in item:
            formatted.append(f"{item['type']} {item['number']}: {item['date']}")
        else:
            formatted.append(f"{item['type']}: {item['date']}")
    
    return "\n".join(formatted)
