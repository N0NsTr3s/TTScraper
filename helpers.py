import requests



def extract_video_id_from_url(url, headers=None, proxy=None):
    if headers is None:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    try:
        url = requests.head(
            url=url, allow_redirects=True, headers=headers, proxies=proxy
        ).url
    except Exception:
        # If head request fails, try to extract from original URL
        pass
        
    if "@" in url and "/video/" in url:
        return url.split("/video/")[1].split("?")[0]
    else:
        raise TypeError(
            "URL format not supported. Below is an example of a supported url.\n"
            "https://www.tiktok.com/@therock/video/6829267836783971589"
        )
    
def requests_cookie_to_browser_cookie(req_c):
    """Convert a requests/browser cookie dict to a standardized cookie dict."""
    return {
        'name': req_c.get('name'),
        'value': req_c.get('value'),
        'domain': req_c.get('domain'),
        'path': req_c.get('path'),
        'expiry': req_c.get('expiry'),
        'secure': req_c.get('secure'),
        'httpOnly': req_c.get('httpOnly', False)
    }

# Backward compat alias
requests_cookie_to_selenium_cookie = requests_cookie_to_browser_cookie