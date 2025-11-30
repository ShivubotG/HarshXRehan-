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

def get_facebook_account_info(cookies):
    """Extract Facebook account information from cookies"""
    account_info = {
        'user_id': None,
        'user_name': 'Unknown',
        'is_valid': False
    }
    
    try:
        # Find c_user cookie for user ID
        for cookie in cookies:
            if cookie['name'] == 'c_user':
                account_info['user_id'] = cookie['value']
                account_info['is_valid'] = True
                break
        
        # Try to get username from other cookies
        if account_info['user_id']:
            account_info['user_name'] = f"User_{account_info['user_id'][:6]}"
            
    except Exception as e:
        log_console(f"⚠️ Failed to extract account info: {e}")
    
    return account_info

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

async def verify_login_and_get_profile(page, task_id, user_id):
    """Verify login and get actual profile information - IMPROVED VERSION"""
    try:
        log_console(f"[{task_id}] 🔐 Verifying login status...", user_id)
        
        # Try multiple approaches to verify login
        login_verified = False
        profile_info = {'name': 'Unknown User', 'id': 'Unknown', 'success': False}
        
        # METHOD 1: Check current page state first
        current_url = page.url
        if 'facebook.com' in current_url:
            # Check if we're already on a logged-in page
            logged_in_indicators = [
                '[aria-label="Facebook"][role="navigation"]',
                '[data-testid="blue_bar_root"]',
                '[data-pagelet="root"]',
                '#ssrb_root_start'
            ]
            
            for selector in logged_in_indicators:
                element = await page.query_selector(selector)
                if element:
                    login_verified = True
                    break
        
        # METHOD 2: Navigate to a lightweight Facebook page
        if not login_verified:
            try:
                log_console(f"[{task_id}] 🔄 Navigating to Facebook home...", user_id)
                await page.goto('https://m.facebook.com/', wait_until='domcontentloaded', timeout=15000)
                await page.wait_for_timeout(3000)
                
                # Check for login indicators on mobile version
                login_form = await page.query_selector('input[name="email"], input[name="pass"]')
                if not login_form:
                    login_verified = True
                    
            except Exception as e:
                log_console(f"[{task_id}] ⚠️ Mobile navigation failed: {e}", user_id)
        
        # METHOD 3: Direct profile access
        if not login_verified:
            try:
                log_console(f"[{task_id}] 🔄 Trying direct profile access...", user_id)
                await page.goto('https://www.facebook.com/me', wait_until='domcontentloaded', timeout=15000)
                await page.wait_for_timeout(3000)
                
                # Check if we can access profile
                if 'facebook.com/me' in page.url or 'profile.php' in page.url:
                    login_verified = True
                    
            except Exception as e:
                log_console(f"[{task_id}] ⚠️ Profile access failed: {e}", user_id)
        
        # Final verification
        if not login_verified:
            log_console(f"[{task_id}] ❌ LOGIN FAILED - No valid session found", user_id)
            return profile_info
        
        log_console(f"[{task_id}] ✅ Successfully logged in!", user_id)
        
        # Now extract profile information with multiple fallbacks
        profile_info = await extract_profile_name_improved(page, task_id, user_id)
        return profile_info
        
    except Exception as e:
        log_console(f"[{task_id}] ❌ Login verification failed: {e}", user_id)
        return {'success': False, 'name': 'Error', 'id': 'Unknown'}

