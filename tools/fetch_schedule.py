#!/usr/bin/env python3
"""
Fetches the BSides Fort Wayne schedule from the website and converts it
to a format suitable for the badge app.

Usage:
    python tools/fetch_schedule.py > src/data/schedule.json
"""

import json
import re
from urllib.request import urlopen
from html.parser import HTMLParser


class ScheduleParser(HTMLParser):
    """Parse schedule from HTML table"""
    
    def __init__(self):
        super().__init__()
        self.schedule = []
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.current_row = []
        self.current_cell = []
        
    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table = True
        elif tag == "tr" and self.in_table:
            self.in_row = True
            self.current_row = []
        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True
            self.current_cell = []
    
    def handle_endtag(self, tag):
        if tag == "table":
            self.in_table = False
        elif tag == "tr" and self.in_row:
            self.in_row = False
            if self.current_row:
                self.schedule.append(self.current_row)
        elif tag in ("td", "th") and self.in_cell:
            self.in_cell = False
            self.current_row.append(" ".join(self.current_cell).strip())
    
    def handle_data(self, data):
        if self.in_cell:
            text = data.strip()
            if text:
                self.current_cell.append(text)


def fetch_schedule():
    """Fetch and parse schedule from website"""
    try:
        print("Fetching schedule from https://www.bsidesfortwayne.org/schedule/", file=__import__('sys').stderr)
        with urlopen("https://www.bsidesfortwayne.org/schedule/", timeout=10) as response:
            html = response.read().decode('utf-8')
        
        parser = ScheduleParser()
        parser.feed(html)
        
        # Convert to structured format
        schedule_data = {
            "By Time": {},
            "By Room": {},
            "By Track": {},
        }
        
        # Skip header row and process data rows
        for row in parser.schedule[1:]:
            if len(row) >= 4:
                time = row[0].strip()
                room = row[1].strip()
                title = row[2].strip()
                speaker = row[3].strip() if len(row) > 3 else ""
                
                if time and room and title:
                    # Add to "By Time"
                    schedule_data["By Time"][time] = f"{title} - {room}"
                    
                    # Add to "By Room"
                    if room not in schedule_data["By Room"]:
                        schedule_data["By Room"][room] = {}
                    schedule_data["By Room"][room][time] = title
                    
                    # Add to "By Track" if speaker info available
                    if speaker:
                        schedule_data["By Track"][title] = f"{speaker} ({room})"
        
        return schedule_data
    
    except Exception as e:
        print(f"Error fetching schedule: {e}", file=__import__('sys').stderr)
        return None


def get_embedded_schedule():
    """Fallback schedule if online fetch fails"""
    return {
        "By Time": {
            "8:00 AM - 9:00 AM": "Registration - Main Hall",
            "9:00 AM - 9:30 AM": "Opening Remarks - Keynote Room",
            "9:30 AM - 10:30 AM": "Keynote Speech - Keynote Room",
            "10:30 AM - 10:45 AM": "Break",
            "10:45 AM - 11:45 AM": "Concurrent Talks - Multiple Rooms",
            "11:45 AM - 12:45 PM": "Lunch",
            "12:45 PM - 1:45 PM": "Concurrent Talks - Multiple Rooms",
            "1:45 PM - 2:00 PM": "Break",
            "2:00 PM - 3:00 PM": "Concurrent Talks - Multiple Rooms",
            "3:00 PM - 4:00 PM": "Workshops - Multiple Rooms",
            "4:00 PM - 5:00 PM": "Closing Remarks - Keynote Room",
        },
        "By Room": {
            "Main Hall": {
                "8:00 AM": "Registration",
            },
            "Keynote Room": {
                "9:00 AM": "Opening Remarks",
                "9:30 AM": "Keynote Speech",
                "4:00 PM": "Closing Remarks",
            },
        },
        "By Track": {
            "Security Talks": "Various speakers",
            "Workshops": "Hands-on training",
            "CTF": "Capture the Flag",
        }
    }


if __name__ == "__main__":
    schedule = fetch_schedule()
    
    if schedule is None:
        print("Failed to fetch live schedule, using embedded fallback", file=__import__('sys').stderr)
        schedule = get_embedded_schedule()
    
    print(json.dumps(schedule, indent=2))
