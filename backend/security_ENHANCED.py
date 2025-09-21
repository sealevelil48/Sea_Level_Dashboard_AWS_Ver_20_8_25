# backend/security_ENHANCED.py
"""
Enhanced security module with comprehensive input validation and sanitization
"""

import re
import html
import ipaddress
import logging
from typing import Any, Dict, Optional, Union
from urllib.parse import urlparse, quote
import bleach

logger = logging.getLogger(__name__)

# Allowed HTML tags and attributes for sanitization
ALLOWED_TAGS = ['b', 'i', 'u', 'em', 'strong', 'p', 'br']
ALLOWED_ATTRIBUTES = {}

def secure_log(logger_instance, level: str, message: str, **kwargs):
    """
    Enhanced secure logging with input sanitization and structured logging
    
    Args:
        logger_instance: Logger instance to use
        level: Log level (debug, info, warning, error, critical)
        message: Base log message
        **kwargs: Additional structured data to log
    """
    # Sanitize all input values
    sanitized_kwargs = {}
    for key, value in kwargs.items():
        if isinstance(value, str):
            # Remove control characters and limit length
            sanitized_value = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', str(value))
            sanitized_value = sanitized_value[:1000]  # Limit length
            sanitized_kwargs[f"sanitized_{key}"] = sanitized_value
        elif isinstance(value, (int, float, bool)):
            sanitized_kwargs[key] = value
        else:
            sanitized_kwargs[f"type_{key}"] = type(value).__name__
    
    # Create structured log message
    log_data = {
        'message': message,
        'timestamp': logger_instance.handlers[0].formatter.formatTime(
            logging.LogRecord('', 0, '', 0, '', (), None)
        ) if logger_instance.handlers else None,
        **sanitized_kwargs
    }
    
    # Log with appropriate level
    getattr(logger_instance, level.lower(), logger_instance.info)(
        f"{message} | Data: {log_data}"
    )

def sanitize_html_input(input_string: str) -> str:
    """
    Sanitize HTML input to prevent XSS attacks
    
    Args:
        input_string: Raw HTML input
        
    Returns:
        Sanitized HTML string
    """
    if not isinstance(input_string, str):
        return str(input_string)
    
    # Use bleach for comprehensive HTML sanitization
    sanitized = bleach.clean(
        input_string,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True
    )
    
    # Additional HTML entity encoding
    sanitized = html.escape(sanitized, quote=True)
    
    return sanitized

def validate_station_name(station: str) -> bool:
    """
    Validate station name format
    
    Args:
        station: Station name to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(station, str):
        return False
    
    # Allow alphanumeric, spaces, hyphens, and underscores
    pattern = r'^[a-zA-Z0-9\s\-_]{1,50}$'
    return bool(re.match(pattern, station.strip()))

def validate_date_format(date_string: str) -> bool:
    """
    Validate date string format (YYYY-MM-DD)
    
    Args:
        date_string: Date string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(date_string, str):
        return False
    
    pattern = r'^\d{4}-\d{2}-\d{2}$'
    return bool(re.match(pattern, date_string))

def sanitize_sql_input(input_value: Any) -> str:
    """
    Sanitize input for SQL queries (though parameterized queries should be used)
    
    Args:
        input_value: Value to sanitize
        
    Returns:
        Sanitized string value
    """
    if input_value is None:
        return ''
    
    # Convert to string and remove dangerous characters
    sanitized = str(input_value)
    
    # Remove SQL injection patterns
    dangerous_patterns = [
        r"[';\"\\]",  # Quotes and backslashes
        r"--",        # SQL comments
        r"/\*.*?\*/", # Multi-line comments
        r"\b(DROP|DELETE|INSERT|UPDATE|CREATE|ALTER|EXEC|EXECUTE)\b",  # Dangerous keywords
    ]
    
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
    
    return sanitized.strip()

