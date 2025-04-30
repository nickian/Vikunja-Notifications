# Vikunja Task Notifications

A Python script to fetch, filter, and send custom email and Mattermost notifications for tasks from a Vikunja instance.

## Features

- Fetch tasks from your Vikunja instance
- Filter tasks by due dates (today, overdue, this week, next week)
- Send email notifications with task details
- Send Mattermost webhook notifications
- Generate HTML email previews

## Setup

1. Clone this repository
2. Install the required dependencies:
   ```
   pip install requests pytz jinja2 python-dotenv
   ```
3. Copy the `env.template` file to `.env` and fill in your credentials:
   ```
   cp env.template .env
   ```
4. Edit the `.env` file with your Vikunja API token and email settings

## Usage

### Basic Usage

Show all tasks with due dates:
```
python vikunja_tasks.py --all
```

Show tasks due today:
```
python vikunja_tasks.py --today
```

Show overdue tasks:
```
python vikunja_tasks.py --overdue
```

Show tasks due this week (Monday-Sunday):
```
python vikunja_tasks.py --this_week
```

Show tasks due next week (next Monday-Sunday):
```
python vikunja_tasks.py --next_week
```

### Upcoming Task Reminders

Check for tasks due in the next 15, 30, and 60 minutes and send individual notifications:

```
python vikunja_tasks.py --upcoming --email your@email.com --mattermost
```

This will send notifications for upcoming tasks using the following time windows:

- **15-minute notification**: Tasks due in 0-20 minutes
- **30-minute notification**: Tasks due in 20-40 minutes 
- **60-minute notification**: Tasks due in 40-75 minutes

Each task gets its own individual notification with:
- Time remaining in human-readable format (e.g., "15 minutes", "1 hour")
- A direct link to the task
- Customized subject line with the time remaining

For verbose debugging output that can help troubleshoot why notifications aren't being sent:

```
python vikunja_tasks.py --upcoming --verbose
```

This command will show detailed information about each task being evaluated, including its due time and whether it matches the notification thresholds.

### Email Notifications

To send email notifications, you must specify a recipient email address with the `--email` parameter:

```
python vikunja_tasks.py --next_week --email your@email.com
```

The SMTP settings can be configured in your `.env` file or specified via command line. Most email providers require TLS or SSL encryption:

```
# For Gmail, Outlook, and most modern providers (TLS)
python vikunja_tasks.py --next_week --email your@email.com --smtp_server smtp.gmail.com --smtp_port 587 --smtp_user username --smtp_password password --use_tls

# For providers requiring SSL
python vikunja_tasks.py --next_week --email your@email.com --smtp_server smtp.example.com --smtp_port 465 --smtp_user username --smtp_password password --use_ssl
```

If you're having trouble with email sending, you can enable debugging output:

```
python vikunja_tasks.py --next_week --email your@email.com --use_tls --debug
```

### Mattermost Webhook Notifications

To send notifications to a Mattermost channel using webhooks:

```
python vikunja_tasks.py --next_week --mattermost
```

You can configure the webhook URL, username, and icon in your `.env` file or specify them via command line:

```
python vikunja_tasks.py --today --mattermost --webhook_url "https://mattermost.example.com/hooks/your-webhook-id" --webhook_username "Vikunja Tasks" --webhook_icon "https://example.com/icon.png"
```

You can use both email and Mattermost notifications together:

```
python vikunja_tasks.py --today --email your@email.com --mattermost
```

### Logging Options

For automated runs or cron jobs, you can control the output verbosity:

```
# Run quietly (show only errors)
python vikunja_tasks.py --today --mattermost --quiet

# Send output to a log file
python vikunja_tasks.py --today --mattermost --log-file /path/to/vikunja.log

# Show verbose output (debug information)
python vikunja_tasks.py --today --verbose
```

## Setting Up Cron Jobs

For regular task notifications, it's recommended to use cron to automate script execution.

### Cron Setup Examples

Here are some useful cron patterns:

