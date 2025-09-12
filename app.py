from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
import json
import os
import time
import threading
import random
import requests
from datetime import datetime, timedelta
from pishock import PiShockAPI
from switchbot import SwitchBot
from collections import deque

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

SETTINGS_FILE = 'data/settings.json'
SCENE_STATE_FILE = 'data/scene_state.json'

# Ensure data directory exists
os.makedirs('data', exist_ok=True)

scene_thread = None
scene_active = False
scene_end_time = None
scene_in_delay = False  # Track if scene is in initial delay phase
scene_execution_start_time = None  # When actual scene execution starts
status_messages = deque(maxlen=50)  # Keep last 50 status messages

def load_version():
    """Load version from VERSION file"""
    try:
        if os.path.exists('VERSION'):
            with open('VERSION', 'r') as f:
                return f.read().strip()
    except Exception:
        pass
    return '0.0.0'  # fallback version

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    
    # Create default settings file if it doesn't exist
    default_settings = {
        'switchbot': {
            'token': '', 'secret': '',
            'device_1_id': '', 'device_2_id': '', 'device_3_id': '', 'device_4_id': ''
        },
        'pishock': {
            'username': '', 'api_key': '',
            'sharecode_1': '', 'sharecode_2': '', 'sharecode_3': '', 'sharecode_4': ''
        },
        'lock': {
            'engage_webhook': '', 'disengage_webhook': ''
        }
    }
    
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(default_settings, f, indent=2)
    
    return default_settings

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

def load_scene_state():
    if os.path.exists(SCENE_STATE_FILE):
        with open(SCENE_STATE_FILE, 'r') as f:
            return json.load(f)
    
    # Create default scene state file if it doesn't exist
    default_scene_state = {
        'scene_duration_type': 'fixed',
        'scene_duration_fixed': 10,
        'scene_duration_random_min': 2,
        'scene_duration_random_max': 20,
        'initial_delay': 0,
        'pishock_1_enabled': False,
        'pishock_1_interval_type': 'fixed',
        'pishock_1_interval_fixed': 5,
        'pishock_1_interval_random_min': 2,
        'pishock_1_interval_random_max': 10,
        'pishock_1_repeat': '',
        'pishock_1_intensity': 25,
        'pishock_1_duration': 1,
        'pishock_2_enabled': False,
        'pishock_2_interval_type': 'fixed',
        'pishock_2_interval_fixed': 5,
        'pishock_2_interval_random_min': 2,
        'pishock_2_interval_random_max': 10,
        'pishock_2_repeat': '',
        'pishock_2_intensity': 25,
        'pishock_2_duration': 1,
        'pishock_3_enabled': False,
        'pishock_3_interval_type': 'fixed',
        'pishock_3_interval_fixed': 5,
        'pishock_3_interval_random_min': 2,
        'pishock_3_interval_random_max': 10,
        'pishock_3_repeat': '',
        'pishock_3_intensity': 25,
        'pishock_3_duration': 1,
        'pishock_4_enabled': False,
        'pishock_4_interval_type': 'fixed',
        'pishock_4_interval_fixed': 5,
        'pishock_4_interval_random_min': 2,
        'pishock_4_interval_random_max': 10,
        'pishock_4_repeat': '',
        'pishock_4_intensity': 25,
        'pishock_4_duration': 1,
        'switchbot_1_enabled': False,
        'switchbot_1_interval_type': 'fixed',
        'switchbot_1_interval_fixed': 5,
        'switchbot_1_interval_random_min': 2,
        'switchbot_1_interval_random_max': 10,
        'switchbot_1_repeat': '',
        'switchbot_1_duration': 1,
        'switchbot_2_enabled': False,
        'switchbot_2_interval_type': 'fixed',
        'switchbot_2_interval_fixed': 5,
        'switchbot_2_interval_random_min': 2,
        'switchbot_2_interval_random_max': 10,
        'switchbot_2_repeat': '',
        'switchbot_2_duration': 1,
        'switchbot_3_enabled': False,
        'switchbot_3_interval_type': 'fixed',
        'switchbot_3_interval_fixed': 5,
        'switchbot_3_interval_random_min': 2,
        'switchbot_3_interval_random_max': 10,
        'switchbot_3_repeat': '',
        'switchbot_3_duration': 1,
        'switchbot_4_enabled': False,
        'switchbot_4_interval_type': 'fixed',
        'switchbot_4_interval_fixed': 5,
        'switchbot_4_interval_random_min': 2,
        'switchbot_4_interval_random_max': 10,
        'switchbot_4_repeat': '',
        'switchbot_4_duration': 1
    }
    
    with open(SCENE_STATE_FILE, 'w') as f:
        json.dump(default_scene_state, f, indent=2)
    
    return default_scene_state

