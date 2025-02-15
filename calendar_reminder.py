#!/usr/bin/python3
import smtplib
import pytz
import os
import requests
import re
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate
from datetime import datetime, timedelta, date
from icalendar import Calendar
from dateutil import rrule, parser
from decouple import config
import urllib3

# SSL-Warnungen unterdrücken
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Konfigurations-ENV abrufen
smtp_server = config('SMTP_HOST')
smtp_port = config('SMTP_PORT', cast=int)
smtp_username = config('SMTP_USERNAME')
smtp_password = config('SMTP_PASSWORD')
sender_email = config('SENDER_EMAIL')
sender_name = config('SENDER_NAME')
to_email = config('RECEIVER_EMAIL')
tracking_file_path = config('TRACKING_FILE_PATH', default='tracking_file.txt')
template_file_path = config('TEMPLATE_REMINDER_PATH', default='template_reminder.html')
LOCAL_TIMEZONE = pytz.timezone(config('TIMEZONE', default='Europe/Berlin'))
DATE_FORMAT = config("DATE_FORMAT", default='%d.%m.%Y ⋅ %H:%M Uhr') # US-Format: '%m/%d/%Y ⋅ %I:%M %p'
language = config('LANGUAGE', default='EN')

# Test-Mode aktivieren (True) oder deaktivieren (False)
TEST_MODE = False

# Intervall für die Bereinigung des Tracking-Files
cleanup_interval_hours = 48

# Wörterbuch für die Texte
texts = {
    'DE': {
        'subject': "Benachrichtigung:",
        'header': "Termin-Erinnerung",
        'event': "Termin:",
        'start': "Start:",
        'end': "Ende:",
        'location1': "Ort:",
        'description1': "Beschreibung:",
        'organizer1': "Organisator:",
        'attendee1': "Teilnehmer:",
        'footer': "Diese E-Mail wurde automatisch generiert. Bitte nicht antworten."
    },
    'EN': {
        'subject': "Notification:",
        'header': "Event Reminder",
        'event': "Event:",
        'start': "Start:",
        'end': "End:",
        'location1': "Location:",
        'description1': "Description:",
        'organizer1': "Organizer:",
        'attendee1': "Attendees:",
        'footer': "This email was automatically generated. Please do not reply."
    }
}

# Wähle die Texte basierend auf der Sprache aus
selected_texts = texts.get(language, texts['EN'])  # Fallback auf Englisch, wenn die Sprache nicht gefunden wird

def save_html_to_file(body):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    with open(f"calendar_reminder_{timestamp}.html", "w") as file:
        file.write(body)
    print("HTML-Datei erfolgreich gespeichert.")

# Funktion zum Senden einer E-Mail
def send_email(sender_name, sender_email, subject, body, to_email):
    if TEST_MODE:
        save_html_to_file(body)
    else:
        msg = MIMEText(body, 'html')
        msg['Subject'] = subject
        msg['From'] = formataddr((sender_name, sender_email))
        msg['To'] = to_email
        msg['Date'] = formatdate(localtime=True)

        try:
            if smtp_port == 587:
                # Verwende STARTTLS für Port 587
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.starttls() 
                    server.login(smtp_username, smtp_password)
                    server.sendmail(sender_email, to_email, msg.as_string())
            else:
                # Verwende SSL für alle anderen Ports
                with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
                    server.login(smtp_username, smtp_password)
                    server.sendmail(sender_email, to_email, msg.as_string())
            print("E-Mail erfolgreich verschickt.")
        except Exception as e:
            print(f"Fehler beim Versenden der E-Mail: {e}")