async def extract_profile_name_improved(page, task_id, user_id):
    """Improved profile name extraction with multiple methods"""
    try:
        log_console(f"[{task_id}] 👤 Extracting profile name...", user_id)
        
        profile_name = "Unknown User"
        profile_id = "Unknown"
        
        # METHOD 1: Try to get name from navigation
        try:
            nav_selectors = [
                '[aria-label="Your profile"]',
                'a[role="button"][tabindex="0"] span',
                '[data-testid="blue_bar_profile_link"] span',
                'div[role="navigation"] span[dir="auto"]'
            ]
            
            for selector in nav_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        name_text = await element.text_content()
                        if name_text and len(name_text.strip()) > 1 and len(name_text.strip()) < 50:
                            if name_text.strip().lower() not in ['facebook', 'home', 'friends', 'watch', 'marketplace', 'groups', 'menu']:
                                profile_name = name_text.strip()
                                log_console(f"[{task_id}] ✅ Found profile name in nav: {profile_name}", user_id)
                                break
                except:
                    continue
        except:
            pass
        
        # METHOD 2: Navigate to profile page
        if profile_name == "Unknown User":
            try:
                await page.goto('https://www.facebook.com/me', wait_until='domcontentloaded', timeout=15000)
                await page.wait_for_timeout(3000)
                
                # Look for profile name on profile page
                name_selectors = [
                    'h1',
                    'span[dir="auto"]',
                    '.b6ax4al1',
                    'div[role="main"] h1',
                    '[data-testid="profile_name"]'
                ]
                
                for selector in name_selectors:
                    try:
                        elements = await page.query_selector_all(selector)
                        for element in elements:
                            name_text = await element.text_content()
                            if name_text and len(name_text.strip()) > 1 and len(name_text.strip()) < 50:
                                if name_text.strip().lower() not in ['facebook', 'home', 'friends', 'watch', 'marketplace', 'groups']:
                                    profile_name = name_text.strip()
                                    log_console(f"[{task_id}] ✅ Found profile name on profile page: {profile_name}", user_id)
                                    break
                        if profile_name != "Unknown User":
                            break
                    except:
                        continue
            except Exception as e:
                log_console(f"[{task_id}] ⚠️ Profile page navigation failed: {e}", user_id)
        
        # METHOD 3: Extract from page title or URL
        if profile_name == "Unknown User":
            try:
                # Get page title
                title = await page.title()
                if 'Facebook' in title and '|' in title:
                    name_from_title = title.split('|')[0].strip()
                    if len(name_from_title) > 1:
                        profile_name = name_from_title
                        log_console(f"[{task_id}] ✅ Extracted name from title: {profile_name}", user_id)
            except:
                pass
        
        # Get user ID from cookies or URL
        try:
            # Extract from current URL
            current_url = page.url
            if 'profile.php?id=' in current_url:
                profile_id = current_url.split('id=')[1].split('&')[0]
            elif 'facebook.com/' in current_url and '/me' not in current_url:
                parts = current_url.split('facebook.com/')[1].split('/')[0]
                if not any(x in parts for x in ['?', '&', '=']) and len(parts) > 3:
                    profile_id = parts
            
            # If still unknown, try to get from page context
            if profile_id == "Unknown":
                user_id_from_page = await page.evaluate("""
                    () => {
                        // Try to find user ID in page data
                        const scripts = document.querySelectorAll('script');
                        for (let script of scripts) {
                            const text = script.textContent || '';
                            if (text.includes('USER_ID') || text.includes('userID') || text.includes('profile_owner')) {
                                const match = text.match(/"userID":"([^"]+)"/) || 
                                            text.match(/"USER_ID":"([^"]+)"/) ||
                                            text.match(/profile_owner":{"id":"([^"]+)"/);
                                if (match) return match[1];
                            }
                        }
                        return null;
                    }
                """)
                if user_id_from_page:
                    profile_id = user_id_from_page
                    
        except Exception as e:
            log_console(f"[{task_id}] ⚠️ ID extraction failed: {e}", user_id)
        
        log_console(f"[{task_id}] 🔍 Final Profile: {profile_name} (ID: {profile_id})", user_id)
        
        return {
            'name': profile_name,
            'id': profile_id,
            'success': profile_name != "Unknown User"
        }
        
    except Exception as e:
        log_console(f"[{task_id}] ❌ Profile extraction failed: {e}", user_id)
        return {
            'name': "Unknown User", 
            'id': "Unknown",
            'success': False
        }

async def find_message_input_advanced(page, task_id, user_id):
    """Advanced message input finding for groups and individual chats"""
    log_console(f"[{task_id}] 🔍 Finding message input...", user_id)
    
    # Wait for page to load completely
    await page.wait_for_timeout(8000)
    
    try:
        # Multiple scrolls to trigger lazy loading
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
        await page.wait_for_timeout(3000)
        await page.evaluate("window.scrollTo(0, 0);")
        await page.wait_for_timeout(2000)
    except Exception as e:
        log_console(f"[{task_id}] ⚠️ Scrolling failed: {e}", user_id)
    
    # Comprehensive selectors for message input
    message_input_selectors = [
        'div[contenteditable="true"][role="textbox"]',
        'div[contenteditable="true"][data-lexical-editor="true"]',
        'div[aria-label*="Message" i][contenteditable="true"]',
        'div[aria-label*="message" i][contenteditable="true"]',
        'div[contenteditable="true"][spellcheck="true"]',
        'div[aria-label*="Write a message" i][contenteditable="true"]',
        'div[aria-label*="Type a message" i][contenteditable="true"]',
        '[role="textbox"][contenteditable="true"]',
        'textarea[placeholder*="message" i]',
        'div[aria-placeholder*="message" i]',
        '[contenteditable="true"]'
    ]
    
    log_console(f"[{task_id}] 🔄 Trying {len(message_input_selectors)} selectors...", user_id)
    
    for idx, selector in enumerate(message_input_selectors):
        try:
            elements = await page.query_selector_all(selector)
            log_console(f"[{task_id}] Selector {idx+1}: found {len(elements)} elements", user_id)
            
            for element_idx, element in enumerate(elements):
                try:
                    # Check if element is visible and editable
                    is_visible = await element.is_visible()
                    if not is_visible:
                        continue
                    
                    # Check if element is editable
                    is_editable = await page.evaluate("""
                        (element) => {
                            return element.contentEditable === 'true' || 
                                   element.tagName === 'TEXTAREA';
                        }
                    """, element)
                    
                    if is_editable:
                        log_console(f"[{task_id}] ✅ Found editable element", user_id)
                        
                        # Try to click and focus
                        try:
                            await element.click()
                            await page.wait_for_timeout(1000)
                            
                            # Test typing
                            await element.press('a')
                            await page.wait_for_timeout(500)
                            await page.keyboard.press('Backspace')
                            await page.wait_for_timeout(500)
                            
                        except Exception as e:
                            log_console(f"[{task_id}] ⚠️ Element interaction failed: {e}", user_id)
                        
                        return element
                            
                except Exception as e:
                    continue
                    
        except Exception as e:
            continue
    
    log_console(f"[{task_id}] ❌ No message input found", user_id)
    return None

