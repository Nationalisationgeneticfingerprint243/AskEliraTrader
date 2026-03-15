"""
Pipeline status writer for dashboard real-time updates.
Called by agents to update current step + details.
"""

import json
import os
from datetime import datetime
from pathlib import Path

STATUS_FILE = Path.home() / "Desktop" / "Polymarket" / "data" / "pipeline_status.json"

def update_status(step: str, details: str = None, append_log: str = None):
    """
    Update pipeline status for dashboard.
    
    Args:
        step: Current step ID (e.g., 'alba-scan', 'david-simulate')
        details: Optional details about what's happening
        append_log: Optional log message to append
    """
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing status or create new
    if STATUS_FILE.exists():
        with open(STATUS_FILE, 'r') as f:
            status = json.load(f)
    else:
        status = {
            'current_step': 'idle',
            'details': None,
            'log': [],
            'started_at': None,
        }
    
    # Update
    status['current_step'] = step
    status['details'] = details
    
    if step != 'idle' and not status['started_at']:
        status['started_at'] = datetime.now().isoformat()
    
    if append_log:
        status['log'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': append_log,
        })
        # Keep last 50 log entries
        status['log'] = status['log'][-50:]
    
    # Write
    with open(STATUS_FILE, 'w') as f:
        json.dump(status, f, indent=2)

def clear_status():
    """Reset pipeline status to idle."""
    update_status('idle', None, 'Pipeline completed')
    
def log_message(message: str):
    """Append a log message without changing step."""
    if STATUS_FILE.exists():
        with open(STATUS_FILE, 'r') as f:
            status = json.load(f)
        update_status(
            status.get('current_step', 'idle'),
            status.get('details'),
            message
        )
    else:
        update_status('idle', None, message)
