#!/usr/bin/env python3
import requests
import json
import sys
import argparse
import pytz
import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import email_utils
import mattermost_utils

# Load environment variables from .env file
load_dotenv()

# Configuration from environment variables - no fallbacks
VIKUNJA_BASE_URL = os.getenv("VIKUNJA_BASE_URL")
API_TOKEN = os.getenv("VIKUNJA_API_TOKEN")
TIMEZONE = os.getenv("TIMEZONE")

# Email configuration from environment variables - no fallbacks
DEFAULT_SENDER = os.getenv("EMAIL_SENDER")
DEFAULT_SUBJECT = os.getenv("EMAIL_SUBJECT")
DEFAULT_SMTP_SERVER = os.getenv("SMTP_SERVER")
DEFAULT_SMTP_PORT = int(os.getenv("SMTP_PORT") or "25")  # Default to 25 if missing or empty
DEFAULT_SMTP_USER = os.getenv("SMTP_USER")
DEFAULT_SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# Mattermost configuration from environment variables
DEFAULT_MATTERMOST_WEBHOOK = os.getenv("MATTERMOST_WEBHOOK_URL")
DEFAULT_MATTERMOST_USERNAME = os.getenv("MATTERMOST_USERNAME")
DEFAULT_MATTERMOST_ICON_URL = os.getenv("MATTERMOST_ICON_URL")

# Setup logger
logger = logging.getLogger("vikunja_tasks")

def setup_logging(args):
    """Configure logging based on command line arguments"""
    logger.setLevel(logging.DEBUG)  # Set base level to capture everything
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Configure console handler
    console_handler = logging.StreamHandler()
    
    if args.quiet:
        console_handler.setLevel(logging.ERROR)  # Show only errors in quiet mode
    elif args.verbose:
        console_handler.setLevel(logging.DEBUG)  # Show everything in verbose mode
    else:
        console_handler.setLevel(logging.INFO)   # Show info and above by default
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Add file handler if log file specified
    if args.log_file:
        try:
            # Create directory for log file if it doesn't exist
            log_dir = os.path.dirname(args.log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
                
            file_handler = logging.FileHandler(args.log_file)
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.INFO)  # Log info and above to file
            logger.addHandler(file_handler)
        except Exception as e:
            logger.error(f"Failed to setup log file: {e}")

def get_current_time():
    """Get the current time in the configured timezone"""
    tz = pytz.timezone(TIMEZONE or "UTC")  # Fallback to UTC only if TIMEZONE is None
    return datetime.now(tz)

def parse_arguments():
    parser = argparse.ArgumentParser(description="Fetch and filter Vikunja tasks")
    parser.add_argument("--today", action="store_true", help="Show tasks due today")
    parser.add_argument("--overdue", action="store_true", help="Show overdue tasks")
    parser.add_argument("--this_week", action="store_true", help="Show tasks due this week (Monday-Sunday)")
    parser.add_argument("--next_week", action="store_true", help="Show tasks due next week (next Monday-Sunday)")
    parser.add_argument("--all", action="store_true", help="Show all tasks with due dates")
    parser.add_argument("--upcoming", action="store_true", help="Check for tasks due in the next hour, 30 minutes, or 15 minutes")
    
    # Email options (with defaults from .env)
    parser.add_argument("--email", help="Send email to specified address")
    parser.add_argument("--smtp_server", default=DEFAULT_SMTP_SERVER, help="SMTP server address")
    parser.add_argument("--smtp_port", type=int, default=DEFAULT_SMTP_PORT, help="SMTP server port")
    parser.add_argument("--smtp_user", default=DEFAULT_SMTP_USER, help="SMTP username")
    parser.add_argument("--smtp_password", default=DEFAULT_SMTP_PASSWORD, help="SMTP password")
    parser.add_argument("--use_tls", action="store_true", default=(os.getenv("USE_TLS", "").lower() == "true"), 
                        help="Use TLS encryption for SMTP")
    parser.add_argument("--use_ssl", action="store_true", default=(os.getenv("USE_SSL", "").lower() == "true"), 
                        help="Use SSL encryption for SMTP")
    parser.add_argument("--template", default=os.getenv("EMAIL_TEMPLATE"), 
                        help="Email template to use (filename in email_templates directory)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output for SMTP")
    parser.add_argument("--sender", default=DEFAULT_SENDER, help="Email sender address")
    parser.add_argument("--subject", default=DEFAULT_SUBJECT, help="Email subject")
    parser.add_argument("--save_preview", action="store_true", help="Save email preview as HTML file")
    
    # Mattermost webhook options
    parser.add_argument("--mattermost", action="store_true", help="Send notification to Mattermost")
    parser.add_argument("--webhook_url", default=DEFAULT_MATTERMOST_WEBHOOK, 
                        help="Mattermost webhook URL")
    parser.add_argument("--webhook_username", default=DEFAULT_MATTERMOST_USERNAME, 
                        help="Mattermost webhook username")
    parser.add_argument("--webhook_icon", default=DEFAULT_MATTERMOST_ICON_URL, 
                        help="Mattermost webhook icon URL")
    
    # Logging options
    parser.add_argument("--quiet", action="store_true", help="Suppress normal output (errors still shown)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--log-file", default=os.getenv("LOG_FILE"), 
                        help="Log messages to the specified file")
    
    return parser.parse_args()