```bash
# Daily morning email with today's tasks (8:00 AM)
0 8 * * * cd /path/to/vikunja && python vikunja_tasks.py --today --email your@email.com --quiet --log-file logs/vikunja.log

# Daily evening notification with tomorrow's tasks (8:00 PM)
0 20 * * * cd /path/to/vikunja && python vikunja_tasks.py --next_week --email your@email.com --quiet --log-file logs/vikunja.log

# Monday morning weekly overview (7:30 AM)
30 7 * * 1 cd /path/to/vikunja && python vikunja_tasks.py --this_week --email your@email.com --mattermost --quiet --log-file logs/vikunja.log

# Sunday evening preview of next week's tasks (6:00 PM)
0 18 * * 0 cd /path/to/vikunja && python vikunja_tasks.py --next_week --email your@email.com --mattermost --quiet --log-file logs/vikunja.log

# Check for upcoming tasks every 15 minutes
*/15 * * * * cd /path/to/vikunja && python vikunja_tasks.py --upcoming --email your@email.com --mattermost --quiet --log-file logs/vikunja_upcoming.log
```

For the upcoming task notifications, running the check every 15 minutes works with the following notification windows:
- Tasks due in 40-75 minutes will receive a "due in 1 hour" notification
- Tasks due in 20-40 minutes will receive a "due in 30 minutes" notification
- Tasks due in 0-20 minutes will receive a "due in 15 minutes" notification

These wider windows ensure that all tasks get notified about, even with a 15-minute cron interval. If troubleshooting is needed, you can temporarily add the `--verbose` flag and check the log file for detailed information.

### Cron Best Practices

When setting up cron jobs:

1. **Use absolute paths:** Either use absolute paths in the cron command or include a `cd` command to ensure the script runs from the correct directory.

2. **Always use --quiet and --log-file:** This prevents unnecessary emails from cron while still capturing important information.

3. **Create a log directory:** Use a dedicated log directory to keep log files organized:
   ```bash
   mkdir -p /path/to/vikunja/logs
   ```

4. **Consider log rotation:** For long-running setups, consider using logrotate to manage log files.

5. **Test your cron setup:** Run the command manually first to verify it works as expected.

6. **Set up your environment:** Make sure your .env file is properly configured with all necessary settings.

7. **Check your cron environment:** Cron environments can differ from interactive shells, so ensure all dependencies are available.

### Preview Emails

You can generate HTML previews without sending by using the `--save_preview` flag (no email address required):

```
python vikunja_tasks.py --next_week --save_preview
```

Generate a sample preview with dummy data:
```
python vikunja_tasks.py --save_preview
```

## Environment Variables

You can set the following environment variables in the `.env` file:

- `VIKUNJA_BASE_URL`: Base URL of your Vikunja API
- `VIKUNJA_API_TOKEN`: Your Vikunja API token
- `TIMEZONE`: Your timezone (default: America/Denver)
- `EMAIL_SENDER`: Default sender email address
- `EMAIL_SUBJECT`: Default email subject
- `SMTP_SERVER`: SMTP server address
- `SMTP_PORT`: SMTP server port
- `SMTP_USER`: SMTP username
- `SMTP_PASSWORD`: SMTP password

## Customizing Email Templates

You can create multiple email templates in the `email_templates/` directory and specify which one to use:

```
python vikunja_tasks.py --today --email user@example.com --template custom.html
```

Or set the default in your `.env` file:

```
EMAIL_TEMPLATE=custom.html
```

### Email Previews

When using the `--save_preview` flag, preview files are saved in the `email_previews/` directory:

```
python vikunja_tasks.py --next_week --save_preview
```

## Project Structure

The project is organized into the following components:

- `vikunja_tasks.py`: Main script for fetching and filtering tasks
- `email_utils.py`: Email generation and sending functionality
- `email_templates/`: Directory containing HTML email templates
  - `default.html`: Default email template
- `email_previews/`: Directory where email previews are saved
- `env.template`: Template for environment variables

This modular structure keeps concerns separated and makes the code more maintainable:
- Task processing logic is in the main script
- Email functionality is isolated in its own module
- Templates are stored in separate files 