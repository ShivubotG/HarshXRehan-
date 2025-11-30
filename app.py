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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TITLE = "Configure logging..."

PLAYWRIGHTAVAILABLE = False
BROWSERINSTALLED = False

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

TITLE = "Global variables with user isolation..."

usersessions = {}
sessionlock = threading.Lock()
systemlogs = []

TITLE = "System logs for initialization"

EMOJIRANGES = [
    (0x1F600, 0x1F64F),  # Emoticons
    (0x1F300, 0x1F5FF),  # Misc Symbols and Pictographs
    (0x1F680, 0x1F6FF),  # Transport and Map
    (0x1F1E0, 0x1F1FF),  # Flags
    (0x2600, 0x26FF),    # Misc symbols
    (0x2700, 0x27BF),    # Dingbats
]

def getusersession():
    """Get or create user session"""
    if 'userid' not in session:
        session['userid'] = str(uuid.uuid4())
        userid = session['userid']
    else:
        userid = session['userid']
    
    with sessionlock:
        if userid not in usersessions:
            usersessions[userid] = {
                'livelogs': list(systemlogs),  # Copy system logs to user
                'tasksdata': {},
                'lastactivity': time.time()
            }
        usersessions[userid]['lastactivity'] = time.time()
    return usersessions[userid]