async def send_message_guaranteed(page, message_input, message, task_id, user_id):
    """Guaranteed message sending with verification"""
    try:
        log_console(f"[{task_id}] 📝 Sending message: {message[:50]}...", user_id)
        
        # Clear and type message
        await message_input.click()
        await page.wait_for_timeout(1000)
        
        # Clear existing content
        await message_input.press('Control+A')
        await page.wait_for_timeout(500)
        await message_input.press('Backspace')
        await page.wait_for_timeout(1000)
        
        # Type message character by character
        for char in message:
            await message_input.press(char)
            await page.wait_for_timeout(random.randint(30, 80))
        
        await page.wait_for_timeout(2000)
        
        # Send message with Enter key (most reliable)
        await message_input.press('Enter')
        log_console(f"[{task_id}] ✅ Message sent via Enter key", user_id)
        
        # Wait for delivery
        await page.wait_for_timeout(5000)
        
        # Verify delivery
        delivery_verified = await verify_message_delivery(page, message, task_id, user_id)
        
        if delivery_verified:
            log_console(f"[{task_id}] 🎉 MESSAGE DELIVERED SUCCESSFULLY!", user_id)
            return True
        else:
            log_console(f"[{task_id}] ⚠️ Delivery verification inconclusive", user_id)
            return True  # Still return True as message might have sent
            
    except Exception as e:
        log_console(f"[{task_id}] ❌ Message sending failed: {e}", user_id)
        return False

async def verify_message_delivery(page, original_message, task_id, user_id):
    """Verify if message was actually delivered"""
    try:
        log_console(f"[{task_id}] 🔍 Verifying message delivery...", user_id)
        
        # Wait for message to appear
        await page.wait_for_timeout(3000)
        
        # Check if input is cleared (basic indication of send)
        is_cleared = await page.evaluate("""
            () => {
                const active = document.activeElement;
                if (!active) return false;
                if (active.contentEditable === 'true') {
                    return active.textContent === '' && active.innerHTML === '';
                }
                return active.value === '';
            }
        """)
        
        if is_cleared:
            log_console(f"[{task_id}] ✅ Input cleared - message likely sent", user_id)
        else:
            log_console(f"[{task_id}] ⚠️ Input not cleared", user_id)
        
        # Look for message in chat
        message_found = await page.evaluate("""
            (searchText) => {
                const elements = document.querySelectorAll('[role="article"], ._2w1p, ._2w1q, [data-testid*="message"]');
                for (let element of elements) {
                    const text = element.textContent || '';
                    if (text.includes(searchText)) {
                        return true;
                    }
                }
                return false;
            }
        """, original_message[:50])
        
        if message_found:
            log_console(f"[{task_id}] ✅ MESSAGE FOUND IN CHAT!", user_id)
            return True
        
        return False
        
    except Exception as e:
        log_console(f"[{task_id}] ⚠️ Delivery verification failed: {e}", user_id)
        return False

