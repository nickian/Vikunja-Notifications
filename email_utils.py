#!/usr/bin/env python3
import os
import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template
from markupsafe import Markup

# Directory configuration
TEMPLATES_DIR = "email_templates"
PREVIEWS_DIR = "email_previews"
DEFAULT_TEMPLATE = "default.html"

# Get logger
logger = logging.getLogger("vikunja_tasks")

def format_due_date(dt):
    """Format a datetime object to look like 'Monday, April 28th at 1:00pm'"""
    # Get day suffix (st, nd, rd, th)
    day = dt.day
    if 4 <= day <= 20 or 24 <= day <= 30:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    
    # Format date and time
    weekday = dt.strftime("%A")
    month = dt.strftime("%B")
    hour = dt.strftime("%I").lstrip("0")  # Remove leading zero
    minute = dt.strftime("%M")
    ampm = dt.strftime("%p").lower()
    
    # Build the formatted string
    if minute == "00":
        time_str = f"{hour}{ampm}"  # e.g. "1pm" instead of "1:00pm" 
    else:
        time_str = f"{hour}:{minute}{ampm}"  # e.g. "1:30pm"
    
    return f"{weekday}, {month} {day}{suffix} at {time_str}"

def get_email_template(template_name=None):
    """Load the email template file"""
    # Use default template if none specified
    if template_name is None:
        template_name = DEFAULT_TEMPLATE
        
    # Ensure directories exist
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    
    # Build the template path
    template_path = os.path.join(TEMPLATES_DIR, template_name)
    
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Email template file '{template_path}' not found")
    
    with open(template_path, 'r') as f:
        return f.read()

def prepare_email_content(tasks, category_name, base_url, current_time, template_name=None):
    """Prepare the HTML content for the email"""
    template_str = get_email_template(template_name)
    template = Template(template_str)
    
    # Format the tasks for the template
    formatted_tasks = []
    for task in tasks:
        # Get the task URL
        task_id = task.get('id')
        task_url = f"{base_url.replace('/api/v1', '')}/tasks/{task_id}"
        
        # Format the due date
        formatted_due_date = format_due_date(task['due_datetime'])
        
        # Preserve HTML in the description but truncate to a reasonable length if needed
        description = task.get('description', '')
        
        # Transform task list checkboxes into bullet lists
        description = transform_checkboxes_to_bullets(description)
        
        # If description is longer than 2000 chars, truncate it and add ellipsis
        if len(description) > 2000:
            # Try to truncate at a tag end to avoid breaking HTML
            cutoff = description[:2000].rfind('</') 
            if cutoff == -1:  # No tag end found, use a space
                cutoff = description[:2000].rfind(' ')
            if cutoff == -1:  # No space found either, just use 2000
                cutoff = 2000
            description = description[:cutoff] + '...'
        
        formatted_tasks.append({
            'title': task.get('title', 'Untitled'),
            'due_date': formatted_due_date,
            'description': description,  # Keep the HTML intact
            'url': task_url
        })
    
    # Generate HTML using Markup to properly handle nested HTML
    context_text = "that are " + category_name.lower()
    
    # Mark descriptions as safe HTML in the template
    for task in formatted_tasks:
        task['description'] = Markup(task['description'])
    
    html = template.render(
        title=f"Tasks: {category_name}",
        tasks=formatted_tasks,
        context=context_text,
        generation_time=current_time.strftime('%Y-%m-%d %H:%M %Z')
    )
    
    return html

def transform_checkboxes_to_bullets(html_content):
    """Transform checkbox inputs in task lists to bullet lists with open circles"""
    import re
    
    # Convert task list to a normal list with special class
    html_content = re.sub(
        r'<ul\s+data-type="taskList"[^>]*>',
        '<ul class="checkbox-list">',
        html_content
    )
    
    # Convert task items to normal list items with appropriate styling
    html_content = re.sub(
        r'<li\s+data-checked="(true|false)"\s+data-type="taskItem"[^>]*>\s*<label[^>]*>\s*<input\s+type="checkbox"[^>]*>\s*<span[^>]*></span>\s*</label>\s*<div>',
        r'<li class="checkbox-item checkbox-\1"><div>',
        html_content
    )
    
    return html_content

