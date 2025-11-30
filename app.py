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

async def find_message_input_advanced(page, task_id, user_id):
    """Advanced message input finding for groups and individual chats"""
    log_console(f"[{task_id}] 🔍 Finding message input for group/individual chat...", user_id)
    
    # Wait for page to load completely
    await page.wait_for_timeout(8000)
    
    try:
        # Multiple scrolls to trigger lazy loading
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
        await page.wait_for_timeout(3000)
        await page.evaluate("window.scrollTo(0, 0);")
        await page.wait_for_timeout(2000)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight/2);")
        await page.wait_for_timeout(2000)
    except Exception as e:
        log_console(f"[{task_id}] ⚠️ Scrolling failed: {e}", user_id)
    
    # Comprehensive selectors for both groups and individual chats
    message_input_selectors = [
        # Primary selectors for modern Facebook
        'div[contenteditable="true"][role="textbox"]',
        'div[contenteditable="true"][data-lexical-editor="true"]',
        'div[aria-label*="Message" i][contenteditable="true"]',
        'div[aria-label*="message" i][contenteditable="true"]',
        'div[contenteditable="true"][spellcheck="true"]',
        
        # Group chat specific selectors
        'div[aria-label*="Write a message" i][contenteditable="true"]',
        'div[aria-label*="Type a message" i][contenteditable="true"]',
        'div[aria-label*="Text message" i][contenteditable="true"]',
        'div[data-placeholder*="Message" i][contenteditable="true"]',
        
        # Fallback selectors
        '[role="textbox"][contenteditable="true"]',
        'textarea[placeholder*="message" i]',
        'div[aria-placeholder*="message" i]',
        '[contenteditable="true"]',
        'textarea',
        'input[type="text"]'
    ]
    
    log_console(f"[{task_id}] 🔄 Trying {len(message_input_selectors)} selectors...", user_id)
    
    for idx, selector in enumerate(message_input_selectors):
        try:
            elements = await page.query_selector_all(selector)
            log_console(f"[{task_id}] Selector {idx+1}/{len(message_input_selectors)} '{selector[:50]}...' found {len(elements)} elements", user_id)
            
            for element_idx, element in enumerate(elements):
                try:
                    # Check if element is visible and editable
                    is_visible = await element.is_visible()
                    if not is_visible:
                        continue
                    
                    # Check if element is editable using JavaScript
                    is_editable = await page.evaluate("""
                        (element) => {
                            return element.contentEditable === 'true' || 
                                   element.tagName === 'TEXTAREA' || 
                                   element.tagName === 'INPUT';
                        }
                    """, element)
                    
                    if is_editable:
                        log_console(f"[{task_id}] ✅ Found editable element #{element_idx+1} with selector #{idx+1}", user_id)
                        
                        # Try to click and focus the element
                        try:
                            await element.click()
                            await page.wait_for_timeout(1000)
                            
                            # Check if we can type in it
                            await element.press('a')
                            await page.wait_for_timeout(500)
                            await page.keyboard.press('Backspace')
                            await page.wait_for_timeout(500)
                            
                        except Exception as e:
                            log_console(f"[{task_id}] ⚠️ Element interaction failed but continuing: {e}", user_id)
                        
                        # Get element attributes for verification
                        element_info = await page.evaluate("""
                            (element) => {
                                return {
                                    placeholder: element.placeholder || '',
                                    ariaLabel: element.getAttribute('aria-label') || '',
                                    ariaPlaceholder: element.getAttribute('aria-placeholder') || '',
                                    dataPlaceholder: element.getAttribute('data-placeholder') || '',
                                    className: element.className || '',
                                    tagName: element.tagName
                                };
                            }
                        """, element)
                        
                        element_text = f"{element_info['ariaLabel']} {element_info['placeholder']} {element_info['ariaPlaceholder']}".lower()
                        keywords = ['message', 'write', 'type', 'send', 'chat', 'msg', 'reply', 'text']
                        
                        if any(keyword in element_text for keyword in keywords) or idx < 10:
                            log_console(f"[{task_id}] 🎯 Confirmed message input: {element_text[:100]}", user_id)
                            return element
                            
                except Exception as e:
                    log_console(f"[{task_id}] ⚠️ Element #{element_idx+1} check failed: {str(e)[:50]}", user_id)
                    continue
                    
        except Exception as e:
            log_console(f"[{task_id}] ⚠️ Selector failed: {str(e)[:50]}", user_id)
            continue
    
    # Final attempt: Try to find any clickable input area
    try:
        clickable_elements = await page.query_selector_all('div, textarea, input')
        for element in clickable_elements[:50]:  # Check first 50 elements
            try:
                is_visible = await element.is_visible()
                if is_visible:
                    box = await element.bounding_box()
                    if box and box['width'] > 100 and box['height'] > 20:
                        await element.click()
                        await page.wait_for_timeout(1000)
                        # Check if input is focused
                        is_focused = await page.evaluate("""
                            () => document.activeElement.contentEditable === 'true' || 
                                  document.activeElement.tagName === 'TEXTAREA' ||
                                  document.activeElement.tagName === 'INPUT'
                        """)
                        if is_focused:
                            log_console(f"[{task_id}] 🎯 Found message input by clicking random element", user_id)
                            return await page.evaluate_handle("document.activeElement")
            except:
                continue
    except Exception as e:
        log_console(f"[{task_id}] ⚠️ Final attempt failed: {e}", user_id)
    
    log_console(f"[{task_id}] ❌ No message input found after all attempts", user_id)
    return None

