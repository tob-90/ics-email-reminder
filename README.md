# Calendar Reminder Script

## Overview
This Python script fetches events from one or more iCalendar (ICS) sources and sends reminder emails. 
It was specifically developed for Radicale, but it also works with other services such as Google Calendar.
It supports recurring events, custom reminder times, and tracking of already sent reminders.

![calendar_reminder](https://github.com/user-attachments/assets/d3d284b1-4328-475a-b211-7a942eea8d12)

## Features
- Automatically retrieves events from ICS files
- Sends email notifications using HTML templates
- Supports recurring events (RRULE)
- Tracks sent reminders to avoid duplicate emails
- Simple configurable via a single `.env` file
- Multi-language (german/english)

## Installation
### Requirements
This script requires Python 3 and the following dependencies:

```bash
pip install smtplib pytz requests icalendar python-decouple dateutil
```

### Setup
1. Copy the file `calendar_reminder.py` to a folder of your choice.
2. Copy the HTML template file `template_reminder.html` for email notifications to a folder of your choice.
3. Create a `.env` file with __at least__ the following parameters:
   
   ```ini
   SMTP_HOST = '<Your SMTP server>'
   SMTP_PORT = '<Your SMTP port>'
   SMTP_USERNAME = '<Your SMTP username>'
   SMTP_PASSWORD = '<Your SMTP password>'
   SENDER_EMAIL = '<Your sender email>'
   SENDER_NAME = '<Your name>'
   RECEIVER_EMAIL = '<Recipient email>'
   ICS_URLS = '<Comma-separated list of ICS URLs>'
   TEMPLATE_REMINDER_PATH = '/path/to/template_reminder.html'
   ```
4. Secure the `.env` file by restricting permissions:
   ```bash
   chmod 600 .env
   ```  
5. Make the script executable:
   ```bash
   chmod +x calendar_reminder.py
   ```

## Usage
### Automated Execution with Cronjob (Recommended) 
To run the script automatically at a set interval (e.g., every 30 minutes), add a Cronjob:

1. Open the Crontab editor:
   ```bash
   crontab -e
   ```
2. Add the following line to execute the script every 30 minutes:
   ```bash
   */30 * * * * /usr/bin/python3 /path/to/calendar_reminder.py
   ```
   Ensure the correct path to Python and the script is used.

### Manual Execution
Run the script with:
```bash
python3 calendar_reminder.py
```

## Customization
- **TEST_MODE:** For testing purposes, set `TEST_MODE = True` within the script to save emails locally as HTML files instead of sending them.

### Additional `.env` Parameters
| Parameter               | Description                          | Example Value             | Default Value           |
|-------------------------|--------------------------------------|---------------------------|-------------------------|
| `TIMEZONE`             | Timezone for event processing       | `Europe/Berlin`, `UTC`           | `Europe/Berlin`                   |
| `DATE_FORMAT`          | Date format for reminders           | `%d.%m.%Y ⋅ %H:%M Uhr`, `%m/%d/%Y ⋅ %I:%M %p`    | `%d.%m.%Y ⋅ %H:%M Uhr`     |
| `LANGUAGE`            | Language setting (`EN` or `DE`)     | `EN`, `DE`                       | `EN`                    |
| `TRACKING_FILE_PATH`   | Path to save the tracking file           | `/path/to/tracking_file.txt`       | `tracking_file.txt`     |

## Disclaimer
This script is provided "as is," without any warranties or guarantees. The author is not responsible for any data loss, missed reminders, or unintended consequences resulting from the use of this script. Users are responsible for configuring and testing the script to ensure it meets their needs. Use at your own risk.