def validate_ip_address(ip_string: str) -> bool:
    """
    Enhanced IP address validation with private network checks
    
    Args:
        ip_string: IP address string to validate
        
    Returns:
        True if valid public IP, False otherwise
    """
    try:
        ip = ipaddress.ip_address(ip_string)
        
        # Check if it's a private IP address
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            logger.warning(f"Private IP address rejected: {ip_string}")
            return False
        
        # Additional checks for specific ranges
        if isinstance(ip, ipaddress.IPv4Address):
            # More precise private network validation
            private_networks = [
                ipaddress.IPv4Network('10.0.0.0/8'),
                ipaddress.IPv4Network('172.16.0.0/12'),  # Fixed: proper range
                ipaddress.IPv4Network('192.168.0.0/16'),
                ipaddress.IPv4Network('127.0.0.0/8'),    # Loopback
                ipaddress.IPv4Network('169.254.0.0/16'), # Link-local
            ]
            
            for network in private_networks:
                if ip in network:
                    logger.warning(f"IP address in private network rejected: {ip_string}")
                    return False
        
        return True
        
    except ValueError:
        logger.warning(f"Invalid IP address format: {ip_string}")
        return False

def validate_hostname(hostname: str) -> bool:
    """
    Validate hostname format and check against private networks
    
    Args:
        hostname: Hostname to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(hostname, str) or not hostname:
        return False
    
    # Basic hostname format validation
    if len(hostname) > 253:
        return False
    
    # Check for valid hostname pattern
    hostname_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
    if not re.match(hostname_pattern, hostname):
        return False
    
    # Check if it resolves to a private IP
    try:
        import socket
        ip = socket.gethostbyname(hostname)
        return validate_ip_address(ip)
    except socket.gaierror:
        # If hostname doesn't resolve, allow it (might be internal)
        return True

def sanitize_file_path(file_path: str, allowed_extensions: Optional[list] = None) -> Optional[str]:
    """
    Sanitize file path to prevent path traversal attacks
    
    Args:
        file_path: File path to sanitize
        allowed_extensions: List of allowed file extensions
        
    Returns:
        Sanitized file path or None if invalid
    """
    if not isinstance(file_path, str):
        return None
    
    # Remove path traversal attempts
    sanitized = file_path.replace('..', '').replace('\\', '/').strip('/')
    
    # Remove leading slashes to prevent absolute path access
    sanitized = sanitized.lstrip('/')
    
    # Validate file extension if provided
    if allowed_extensions:
        file_ext = sanitized.split('.')[-1].lower() if '.' in sanitized else ''
        if file_ext not in [ext.lower().lstrip('.') for ext in allowed_extensions]:
            logger.warning(f"File extension not allowed: {file_ext}")
            return None
    
    # Additional security checks
    dangerous_patterns = [
        r'[<>:"|?*]',  # Windows forbidden characters
        r'^\.',        # Hidden files
        r'\.{2,}',     # Multiple dots
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, sanitized):
            logger.warning(f"Dangerous pattern in file path: {sanitized}")
            return None
    
    return sanitized

def validate_url(url: str, allowed_schemes: Optional[list] = None) -> bool:
    """
    Validate URL format and scheme
    
    Args:
        url: URL to validate
        allowed_schemes: List of allowed URL schemes (default: ['http', 'https'])
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(url, str):
        return False
    
    if allowed_schemes is None:
        allowed_schemes = ['http', 'https']
    
    try:
        parsed = urlparse(url)
        
        # Check scheme
        if parsed.scheme.lower() not in allowed_schemes:
            return False
        
        # Check hostname
        if parsed.hostname and not validate_hostname(parsed.hostname):
            return False
        
        return True
        
    except Exception:
        return False

def rate_limit_key(request_info: Dict[str, Any]) -> str:
    """
    Generate rate limiting key from request information
    
    Args:
        request_info: Dictionary containing request information
        
    Returns:
        Rate limiting key
    """
    # Use IP address and user agent for rate limiting
    ip = request_info.get('ip', 'unknown')
    user_agent = request_info.get('user_agent', 'unknown')
    
    # Sanitize inputs
    ip = sanitize_sql_input(ip)
    user_agent = sanitize_sql_input(user_agent)[:100]  # Limit length
    
    return f"{ip}:{hash(user_agent)}"

def create_security_headers() -> Dict[str, str]:
    """
    Create security headers for HTTP responses
    
    Returns:
        Dictionary of security headers
    """
    return {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'geolocation=(), microphone=(), camera=()'
    }

# Input validation decorators
def validate_input(**validators):
    """
    Decorator for input validation
    
    Args:
        **validators: Dictionary of field validators
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            for field, validator in validators.items():
                if field in kwargs:
                    if not validator(kwargs[field]):
                        raise ValueError(f"Invalid {field}: {kwargs[field]}")
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Example usage:
# @validate_input(station=validate_station_name, date=validate_date_format)
# def get_station_data(station, date):
#     pass