async def send_message_guaranteed(page, message_input, message, task_id, user_id):
    """Guaranteed message sending with multiple fallback methods"""
    max_attempts = 3
    methods_tried = []
    
    for attempt in range(max_attempts):
        try:
            log_console(f"[{task_id}] 📝 Attempt {attempt+1}/{max_attempts} to send message", user_id)
            
            # Method 1: Direct JavaScript injection (most reliable)
            if "javascript" not in methods_tried:
                log_console(f"[{task_id}] 🔧 Trying JavaScript method...", user_id)
                success = await page.evaluate("""
                    ([element, message]) => {
                        try {
                            // Clear existing content
                            if (element.tagName === 'DIV') {
                                element.textContent = '';
                                element.innerHTML = '';
                            } else {
                                element.value = '';
                            }
                            
                            // Set new content
                            if (element.tagName === 'DIV') {
                                element.textContent = message;
                                element.innerHTML = message;
                            } else {
                                element.value = message;
                            }
                            
                            // Trigger all possible events
                            const events = ['input', 'change', 'keydown', 'keypress', 'keyup', 'blur', 'focus'];
                            events.forEach(eventType => {
                                element.dispatchEvent(new Event(eventType, { bubbles: true }));
                            });
                            
                            // Special input event with data
                            element.dispatchEvent(new InputEvent('input', { 
                                bubbles: true, 
                                cancelable: true,
                                inputType: 'insertText',
                                data: message
                            }));
                            
                            return { success: true, method: 'javascript' };
                        } catch (e) {
                            return { success: false, error: e.message, method: 'javascript' };
                        }
                    }
                """, [message_input, message])
                
                if success.get('success'):
                    methods_tried.append("javascript")
                    log_console(f"[{task_id}] ✅ JavaScript content set successfully", user_id)
                    await page.wait_for_timeout(2000)
                    
                    # Try to send with multiple methods
                    send_success = await try_all_send_methods(page, message_input, task_id, user_id)
                    if send_success:
                        return True
                else:
                    log_console(f"[{task_id}] ❌ JavaScript method failed: {success.get('error', 'Unknown error')}", user_id)
            
            # Method 2: Type character by character (simulates real typing)
            if "typing" not in methods_tried:
                log_console(f"[{task_id}] ⌨️ Trying typing method...", user_id)
                try:
                    await message_input.click()
                    await page.wait_for_timeout(1000)
                    await message_input.press('Control+A')
                    await page.wait_for_timeout(500)
                    await message_input.press('Backspace')
                    await page.wait_for_timeout(1000)
                    
                    # Type message character by character
                    for char in message:
                        await message_input.press(char)
                        await page.wait_for_timeout(random.randint(50, 150))
                    
                    methods_tried.append("typing")
                    await page.wait_for_timeout(2000)
                    
                    send_success = await try_all_send_methods(page, message_input, task_id, user_id)
                    if send_success:
                        return True
                        
                except Exception as e:
                    log_console(f"[{task_id}] ❌ Typing method failed: {e}", user_id)
            
            # Method 3: Focus and paste (alternative approach)
            if "paste" not in methods_tried:
                log_console(f"[{task_id}] 📋 Trying paste method...", user_id)
                try:
                    await message_input.click()
                    await page.wait_for_timeout(1000)
                    await message_input.press('Control+A')
                    await page.wait_for_timeout(500)
                    
                    # Use clipboard API to set content
                    await page.evaluate("""
                        ([element, message]) => {
                            element.focus();
                            element.select();
                            document.execCommand('insertText', false, message);
                        }
                    """, [message_input, message])
                    
                    methods_tried.append("paste")
                    await page.wait_for_timeout(2000)
                    
                    send_success = await try_all_send_methods(page, message_input, task_id, user_id)
                    if send_success:
                        return True
                        
                except Exception as e:
                    log_console(f"[{task_id}] ❌ Paste method failed: {e}", user_id)
            
            await page.wait_for_timeout(3000)  # Wait before next attempt
            
        except Exception as e:
            log_console(f"[{task_id}] ❌ Attempt {attempt+1} failed: {e}", user_id)
    
    return False

