"""
Compatibility shim for the cgi module which was removed in Python 3.13.
This provides just enough functionality to support the dependencies.
"""

def escape(s: str, quote: bool = None) -> str:
    """
    Replace special characters "&", "<" and ">" to HTML-safe sequences.
    If the optional flag quote is true, the quotation mark character (")
    is also translated.
    """
    s = s.replace("&", "&amp;")  # Must be done first!
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    if quote:
        s = s.replace('"', "&quot;")
    return s