def convert_until_to_datetime(rrule_dict, timezone):
    if "UNTIL" in rrule_dict:
        until_values = rrule_dict["UNTIL"]
        for i, value in enumerate(until_values):
            #print(f"UNTIL-Wert vor der Verarbeitung: {value} (Typ: {type(value)})")  # Debugging
            try:
                if isinstance(value, str):
                    # Wenn der UNTIL-Wert ein String ist, konvertiere ihn
                    if len(value) == 10:  # YYYY-MM-DD
                        until_date = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone)
                    else:
                        until_date = parser.parse(value).astimezone(timezone)
                elif isinstance(value, datetime):
                    # Wenn der UNTIL-Wert bereits ein datetime-Objekt ist, überspringen
                    until_date = value
                elif isinstance(value, date):  # Überprüfung auf datetime.date
                    # Wenn der UNTIL-Wert ein datetime.date-Objekt ist, konvertiere es in datetime
                    until_date = datetime.combine(value, datetime.min.time(), tzinfo=timezone)
                else:
                    print(f"Unbekannter UNTIL-Wert: {value} (Typ: {type(value)})")
                    continue

                # Setze den konvertierten UNTIL-Wert zurück
                rrule_dict["UNTIL"][i] = until_date
            except Exception as e:
                print(f"Fehler beim Konvertieren des UNTIL-Werts: {value}, Fehler: {e}")

def generate_recurring_events(start_date, rule, until=None):
    start_date = start_date.astimezone(LOCAL_TIMEZONE)

    if until:
        until = until.astimezone(LOCAL_TIMEZONE)

    try:
        rrule_set = rrule.rrulestr(rule, dtstart=start_date)
    except Exception as e:
        print(f"Error parsing RRULE: {e}")
        return []

    events = []
    for event_date in rrule_set:
        if until and event_date > until:
            break
        events.append(event_date)

    return events

# Funktion zum Extrahieren der tatsächlichen Alarmzeit
def extract_last_ack_time(component, timezone):
    last_ack_str = component.get("ACKNOWLEDGED") or component.get("X-MOZ-LASTACK")
    if last_ack_str:
        # Überprüfe auf den speziellen Wert
        if last_ack_str == "99991231T235859Z":
            return "99991231T235859Z"  # Oder eine andere geeignete Rückgabe, je nach Bedarf

        try:
            # Versuche, das Datum zu parsen
            last_ack_time = datetime.strptime(last_ack_str, "%Y%m%dT%H%M%S%z")
            # Konvertiere in die gewünschte Zeitzone
            return last_ack_time.astimezone(timezone)
        except ValueError as e:
            print(f"Fehler beim Parsen des Datums: {e}")
        except OverflowError as e:
            print(f"OverflowError: {e} - Überprüfe den Wert von last_ack_str: {last_ack_str}")
    return None

# Funktion zum Generieren des E-Mail-Body mit HTML-Template
def generate_email_body(summary, formatted_start_date, formatted_end_date, location, description, organizer, attendee):
    with open(template_file_path, 'r') as template_file:
        template = template_file.read()

    # Sicherstellen, dass description ein String ist
    # if isinstance(description, list):
        # description = "\n".join(description)  # Liste in einen String umwandeln

    # Sicherstellen, dass attendee ein String ist
    if isinstance(attendee, list):
        attendee = ", ".join(attendee)  # Liste in einen String umwandeln

    # Convert newlines to <br> for HTML
    description_html = description.replace('\n', '<br>')

    body = template.replace("{{lang}}", "de" if language == "DE" else "en")\
                   .replace("{{summary}}", summary)\
                   .replace("{{formatted_start_date}}", formatted_start_date)\
                   .replace("{{formatted_end_date}}", formatted_end_date)\
                   .replace("{{location}}", location)\
                   .replace("{{description}}", description_html)\
                   .replace("{{organizer}}", organizer)\
                   .replace("{{attendee}}", attendee)\
                   .replace("{{header}}", selected_texts['header'])\
                   .replace("{{event}}", selected_texts['event'])\
                   .replace("{{start}}", selected_texts['start'])\
                   .replace("{{end}}", selected_texts['end'])\
                   .replace("{{location1}}", selected_texts['location1'])\
                   .replace("{{description1}}", selected_texts['description1'])\
                   .replace("{{organizer1}}", selected_texts['organizer1'])\
                   .replace("{{attendee1}}", selected_texts['attendee1'])\
                   .replace("{{footer}}", selected_texts['footer'])
    return body