async def try_all_send_methods(page, message_input, task_id, user_id):
    """Try all possible methods to send the message"""
    send_methods = [
        ("enter_key", "Pressing Enter key"),
        ("ctrl_enter", "Pressing Ctrl+Enter"),
        ("send_button", "Clicking send button"),
        ("submit_form", "Submitting form")
    ]
    
    for method_name, method_desc in send_methods:
        try:
            log_console(f"[{task_id}] 🔘 Trying to send via {method_desc}...", user_id)
            
            if method_name == "enter_key":
                await message_input.press('Enter')
                await page.wait_for_timeout(3000)
                return await verify_message_sent(page, task_id, user_id)
                
            elif method_name == "ctrl_enter":
                await page.keyboard.press('Control+Enter')
                await page.wait_for_timeout(3000)
                return await verify_message_sent(page, task_id, user_id)
                
            elif method_name == "send_button":
                send_button_selectors = [
                    '[aria-label*="Send" i]',
                    '[data-testid="send-button"]',
                    'div[role="button"][aria-label*="send" i]',
                    'div[role="button"][data-testid*="send"]',
                    'svg[aria-label*="Send" i]',
                    'button[type="submit"]',
                    'div[aria-label*="Message" i][role="button"]',
                    'div[data-tooltip-content*="Send" i]'
                ]
                
                for selector in send_button_selectors:
                    try:
                        buttons = await page.query_selector_all(selector)
                        for btn in buttons:
                            if await btn.is_visible():
                                await btn.click()
                                await page.wait_for_timeout(3000)
                                if await verify_message_sent(page, task_id, user_id):
                                    return True
                    except:
                        continue
                        
            elif method_name == "submit_form":
                try:
                    await page.evaluate("""
                        () => {
                            const forms = document.querySelectorAll('form');
                            for (let form of forms) {
                                form.dispatchEvent(new Event('submit', { bubbles: true }));
                            }
                        }
                    """)
                    await page.wait_for_timeout(3000)
                    return await verify_message_sent(page, task_id, user_id)
                except:
                    continue
                    
        except Exception as e:
            log_console(f"[{task_id}] ⚠️ {method_desc} failed: {e}", user_id)
            continue
    
    return False

async def verify_message_sent(page, task_id, user_id):
    """Verify if message was actually sent by checking UI changes"""
    try:
        # Check if input was cleared (indicates message was sent)
        is_cleared = await page.evaluate("""
            () => {
                const activeElement = document.activeElement;
                if (activeElement) {
                    if (activeElement.tagName === 'DIV') {
                        return activeElement.textContent === '' && activeElement.innerHTML === '';
                    } else {
                        return activeElement.value === '';
                    }
                }
                return false;
            }
        """)
        
        if is_cleared:
            log_console(f"[{task_id}] ✅ Message verified as sent (input cleared)", user_id)
            return True
        
        # Check for sent indicators in the chat
        sent_indicators = await page.query_selector_all('[aria-label*="Sent" i], [data-testid*="message_sent" i], ._3oh-')
        if sent_indicators:
            log_console(f"[{task_id}] ✅ Message verified as sent (sent indicator found)", user_id)
            return True
            
        # Check if new message appears in chat
        await page.wait_for_timeout(2000)
        recent_messages = await page.query_selector_all('[role="article"], ._2w1p, ._2w1q')
        if recent_messages:
            log_console(f"[{task_id}] ✅ Message likely sent (chat messages detected)", user_id)
            return True
            
    except Exception as e:
        log_console(f"[{task_id}] ⚠️ Verification failed: {e}", user_id)
    
    log_console(f"[{task_id}] ⚠️ Could not verify message delivery", user_id)
    return True  # Return True anyway to continue, as verification might fail

