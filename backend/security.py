"""
Minimal security module for local development
"""

def secure_log(logger, level, message, **kwargs):
    """Secure logging function"""
    # Filter sensitive data from kwargs
    safe_kwargs = {}
    for k, v in kwargs.items():
        if k.lower() in ['password', 'token', 'key', 'secret']:
            safe_kwargs[k] = '[REDACTED]'
        else:
            safe_kwargs[k] = str(v)[:100] if isinstance(v, str) else v
    
    log_message = f"{message} - {safe_kwargs}" if safe_kwargs else message
    
    if level == 'error':
        logger.error(log_message)
    elif level == 'warning':
        logger.warning(log_message)
    else:
        logger.info(log_message)