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
                'livelogs': [],
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
    
    user_session = get_user_session()
    
    user_session['livelogs'].append(formatted_msg)
    if len(user_session['livelogs']) > 1000:
        user_session['livelogs'].pop(0)

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
    """Parse cookies from various formats"""
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
    
    # Method 2: Key=value format (most common)
    lines = cookie_input.split('\n')
    for line in lines:
        line = line.strip()
        if '=' in line and not line.startswith('#') and not line.startswith('//'):
            # Handle key=value pairs
            parts = line.split('=', 1)
            if len(parts) == 2:
                name = parts[0].strip()
                value = parts[1].strip()
                
                # Remove quotes and semicolons
                name = name.replace('"', '').replace("'", "").replace(';', '')
                value = value.split(';')[0].replace('"', '').replace("'", "")
                
                if name and value and len(name) > 1 and len(value) > 1:
                    cookies.append({
                        'name': name,
                        'value': value,
                        'domain': '.facebook.com',
                        'path': '/',
                        'secure': True,
                        'httpOnly': False
                    })
    
    # Remove duplicates
    unique_cookies = []
    seen = set()
    for cookie in cookies:
        key = (cookie['name'].lower(), cookie['value'])
        if key not in seen:
            unique_cookies.append(cookie)
            seen.add(key)
    
    log_console(f"✅ Final parsed cookies: {len(unique_cookies)}")
    return unique_cookies[:20]  # Limit to 20 cookies

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
    """Send message using Playwright"""
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
                    '--disable-renderer-backgrounding'
                ],
                timeout=60000
            )
            
            # Create context with realistic user agent
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                ignore_https_errors=True
            )
            
            # Add cookies to context
            if cookies:
                await context.add_cookies(cookies)
                log_console(f"[{task_id}] ✅ Loaded {len(cookies)} cookies", user_id)
            
            page = await context.new_page()
            
            # Navigate to Facebook messages
            url = f"https://www.facebook.com/messages/t/{conversation_id}"
            log_console(f"[{task_id}] 🌐 Navigating to {url}", user_id)
            
            try:
                await page.goto(url, wait_until='networkidle', timeout=45000)
            except Exception as e:
                log_console(f"[{task_id}] ⚠️ Page load timeout, continuing...", user_id)
            
            # Wait for page to settle
            await page.wait_for_timeout(5000)
            
            # Check if we're logged in by looking for login elements or message input
            login_indicators = await page.query_selector('input[name="email"], input[name="pass"], #loginform')
            if login_indicators:
                log_console(f"[{task_id}] ❌ Not logged in - invalid cookies", user_id)
                await browser.close()
                return False
            
            # Try multiple selectors for message input
            input_selectors = [
                'div[contenteditable="true"][role="textbox"]',
                'div[aria-label*="Message"][contenteditable="true"]',
                'div[aria-label*="message"][contenteditable="true"]',
                'div[data-lexical-editor="true"]',
                '[contenteditable="true"]',
                'div[role="textbox"]'
            ]
            
            message_input = None
            for selector in input_selectors:
                message_input = await page.query_selector(selector)
                if message_input:
                    log_console(f"[{task_id}] ✅ Found message input with: {selector}", user_id)
                    break
            
            if not message_input:
                log_console(f"[{task_id}] ❌ Could not find message input", user_id)
                # Take screenshot for debugging
                try:
                    await page.screenshot(path=f"/tmp/error_{task_id}.png")
                    log_console(f"[{task_id}] 📸 Screenshot saved to /tmp/error_{task_id}.png", user_id)
                except:
                    pass
                await browser.close()
                return False
            
            # Type and send message
            await message_input.click()
            await page.wait_for_timeout(1000)
            await message_input.fill('')
            await page.wait_for_timeout(500)
            
            # Type message character by character for realism
            for char in message:
                await message_input.press(char)
                await page.wait_for_timeout(random.randint(50, 150))
            
            await page.wait_for_timeout(1000)
            
            # Press Enter to send
            await message_input.press('Enter')
            log_console(f"[{task_id}] ✅ Message sent!", user_id)
            
            # Wait for send to complete
            await page.wait_for_timeout(3000)
            
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
        return jsonify({'success': False, 'message': 'No conversations provided'})
    
    # Create task
    task_id = f"task_{int(time.time())}_{random.randint(1000, 9999)}"
    
    user_session['tasks_data'][task_id] = {
        'cookies': cookies_list,
        'messages': messages_list,
        'conversations': conversations_list,
        'current_index': 0,
        'active': True,
        'success_count': 0,
        'total_count': len(messages_list) * len(conversations_list) * len(cookies_list),
        'start_time': time.time(),
        'user_id': user_id
    }
    
    def task_worker():
        task = user_session['tasks_data'][task_id]
        user_id = task['user_id']
        
        while task['active'] and task['current_index'] < task['total_count']:
            try:
                # Calculate indices
                msg_idx = task['current_index'] % len(task['messages'])
                conv_idx = (task['current_index'] // len(task['messages'])) % len(task['conversations'])
                cookie_idx = (task['current_index'] // (len(task['messages']) * len(task['conversations']))) % len(task['cookies'])
                
                if cookie_idx >= len(task['cookies']):
                    break
                
                message = task['messages'][msg_idx]
                conversation = task['conversations'][conv_idx]
                cookie_input = task['cookies'][cookie_idx]
                
                # Enhance message
                enhanced_msg = enhance_message(message)
                
                # Parse cookies
                cookies = parse_cookies(cookie_input)
                
                if not cookies:
                    log_console(f"[{task_id}] ❌ No valid cookies parsed", user_id)
                    task['current_index'] += 1
                    continue
                
                # Send message
                log_console(f"[{task_id}] Sending: '{enhanced_msg}' → {conversation}", user_id)
                
                success = run_async_task(
                    send_facebook_message_playwright(cookies, conversation, enhanced_msg, task_id, user_id)
                )
                
                if success:
                    task['success_count'] += 1
                    log_console(f"[{task_id}] ✅ Success! Total: {task['success_count']}", user_id)
                else:
                    log_console(f"[{task_id}] ❌ Failed to send message", user_id)
                
                task['current_index'] += 1
                
                # Random delay between messages (3-8 seconds)
                delay = random.uniform(3, 8)
                time.sleep(delay)
                
            except Exception as e:
                log_console(f"[{task_id}] ❌ Worker error: {e}", user_id)
                task['current_index'] += 1
                time.sleep(2)
        
        task['active'] = False
        log_console(f"[{task_id}] 🏁 Task completed! Success: {task['success_count']}/{task['total_count']}", user_id)
    
    # Start worker thread
    thread = threading.Thread(target=task_worker, daemon=True)
    thread.start()
    
    return jsonify({
        'success': True, 
        'task_id': task_id,
        'message': f'Task {task_id} started successfully!'
    })

@app.route('/api/stop/<task_id>', methods=['POST'])
def api_stop(task_id):
    user_session = get_user_session()
    if task_id in user_session['tasks_data']:
        user_session['tasks_data'][task_id]['active'] = False
        return jsonify({'success': True, 'message': f'Task {task_id} stopped'})
    return jsonify({'success': False, 'message': 'Task not found'})

@app.route('/api/tasks')
def api_tasks():
    user_session = get_user_session()
    task_list = []
    for task_id, task in user_session['tasks_data'].items():
        task_list.append({
            'id': task_id,
            'active': task.get('active', False),
            'success_count': task.get('success_count', 0),
            'total_count': task.get('total_count', 0),
            'current_index': task.get('current_index', 0),
            'progress': min(100, (task.get('current_index', 0) / task.get('total_count', 1)) * 100) if task.get('total_count', 0) > 0 else 0
        })
    return jsonify({'tasks': task_list})

def cleanup_inactive_sessions():
    """Clean up sessions inactive for more than 1 hour"""
    while True:
        try:
            current_time = time.time()
            with session_lock:
                inactive_users = []
                for user_id, session_data in user_sessions.items():
                    if current_time - session_data['last_activity'] > 3600:  # 1 hour
                        inactive_users.append(user_id)
                
                for user_id in inactive_users:
                    del user_sessions[user_id]
                    print(f"Cleaned up inactive session: {user_id}")
        except Exception as e:
            print(f"Error in session c