def validate_email_config(args):
    """Validate email settings before sending"""
    missing = []
    
    # Check if recipient is specified when trying to send an email
    if not args.email:
        logger.error("No recipient email address specified. Use --email parameter to specify recipient.")
        return False
        
    if not args.smtp_server:
        missing.append("SMTP_SERVER")
    if not args.sender:
        missing.append("EMAIL_SENDER")
    
    if missing:
        logger.error("Missing required email configuration:")
        for var in missing:
            logger.error(f"- {var}")
        logger.error("Please set these variables in your .env file or provide them as command-line arguments.")
        return False
        
    return True

def send_email(recipient, html_content, subject, args):
    """Send an email with the tasks"""
    # Ensure preview directory exists
    os.makedirs(PREVIEWS_DIR, exist_ok=True)
    
    # Save preview if requested
    if args.save_preview:
        preview_filename = f"preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        preview_path = os.path.join(PREVIEWS_DIR, preview_filename)
        
        with open(preview_path, 'w') as f:
            f.write(html_content)
        logger.info(f"Email preview saved as {preview_path}")
    
    # If no recipient, just return after saving preview
    if not recipient:
        return
        
    # Validate email configuration
    if not validate_email_config(args):
        logger.error("Email not sent due to missing configuration.")
        return
        
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    # Set friendly From name as "Tasks" with the email address
    message["From"] = f"Tasks <{args.sender}>"
    message["To"] = recipient
    
    # Attach HTML content
    html_part = MIMEText(html_content, "html")
    message.attach(html_part)
    
    # Send email
    try:
        # Use appropriate SMTP connection based on security settings
        if args.use_ssl:
            server = smtplib.SMTP_SSL(args.smtp_server, args.smtp_port)
        else:
            server = smtplib.SMTP(args.smtp_server, args.smtp_port)
            
            # Start TLS encryption if requested
            if args.use_tls:
                server.starttls()
        
        # Optional debugging
        if args.debug:
            server.set_debuglevel(1)
        
        # Login if credentials are provided
        if args.smtp_user and args.smtp_password:
            server.login(args.smtp_user, args.smtp_password)
            
        server.sendmail(args.sender, recipient, message.as_string())
        server.quit()
        logger.info(f"Email sent to {recipient}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()

def generate_dummy_preview():
    """Generate a preview email with dummy data"""
    # Ensure directories exist
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    os.makedirs(PREVIEWS_DIR, exist_ok=True)
    
    template_str = get_email_template()
    template = Template(template_str)
    
    # Create dummy tasks
    dummy_tasks = [
        {
            'title': 'Complete project proposal',
            'due_date': 'Monday, April 29th at 2pm',
            'description': 'Finalize the project proposal document with budget estimates and timeline.',
            'url': 'https://todo.nick.place/tasks/123'
        },
        {
            'title': 'Schedule team meeting',
            'due_date': 'Tuesday, April 30th at 10am',
            'description': 'Set up weekly team sync to discuss progress and blockers.',
            'url': 'https://todo.nick.place/tasks/124'
        },
        {
            'title': 'Review client feedback',
            'due_date': 'Wednesday, May 1st at 4:30pm',
            'description': 'Go through client notes and prepare response with action items.',
            'url': 'https://todo.nick.place/tasks/125'
        }
    ]
    
    # Generate HTML
    html = template.render(
        title="Tasks: PREVIEW",
        tasks=dummy_tasks,
        context="due this week",
        generation_time=datetime.now().strftime('%Y-%m-%d %H:%M %Z')
    )
    
    # Save the preview
    preview_filename = "sample_preview.html"
    preview_path = os.path.join(PREVIEWS_DIR, preview_filename)
    
    with open(preview_path, 'w') as f:
        f.write(html)
    logger.info(f"Sample email preview saved as {preview_path}") 