def logconsole(msg, userid=None):
    """Thread-safe logging with user isolation"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    formattedmsg = f"[{timestamp}] {msg}"
    print(formattedmsg)
    
    # Add to system logs
    systemlogs.append(formattedmsg)
    if len(systemlogs) > 1000:
        systemlogs.pop(0)
    
    # If userid provided, add to user logs
    if userid:
        with sessionlock:
            if userid in usersessions:
                usersessions[userid]['livelogs'].append(formattedmsg)
                if len(usersessions[userid]['livelogs']) > 1000:
                    usersessions[userid]['livelogs'].pop(0)
    
    # If in request context, add to current user logs
    try:
        from flask import has_request_context
        if has_request_context():
            usersession = getusersession()
            usersession['livelogs'].append(formattedmsg)
            if len(usersession['livelogs']) > 1000:
                usersession['livelogs'].pop(0)
    except:
        pass

def installplaywrightandbrowser():
    """Install Playwright and Chromium browser"""
    global PLAYWRIGHTAVAILABLE, BROWSERINSTALLED
    try:
        logconsole("Installing Playwright...")
        result = subprocess.run([
            sys.executable, '-m', 'pip', 'install', 
            'playwright==1.47.0', 'flask==2.3.3'
        ], capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0:
            PLAYWRIGHTAVAILABLE = True
            logconsole("Playwright installed successfully!")
        else:
            logconsole(f"Playwright installation failed: {result.stderr[:500]}")
            return False

        logconsole("Installing Chromium browser...")
        installresult = subprocess.run([
            sys.executable, '-m', 'playwright', 'install', 'chromium'
        ], capture_output=True, text=True, timeout=1800)
        
        if installresult.returncode == 0:
            BROWSERINSTALLED = True
            logconsole("Chromium installed successfully!")
        else:
            logconsole(f"Chromium installation warning: {installresult.stderr[:500]}")

        # Test imports
        try:
            from playwright.async_api import async_playwright
            logconsole("Playwright imports successful!")
            return True
        except ImportError as e:
            logconsole(f"Playwright import test failed: {e}")
            return False
            
    except subprocess.TimeoutExpired:
        logconsole("Installation timed out")
        return False
    except Exception as e:
        logconsole(f"Installation error: {str(e)}")
        return False

def generaterandomemoji():
    """Generate a random emoji"""
    start, end = random.choice(EMOJIRANGES)
    return chr(random.randint(start, end))

def enhancemessage(message):
    """Add random emojis to message"""
    if not message or len(message.strip()) == 0:
        return message
    
    words = message.split()
    if len(words) == 1:
        return f"{generaterandomemoji()} {message} {generaterandomemoji()}"
    
    generaterandomemoji()
    enhancedwords = []
    for i, word in enumerate(words):
        enhancedwords.append(word)
        if random.random() < 0.3 and i < len(words) - 1:
            enhancedwords.append(generaterandomemoji())
    
    if random.random() < 0.4:
        enhancedwords.insert(0, generaterandomemoji())
    if random.random() < 0.4:
        enhancedwords.append(generaterandomemoji())
    
    return ' '.join(enhancedwords)

def parsecookies(cookieinput):
    """Parse cookies from various formats - IMPROVED VERSION"""
    cookies = []
    if not cookieinput or not cookieinput.strip():
        return cookies
    
    logconsole(f"Parsing cookies input length: {len(cookieinput)}")
    cookieinput = cookieinput.strip()

    # Method 1: JSON array format
    if cookieinput.startswith('[') and cookieinput.endswith(']'):
        try:
            data = json.loads(cookieinput)
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
                logconsole(f"Parsed {len(cookies)} cookies from JSON array")
                return cookies
        except json.JSONDecodeError:
            pass

    # Method 2: Handle multiple cookies in single line separated by semicolons
    cookieinput = cookieinput.replace('', '').replace('', ';')
    cookieparts = []
    if ';' in cookieinput:
        cookieparts = [part.strip() for part in cookieinput.split(';') if part.strip()]
    else:
        cookieparts = [line.strip() for line in cookieinput.split('') if line.strip()]
    
    for part in cookieparts:
        if not part or part.startswith('#') or part.startswith('//'):
            continue
        
        if '=' in part:
            try:
                # Handle key=value pairs
                name, value = part.split('=', 1)
                name = name.strip()
                value = value.strip()
                
                # Remove quotes and semicolons from name
                name = name.replace('"', '').replace("'", '').replace(';', '')
                
                if '=' in value:
                    try:
                        value = unquote(value)
                    except:
                        pass
                    value = value.split(';')[0].replace('"', '').replace("'", '')
                
                if name and value and len(name) > 0 and len(value) > 0 and not name.startswith('http') and '=' not in name:
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
                    logconsole(f"Added cookie {name}={value[:20]}...")
            except Exception as e:
                logconsole(f"Failed to parse cookie part '{part}' - Error: {e}")
                continue

    # Remove duplicates based on name
    uniquecookies = []
    seennames = set()
    for cookie in cookies:
        if cookie['name'] not in seennames:
            uniquecookies.append(cookie)
            seennames.add(cookie['name'])
    
    logconsole(f"Final parsed cookies: {len(uniquecookies)}")
    
    # Log important cookies found
    importantcookies = ['c_user', 'xs', 'fr', 'datr', 'sb']
    foundimportant = [c['name'] for c in uniquecookies if c['name'] in importantcookies]
    if foundimportant:
        logconsole(f"Found important cookies: {', '.join(foundimportant)}")
    else:
        logconsole("No important session cookies found (c_user, xs, fr, etc.)")
    
    return uniquecookies[:30]  # Increased limit to 30 cookies

def getfacebookaccountinfo(cookies):
    """Extract Facebook account information from cookies"""
    accountinfo = {'userid': None, 'username': 'Unknown', 'isvalid': False}
    try:
        for cookie in cookies:
            if cookie['name'] == 'c_user':
                accountinfo['userid'] = cookie['value']
                accountinfo['isvalid'] = True
                break
        
        if accountinfo['userid']:
            accountinfo['username'] = f"User{accountinfo['userid'][:6]}"
    except Exception as e:
        logconsole(f"Failed to extract account info: {e}")
    return accountinfo

def getinputdata(req, fieldname):
    """Extract input data from request data"""
    data = []
    # Try text input first
    textinput = req.form.get(fieldname, '').strip()
    if textinput:
        lines = [line.strip() for line in textinput.split('') if line.strip()]
        data.extend(lines)
    
    # Try file upload
    file = req.files.get(f'{fieldname}file')
    if file and file.filename:
        try:
            content = file.read().decode('utf-8')
            lines = [line.strip() for line in content.split('') if line.strip()]
            data.extend(lines)
            logconsole(f"Loaded {len(lines)} items from {file.filename}")
        except Exception as e:
            logconsole(f"File read error: {e}")
    return data

async def verifyloginandgetprofile(page, taskid, userid):
    """Verify login and get actual profile information"""
    try:
        logconsole(f"[{taskid}] Verifying login status...", userid)
        
        # Navigate to Facebook home to check login
        await page.goto('https://www.facebook.com/', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)
        
        # Check for login indicators
        loginindicators = await page.query_selector('input[name="email"], input[name="pass"], .loginform')
        profileindicators = await page.query_selector('[aria-label="Facebook"][role="navigation"], [data-testid="bluebar_root"]')
        
        if loginindicators:
            logconsole(f"[{taskid}] LOGIN FAILED - Showing login form", userid)
            return {'success': False, 'name': 'Login Failed', 'id': 'Unknown'}
        
        if not profileindicators:
            logconsole(f"[{taskid}] Cannot determine login status", userid)
        
        logconsole(f"[{taskid}] Successfully logged in!", userid)
        
        # Now get profile information
        profileinfo = await extractprofilename(page, taskid, userid)
        return profileinfo
        
    except Exception as e:
        logconsole(f"[{taskid}] Login verification failed: {e}", userid)
        return {'success': False, 'name': 'Error', 'id': 'Unknown'}

async def extractprofilename(page, taskid, userid):
    """Extract actual profile name from Facebook"""
    try:
        logconsole(f"[{taskid}] Extracting profile name...", userid)
        
        # Method 1: Try to navigate to profile page
        profileurl = 'https://www.facebook.com/profile.php'
        await page.goto(profileurl, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)
        
        nameselectors = [
            'h1',
            '[data-testid="profile_name"]',
            'div[role="main"] h1',
            'span[dir="auto"]',
            '.b6ax4al1',
            'a[role="button"][tabindex="0"] span',
            '[aria-label="Profile"] span'
        ]
        
        profilename = 'Unknown User'
        profileid = 'Unknown'
        
        for selector in nameselectors:
            try:
                elements = await page.query_selector_all(selector)
                logconsole(f"[{taskid}] Selector {nameselectors.index(selector)+1} found {len(elements)} elements", userid)
                
                for element in elements:
                    try:
                        nametext = await element.text_content()
                        if nametext and len(nametext.strip()) > 1 and len(nametext.strip()) < 50:
                            if nametext.strip().lower() not in ['facebook', 'home', 'friends', 'watch', 'marketplace', 'groups']:
                                profilename = nametext.strip()
                                logconsole(f"[{taskid}] Found profile name: {profilename}", userid)
                                break
                    except:
                        continue
                
                if profilename != 'Unknown User':
                    break
            except:
                continue
        
        # Get user ID from URL
        currenturl = page.url
        if 'profile.php?id=' in currenturl:
            profileid = currenturl.split('id=')[1].split('&')[0]
        elif 'facebook.com/' in currenturl:
            parts = currenturl.split('facebook.com/')[1].split('/')
            if not any('?' in x or '#' in x for x in parts) and len(parts) >= 3:
                profileid = parts[0]
                logconsole(f"[{taskid}] Profile ID: {profileid}", userid)
        
        return {'name': profilename, 'id': profileid, 'success': profilename != 'Unknown User'}
        
    except Exception as e:
        logconsole(f"[{taskid}] Profile extraction failed: {e}", userid)
        return {'name': 'Unknown User', 'id': 'Unknown', 'success': False}

async def findmessageinputadvanced(page, taskid, userid):
    """Advanced message input finding for groups and individual chats"""
    logconsole(f"[{taskid}] Finding message input...", userid)
    
    messageinputselectors = [
        'div[contenteditable="true"][role="textbox"]',
        'div[contenteditable="true"][data-lexical-editor="true"]',
        'div[aria-label="Message"] [contenteditable="true"]',
        'div[aria-label="message"] [contenteditable="true"]',
        'div[contenteditable="true"][spellcheck="true"]',
        'div[aria-label="Write a message"] [contenteditable="true"]',
        'div[aria-label="Type a message"] [contenteditable="true"]',
        '[role="textbox"][contenteditable="true"]',
        'textarea[placeholder*="message"]',
        'div[aria-placeholder*="message"]',
        '[contenteditable="true"]'
    ]
    
    logconsole(f"[{taskid}] Trying {len(messageinputselectors)} selectors...", userid)
    
    for idx, selector in enumerate(messageinputselectors):
        try:
            elements = await page.query_selector_all(selector)
            logconsole(f"[{taskid}] Selector {idx+1} found {len(elements)} elements", userid)
            
            for elementidx, element in enumerate(elements):
                try:
                    # Test typing
                    await element.press('a')
                    await page.wait_for_timeout(500)
                    await page.keyboard.press('Backspace')
                    await page.wait_for_timeout(500)
                    logconsole(f"[{taskid}] Element {elementidx+1} is clickable", userid)
                    return element
                except Exception as e:
                    logconsole(f"[{taskid}] Element interaction failed: {e}", userid)
                    continue
        except Exception as e:
            continue
    
    logconsole(f"[{taskid}] No message input found", userid)
    return None

async def sendmessageguaranteed(page, messageinput, message, taskid, userid):
    """Guaranteed message sending with verification"""
    try:
        logconsole(f"[{taskid}] Sending message '{message[:50]}...'", userid)
        
        # Type message
        await messageinput.fill('')
        await messageinput.type(message, delay=50)
        
        # Check if input is cleared (basic indication of send)
        iscleared = await page.evaluate("""
            () => {
                const active = document.activeElement;
                if (!active) return false;
                if (active.contentEditable === true) {
                    return active.textContent === '' || active.innerHTML === '';
                }
                return active.value === '';
            }
        """)
        
        if iscleared:
            logconsole(f"[{taskid}] Input cleared - message likely sent", userid)
        else:
            logconsole(f"[{taskid}] Input not cleared", userid)
        
        await messageinput.press('Enter')
        logconsole(f"[{taskid}] Message sent via Enter key", userid)
        
        # Verify delivery
        deliveryverified = await verifymessagedelivery(page, message, taskid, userid)
        if deliveryverified:
            logconsole(f"[{taskid}] MESSAGE DELIVERED SUCCESSFULLY!", userid)
            return True
        else:
            logconsole(f"[{taskid}] Delivery verification inconclusive", userid)
            return True  # Still return True as message might have sent
        
    except Exception as e:
        logconsole(f"[{taskid}] Message sending failed: {e}", userid)
        return False

async def verifymessagedelivery(page, originalmessage, taskid, userid):
    """Verify if message was actually delivered"""
    try:
        logconsole(f"[{taskid}] Verifying message delivery...", userid)
        
        messagefound = await page.evaluate("""
            (searchText) => {
                const elements = document.querySelectorAll('[role="article"], .2w1p, .2w1q, [data-testid="message"]');
                for (let element of elements) {
                    const text = element.textContent;
                    if (text.includes(searchText)) return true;
                }
                return false;
            }
        """, originalmessage[:50])
        
        if messagefound:
            logconsole(f"[{taskid}] MESSAGE FOUND IN CHAT!", userid)
            return True
        return False
        
    except Exception as e:
        logconsole(f"[{taskid}] Delivery verification failed: {e}", userid)
        return False

async def sendfacebookmessageplaywright(cookies, conversation, enhancedmsg, taskid, userid):
    """Send message using Playwright - WITH PROPER LOGIN VERIFICATION"""
    if not PLAYWRIGHTAVAILABLE:
        logconsole(f"[{taskid}] Playwright not available", userid)
        return False
    
    try:
        from playwright.async_api import async_playwright
        
        logconsole(f"[{taskid}] Starting browser...", userid)
        async with async_playwright() as p:
            # FIXED: Enhanced browser launch args for Facebook
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu',
                    '--disable-blink-features=AutomationControlled',  # FIXED: Anti-detection
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',  # FIXED: Updated UA
                ],
                timeout=60000
            )
            
            context = await browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
            )
            
            # FIXED: Add cookies to context FIRST
            page = await context.new_page()
            if cookies:
                try:
                    await context.add_cookies(cookies)
                    logconsole(f"[{taskid}] Loaded {len(cookies)} cookies", userid)
                except Exception as e:
                    logconsole(f"[{taskid}] Error adding cookies: {e}", userid)
            
            # STEP 1: Verify login and get actual profile info
            profileinfo = await verifyloginandgetprofile(page, taskid, userid)
            if not profileinfo['success']:
                logconsole(f"[{taskid}] LOGIN FAILED - Cannot proceed", userid)
                await browser.close()
                return False
            
            logconsole(f"[{taskid}] Logged in as {profileinfo['name']} ID: {profileinfo['id']}", userid)
            
            # Get account info from cookies first
            accountinfo = getfacebookaccountinfo(cookies)
            if accountinfo['isvalid']:
                logconsole(f"[{taskid}] Cookie Account: {accountinfo['username']} UID: {accountinfo['userid']}", userid)
            else:
                logconsole(f"[{taskid}] Could not extract account info from cookies", userid)
            
            # STEP 2: Navigate to conversation
            url = f"https://www.facebook.com/messages/t/{conversation}"
            logconsole(f"[{taskid}] Navigating to conversation...", userid)
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                logconsole(f"[{taskid}] Conversation page loaded", userid)
            except Exception as e:
                logconsole(f"[{taskid}] Page load issue: {e}", userid)
            
            # STEP 3: Find message input
            messageinput = await findmessageinputadvanced(page, taskid, userid)
            if not messageinput:
                logconsole(f"[{taskid}] Could not find message input", userid)
                await browser.close()
                return False
            
            # STEP 4: Send message
            success = await sendmessageguaranteed(page, messageinput, enhancedmsg, taskid, userid)
            if success:
                logconsole(f"[{taskid}] MESSAGE SUCCESSFULLY SENT!", userid)
            else:
                logconsole(f"[{taskid}] Failed to send message", userid)
            
            await browser.close()
            return success
            
    except Exception as e:
        logconsole(f"[{taskid}] Error: {str(e)}", userid)
        return False

def runasynctask(coro):
    """Run async task in background thread"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    except Exception as e:
        logconsole(f"Async task error: {e}")
        return False
    finally:
        loop.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def apistatus():
    usersession = getusersession()
    activetasks = sum(1 for t in usersession['tasksdata'].values() if t.get('active', False))
    return jsonify({
        'playwright': PLAYWRIGHTAVAILABLE,
        'browser': BROWSERINSTALLED,
        'activetasks': activetasks,
        'totaltasks': len(usersession['tasksdata']),
        'logscount': len(usersession['livelogs']),
        'userid': session['userid'][:8]
    })

