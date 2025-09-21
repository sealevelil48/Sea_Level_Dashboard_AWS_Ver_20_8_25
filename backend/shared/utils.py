# backend/shared/utils.py
import re
from datetime import datetime

def generate_export_filename(station, start_date, end_date, extension="png"):
    import html
    station = station or "AllStations"
    # Escape HTML and sanitize for filename
    sanitized_station = html.escape(str(station))
    sanitized_station = re.sub(r'[^\w\-]', '', sanitized_station)

    def format_date(date_str):
        if not date_str:
            return "NODATE"
        try:
            if ' ' in date_str:
                date_part = date_str.split(' ')[0]
                return datetime.strptime(date_part, '%Y-%m-%d').strftime('%Y-%m-%d')
            return datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
        except:
            return re.sub(r'[^\w\-]', '_', date_str)[:20]

    sanitized_start = format_date(start_date)
    sanitized_end = format_date(end_date)

    return f"sea_level_{sanitized_station}_{sanitized_start}_to_{sanitized_end}.{extension}"