#!/usr/bin/env python3
import json
import requests
import logging
from datetime import datetime
import email_utils  # To use the same date formatting function

# Get logger
logger = logging.getLogger("vikunja_tasks")

def send_webhook_notification(tasks, category_name, base_url, webhook_url, username=None, icon_url=None):
    """Send a notification to Mattermost webhook"""
    if not webhook_url:
        logger.error("No Mattermost webhook URL specified.")
        return False
    
    # Check if we have any tasks to notify about
    if not tasks:
        logger.info("No tasks to send to Mattermost webhook.")
        return True
    
    # Count tasks
    task_count = len(tasks)
    
    # Sort tasks by due date
    sorted_tasks = sorted(tasks, key=lambda task: task.get('due_datetime'))
    
    # Create message content with a Markdown bulleted list
    message = f"### You have {task_count} task{'s' if task_count != 1 else ''} {category_name.lower()}\n\n"
    
    # Add each task as a list item with link and due date using Markdown
    for task in sorted_tasks:
        # Get task details
        task_id = task.get('id')
        task_title = task.get('title', 'Untitled')
        task_url = f"{base_url.replace('/api/v1', '')}/tasks/{task_id}"
        
        # Format due date nicely
        try:
            due_date = email_utils.format_due_date(task['due_datetime'])
        except:
            # Fallback if formatting fails
            due_date = task['due_datetime'].strftime('%Y-%m-%d %H:%M')
        
        # Add list item with Markdown link and due date
        message += f"* [{task_title}]({task_url}) ({due_date})\n"
    
    # Create payload
    payload = {
        "text": message
    }
    
    # Add optional username and icon if provided
    if username:
        payload["username"] = username
    if icon_url:
        payload["icon_url"] = icon_url
    
    # Send the webhook
    try:
        response = requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        logger.info(f"Mattermost notification sent successfully ({response.status_code})")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Mattermost notification: {e}")
        return False 