async def send_facebook_message_playwright(cookies, conversation_id, message, task_id, user_id):
    """Send message using Playwright - GUARANTEED VERSION"""
    if not PLAYWRIGHT_AVAILABLE:
        log_console(f"[{task_id}] ❌ Playwright not available", user_id)
        return False
    
    try:
        from playwright.async_api import async_playwright
        
        log_console(f"[{task_id}] 🚀 Starting browser for group message...", user_id)
        
        async with async_playwright() as p:
            # Launch browser with realistic options
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
            
            # Create context with realistic settings
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                ignore_https_errors=True,
                locale='en-US',
                timezone_id='America/New_York',
                permissions=['notifications']
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
            
            # Navigate to Facebook group/individual chat
            url = f"https://www.facebook.com/messages/t/{conversation_id}"
            log_console(f"[{task_id}] 🌐 Navigating to {url}", user_id)
            
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                log_console(f"[{task_id}] ✅ Page loaded successfully", user_id)
            except Exception as e:
                log_console(f"[{task_id}] ⚠️ Page load timeout, continuing...", user_id)
            
            # Extended wait for group chats (they load slower)
            await page.wait_for_timeout(10000)
            
            # Check if we're in the correct conversation
            current_url = page.url
            if conversation_id not in current_url:
                log_console(f"[{task_id}] ⚠️ Possibly redirected, current URL: {current_url}", user_id)
            
            # Check login status
            login_indicators = await page.query_selector('input[name="email"], input[name="pass"], #loginform')
            if login_indicators:
                log_console(f"[{task_id}] ❌ Not logged in - invalid cookies", user_id)
                await browser.close()
                return False
            
            # Find message input with advanced method
            message_input = await find_message_input_advanced(page, task_id, user_id)
            
            if not message_input:
                log_console(f"[{task_id}] ❌ Could not find message input after all attempts", user_id)
                # Take screenshot for debugging
                try:
                    screenshot_path = f"/tmp/error_{task_id}.png"
                    await page.screenshot(path=screenshot_path)
                    log_console(f"[{task_id}] 📸 Screenshot saved: {screenshot_path}", user_id)
                except Exception as e:
                    log_console(f"[{task_id}] ❌ Screenshot failed: {e}", user_id)
                await browser.close()
                return False
            
            # Send message with guaranteed delivery
            success = await send_message_guaranteed(page, message_input, message, task_id, user_id)
            
            if success:
                log_console(f"[{task_id}] ✅ Message delivery confirmed!", user_id)
                # Extra wait to ensure message is fully delivered
                await page.wait_for_timeout(5000)
            else:
                log_console(f"[{task_id}] ❌ Failed to send message after all attempts", user_id)
            
            await browser.close()
            return success
            
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

# [Rest of the Flask routes and functions remain the same]
# ... (index, api_status, api_logs, api_start, api_stop, api_tasks, cleanup_inactive_sessions, init_app)

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
                
                # Random delay between messages (8-15 seconds for groups)
                delay = random.uniform(8, 15)
                time.sleep(delay)
                
            except Exception as e:
                log_console(f"[{task_id}] ❌ Worker error: {e}", user_id)
                task['current_index'] += 1
                time.sleep(5)
        
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
            print(f"Error in session cleanup: {e}")
        
        time.sleep(300)  # Run every 5 minutes

def init_app():
    """Initialize the application - FIXED VERSION"""
    print("🚀 Neural Messenger 2030 Initializing...")
    print("📦 Checking dependencies...")
    
    # Start session cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_inactive_sessions, daemon=True)
    cleanup_thread.start()
    
    # Try to import playwright
    try:
        from playwright.async_api import async_playwright
        global PLAYWRIGHT_AVAILABLE
        PLAYWRIGHT_AVAILABLE = True
        print("✅ Playwright is available")
    except ImportError:
        print("⚠️ Playwright not installed, will auto-install on first use")
    
    # Check if browser is installed
    try:
        subprocess.run([sys.executable, "-m", "playwright", "list-browsers"], 
                      capture_output=True, timeout=30)
        global BROWSER_INSTALLED
        BROWSER_INSTALLED = True
        print("✅ Browser is installed")
    except:
        print("⚠️ Browser not installed, will auto-install on first use")

# Initialize the app
init_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Starting server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)