def validate_config():
    """Validate that required environment variables are set"""
    missing = []
    if not VIKUNJA_BASE_URL:
        missing.append("VIKUNJA_BASE_URL")
    if not API_TOKEN:
        missing.append("VIKUNJA_API_TOKEN")
    if not TIMEZONE:
        missing.append("TIMEZONE")
    
    if missing:
        logger.error("Missing required environment variables in .env file:")
        for var in missing:
            logger.error(f"- {var}")
        logger.error("Please create a .env file using env.template as a reference.")
        sys.exit(1)

def validate_mattermost_config(args):
    """Validate Mattermost webhook configuration"""
    if not args.webhook_url:
        logger.error("No Mattermost webhook URL specified.")
        logger.error("Set MATTERMOST_WEBHOOK_URL in your .env file or use the --webhook_url parameter.")
        return False
    return True

def get_lists():
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(f"{VIKUNJA_BASE_URL}/lists", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching lists: {e}")
        sys.exit(1)

def get_tasks(list_id=None):
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    all_tasks = []
    page = 1
    per_page = 50  # Default Vikunja page size
    total_pages = 1  # Start with assumption of at least 1 page
    
    # Determine the base URL
    if list_id:
        base_url = f"{VIKUNJA_BASE_URL}/lists/{list_id}/tasks"
    else:
        base_url = f"{VIKUNJA_BASE_URL}/tasks/all"
    
    # Get first page and determine total pages
    try:
        params = {"page": page}
        response = requests.get(base_url, headers=headers, params=params)
        response.raise_for_status()
        
        # Get total pages from header
        if 'X-Pagination-Total-Pages' in response.headers:
            total_pages = int(response.headers['X-Pagination-Total-Pages'])
            logger.debug(f"API reports {total_pages} total pages of tasks")
        
        # Process first page
        tasks = response.json()
        logger.debug(f"Retrieved page {page}/{total_pages} with {len(tasks)} tasks")
        all_tasks.extend(tasks)
        
        # Get remaining pages
        for page in range(2, total_pages + 1):
            params = {"page": page}
            response = requests.get(base_url, headers=headers, params=params)
            response.raise_for_status()
            tasks = response.json()
            logger.debug(f"Retrieved page {page}/{total_pages} with {len(tasks)} tasks")
            all_tasks.extend(tasks)
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching tasks: {e}")
        sys.exit(1)
    
    return all_tasks

def filter_tasks_with_due_dates(tasks):
    # Filter for tasks that are not done and have a valid due date
    filtered_tasks = []
    null_date = "0001-01-01T00:00:00Z"
    
    for task in tasks:
        if task.get("done") is False and task.get("due_date") != null_date:
            # Add a parsed datetime object to each task for easier categorization
            due_date = task.get("due_date")
            # Parse with timezone awareness
            task["due_datetime"] = datetime.fromisoformat(due_date.replace("Z", "+00:00")).astimezone(pytz.timezone(TIMEZONE))
            filtered_tasks.append(task)
    
    return filtered_tasks

def get_due_today_tasks(tasks):
    today = get_current_time().date()
    return [task for task in tasks if task["due_datetime"].date() == today]

def get_overdue_tasks(tasks):
    now = get_current_time()
    today = now.date()
    return [task for task in tasks if task["due_datetime"] < now]

def get_due_this_week_tasks(tasks):
    now = get_current_time()
    today = now.date()
    # Find the most recent Monday
    start_of_week = today - timedelta(days=today.weekday())
    # Find the upcoming Sunday
    end_of_week = start_of_week + timedelta(days=6)
    
    return [task for task in tasks 
            if start_of_week <= task["due_datetime"].date() <= end_of_week
            and task["due_datetime"] >= now]  # Don't include overdue tasks

def get_due_next_week_tasks(tasks):
    now = get_current_time()
    today = now.date()
    # Calculate the next Monday
    days_until_next_monday = (7 - today.weekday()) % 7
    next_monday = today + timedelta(days=days_until_next_monday)
    
    # Next week is next Monday through the following Sunday
    start_of_next_week = next_monday
    end_of_next_week = start_of_next_week + timedelta(days=6)
    
    logger.debug(f"Today is {today} (weekday {today.weekday()}) in {TIMEZONE} timezone")
    logger.debug(f"Current time is {now}")
    logger.debug(f"Next Monday is {next_monday}")
    logger.debug(f"Next week range: {start_of_next_week} to {end_of_next_week}")
    
    # Create filtered list
    next_week_tasks = []
    
    for task in tasks:
        task_date = task["due_datetime"].date()
        task_datetime = task["due_datetime"]
        is_in_range = start_of_next_week <= task_date <= end_of_next_week
        
        # Debug each task's due date and whether it falls in next week
        logger.debug(f"Task '{task.get('title')}' due on {task_datetime}, in next week range: {is_in_range}")
        
        if is_in_range:
            next_week_tasks.append(task)
    
    return next_week_tasks

def sort_tasks_by_due_date(tasks):
    """Sort tasks by due date in ascending order (oldest first)"""
    return sorted(tasks, key=lambda task: task["due_datetime"])

def display_tasks(tasks, category_name=""):
    if not tasks:
        logger.info(f"No {category_name} tasks found.")
        return
    
    # Sort tasks by due date
    sorted_tasks = sort_tasks_by_due_date(tasks)
    
    logger.info(f"\n{category_name} TASKS ({len(sorted_tasks)}):")
    
    for task in sorted_tasks:
        # Get friendly formatted date
        due_date = email_utils.format_due_date(task["due_datetime"])
        task_id = task.get('id')
        task_url = f"{VIKUNJA_BASE_URL.replace('/api/v1', '')}/tasks/{task_id}"
        
        logger.info(f"- {task.get('title', 'Untitled')} ({due_date})")
        logger.debug(f"  URL: {task_url}")
        logger.debug(f"  Description: {task.get('description', 'No description')[:100]}...")

def get_tasks_due_soon(tasks, minutes):
    """Find tasks due within the specified number of minutes"""
    now = get_current_time()
    soon = now + timedelta(minutes=minutes)
    
    logger.debug(f"Checking for tasks due between {now} and {soon} (within {minutes} minutes)")
    
    # Filter tasks due between now and soon
    due_soon = []
    for task in tasks:
        due_time = task["due_datetime"]
        # Log each task we're evaluating for debugging
        logger.debug(f"Evaluating task '{task.get('title')}' due at {due_time}")
        
        # Skip tasks that are already overdue
        if due_time < now:
            logger.debug(f"  - Skipping task as it's already overdue")
            continue
            
        # Include tasks due within the time window
        if due_time <= soon:
            # Calculate time remaining
            time_diff = due_time - now
            minutes_remaining = int(time_diff.total_seconds() / 60)
            task["minutes_remaining"] = minutes_remaining
            logger.debug(f"  + Adding task to due_soon list. Minutes remaining: {minutes_remaining}")
            due_soon.append(task)
        else:
            logger.debug(f"  - Task is due later than {minutes} minutes from now")
    
    logger.debug(f"Found {len(due_soon)} tasks due within {minutes} minutes")
    return due_soon

def format_time_remaining(minutes):
    """Format minutes into a human-readable time string"""
    if minutes < 1:
        return "less than a minute"
    elif minutes == 1:
        return "1 minute"
    elif minutes < 60:
        return f"{minutes} minutes"
    elif minutes == 60:
        return "1 hour"
    else:
        hours = minutes // 60
        mins = minutes % 60
        if mins == 0:
            return f"{hours} hours"
        else:
            return f"{hours} hours and {mins} minutes"

def main():
    # Parse args first
    args = parse_arguments()
    
    # Setup logging
    setup_logging(args)
    
    # Validate configuration before proceeding
    validate_config()
    
    # Generate dummy preview if requested (no API call needed)
    if args.save_preview and not any([args.today, args.overdue, args.this_week, args.next_week, args.all, args.upcoming]):
        email_utils.generate_dummy_preview()
        return
    
    logger.info("Fetching tasks from Vikunja...")
    
    # Try to get all tasks first
    all_tasks = get_tasks()
    
    # If that fails, try getting lists and then tasks for each list
    if not all_tasks:
        all_tasks = []
        lists = get_lists()
        logger.info(f"Retrieved {len(lists)} lists.")
        
        for task_list in lists:
            list_id = task_list.get("id")
            list_name = task_list.get("title")
            logger.info(f"Fetching tasks from list: {list_name} (ID: {list_id})...")
            
            list_tasks = get_tasks(list_id)
            all_tasks.extend(list_tasks)
    
    logger.info(f"Retrieved {len(all_tasks)} tasks total.")
    
    # Get all tasks with due dates
    tasks_with_due_dates = filter_tasks_with_due_dates(all_tasks)
    logger.info(f"Found {len(tasks_with_due_dates)} tasks with valid due dates.")
    
    # Handle upcoming tasks check
    if args.upcoming:
        # Time thresholds to check (in minutes)
        thresholds = [15, 30, 60]  # 15 min, 30 min, 1 hour
        notified_tasks = set()  # Track which tasks we've already notified about
        
        logger.info(f"Checking for tasks due soon at {get_current_time()}")
        
        # Check for tasks due within each threshold
        for minutes in thresholds:
            tasks_due_soon = get_tasks_due_soon(tasks_with_due_dates, minutes)
            
            # Send individual notifications for each task
            for task in tasks_due_soon:
                task_id = task.get('id', '')
                
                # If we've already notified about this task in a smaller threshold, skip it
                if task_id in notified_tasks:
                    logger.debug(f"Already notified about task {task_id}, skipping")
                    continue
                
                # Calculate remaining time and determine if we should notify
                remaining = task["minutes_remaining"]
                
                # More lenient threshold check:
                # For 15 min threshold: notify if 5-20 minutes remaining
                # For 30 min threshold: notify if 20-40 minutes remaining
                # For 60 min threshold: notify if 45-75 minutes remaining
                should_notify = False
                
                if minutes == 15 and 0 <= remaining <= 20:
                    should_notify = True
                elif minutes == 30 and 20 < remaining <= 40:
                    should_notify = True
                elif minutes == 60 and 40 < remaining <= 75:
                    should_notify = True
                
                if not should_notify:
                    logger.debug(f"Task '{task.get('title')}' with {remaining} minutes remaining doesn't match threshold {minutes}")
                    continue
                    
                # Add to notified set to prevent duplicates
                notified_tasks.add(task_id)
                
                time_str = format_time_remaining(remaining)
                task_title = task.get("title", "Untitled")
                
                logger.info(f"Task '{task_title}' is due in {time_str}")
                
                # Send email notification if requested
                if args.email:
                    subject = f"Task due in {time_str}: {task_title}"
                    # Format a single task for the email
                    html = email_utils.prepare_email_content(
                        [task],  # Send just this one task
                        f"DUE IN {time_str.upper()}",
                        VIKUNJA_BASE_URL,
                        get_current_time(),
                        args.template
                    )
                    email_utils.send_email(args.email, html, subject, args)
                
                # Send Mattermost notification if requested
                if args.mattermost and validate_mattermost_config(args):
                    # Notify about just this one task
                    task_list = [task]
                    mattermost_utils.send_webhook_notification(
                        task_list,
                        f"DUE IN {time_str.upper()}",
                        VIKUNJA_BASE_URL,
                        args.webhook_url,
                        args.webhook_username,
                        args.webhook_icon
                    )
        
        # Exit after checking upcoming tasks
        return
    
    # If no task filters specified or --all flag, show all tasks with due dates
    if not any([args.today, args.overdue, args.this_week, args.next_week]) or args.all:
        display_tasks(tasks_with_due_dates, "ALL PENDING")
        
        # Send email if requested
        if args.email or args.save_preview:
            html = email_utils.prepare_email_content(
                sort_tasks_by_due_date(tasks_with_due_dates), 
                "ALL PENDING",
                VIKUNJA_BASE_URL,
                get_current_time(),
                args.template
            )
            email_utils.send_email(args.email, html, args.subject, args)
            
        # Send Mattermost notification if requested
        if args.mattermost and validate_mattermost_config(args):
            mattermost_utils.send_webhook_notification(
                sort_tasks_by_due_date(tasks_with_due_dates),
                "ALL PENDING",
                VIKUNJA_BASE_URL,
                args.webhook_url,
                args.webhook_username,
                args.webhook_icon
            )
            
        return
    
    # Handle each filter option, displaying results and sending emails as requested
    if args.today:
        due_today = get_due_today_tasks(tasks_with_due_dates)
        display_tasks(due_today, "DUE TODAY")
        
        # Send email if requested
        if args.email or args.save_preview:
            html = email_utils.prepare_email_content(
                sort_tasks_by_due_date(due_today), 
                "DUE TODAY",
                VIKUNJA_BASE_URL,
                get_current_time(),
                args.template
            )
            email_utils.send_email(args.email, html, args.subject, args)
            
        # Send Mattermost notification if requested
        if args.mattermost and validate_mattermost_config(args):
            mattermost_utils.send_webhook_notification(
                sort_tasks_by_due_date(due_today),
                "DUE TODAY",
                VIKUNJA_BASE_URL,
                args.webhook_url,
                args.webhook_username,
                args.webhook_icon
            )
    
    if args.overdue:
        overdue = get_overdue_tasks(tasks_with_due_dates)
        display_tasks(overdue, "OVERDUE")
        
        # Send email if requested
        if args.email or args.save_preview:
            html = email_utils.prepare_email_content(
                sort_tasks_by_due_date(overdue), 
                "OVERDUE",
                VIKUNJA_BASE_URL,
                get_current_time(),
                args.template
            )
            email_utils.send_email(args.email, html, args.subject, args)
            
        # Send Mattermost notification if requested
        if args.mattermost and validate_mattermost_config(args):
            mattermost_utils.send_webhook_notification(
                sort_tasks_by_due_date(overdue),
                "OVERDUE",
                VIKUNJA_BASE_URL,
                args.webhook_url,
                args.webhook_username,
                args.webhook_icon
            )
    
    if args.this_week:
        due_this_week = get_due_this_week_tasks(tasks_with_due_dates)
        display_tasks(due_this_week, "DUE THIS WEEK")
        
        # Send email if requested
        if args.email or args.save_preview:
            html = email_utils.prepare_email_content(
                sort_tasks_by_due_date(due_this_week), 
                "DUE THIS WEEK",
                VIKUNJA_BASE_URL,
                get_current_time(),
                args.template
            )
            email_utils.send_email(args.email, html, args.subject, args)
            
        # Send Mattermost notification if requested
        if args.mattermost and validate_mattermost_config(args):
            mattermost_utils.send_webhook_notification(
                sort_tasks_by_due_date(due_this_week),
                "DUE THIS WEEK",
                VIKUNJA_BASE_URL,
                args.webhook_url,
                args.webhook_username,
                args.webhook_icon
            )
    
    if args.next_week:
        due_next_week = get_due_next_week_tasks(tasks_with_due_dates)
        display_tasks(due_next_week, "DUE NEXT WEEK")
        
        # Send email if requested
        if args.email or args.save_preview:
            html = email_utils.prepare_email_content(
                sort_tasks_by_due_date(due_next_week), 
                "DUE NEXT WEEK",
                VIKUNJA_BASE_URL,
                get_current_time(),
                args.template
            )
            email_utils.send_email(args.email, html, args.subject, args)
            
        # Send Mattermost notification if requested
        if args.mattermost and validate_mattermost_config(args):
            mattermost_utils.send_webhook_notification(
                sort_tasks_by_due_date(due_next_week),
                "DUE NEXT WEEK",
                VIKUNJA_BASE_URL,
                args.webhook_url,
                args.webhook_username,
                args.webhook_icon
            )

if __name__ == "__main__":
    main() 