def save_scene_state(state):
    with open(SCENE_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def add_status_message(message):
    timestamp = datetime.now().strftime('%H:%M:%S')
    status_messages.append(f"[{timestamp}] {message}")
    print(f"STATUS: [{timestamp}] {message}")

def parse_parameter(value, default_fixed=5, default_min=2, default_max=10):
    """Parse parameter string like '5' or '2-10' into type and values"""
    if not value or not value.strip():
        return 'fixed', default_fixed, default_min, default_max
    
    value = value.strip()
    if '-' in value:
        try:
            min_val, max_val = value.split('-', 1)
            return 'random', default_fixed, int(min_val.strip()), int(max_val.strip())
        except ValueError:
            return 'fixed', default_fixed, default_min, default_max
    else:
        try:
            return 'fixed', int(value), default_min, default_max
        except ValueError:
            return 'fixed', default_fixed, default_min, default_max

def parse_repeat_parameter(value):
    """Parse repeat parameter - can be empty for unlimited"""
    if not value or not value.strip():
        return ''  # Empty means unlimited
    return value.strip()

def get_parameter_value(scene_state, prefix, param_name, default_value):
    """Get actual parameter value (fixed or random) for scene execution"""
    param_type_key = f'{prefix}_{param_name}_type'
    param_type = scene_state.get(param_type_key, 'fixed')
    
    if param_type == 'fixed':
        return scene_state.get(f'{prefix}_{param_name}_fixed', default_value)
    else:
        min_val = scene_state.get(f'{prefix}_{param_name}_random_min', default_value)
        max_val = scene_state.get(f'{prefix}_{param_name}_random_max', default_value)
        return random.randint(min_val, max_val)

def call_webhook(url, description):
    if not url:
        print(f"WEBHOOK: No URL configured for {description}")
        return False
    try:
        print(f"WEBHOOK: Calling {description} - {url}")
        
        # Simulate a real web browser request (simplified headers for eWeLink compatibility)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        if response.status_code == 200:
            add_status_message(f"{description} successful")
            return True
        else:
            add_status_message(f"{description} failed (HTTP {response.status_code})")
            return False
    except Exception as e:
        print(f"WEBHOOK ERROR: {description} failed - {e}")
        add_status_message(f"{description} failed - connection error")
        return False

@app.route('/')
def dashboard():
    scene_state = load_scene_state()
    status = get_scene_status()
    version = load_version()
    return render_template('dashboard.html', scene_state=scene_state, status=status, version=version)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.svg', mimetype='image/svg+xml')

@app.route('/settings')
def settings():
    settings = load_settings()
    version = load_version()
    return render_template('settings.html', settings=settings, version=version)

@app.route('/save_settings', methods=['POST'])
def save_settings_route():
    print("SETTINGS: Saving new settings configuration")
    settings = {
        'switchbot': {
            'token': request.form['switchbot_token'],
            'secret': request.form['switchbot_secret'],
            'device_1_id': request.form['switchbot_device_1_id'],
            'device_2_id': request.form['switchbot_device_2_id'],
            'device_3_id': request.form['switchbot_device_3_id'],
            'device_4_id': request.form['switchbot_device_4_id']
        },
        'pishock': {
            'username': request.form['pishock_username'],
            'api_key': request.form['pishock_api_key'],
            'sharecode_1': request.form['pishock_sharecode_1'],
            'sharecode_2': request.form['pishock_sharecode_2'],
            'sharecode_3': request.form['pishock_sharecode_3'],
            'sharecode_4': request.form['pishock_sharecode_4']
        },
        'lock': {
            'engage_webhook': request.form['lock_engage_webhook'],
            'disengage_webhook': request.form['lock_disengage_webhook']
        }
    }
    save_settings(settings)
    print("SETTINGS: Configuration saved successfully")
    return redirect(url_for('settings'))

@app.route('/check_updates')
def check_updates():
    """Check for updates by comparing current version with GitHub repo version"""
    try:
        current_version = load_version()
        
        # Fetch VERSION file from GitHub repo
        github_url = "https://raw.githubusercontent.com/artisanforgedesigns/afd-web/main/VERSION"
        response = requests.get(github_url, timeout=10)
        
        if response.status_code == 200:
            remote_version = response.text.strip()
            print(f"DEBUG: Local version: '{current_version}', Remote version: '{remote_version}'")
            
            if remote_version != current_version:
                message = f"New version available: {remote_version}"
                update_available = True
            else:
                message = f"You already have the latest version: {current_version}"
                update_available = False
        else:
            message = "Unable to check for updates. Please try again later."
            update_available = False
            
        return jsonify({"message": message, "update_available": update_available})
        
    except requests.exceptions.RequestException:
        return jsonify({"message": "Unable to connect to update server. Please check your internet connection."})
    except Exception as e:
        return jsonify({"message": f"Error checking for updates: {str(e)}", "update_available": False})

@app.route('/update_app', methods=['POST'])
def update_app():
    """Update the application by pulling changes from GitHub"""
    try:
        import subprocess
        result = subprocess.run(['git', 'pull'], capture_output=True, text=True, cwd='.')
        
        if result.returncode == 0:
            message = "Update successful! Please restart the application."
            success = True
        else:
            message = f"Update failed: {result.stderr}"
            success = False
            
        return jsonify({"message": message, "success": success})
        
    except Exception as e:
        return jsonify({"message": f"Update error: {str(e)}", "success": False})

@app.route('/save_scene_config', methods=['POST'])
def save_scene_config():
    print("SCENE CONFIG: Saving scene configuration")
    
    # Parse scene duration
    duration_str = request.form.get('scene_duration', '5')
    duration_type, duration_fixed, duration_min, duration_max = parse_parameter(duration_str, 5, 2, 10)
    
    # Parse initial_delay with error handling (convert minutes to seconds)
    try:
        initial_delay = int(request.form.get('initial_delay', 0)) * 60  # Convert minutes to seconds
    except (ValueError, TypeError):
        initial_delay = 0
    
    scene_state = {
        'scene_duration_type': duration_type,
        'scene_duration_fixed': duration_fixed,
        'scene_duration_random_min': duration_min,
        'scene_duration_random_max': duration_max,
        'initial_delay': initial_delay
    }
    
    # Handle multiple PiShock devices
    for i in range(1, 5):
        prefix = f'pishock_{i}'
        
        # Parse interval string
        interval_str = request.form.get(f'{prefix}_interval', '5')
        interval_type, interval_fixed, interval_min, interval_max = parse_parameter(interval_str, 5, 2, 10)
        
        # Parse intensity string
        intensity_str = request.form.get(f'{prefix}_intensity', '25')
        intensity_type, intensity_fixed, intensity_min, intensity_max = parse_parameter(intensity_str, 25, 10, 50)
        
        # Parse repeat string
        repeat_str = request.form.get(f'{prefix}_repeat', '')
        
        # Parse duration string  
        duration_str = request.form.get(f'{prefix}_duration', '1')
        duration_type, duration_fixed, duration_min, duration_max = parse_parameter(duration_str, 1, 1, 3)
        
        scene_state.update({
            f'{prefix}_enabled': f'{prefix}_enabled' in request.form,
            f'{prefix}_interval_type': interval_type,
            f'{prefix}_interval_fixed': interval_fixed,
            f'{prefix}_interval_random_min': interval_min,
            f'{prefix}_interval_random_max': interval_max,
            f'{prefix}_repeat': repeat_str,
            f'{prefix}_intensity_type': intensity_type,
            f'{prefix}_intensity_fixed': intensity_fixed,
            f'{prefix}_intensity_random_min': intensity_min,
            f'{prefix}_intensity_random_max': intensity_max,
            f'{prefix}_duration_type': duration_type,
            f'{prefix}_duration_fixed': duration_fixed,
            f'{prefix}_duration_random_min': duration_min,
            f'{prefix}_duration_random_max': duration_max
        })
    
    # Handle multiple Switchbot devices
    for i in range(1, 5):
        prefix = f'switchbot_{i}'
        
        # Parse interval string
        interval_str = request.form.get(f'{prefix}_interval', '5')
        interval_type, interval_fixed, interval_min, interval_max = parse_parameter(interval_str, 5, 2, 10)
        
        # Parse repeat string
        repeat_str = request.form.get(f'{prefix}_repeat', '')
        
        # Parse duration string  
        duration_str = request.form.get(f'{prefix}_duration', '1')
        duration_type, duration_fixed, duration_min, duration_max = parse_parameter(duration_str, 1, 1, 3)
        
        scene_state.update({
            f'{prefix}_enabled': f'{prefix}_enabled' in request.form,
            f'{prefix}_interval_type': interval_type,
            f'{prefix}_interval_fixed': interval_fixed,
            f'{prefix}_interval_random_min': interval_min,
            f'{prefix}_interval_random_max': interval_max,
            f'{prefix}_repeat': repeat_str,
            f'{prefix}_duration_type': duration_type,
            f'{prefix}_duration_fixed': duration_fixed,
            f'{prefix}_duration_random_min': duration_min,
            f'{prefix}_duration_random_max': duration_max
        })
    
    save_scene_state(scene_state)
    print("SCENE CONFIG: Configuration saved successfully")
    return redirect(url_for('dashboard'))

@app.route('/start_scene', methods=['POST'])
def start_scene():
    global scene_thread, scene_active
    if not scene_active:
        print("SCENE: Starting new scene")
        add_status_message("Scene starting...")
        scene_thread = threading.Thread(target=run_scene)
        scene_thread.daemon = True
        scene_thread.start()
    else:
        print("SCENE: Scene already running, ignoring start request")
    return redirect(url_for('dashboard'))

@app.route('/stop_scene', methods=['POST'])
def stop_scene():
    global scene_active, scene_end_time, scene_in_delay, scene_execution_start_time
    if scene_active:
        print("SCENE: Stopping scene")
        add_status_message("Scene stopped by user")
        scene_active = False
        scene_end_time = None
        scene_in_delay = False
        scene_execution_start_time = None
    else:
        print("SCENE: No scene running, ignoring stop request")
    return redirect(url_for('dashboard'))

@app.route('/status_messages')
def status_messages_endpoint():
    return jsonify(list(status_messages))

@app.route('/clear_status_log', methods=['POST'])
def clear_status_log():
    """Clear the status message log"""
    global status_messages
    status_messages.clear()
    print("STATUS: Status log cleared by user")
    return redirect(url_for('dashboard'))

@app.route('/reset_config', methods=['POST'])
def reset_config():
    print("SCENE CONFIG: Resetting to default configuration")
    default_state = load_scene_state()  # This will return defaults if file doesn't exist
    # Clear the file to force defaults
    if os.path.exists(SCENE_STATE_FILE):
        os.remove(SCENE_STATE_FILE)
    add_status_message("Configuration reset to defaults")
    return redirect(url_for('dashboard'))

@app.route('/status')
def status():
    return jsonify(get_scene_status())

def get_scene_status():
    global scene_active, scene_end_time, scene_in_delay, scene_execution_start_time
    if scene_active and scene_end_time:
        remaining = max(0, int((scene_end_time - datetime.now()).total_seconds()))
        
        if scene_in_delay:
            # During delay phase, show "Waiting" status
            return {
                'status': 'Waiting',
                'remaining_minutes': remaining // 60,
                'remaining_seconds': remaining % 60
            }
        else:
            # During actual scene execution, show "Running" status
            return {
                'status': 'Running',
                'remaining_minutes': remaining // 60,
                'remaining_seconds': remaining % 60
            }
    return {'status': 'Idle', 'remaining_minutes': 0, 'remaining_seconds': 0}

def run_scene():
    global scene_active, scene_end_time, scene_in_delay, scene_execution_start_time
    
    print("SCENE: Loading settings and scene state")
    settings = load_settings()
    scene_state = load_scene_state()
    
    scene_active = True
    scene_in_delay = False  # Initialize delay flag
    
    # Determine scene duration first
    if scene_state['scene_duration_type'] == 'fixed':
        duration = scene_state['scene_duration_fixed'] * 60  # Convert to seconds
        print(f"SCENE: Fixed duration of {scene_state['scene_duration_fixed']} minutes ({duration} seconds)")
    else:
        duration = random.randint(
            scene_state['scene_duration_random_min'] * 60,
            scene_state['scene_duration_random_max'] * 60
        )
        print(f"SCENE: Random duration of {duration//60} minutes ({duration} seconds)")
    
    # Set scene end time including initial delay + scene duration
    initial_delay = scene_state['initial_delay']
    total_time = initial_delay + duration
    scene_end_time = datetime.now() + timedelta(seconds=total_time)
    
    add_status_message(f"Scene Duration: {duration//60}m")
    
    # Initial delay
    if initial_delay > 0:
        scene_in_delay = True  # Set delay flag
        delay_minutes = initial_delay // 60
        delay_seconds = initial_delay % 60
        if delay_minutes > 0:
            delay_display = f"{delay_minutes}m" + (f" {delay_seconds}s" if delay_seconds > 0 else "")
        else:
            delay_display = f"{delay_seconds}s"
        print(f"SCENE: Initial delay of {initial_delay} seconds")
        add_status_message(f"Waiting {delay_display} before starting...")
        time.sleep(initial_delay)
        scene_in_delay = False  # Clear delay flag
        add_status_message("Initial delay complete - scene starting now...")
    
    # Mark when actual scene execution starts
    scene_execution_start_time = datetime.now()
    
    # Engage lock
    if settings.get('lock', {}).get('engage_webhook'):
        print("LOCK: Engaging lock via webhook")
        call_webhook(settings.get('lock', {}).get('engage_webhook'), "Activate Lock: ")
    
    # Initialize APIs
    switchbot_api = None
    pishock_api = None
    switchbot_devices = {}
    pishock_shockers = {}
    
    # Initialize Switchbot API
    if settings.get('switchbot', {}).get('token'):
        try:
            print("API: Initializing Switchbot API")
            switchbot_api = SwitchBot(
                token=settings['switchbot']['token'],
                secret=settings['switchbot']['secret']
            )
            
            # Initialize Switchbot devices
            for i in range(1, 5):
                device_id = settings.get('switchbot', {}).get(f'device_{i}_id', '')
                if device_id and scene_state.get(f'switchbot_{i}_enabled', False):
                    try:
                        switchbot_devices[i] = switchbot_api.device(id=device_id)
                        print(f"API: Switchbot device {i} initialized (ID: {device_id})")
                        add_status_message(f"Switchbot {i} ready")
                    except Exception as e:
                        print(f"API ERROR: Switchbot device {i} initialization failed - {e}")
                        add_status_message(f"Switchbot {i} failed to initialize")
        except Exception as e:
            print(f"API ERROR: Switchbot API initialization failed - {e}")
            add_status_message("Switchbot API initialization failed")
    
    # Initialize PiShock API
    if settings.get('pishock', {}).get('username'):
        try:
            print("API: Initializing PiShock API")
            pishock_api = PiShockAPI(
                settings['pishock']['username'],
                settings['pishock']['api_key']
            )
            
            # Initialize PiShock devices
            for i in range(1, 5):
                sharecode = settings.get('pishock', {}).get(f'sharecode_{i}', '')
                if sharecode and scene_state.get(f'pishock_{i}_enabled', False):
                    try:
                        pishock_shockers[i] = pishock_api.shocker(sharecode)
                        print(f"API: PiShock device {i} initialized (Sharecode: {sharecode})")
                        add_status_message(f"Haptic Module {i} ready")
                    except Exception as e:
                        print(f"API ERROR: PiShock device {i} initialization failed - {e}")
                        add_status_message(f"Haptic Module {i} failed to initialize")
        except Exception as e:
            print(f"API ERROR: PiShock API initialization failed - {e}")
            add_status_message("Haptic API initialization failed")
    
    # Track accessory usage
    device_counts = {}
    device_max_counts = {}
    
    # Initialize counters for all devices
    for i in range(1, 5):
        device_counts[f'pishock_{i}'] = 0
        repeat_val = scene_state.get(f'pishock_{i}_repeat', '')
        device_max_counts[f'pishock_{i}'] = int(repeat_val) if repeat_val else None
    
    for i in range(1, 5):
        device_counts[f'switchbot_{i}'] = 0
        repeat_val = scene_state.get(f'switchbot_{i}_repeat', '')
        device_max_counts[f'switchbot_{i}'] = int(repeat_val) if repeat_val else None
    
    start_time = time.time()
    print(f"SCENE: Scene execution starting - will run for {duration} seconds")
    
    while time.time() - start_time < duration and scene_active:
        current_time = time.time() - start_time
        
        # Process PiShock devices
        for i in range(1, 5):
            device_key = f'pishock_{i}'
            if (scene_state.get(f'{device_key}_enabled', False) and 
                i in pishock_shockers and 
                (device_max_counts[device_key] is None or device_counts[device_key] < device_max_counts[device_key])):
                
                if scene_state.get(f'{device_key}_interval_type') == 'fixed':
                    next_interval = scene_state.get(f'{device_key}_interval_fixed', 5)
                else:
                    next_interval = random.randint(
                        scene_state.get(f'{device_key}_interval_random_min', 2),
                        scene_state.get(f'{device_key}_interval_random_max', 10)
                    )
                
                if current_time >= next_interval * (device_counts[device_key] + 1):
                    try:
                        intensity = get_parameter_value(scene_state, device_key, 'intensity', 25)
                        duration_val = get_parameter_value(scene_state, device_key, 'duration', 1)
                        
                        pishock_shockers[i].vibrate(duration=duration_val, intensity=intensity)
                        print(f"PISHOCK {i}: Triggering shock (intensity: {intensity}, duration: {duration_val}s)")
                        pishock_shockers[i].shock(duration=duration_val, intensity=intensity)
                        device_counts[device_key] += 1
                        add_status_message(f"Haptic Module {i} activated ({device_counts[device_key]} times)")
                    except Exception as e:
                        print(f"PISHOCK {i} ERROR: Trigger failed - {e}")
                        add_status_message(f"Haptic Module {i} failed to activate")
        
        # Process Switchbot devices
        for i in range(1, 5):
            device_key = f'switchbot_{i}'
            if (scene_state.get(f'{device_key}_enabled', False) and 
                i in switchbot_devices and 
                (device_max_counts[device_key] is None or device_counts[device_key] < device_max_counts[device_key])):
                
                if scene_state.get(f'{device_key}_interval_type') == 'fixed':
                    next_interval = scene_state.get(f'{device_key}_interval_fixed', 5)
                else:
                    next_interval = random.randint(
                        scene_state.get(f'{device_key}_interval_random_min', 2),
                        scene_state.get(f'{device_key}_interval_random_max', 10)
                    )
                
                if current_time >= next_interval * (device_counts[device_key] + 1):
                    try:
                        duration_val = get_parameter_value(scene_state, device_key, 'duration', 1)
                        print(f"SWITCHBOT {i}: Triggering press (duration: {duration_val}s)")
                        switchbot_devices[i].press()
                        device_counts[device_key] += 1
                        add_status_message(f"Switchbot {i} activated ({device_counts[device_key]} times)")
                        # Sleep for the specified duration
                        if duration_val > 0:
                            time.sleep(duration_val)
                    except Exception as e:
                        print(f"SWITCHBOT {i} ERROR: Trigger failed - {e}")
                        add_status_message(f"Switchbot {i} failed to activate")
        
        time.sleep(1)  # Check every second
    
    # Disengage lock
    if settings.get('lock', {}).get('disengage_webhook'):
        print("LOCK: Disengaging lock via webhook")
        call_webhook(settings.get('lock', {}).get('disengage_webhook'), "Lock disengaged")
    
    scene_active = False
    scene_end_time = None
    scene_in_delay = False
    scene_execution_start_time = None
    
    if scene_active is False:  # Scene completed normally
        print("SCENE: Scene completed successfully")
        add_status_message("Scene completed")
    else:
        print("SCENE: Scene stopped by user")
        add_status_message("Scene stopped")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)