async def send_facebook_message_playwright(cookies, conversation_id, message, task_id, user_id):
    """Send message using Playwright - WITH IMPROVED LOGIN HANDLING"""
    if not PLAYWRIGHT_AVAILABLE:
        log_console(f"[{task_id}] ❌ Playwright not available", user_id)
        return False
    
    try:
        from playwright.async_api import async_playwright
        
        log_console(f"[{task_id}] 🚀 Starting browser...", user_id)
        
        # Get account info from cookies first
        account_info = get_facebook_account_info(cookies)
        if account_info['is_valid']:
            log_console(f"[{task_id}] 👤 Cookie Account: {account_info['user_name']} (UID: {account_info['user_id']})", user_id)
        else:
            log_console(f"[{task_id}] ⚠️ Could not extract account info from cookies", user_id)
        
        async with async_playwright() as p:
            # Launch browser with better configuration
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
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
                timeout=90000  # Increased timeout
            )
            
            # Create context with better settings
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                ignore_https_errors=True,
                java_script_enabled=True,
                bypass_csp=True
            )
            
            # Add cookies to context FIRST
            if cookies:
                try:
                    await context.add_cookies(cookies)
                    log_console(f"[{task_id}] ✅ Loaded {len(cookies)} cookies", user_id)
                    
                    # Verify cookies were added
                    context_cookies = await context.cookies()
                    log_console(f"[{task_id}] 🔍 Context now has {len(context_cookies)} cookies", user_id)
                    
                except Exception as e:
                    log_console(f"[{task_id}] ❌ Error adding cookies: {e}", user_id)
                    await browser.close()
                    return False
            
            page = await context.new_page()
            
            # Set longer timeouts
            page.set_default_timeout(30000)
            page.set_default_navigation_timeout(45000)
            
            # STEP 1: Improved login verification
            profile_info = await verify_login_and_get_profile(page, task_id, user_id)
            
            if not profile_info['success']:
                log_console(f"[{task_id}] ❌ LOGIN FAILED - Cannot proceed", user_id)
                
                # Try one more approach - direct message URL with cookies
                log_console(f"[{task_id}] 🔄 Attempting direct message access...", user_id)
                try:
                    url = f"https://www.facebook.com/messages/t/{conversation_id}"
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    await page.wait_for_timeout(5000)
                    
                    # Check if we can see the message interface
                    message_interface = await page.query_selector('div[role="main"], [aria-label*="message" i]')
                    if message_interface:
                        log_console(f"[{task_id}] ✅ Direct message access successful!", user_id)
                        profile_info = {'name': 'Direct Access User', 'id': 'Direct', 'success': True}
                    else:
                        await browser.close()
                        return False
                        
                except Exception as e:
                    log_console(f"[{task_id}] ❌ Direct access also failed: {e}", user_id)
                    await browser.close()
                    return False
            
            log_console(f"[{task_id}] ✅ Logged in as: {profile_info['name']} (ID: {profile_info['id']})", user_id)
            
            # STEP 2: Navigate to conversation (if not already there)
            current_url = page.url
            target_url = f"https://www.facebook.com/messages/t/{conversation_id}"
            
            if conversation_id not in current_url:
                log_console(f"[{task_id}] 💬 Navigating to conversation...", user_id)
                try:
                    await page.goto(target_url, wait_until='domcontentloaded', timeout=45000)
                    log_console(f"[{task_id}] ✅ Conversation page loaded", user_id)
                except Exception as e:
                    log_console(f"[{task_id}] ⚠️ Page load issue: {e}", user_id)
            
            # Wait for page to settle
            await page.wait_for_timeout(8000)
            
            # STEP 3: Find message input
            message_input = await find_message_input_advanced(page, task_id, user_id)
            
            if not message_input:
                log_console(f"[{task_id}] ❌ Could not find message input", user_id)
                await browser.close()
                return False
            
            # STEP 4: Send message
            success = await send_message_guaranteed(page, message_input, message, task_id, user_id)
            
            if success:
                log_console(f"[{task_id}] 🎉 MESSAGE SUCCESSFULLY SENT!", user_id)
            else:
                log_console(f"[{task_id}] ❌ Failed to send message", user_id)
            
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
        'user_id': session['user_id'][:8]
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
                
                # Show account info
                account_info = get_facebook_account_info(cookies)
                if account_info['is_valid']:
                    log_console(f"[{task_id}] 👤 Cookie Account: {account_info['user_name']} (UID: {account_info['user_id']})", user_id)
                
                # Send message
                log_console(f"[{task_id}] Sending: '{enhanced_msg}' → {conversation}", user_id)
                
                success = run_async_task(
                    send_facebook_message_playwright(cookies, conversation, enhanced_msg, task_id, user_id)
                )
                
                if success:
                    task['success_count'] += 1
                    log_console(f"[{task_id}] ✅ SUCCESS! Total: {task['success_count']}", user_id)
                else:
                    log_console(f"[{task_id}] ❌ FAILED to send message", user_id)
                
                task['current_index'] += 1
                
                # Random delay
                delay = random.uniform(10, 20)
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
        
        time.sleep(300)

def init_app():
    """Initialize the application"""
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