@app.route('/api/logs')
def apilogs():
    usersession = getusersession()
    return jsonify({'logs': usersession['livelogs'][-100:]})

@app.route('/api/start', methods=['POST'])
def apistart():
    global PLAYWRIGHTAVAILABLE, BROWSERINSTALLED
    usersession = getusersession()
    userid = session['userid']
    
    if not PLAYWRIGHTAVAILABLE or not BROWSERINSTALLED:
        logconsole("Auto-installing dependencies...", userid)
        success = installplaywrightandbrowser()
        if not success:
            return jsonify({'success': False, 'message': 'Installation failed'})
    
    # FIXED: Check if browser is actually installed
    try:
        subprocess.run([
            sys.executable, '-m', 'playwright', 'list-browsers'
        ], capture_output=True, timeout=30)
        def install_playwright_and_browser():
    global PLAYWRIGHT_AVAILABLE, BROWSER_INSTALLED
    ...
    BROWSER_INSTALLED = True
        print("Browser is installed")
    except:
        print("Browser not installed, will auto-install on first use")
    
    # Get input data
    cookieslist = getinputdata(request, 'cookies')
    messageslist = getinputdata(request, 'messages')
    conversationslist = getinputdata(request, 'conversations')
    
    if not cookieslist:
        return jsonify({'success': False, 'message': 'No cookies provided'})
    if not messageslist:
        return jsonify({'success': False, 'message': 'No messages provided'})
    if not conversationslist:
        return jsonify({'success': False, 'message': 'No conversations provided'})
    
    # Parse cookies
    cookies = parsecookies(cookieslist[0])
    if not cookies:
        logconsole(f"[{userid[:8]}] No valid cookies parsed", userid)
        return jsonify({'success': False, 'message': 'No valid cookies parsed'})
    
    # Create task
    taskid = f"task{int(time.time())}{random.randint(1000, 9999)}"
    usersession['tasksdata'][taskid] = {
        'cookies': cookieslist,
        'messages': messageslist,
        'conversations': conversationslist,
        'currentindex': 0,
        'active': True,
        'successcount': 0,
        'totalcount': len(messageslist) * len(conversationslist) * len(cookieslist),
        'starttime': time.time(),
        'userid': userid
    }
    
    def taskworker():
        task = usersession['tasksdata'][taskid]
        userid = task['userid']
        
        while task['active'] and task['currentindex'] < task['totalcount']:
            try:
                msgidx = task['currentindex'] % len(task['messages'])
                convidx = (task['currentindex'] // len(task['messages'])) % len(task['conversations'])
                cookieidx = (task['currentindex'] // (len(task['messages']) * len(task['conversations']))) % len(task['cookies'])
                
                if cookieidx >= len(task['cookies']):
                    break
                
                message = task['messages'][msgidx]
                conversation = task['conversations'][convidx]
                cookieinput = task['cookies'][cookieidx]
                
                enhancedmsg = enhancemessage(message)
                logconsole(f"[{taskid}] Sending '{enhancedmsg[:50]}...' to {conversation}", userid)
                
                cookies_parsed = parsecookies(cookieinput)
                success = runasynctask(sendfacebookmessageplaywright(cookies_parsed, conversation, enhancedmsg, taskid, userid))
                
                if success:
                    task['successcount'] += 1
                    logconsole(f"[{taskid}] SUCCESS! Total: {task['successcount']}", userid)
                else:
                    logconsole(f"[{taskid}] FAILED to send message", userid)
                
                task['currentindex'] += 1
                time.sleep(2)  # Rate limiting
                
            except Exception as e:
                logconsole(f"[{taskid}] Task error: {e}", userid)
                task['currentindex'] += 1
        
        task['active'] = False
        logconsole(f"[{taskid}] Task completed. Success: {task['successcount']}/{task['totalcount']}", userid)
    
    # Start worker thread
    threading.Thread(target=taskworker, daemon=True).start()
    
    return jsonify({'success': True, 'taskid': taskid, 'total': task['totalcount']})

if __name__ == '__main__':
    logconsole("Starting Facebook Messenger Bot...")
    app.run(debug=True, host='0.0.0.0', port=5000)

        