# Funktion zum Bereinigen des Tracking-Files
def cleanup_tracking_file():
    now = datetime.now(LOCAL_TIMEZONE)
    cutoff_time = now - timedelta(hours=cleanup_interval_hours)
    kept_lines = []

    if os.path.exists(tracking_file_path):
        with open(tracking_file_path, 'r') as f:
            lines = f.readlines()

        for i in range(0, len(lines), 2):
            timestamp_str = lines[i].strip()
            tracking_data = lines[i + 1].strip()
            try:
                timestamp = datetime.fromisoformat(timestamp_str).astimezone(LOCAL_TIMEZONE)
                if timestamp >= cutoff_time and tracking_data not in kept_lines:
                    kept_lines.append(lines[i])
                    kept_lines.append(lines[i + 1])
            except ValueError:
                print(f"Ungültiger Zeitstempel: {timestamp_str}, überspringen.")

        with open(tracking_file_path, 'w') as f:
            f.writelines(kept_lines)

# Funktion zum Überprüfen von anstehenden Terminen und Senden von Erinnerungen
def check_and_send_reminders():
    ics_urls = config('ICS_URLS').split(',')
    now = datetime.now(LOCAL_TIMEZONE)
    max_emails_per_run = 10
    sent_emails_count = 0
    time_lower_bound = -86400  # Prüfung Events in den vergangenen 24 Stunden - Angabe in Sekunden
    time_upper_bound = 1800    # Prüfung Events in den nächsten 30 Minuten - Angabe in Sekunden

    reminded_events = set()
    if os.path.exists(tracking_file_path):
        with open(tracking_file_path, 'r') as tracking_file:
            lines = tracking_file.readlines()
            for i in range(0, len(lines), 2):
                reminded_events.add(lines[i + 1].strip())

    with open(tracking_file_path, 'a') as tracking_file:
        for ics_url in ics_urls:
            response = requests.get(ics_url, verify=False)
            if response.status_code != 200:
                print(f"Fehler beim Abrufen der ICS-Datei ({ics_url}): {response.status_code}")
                continue

            calendar = Calendar.from_ical(response.content)
            calendar_name = calendar.get('X-WR-CALNAME', 'Unbekannter Kalender')
            for component in calendar.walk():
                if component.name == "VEVENT":
                    event_id = component.get("UID")

                    # Extrahiere die relevanten Felder für die E-Mail
                    summary = component.get("SUMMARY")
                    description = component.get("DESCRIPTION", "")
                    location = component.get("LOCATION", "")
                    organizer = component.get("ORGANIZER", "")
                    attendee = component.get("ATTENDEE", "")

                    dtstart_str = component.get("DTSTART").to_ical().decode('utf-8')
                    event_start = parser.parse(dtstart_str).astimezone(LOCAL_TIMEZONE)
                    event_end = event_start + timedelta(hours=1)

                    # Falls DTEND vorhanden ist, verwenden
                    if "DTEND" in component:
                        dtend_str = component.get("DTEND").to_ical().decode('utf-8')
                        event_end = parser.parse(dtend_str).astimezone(LOCAL_TIMEZONE)

                    # Serientermine prüfen
                    recurring_events = []
                    if "RRULE" in component:
                        rrule_dict = component.get("RRULE")

                        convert_until_to_datetime(rrule_dict, LOCAL_TIMEZONE)

                        rrule_parts = []

                        for key, values in rrule_dict.items():
                            if key == "UNTIL" and isinstance(values[0], datetime):
                                #print(f"Original UNTIL: {values[0]} (tzinfo={values[0].tzinfo})")  # Debugging
                                values = [values[0].astimezone(LOCAL_TIMEZONE).strftime("%Y%m%dT%H%M%SZ")]
                                #print(f"Converted UNTIL (UTC): {values[0]}")  # Debugging

                            rrule_parts.append(f"{key}={','.join(str(value) for value in values)}")

                        rrule_str = "RRULE:" + ";".join(rrule_parts)

                        #print(f"Final RRULE String: {rrule_str}")  # Debugging
                        recurring_events = generate_recurring_events(event_start, rrule_str, until=now + timedelta(seconds=time_upper_bound))
                        #print(f"Geprüfte Events für {summary} ({event_id}): {recurring_events}")
                    else:
                        recurring_events.append(event_start)

                    # Trigger-Wert aus VALARM extrahieren
                    trigger = None
                    for alarm in component.subcomponents:
                        if alarm.name == "VALARM":
                            trigger_value = alarm.get("TRIGGER")
                            if trigger_value:
                                trigger = trigger_value.to_ical().decode('utf-8')

                    for event_date in recurring_events:
                        event_start = event_date
                        # Überprüfen, ob es sich um einen ganztägigen Termin handelt
                        if event_start.time() == datetime.min.time() and event_end.time() == datetime.min.time():
                            # Ganztägiger Termin: Setze das Enddatum auf den nächsten Tag
                            event_end = event_start + timedelta(days=1)
                        else:
                            # Bestehende Logik für andere Termine
                            if event_end < event_start:
                                event_end = event_end.replace(year=event_start.year, month=event_start.month, day=event_start.day)

                        # Überprüfen, ob das Enddatum in der Vergangenheit liegt
                        #if event_end < event_start:
                            #event_end = event_end.replace(year=event_start.year, month=event_start.month, day=event_start.day)

                        if trigger:
                            match = re.match(r"(-?)P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?", trigger)
                            if match:
                                is_negative = match.group(1) == "-"
                                days = int(match.group(2)) if match.group(2) else 0
                                hours = int(match.group(3)) if match.group(3) else 0
                                minutes = int(match.group(4)) if match.group(4) else 0
                                multiplier = -1 if is_negative else 1
                                trigger_timedelta = timedelta(days=multiplier * days, hours=multiplier * hours, minutes=multiplier * minutes)
                                time_until_event = event_start + trigger_timedelta - now + timedelta(seconds=time_upper_bound)
                            else:
                                #print(f"Ungültiges Trigger-Format: {trigger}! Ignoriere Trigger.") # Debugging
                                last_ack_time = extract_last_ack_time(component, LOCAL_TIMEZONE)
                                if not last_ack_time or last_ack_time == "99991231T235859Z":
                                    time_until_event = event_start - now
                                else:
                                    time_until_event = last_ack_time - now
                        else:
                            time_until_event = event_start - now

                        if time_lower_bound <= time_until_event.total_seconds() <= time_upper_bound:
                            formatted_start_date = event_start.strftime(DATE_FORMAT)
                            formatted_end_date = event_end.strftime(DATE_FORMAT)

                            tracking_entry = f"{event_id}|{summary}|{formatted_start_date}|{formatted_end_date}|{location}"

                            if tracking_entry not in reminded_events:
                                subject = f"{selected_texts['subject']} {summary} - {formatted_start_date} ({calendar_name})"
                                body = generate_email_body(summary, formatted_start_date, formatted_end_date, location, description, organizer, attendee)

                                if sent_emails_count < max_emails_per_run:
                                    send_email(sender_name, sender_email, subject, body, to_email)
                                    tracking_file.write(f"{now.isoformat()}\n{tracking_entry}\n")
                                    reminded_events.add(tracking_entry)
                                    sent_emails_count += 1

if __name__ == "__main__":
    cleanup_tracking_file()
    check_and_send_reminders()
