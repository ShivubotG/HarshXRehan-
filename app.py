import random
import time
import asyncio
import json
import os
import subprocess
import sys
from flask import Flask, render_template, request, jsonify, session
import threading
import logging
from datetime import datetime
import re
import uuid
from urllib.parse import unquote

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variables with user isolation
PLAYWRIGHT_AVAILABLE = False
BROWSER_INSTALLED = False
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# User-specific data stores
user_sessions = {}
session_lock = threading.Lock()
system_logs = []  # System logs for initialization

# Emoji ranges for message enhancement
EMOJI_RANGES = [
    (0x1F600, 0x1F64F), (0x1F300, 0x1F5FF), (0x1F680, 0x1F6FF),
    (0x1F1E0, 0x1F1FF), (0x2600, 0x26FF), (0x2700, 0x27BF)
]

def get_user_session():
    """Get or create user session"""
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    
    user_id = session['user_id']
    
    with session_lock:
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                'livelogs': list(system_logs),  # Copy system logs to user
                'tasks_data': {},
                'last_activity': time.time()
            }
        
        # Update activity timestamp
        user_sessions[user_id]['last_activity'] = time.time()
        
        return user_sessions[user_id]

def log_console(msg, user_id=None):
    """Thread-safe logging with user isolation"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    formatted_msg = f"[{timestamp}] {msg}"
    print(formatted_msg)
    
    # Add to system logs
    system_logs.append(formatted_msg)
    if len(system_logs) > 1000:
        system_logs.pop(0)
    
    # If user_id provided, add to user logs
    if user_id:
        with session_lock:
            if user_id in user_sessions:
                user_sessions[user_id]['livelogs'].append(formatted_msg)
                if len(user_sessions[user_id]['livelogs']) > 1000:
                    user_sessions[user_id]['livelogs'].pop(0)
    
    # If in request context, add to current user logs
    try:
        from flask import has_request_context
        if has_request_context():
            user_session = get_user_session()
            user_session['livelogs'].append(formatted_msg)
            if len(user_session['livelogs']) > 1000:
                user_session['livelogs'].pop(0)
    except:
        pass

def install_playwright_and_browser():
    """Install Playwright and Chromium browser"""
    global PLAYWRIGHT_AVAILABLE, BROWSER_INSTALLED
    
    try:
        log_console("🚀 Installing Playwright...")
        
        # Install Playwright via pip
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "playwright==1.47.0", "flask==2.3.3"
        ], capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0:
            PLAYWRIGHT_AVAILABLE = True
            log_console("✅ Playwright installed successfully!")
        else:
            log_console(f"❌ Playwright installation failed: {result.stderr[:500]}")
            return False

        # Install Chromium browser
        log_console("📦 Installing Chromium browser...")
        install_result = subprocess.run([
            sys.executable, "-m", "playwright", "install", "chromium"
        ], capture_output=True, text=True, timeout=1800)
        
        if install_result.returncode == 0:
            BROWSER_INSTALLED = True
            log_console("✅ Chromium installed successfully!")
        else:
            log_console(f"⚠️ Chromium installation warning: {install_result.stderr[:500]}")

        # Test imports
        try:
            from playwright.async_api import async_playwright
            log_console("🎉 Playwright imports successful!")
            return True
        except ImportError as e:
            log_console(f"❌ Playwright import test failed: {e}")
            return False
            
    except subprocess.TimeoutExpired:
        log_console("❌ Installation timed out")
        return False
    except Exception as e:
        log_console(f"❌ Installation error: {str(e)}")
        return False

def generate_random_emoji():
    """Generate a random emoji"""
    start, end = random.choice(EMOJI_RANGES)
    return chr(random.randint(start, end))

def enhance_message(message):
    """Add random emojis to message"""
    if not message or len(message.strip()) == 0:
        return message
        
    words = message.split()
    if len(words) <= 1:
        return f"{generate_random_emoji()} {message} {generate_random_emoji()}"
    
    # Add emojis randomly
    enhanced_words = []
    for i, word in enumerate(words):
        enhanced_words.append(word)
        if random.random() < 0.3 and i < len(words) - 1:
            enhanced_words.append(generate_random_emoji())
    
    # Add prefix/suffix emojis
    if random.random() < 0.4:
        enhanced_words.insert(0, generate_random_emoji())
    if random.random() < 0.4:
        enhanced_words.append(generate_random_emoji())
    
    return ' '.join(enhanced_words)

def parse_cookies(cookie_input):
    """Parse cookies from various formats - IMPROVED VERSION"""
    cookies = []
    
    if not cookie_input or not cookie_input.strip():
        return cookies
    
    log_console(f"🔍 Parsing cookies input (length: {len(cookie_input)})")
    
    # Clean input
    cookie_input = cookie_input.strip()
    
    # Method 1: JSON array format
    if cookie_input.startswith('[') and cookie_input.endswith(']'):
        try:
            data = json.loads(cookie_input)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'name' in item and 'value' in item:
                        cookies.append({
                            'name': str(item['name']),
                            'value': str(item['value']),
                            'domain': item.get('domain', '.facebook.com'),
                            'path': item.get('path', '/'),
                            'secure': item.get('secure', True),
                            'httpOnly': item.get('httpOnly', False)
                        })
                if cookies:
                    log_console(f"✅ Parsed {len(cookies)} cookies from JSON array")
                    return cookies
        except json.JSONDecodeError:
            pass
    
    # Method 2: Browser copy-paste format (most common)
    # Handle multiple cookies in single line separated by semicolons
    cookie_input = cookie_input.replace('; ', ';').replace(' ;', ';')
    
    # Split by semicolons first
    cookie_parts = []
    if ';' in cookie_input:
        cookie_parts = [part.strip() for part in cookie_input.split(';') if part.strip()]
    else:
        # If no semicolons, treat as single cookie or split by newlines
        cookie_parts = [line.strip() for line in cookie_input.split('\n') if line.strip()]
    
    for part in cookie_parts:
        # Skip comments and empty parts
        if not part or part.startswith('#') or part.startswith('//'):
            continue
            
        # Handle key=value pairs
        if '=' in part:
            try:
                # Split by first equals sign only
                name, value = part.split('=', 1)
                name = name.strip()
                value = value.strip()
                
                # Remove quotes and semicolons from name
                name = name.replace('"', '').replace("'", "").replace(';', '')
                
                # Handle URL encoded values
                if '%' in value:
                    try:
                        value = unquote(value)
                    except:
                        pass
                
                # Clean value - remove trailing semicolons and quotes
                value = value.split(';')[0].replace('"', '').replace("'", "")
                
                # Validate name and value
                if (name and value and 
                    len(name) > 0 and len(value) > 0 and
                    not name.startswith('http') and 
                    ' ' not in name):
                    
                    # Determine domain based on cookie name
                    domain = '.facebook.com'
                    if name in ['xs', 'c_user', 'fr', 'datr', 'sb']:
                        domain = '.facebook.com'
                    elif 'instagram' in name.lower():
                        domain = '.instagram.com'
                    
                    cookies.append({
                        'name': name,
                        'value': value,
                        'domain': domain,
                        'path': '/',
                        'secure': True,
                        'httpOnly': name in ['xs', 'fr', 'c_user']  # Common session cookies
                    })
                    log_console(f"✅ Added cookie: {name}={value[:20]}...")
                    
            except Exception as e:
                log_console(f"⚠️ Failed to parse cookie part: {part} - Error: {e}")
                continue
    
    # Remove duplicates based on name
    unique_cookies = []
    seen_names = set()
    for cookie in cookies:
        if cookie['name'] not in seen_names:
            unique_cookies.append(cookie)
            seen_names.add(cookie['name'])
    
    log_console(f"✅ Final parsed cookies: {len(unique_cookies)}")
    
    # Log important cookies found
    important_cookies = ['c_user', 'xs', 'fr', 'datr', 'sb']
    found_important = [c for c in unique_cookies if c['name'] in important_cookies]
    if found_important:
        log_console(f"🔑 Found important cookies: {[c['name'] for c in found_important]}")
    else:
        log_console("⚠️ No important session cookies found (c_user, xs, fr, etc.)")
    
    return unique_cookies[:30]  # Increased limit to 30 cookies

def get_input_data(req, field_name):
    """Extract input data from request"""
    data = []
    
    # Try text input first
    text_input = req.form.get(field_name, '').strip()
    if text_input:
        lines = [line.strip() for line in text_input.split('\n') if line.strip()]
        data.extend(lines)
    
    # Try file upload
    file = req.files.get(f'{field_name}_file')
    if file and file.filename:
        try:
            content = file.read().decode('utf-8')
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            data.extend(lines)
            log_console(f"📁 Loaded {len(lines)} items from {file.filename}")
        except Exception as e:
            log_console(f"❌ File read error: {e}")
    
    return data

async def send_facebook_message_playwright(cookies, conversation_id, message, task_id, user_id):
    """Send message using Playwright - IMPROVED VERSION"""
    if not PLAYWRIGHT_AVAILABLE:
        log_console(f"[{task_id}] ❌ Playwright not available", user_id)
        return False
    
    try:
        from playwright.async_api import async_playwright
        
        log_console(f"[{task_id}] 🚀 Starting browser...", user_id)
        
        async with async_playwright() as p:
            # Launch browser with options
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ],
                timeout=60000
            )
            
            # Create context with realistic user agent
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                ignore_https_errors=True,
                locale='en-US',
                timezone_id='America/New_York'
            )
            
            # Add cookies to context
            if cookies:
                try:
                    await context.add_cookies(cookies)
                    log_console(f"[{task_id}] ✅ Loaded {len(cookies)} cookies", user_id)
                    
                    # Log important cookies
                    important_cookies = ['c_user', 'xs', 'fr']
                    for cookie in cookies:
                        if cookie['name'] in important_cookies:
                            log_console(f"[{task_id}] 🔑 {cookie['name']}: {cookie['value'][:10]}...", user_id)
                            
                except Exception as e:
                    log_console(f"[{task_id}] ❌ Error adding cookies: {e}", user_id)
                    await browser.close()
                    return False
            
            page = await context.new_page()
            
            # Navigate to Facebook messages
            url = f"https://www.facebook.com/messages/t/{conversation_id}"
            log_console(f"[{task_id}] 🌐 Navigating to {url}", user_id)
            
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            except Exception as e:
                log_console(f"[{task_id}] ⚠️ Page load timeout, continuing...", user_id)
            
            # Wait for page to settle
            await page.wait_for_timeout(8000)
            
            # Check if we're logged in by multiple methods
            login_indicators = await page.query_selector('input[name="email"], input[name="pass"], #loginform, [data-testid="royal_login_form"]')
            profile_indicators = await page.query_selector('[aria-label="Facebook"][role="navigation"], [data-testid="blue_bar_root"], [aria-label="Menu"]')
            
            if login_indicators and not profile_indicators:
                log_console(f"[{task_id}] ❌ Not logged in - showing login form", user_id)
                await browser.close()
                return False
            
            # Try multiple selectors for message input with longer wait
            input_selectors = [
                'div[contenteditable="true"][role="textbox"]',
                'div[aria-label*="Message"][contenteditable="true"]',
                'div[aria-label*="message"][contenteditable="true"]',
                'div[data-lexical-editor="true"]',
                '[contenteditable="true"]',
                'div[role="textbox"]',
                '[aria-label="Message"]',
                'div[spellcheck="true"]'
            ]
            
            message_input = None
            for selector in input_selectors:
                try:
                    message_input = await page.wait_for_selector(selector, timeout=10000)
                    if message_input:
                        log_console(f"[{task_id}] ✅ Found message input with: {selector}", user_id)
                        break
                except:
                    continue
            
            if not message_input:
                log_console(f"[{task_id}] ❌ Could not find message input", user_id)
                # Take screenshot for debugging
                try:
                    screenshot_path = f"/tmp/error_{task_id}.png"
                    await page.screenshot(path=screenshot_path)
                    log_console(f"[{task_id}] 📸 Screenshot saved for debugging", user_id)
                except Exception as e:
                    log_console(f"[{task_id}] ❌ Screenshot failed: {e}", user_id)
                await browser.close()
                return False
            
            # Type and send message
            await message_input.click()
            await page.wait_for_timeout(2000)
            
            # Clear existing content if any
            await message_input.click(click_count=3)  # Select all
            await page.keyboard.press('Backspace')
            await page.wait_for_timeout(1000)
            
            # Type message character by character for realism
            log_console(f"[{task_id}] 📝 Typing message...", user_id)
            for char in message:
                await message_input.press(char)
                await page.wait_for_timeout(random.randint(30, 100))
            
            await page.wait_for_timeout(2000)
            
            # Press Enter to send
            await message_input.press('Enter')
            log_console(f"[{task_id}] ✅ Message sent successfully!", user_id)
            
            # Wait for send to complete and verify
            await page.wait_for_timeout(5000)
            
            # Check if message was sent by looking for sent indicator
            try:
                sent_indicators = await page.query_selector('[aria-label*="Sent"], [data-testid*="message_sent"]')
                if sent_indicators:
                    log_console(f"[{task_id}] ✅ Message delivery confirmed", user_id)
            except:
                log_console(f"[{task_id}] ⚠️ Could not verify delivery, but message was sent", user_id)
            
            await browser.close()
            return True
            
    except Exception as e:
        log_console(f"[{task_id}] ❌ Error: {str(e)}", user_id)
        return False

def run_async_task(coro):
    """Run async task in background thread"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    except Exception as e:
        log_console(f"Async task error: {e}")
        return False
    finally:
        loop.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    user_session = get_user_session()
    active_tasks = sum(1 for t in user_session['tasks_data'].values() if t.get('active', False))
    
    return jsonify({
        'playwright': PLAYWRIGHT_AVAILABLE,
        'browser': BROWSER_INSTALLED,
        'active_tasks': active_tasks,
        'total_tasks': len(user_session['tasks_data']),
        'logs_count': len(user_session['livelogs']),
        'user_id': session['user_id'][:8]  # Return short user ID for display
    })

@app.route('/api/logs')
def api_logs():
    user_session = get_user_session()
    return jsonify({'logs': user_session['livelogs'][-100:]})

@app.route('/api/start', methods=['POST'])
def api_start():
    global PLAYWRIGHT_AVAILABLE, BROWSER_INSTALLED
    
    user_session = get_user_session()
    user_id = session['user_id']
    
    # Auto-install if needed
    if not PLAYWRIGHT_AVAILABLE or not BROWSER_INSTALLED:
        log_console("🔄 Auto-installing dependencies...", user_id)
        success = install_playwright_and_browser()
        if not success:
            return jsonify({'success': False, 'message': 'Installation failed'})
    
    # Get input data
    cookies_list = get_input_data(request, 'cookies')
    messages_list = get_input_data(request, 'messages')
    conversations_list = get_input_data(request, 'conversations')
    
    if not cookies_list:
        return jsonify({'success': False, 'message': 'No cookies provided'})
    if not messages_list:
        return jsonify({'success': False, 'message': 'No messages provided'})
    if not conversations_list:
 
