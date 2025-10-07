from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
import json
import os
import time
import threading
import random
import requests
import argparse
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
contact_sensor_monitor_thread = None  # Thread for monitoring contact sensors
scene_active = False
scene_end_time = None
scene_delay_end_time = None  # When delay phase ends
scene_in_delay = False  # Track if scene is in initial delay phase
scene_execution_start_time = None  # When actual scene execution starts
executed_modifiers = set()  # Track which modifiers have been executed (reset each scene)
status_messages = deque(maxlen=50)  # Keep last 50 status messages
popup_notification_queue = deque(maxlen=10)  # Queue for popup notifications
audio_notification_queue = deque(maxlen=10)  # Queue for audio notifications
contact_sensor_states = {}  # Global state tracking for contact sensors
contact_sensor_devices = {}  # Global device references for contact sensors
monitoring_switchbot_api = None  # Global switchbot API reference for monitoring thread
monitoring_pishock_api = None  # Global pishock API reference for modifier actions
monitoring_pishock_shockers = {}  # Global pishock device references for modifier actions
monitoring_switchbot_devices = {}  # Global switchbot device references for modifier actions
device_counts = {}  # Global device activation counters
device_max_counts = {}  # Global device repeat limits
original_device_states = {}  # Store original device enabled states before scene starts

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
        },
        'interface': {
            'popup_notifications': False,
            'audio_notifications': False,
            'developer_mode': False
        },
        'killswitch': {
            'plug_id': '',
            'api_endpoint': ''
        },
        'custom_accessories': {
            'endpoint_1': '', 'payload_1': '{}', 'method_1': 'POST',
            'endpoint_2': '', 'payload_2': '{}', 'method_2': 'POST',
            'endpoint_3': '', 'payload_3': '{}', 'method_3': 'POST',
            'endpoint_4': '', 'payload_4': '{}', 'method_4': 'POST'
        },
        'contact_sensors': {
            'sensor_1_id': '', 'sensor_2_id': '', 'sensor_3_id': '', 'sensor_4_id': ''
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
        'scene_duration_fixed': 5,
        'scene_duration_random_min': 2,
        'scene_duration_random_max': 10,
        'initial_delay': 60,
        'pishock_1_enabled': True,
        'pishock_1_interval_type': 'random',
        'pishock_1_interval_fixed': 5,
        'pishock_1_interval_random_min': 15,
        'pishock_1_interval_random_max': 60,
        'pishock_1_repeat': '',
        'pishock_1_intensity_type': 'random',
        'pishock_1_intensity_fixed': 25,
        'pishock_1_intensity_random_min': 5,
        'pishock_1_intensity_random_max': 25,
        'pishock_1_duration_type': 'fixed',
        'pishock_1_duration_fixed': 1,
        'pishock_1_duration_random_min': 1,
        'pishock_1_duration_random_max': 3,
        'pishock_2_enabled': False,
        'pishock_2_interval_type': 'fixed',
        'pishock_2_interval_fixed': 5,
        'pishock_2_interval_random_min': 2,
        'pishock_2_interval_random_max': 10,
        'pishock_2_repeat': '',
        'pishock_2_intensity_type': 'fixed',
        'pishock_2_intensity_fixed': 25,
        'pishock_2_intensity_random_min': 10,
        'pishock_2_intensity_random_max': 50,
        'pishock_2_duration_type': 'fixed',
        'pishock_2_duration_fixed': 1,
        'pishock_2_duration_random_min': 1,
        'pishock_2_duration_random_max': 3,
        'pishock_3_enabled': False,
        'pishock_3_interval_type': 'fixed',
        'pishock_3_interval_fixed': 5,
        'pishock_3_interval_random_min': 2,
        'pishock_3_interval_random_max': 10,
        'pishock_3_repeat': '',
        'pishock_3_intensity_type': 'fixed',
        'pishock_3_intensity_fixed': 25,
        'pishock_3_intensity_random_min': 10,
        'pishock_3_intensity_random_max': 50,
        'pishock_3_duration_type': 'fixed',
        'pishock_3_duration_fixed': 1,
        'pishock_3_duration_random_min': 1,
        'pishock_3_duration_random_max': 3,
        'pishock_4_enabled': False,
        'pishock_4_interval_type': 'fixed',
        'pishock_4_interval_fixed': 5,
        'pishock_4_interval_random_min': 2,
        'pishock_4_interval_random_max': 10,
        'pishock_4_repeat': '',
        'pishock_4_intensity_type': 'fixed',
        'pishock_4_intensity_fixed': 25,
        'pishock_4_intensity_random_min': 10,
        'pishock_4_intensity_random_max': 50,
        'pishock_4_duration_type': 'fixed',
        'pishock_4_duration_fixed': 1,
        'pishock_4_duration_random_min': 1,
        'pishock_4_duration_random_max': 3,
        'switchbot_1_enabled': True,
        'switchbot_1_interval_type': 'random',
        'switchbot_1_interval_fixed': 5,
        'switchbot_1_interval_random_min': 15,
        'switchbot_1_interval_random_max': 60,
        'switchbot_1_repeat': '',
        'switchbot_1_duration_type': 'fixed',
        'switchbot_1_duration_fixed': 1,
        'switchbot_1_duration_random_min': 1,
        'switchbot_1_duration_random_max': 3,
        'switchbot_2_enabled': False,
        'switchbot_2_interval_type': 'fixed',
        'switchbot_2_interval_fixed': 5,
        'switchbot_2_interval_random_min': 2,
        'switchbot_2_interval_random_max': 10,
        'switchbot_2_repeat': '',
        'switchbot_2_duration_type': 'fixed',
        'switchbot_2_duration_fixed': 1,
        'switchbot_2_duration_random_min': 1,
        'switchbot_2_duration_random_max': 3,
        'switchbot_3_enabled': False,
        'switchbot_3_interval_type': 'fixed',
        'switchbot_3_interval_fixed': 5,
        'switchbot_3_interval_random_min': 2,
        'switchbot_3_interval_random_max': 10,
        'switchbot_3_repeat': '',
        'switchbot_3_duration_type': 'fixed',
        'switchbot_3_duration_fixed': 1,
        'switchbot_3_duration_random_min': 1,
        'switchbot_3_duration_random_max': 3,
        'switchbot_4_enabled': False,
        'switchbot_4_interval_type': 'fixed',
        'switchbot_4_interval_fixed': 5,
        'switchbot_4_interval_random_min': 2,
        'switchbot_4_interval_random_max': 10,
        'switchbot_4_repeat': '',
        'switchbot_4_duration_type': 'fixed',
        'switchbot_4_duration_fixed': 1,
        'switchbot_4_duration_random_min': 1,
        'switchbot_4_duration_random_max': 3,
        'custom_1_enabled': False,
        'custom_1_interval_type': 'fixed',
        'custom_1_interval_fixed': 5,
        'custom_1_interval_random_min': 2,
        'custom_1_interval_random_max': 10,
        'custom_1_repeat': '',
        'custom_2_enabled': False,
        'custom_2_interval_type': 'fixed',
        'custom_2_interval_fixed': 5,
        'custom_2_interval_random_min': 2,
        'custom_2_interval_random_max': 10,
        'custom_2_repeat': '',
        'custom_3_enabled': False,
        'custom_3_interval_type': 'fixed',
        'custom_3_interval_fixed': 5,
        'custom_3_interval_random_min': 2,
        'custom_3_interval_random_max': 10,
        'custom_3_repeat': '',
        'custom_4_enabled': False,
        'custom_4_interval_type': 'fixed',
        'custom_4_interval_fixed': 5,
        'custom_4_interval_random_min': 2,
        'custom_4_interval_random_max': 10,
        'custom_4_repeat': '',
        'modifier_1_enabled': False,
        'modifier_1_contact_sensor': '',
        'modifier_1_extend_minutes': '5',
        'modifier_2_enabled': False,
        'modifier_2_contact_sensor': '',
        'modifier_2_target_haptic': '',
        'modifier_3_enabled': False,
        'modifier_3_contact_sensor': '',
        'modifier_3_target_bot': '',
        'modifier_4_enabled': False,
        'modifier_4_contact_sensor': '',
        'modifier_4_target_custom': ''
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

def trigger_popup_notification(device_type, device_number, action_details):
    """Add a popup notification to the queue"""
    settings = load_settings()
    if settings.get('interface', {}).get('popup_notifications', False):
        notification = {
            'device_type': device_type,
            'device_number': device_number,
            'action_details': action_details,
            'timestamp': datetime.now().isoformat()
        }
        popup_notification_queue.append(notification)
        print(f"POPUP: {device_type} {device_number} - {action_details}")

def trigger_audio_notification(message):
    """Add an audio notification to the queue"""
    settings = load_settings()
    if settings.get('interface', {}).get('audio_notifications', False):
        notification = {
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        audio_notification_queue.append(notification)
        print(f"AUDIO: {message}")

def check_killswitch_status(switchbot_api, plug_id):
    """Check if the killswitch plug is still on"""
    if not switchbot_api or not plug_id:
        return True  # No killswitch configured, continue normally

    try:
        # Get device status from SwitchBot API
        device = switchbot_api.device(id=plug_id)
        status = device.status()

        # Check if plug is on (power: "on")
        power_status = status.get('power', 'off')
        print(f"KILLSWITCH: Plug {plug_id} status: {power_status}")

        return power_status == 'on'
    except Exception as e:
        print(f"KILLSWITCH ERROR: Failed to check plug status - {e}")
        return True  # On error, continue scene (fail-safe)

def check_contact_sensor_status(switchbot_api, sensor_id):
    """Check contact sensor status and return True if open (triggered)"""
    if not switchbot_api or not sensor_id:
        return False  # No sensor configured

    try:
        # Get device status from SwitchBot API
        device = switchbot_api.device(id=sensor_id)
        status = device.status()

        # Check if sensor is open (contactState: "open")
        contact_state = status.get('contactState', 'close')
        print(f"CONTACT SENSOR: Sensor {sensor_id} status: {contact_state}")

        return contact_state == 'open'
    except Exception as e:
        print(f"CONTACT SENSOR ERROR: Failed to check sensor {sensor_id} status - {e}")
        return False  # On error, assume closed

def call_killswitch_api(api_endpoint):
    """Call the optional API endpoint when scene is terminated by killswitch"""
    if not api_endpoint:
        return

    try:
        print(f"KILLSWITCH: Calling API endpoint - {api_endpoint}")
        headers = {
            'User-Agent': 'PiLock/1.0 (KillSwitch)',
            'Content-Type': 'application/json'
        }

        response = requests.post(api_endpoint, headers=headers, timeout=10, json={
            'event': 'killswitch_triggered',
            'timestamp': datetime.now().isoformat(),
            'reason': 'switchbot_plug_disconnected'
        })

        if response.status_code == 200:
            print(f"KILLSWITCH API: Call successful")
            add_status_message("Killswitch API called successfully")
        else:
            print(f"KILLSWITCH API: Call failed (HTTP {response.status_code})")
            add_status_message(f"Killswitch API failed (HTTP {response.status_code})")
    except Exception as e:
        print(f"KILLSWITCH API ERROR: {e}")
        add_status_message("Killswitch API call failed")

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

def monitor_contact_sensors():
    """Background thread to monitor contact sensors independently of main scene loop"""
    global scene_active, contact_sensor_states, contact_sensor_devices, monitoring_switchbot_api
    global monitoring_pishock_shockers, monitoring_switchbot_devices

    print("CONTACT SENSOR MONITOR: Background monitoring thread started")

    # Load scene state and settings
    scene_state = load_scene_state()
    settings = load_settings()

    while scene_active:
        try:
            # Reload scene state each iteration to get latest configuration
            scene_state = load_scene_state()
            settings = load_settings()

            # Check each configured contact sensor
            for sensor_num, sensor_device in contact_sensor_devices.items():
                try:
                    sensor_id = settings.get('contact_sensors', {}).get(f'sensor_{sensor_num}_id', '')
                    current_state = check_contact_sensor_status(monitoring_switchbot_api, sensor_id)
                    previous_state = contact_sensor_states.get(sensor_num, False)

                    # Detect state change from closed to open (trigger event)
                    if not previous_state and current_state:
                        print(f"CONTACT SENSOR {sensor_num}: State changed to OPEN - checking modifiers")
                        add_status_message(f"Contact Sensor {sensor_num} opened")
                        trigger_popup_notification('contact_sensor', sensor_num, "Sensor Opened")

                        # Check all modifiers that use this sensor
                        for modifier_i in range(1, 5):
                            if (scene_state.get(f'modifier_{modifier_i}_enabled', False) and
                                scene_state.get(f'modifier_{modifier_i}_contact_sensor', '') == str(sensor_num)):

                                print(f"MODIFIER {modifier_i}: Triggered by Contact Sensor {sensor_num}")
                                # Pass device references from global variables
                                execute_modifier_action(modifier_i, scene_state, settings,
                                                       pishock_shockers=monitoring_pishock_shockers,
                                                       switchbot_devices=monitoring_switchbot_devices)

                    # Update stored state
                    contact_sensor_states[sensor_num] = current_state

                except Exception as e:
                    print(f"CONTACT SENSOR ERROR: Failed to check sensor {sensor_num} - {e}")

            # Check every 0.5 seconds for responsive monitoring
            time.sleep(0.5)

        except Exception as e:
            print(f"CONTACT SENSOR MONITOR ERROR: {e}")
            time.sleep(1)  # Sleep longer on error

    print("CONTACT SENSOR MONITOR: Thread stopped")

def execute_modifier_action(modifier_type, scene_state, settings, **kwargs):
    """Execute modifier action based on type"""
    global executed_modifiers, scene_end_time, monitoring_pishock_shockers, monitoring_pishock_api
    global monitoring_switchbot_devices, monitoring_switchbot_api, device_counts

    # Check if this modifier has already been executed
    if modifier_type in executed_modifiers:
        print(f"MODIFIER {modifier_type}: Already executed, ignoring trigger")
        add_status_message(f"Modifier {modifier_type} already executed - ignoring repeated trigger")
        return

    if modifier_type == 1:  # Extend Scene Time
        extend_value = scene_state.get('modifier_1_extend_minutes', '5')

        # Parse extend value (could be "5" or "5-25")
        if '-' in str(extend_value):
            min_val, max_val = map(int, str(extend_value).split('-'))
            extend_minutes = random.randint(min_val, max_val)
        else:
            extend_minutes = int(extend_value)

        extend_seconds = extend_minutes * 60

        # Update global scene end time
        if scene_end_time:
            scene_end_time = scene_end_time + timedelta(seconds=extend_seconds)
            add_status_message(f"Scene extended by {extend_minutes} minutes (from range: {extend_value})")
            trigger_popup_notification('modifier', 1, f"Scene Extended | +{extend_minutes} minutes")
            trigger_audio_notification(f"Scene extended by {extend_minutes} minutes")
            print(f"MODIFIER 1: Scene extended by {extend_minutes} minutes (from range: {extend_value})")
            executed_modifiers.add(modifier_type)

    elif modifier_type == 2:  # Enable Haptic Module
        target_haptic = scene_state.get('modifier_2_target_haptic', '')
        if target_haptic:
            haptic_num = int(target_haptic)

            # Enable the haptic module in scene state dynamically
            scene_state[f'pishock_{haptic_num}_enabled'] = True
            save_scene_state(scene_state)  # Persist to file for dashboard updates

            # Initialize device if not already active
            if haptic_num not in monitoring_pishock_shockers and monitoring_pishock_api:
                sharecode = settings.get('pishock', {}).get(f'sharecode_{haptic_num}', '')
                if sharecode:
                    try:
                        monitoring_pishock_shockers[haptic_num] = monitoring_pishock_api.shocker(sharecode)
                        device_counts[f'pishock_{haptic_num}'] = 0  # Initialize counter
                        print(f"MODIFIER 2: Initialized Haptic Module {haptic_num} (Sharecode: {sharecode})")
                    except Exception as e:
                        print(f"MODIFIER 2 ERROR: Failed to initialize Haptic Module {haptic_num} - {e}")

            add_status_message(f"Haptic Module {haptic_num} enabled by modifier")
            trigger_popup_notification('modifier', 2, f"Haptic {haptic_num} Enabled")
            trigger_audio_notification(f"Haptic {haptic_num} enabled")
            print(f"MODIFIER 2: Enabled Haptic Module {haptic_num}")
            executed_modifiers.add(modifier_type)

    elif modifier_type == 3:  # Enable Bot
        target_bot = scene_state.get('modifier_3_target_bot', '')
        if target_bot:
            bot_num = int(target_bot)

            # Enable the switchbot in scene state dynamically
            scene_state[f'switchbot_{bot_num}_enabled'] = True
            save_scene_state(scene_state)  # Persist to file for dashboard updates

            # Initialize device if not already active
            if bot_num not in monitoring_switchbot_devices and monitoring_switchbot_api:
                device_id = settings.get('switchbot', {}).get(f'device_{bot_num}_id', '')
                if device_id:
                    try:
                        monitoring_switchbot_devices[bot_num] = monitoring_switchbot_api.device(id=device_id)
                        device_counts[f'switchbot_{bot_num}'] = 0  # Initialize counter
                        print(f"MODIFIER 3: Initialized SwitchBot {bot_num} (ID: {device_id})")
                    except Exception as e:
                        print(f"MODIFIER 3 ERROR: Failed to initialize SwitchBot {bot_num} - {e}")

            add_status_message(f"SwitchBot {bot_num} enabled by modifier")
            trigger_popup_notification('modifier', 3, f"SwitchBot {bot_num} Enabled")
            trigger_audio_notification(f"SwitchBot {bot_num} enabled")
            print(f"MODIFIER 3: Enabled SwitchBot {bot_num}")
            executed_modifiers.add(modifier_type)

    elif modifier_type == 4:  # Enable Custom Accessory
        target_custom = scene_state.get('modifier_4_target_custom', '')
        if target_custom:
            custom_num = int(target_custom)

            # Enable the custom accessory in scene state dynamically
            scene_state[f'custom_{custom_num}_enabled'] = True
            save_scene_state(scene_state)  # Persist to file for dashboard updates

            # Initialize counter if not already set
            if f'custom_{custom_num}' not in device_counts:
                device_counts[f'custom_{custom_num}'] = 0

            add_status_message(f"Custom Accessory {custom_num} enabled by modifier")
            trigger_popup_notification('modifier', 4, f"Custom {custom_num} Enabled")
            trigger_audio_notification(f"Custom {custom_num} enabled")
            print(f"MODIFIER 4: Enabled Custom Accessory {custom_num}")
            executed_modifiers.add(modifier_type)

def call_custom_api(endpoint_url, method, payload, device_number, description, dry_run=False):
    """Call a custom API endpoint with specified method and payload"""
    if not endpoint_url:
        print(f"CUSTOM API: No URL configured for {description}")
        return False

    if dry_run:
        print(f"CUSTOM API (DRY RUN): {description} - {method} {endpoint_url}")
        add_status_message(f"Custom {device_number} triggered (DRY RUN)")
        return True

    try:
        print(f"CUSTOM API: Calling {description} - {method} {endpoint_url}")

        headers = {
            'User-Agent': 'PiLock/1.0 (CustomAccessory)',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        # Parse JSON payload
        try:
            json_payload = json.loads(payload) if payload and payload.strip() != '{}' else {}
        except json.JSONDecodeError:
            print(f"CUSTOM API: Invalid JSON payload for {description}")
            add_status_message(f"Custom {device_number} failed - invalid JSON")
            return False

        # Make the API call based on method
        response = None
        if method.upper() == 'GET':
            response = requests.get(endpoint_url, headers=headers, timeout=10, params=json_payload)
        elif method.upper() == 'POST':
            response = requests.post(endpoint_url, headers=headers, timeout=10, json=json_payload)
        elif method.upper() == 'PUT':
            response = requests.put(endpoint_url, headers=headers, timeout=10, json=json_payload)
        elif method.upper() == 'PATCH':
            response = requests.patch(endpoint_url, headers=headers, timeout=10, json=json_payload)
        elif method.upper() == 'DELETE':
            response = requests.delete(endpoint_url, headers=headers, timeout=10, json=json_payload)
        else:
            print(f"CUSTOM API: Unsupported method {method}")
            add_status_message(f"Custom {device_number} failed - unsupported method")
            return False

        if response.status_code in [200, 201, 202, 204]:
            add_status_message(f"Custom {device_number} API call successful")
            return True
        else:
            add_status_message(f"Custom {device_number} API call failed (HTTP {response.status_code})")
            return False

    except Exception as e:
        print(f"CUSTOM API ERROR: {description} failed - {e}")
        add_status_message(f"Custom {device_number} API call failed - connection error")
        return False

def call_webhook(url, description, dry_run=False):
    if not url:
        print(f"WEBHOOK: No URL configured for {description}")
        return False

    if dry_run:
        print(f"WEBHOOK (DRY RUN): {description} - {url}")
        add_status_message(f"{description} (DRY RUN)")
        return True

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
    settings = load_settings()
    version = load_version()
    return render_template('dashboard.html', scene_state=scene_state, status=status, settings=settings, version=version)

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
        },
        'interface': {
            'popup_notifications': 'popup_notifications' in request.form,
            'audio_notifications': 'audio_notifications' in request.form,
            'developer_mode': 'developer_mode' in request.form
        },
        'killswitch': {
            'plug_id': request.form['killswitch_plug_id'],
            'api_endpoint': request.form['killswitch_api_endpoint']
        },
        'custom_accessories': {
            'endpoint_1': request.form['custom_1_endpoint'],
            'payload_1': request.form['custom_1_payload'],
            'method_1': request.form['custom_1_method'],
            'endpoint_2': request.form['custom_2_endpoint'],
            'payload_2': request.form['custom_2_payload'],
            'method_2': request.form['custom_2_method'],
            'endpoint_3': request.form['custom_3_endpoint'],
            'payload_3': request.form['custom_3_payload'],
            'method_3': request.form['custom_3_method'],
            'endpoint_4': request.form['custom_4_endpoint'],
            'payload_4': request.form['custom_4_payload'],
            'method_4': request.form['custom_4_method']
        },
        'contact_sensors': {
            'sensor_1_id': request.form['contact_sensor_1_id'],
            'sensor_2_id': request.form['contact_sensor_2_id'],
            'sensor_3_id': request.form['contact_sensor_3_id'],
            'sensor_4_id': request.form['contact_sensor_4_id']
        }
    }
    save_settings(settings)
    print("SETTINGS: Configuration saved successfully")

    # Check if this is an AJAX request
    is_ajax = (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
               request.headers.get('Content-Type') == 'application/x-www-form-urlencoded' or
               request.headers.get('Sec-Fetch-Mode') == 'cors')
    if is_ajax:
        return jsonify({"success": True, "message": "Settings saved successfully"})
    else:
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

    # Handle multiple Custom Accessories
    for i in range(1, 5):
        prefix = f'custom_{i}'

        # Parse interval string
        interval_str = request.form.get(f'{prefix}_interval', '5')
        interval_type, interval_fixed, interval_min, interval_max = parse_parameter(interval_str, 5, 2, 10)

        # Parse repeat string
        repeat_str = request.form.get(f'{prefix}_repeat', '')

        scene_state.update({
            f'{prefix}_enabled': f'{prefix}_enabled' in request.form,
            f'{prefix}_interval_type': interval_type,
            f'{prefix}_interval_fixed': interval_fixed,
            f'{prefix}_interval_random_min': interval_min,
            f'{prefix}_interval_random_max': interval_max,
            f'{prefix}_repeat': repeat_str
        })

    # Handle Scene Modifiers
    for i in range(1, 5):
        prefix = f'modifier_{i}'
        scene_state.update({
            f'{prefix}_enabled': f'{prefix}_enabled' in request.form,
            f'{prefix}_contact_sensor': request.form.get(f'{prefix}_contact_sensor', ''),
        })

        # Modifier-specific settings
        if i == 1:  # Extend Time
            scene_state[f'{prefix}_extend_minutes'] = request.form.get(f'{prefix}_extend_minutes', '5')
        elif i == 2:  # Haptic Trigger
            scene_state[f'{prefix}_target_haptic'] = request.form.get(f'{prefix}_target_haptic', '')
        elif i == 3:  # Bot Trigger
            scene_state[f'{prefix}_target_bot'] = request.form.get(f'{prefix}_target_bot', '')
        elif i == 4:  # Custom Trigger
            scene_state[f'{prefix}_target_custom'] = request.form.get(f'{prefix}_target_custom', '')

    save_scene_state(scene_state)
    print("SCENE CONFIG: Configuration saved successfully")

    # Check if request is AJAX/fetch by looking for JSON acceptance or specific header
    is_ajax = (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
               'application/json' in request.headers.get('Accept', '') or
               request.headers.get('Sec-Fetch-Mode') == 'cors')

    if is_ajax:
        return jsonify({"success": True, "message": "Configuration saved successfully"})
    else:
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

@app.route('/start_scene_dry_run', methods=['POST'])
def start_scene_dry_run():
    global scene_thread, scene_active
    if not scene_active:
        print("SCENE: Starting new scene (DRY RUN MODE)")
        add_status_message("Scene starting... (DRY RUN MODE)")
        scene_thread = threading.Thread(target=run_scene, args=(True,))
        scene_thread.daemon = True
        scene_thread.start()
    else:
        print("SCENE: Scene already running, ignoring start request")
    return redirect(url_for('dashboard'))

@app.route('/stop_scene', methods=['POST'])
def stop_scene():
    global scene_active, scene_end_time, scene_delay_end_time, scene_in_delay, scene_execution_start_time
    if scene_active:
        print("SCENE: Stopping scene")
        add_status_message("Scene stopped by user")
        scene_active = False
        scene_end_time = None
        scene_delay_end_time = None
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

    # Load defaults from the default file
    default_file_path = 'data/scene_state_default.json'
    if os.path.exists(default_file_path):
        with open(default_file_path, 'r') as f:
            default_state = json.load(f)

        # Write the default state to the scene state file
        with open(SCENE_STATE_FILE, 'w') as f:
            json.dump(default_state, f, indent=2)

        add_status_message("Configuration reset to defaults")
        print("SCENE CONFIG: Default values loaded from scene_state_default.json")
    else:
        # Fallback to old method if default file doesn't exist
        if os.path.exists(SCENE_STATE_FILE):
            os.remove(SCENE_STATE_FILE)
        add_status_message("Configuration reset to defaults")
        print("SCENE CONFIG: Default file not found, using fallback method")

    # Check if request is AJAX/fetch by looking for JSON acceptance or specific header
    is_ajax = (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
               'application/json' in request.headers.get('Accept', '') or
               request.headers.get('Sec-Fetch-Mode') == 'cors')

    if is_ajax:
        return jsonify({"success": True, "message": "Default values restored successfully"})
    else:
        return redirect(url_for('dashboard'))

@app.route('/status')
def status():
    return jsonify(get_scene_status())

@app.route('/device_states')
def device_states():
    """Get current enabled states of all devices"""
    scene_state = load_scene_state()
    states = {
        'pishock': {},
        'switchbot': {},
        'custom': {}
    }

    for i in range(1, 5):
        states['pishock'][i] = scene_state.get(f'pishock_{i}_enabled', False)
        states['switchbot'][i] = scene_state.get(f'switchbot_{i}_enabled', False)
        states['custom'][i] = scene_state.get(f'custom_{i}_enabled', False)

    return jsonify(states)

@app.route('/popup_notifications')
def get_popup_notifications():
    """Get pending popup notifications"""
    global popup_notification_queue
    notifications = list(popup_notification_queue)
    popup_notification_queue.clear()  # Clear the queue after retrieving
    return jsonify(notifications)

@app.route('/audio_notifications')
def get_audio_notifications():
    """Get pending audio notifications"""
    global audio_notification_queue
    notifications = list(audio_notification_queue)
    audio_notification_queue.clear()  # Clear the queue after retrieving
    return jsonify(notifications)

@app.route('/test_contact_sensor', methods=['POST'])
def test_contact_sensor():
    """Test a contact sensor by checking its status"""
    try:
        data = request.get_json()
        sensor_number = data.get('sensor_number')

        settings = load_settings()
        sensor_id = settings.get('contact_sensors', {}).get(f'sensor_{sensor_number}_id', '')

        if not sensor_id:
            return jsonify({'success': False, 'message': f'Contact sensor {sensor_number} not configured'})

        # Initialize Switchbot API
        switchbot_api = None
        if settings.get('switchbot', {}).get('token'):
            try:
                switchbot_api = SwitchBot(
                    token=settings['switchbot']['token'],
                    secret=settings['switchbot']['secret']
                )

                # Test contact sensor status
                device = switchbot_api.device(id=sensor_id)
                status = device.status()

                add_status_message(f"Contact sensor {sensor_number} test - Status: {status}")

                return jsonify({
                    'success': True,
                    'message': f'Contact sensor {sensor_number} responded',
                    'status': status
                })

            except Exception as e:
                add_status_message(f"Contact sensor {sensor_number} test failed - {str(e)}")
                return jsonify({'success': False, 'message': f'Test failed: {str(e)}'})
        else:
            return jsonify({'success': False, 'message': 'Switchbot API not configured'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/test_custom_accessory', methods=['POST'])
def test_custom_accessory():
    """Test a custom accessory API call"""
    try:
        data = request.get_json()
        accessory_number = data.get('accessory_number')

        settings = load_settings()
        endpoint_url = settings.get('custom_accessories', {}).get(f'endpoint_{accessory_number}', '')
        method = settings.get('custom_accessories', {}).get(f'method_{accessory_number}', 'POST')
        payload = settings.get('custom_accessories', {}).get(f'payload_{accessory_number}', '{}')

        if not endpoint_url:
            return jsonify({'success': False, 'message': f'Custom accessory {accessory_number} not configured'})

        success = call_custom_api(endpoint_url, method, payload, accessory_number, f"Custom Accessory {accessory_number} (TEST)")

        return jsonify({
            'success': success,
            'message': f'Custom accessory {accessory_number} test {"successful" if success else "failed"}'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/test_maglock', methods=['POST'])
def test_maglock():
    """Test MagLock webhook"""
    try:
        data = request.get_json()
        action = data.get('action')  # 'engage' or 'disengage'

        settings = load_settings()

        if action == 'engage':
            webhook_url = settings.get('lock', {}).get('engage_webhook', '')
            description = "Test Lock Engage"
        elif action == 'disengage':
            webhook_url = settings.get('lock', {}).get('disengage_webhook', '')
            description = "Test Lock Disengage"
        else:
            return jsonify({'success': False, 'message': 'Invalid action'})

        if not webhook_url:
            return jsonify({'success': False, 'message': f'MagLock {action} webhook not configured'})

        success = call_webhook(webhook_url, description)

        return jsonify({
            'success': success,
            'message': f'MagLock {action} test {"successful" if success else "failed"}'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/test_killswitch', methods=['POST'])
def test_killswitch():
    """Test killswitch component - simulates plug being OFF if scene is running"""
    global scene_active, scene_end_time, scene_delay_end_time, scene_in_delay, scene_execution_start_time

    try:
        data = request.get_json()
        test_type = data.get('type')  # 'plug' or 'api'

        settings = load_settings()

        if test_type == 'plug':
            plug_id = settings.get('killswitch', {}).get('plug_id', '')

            if not plug_id:
                return jsonify({'success': False, 'message': 'Killswitch plug not configured'})

            # If scene is running, simulate killswitch trigger (plug OFF)
            if scene_active:
                print("KILLSWITCH TEST: Simulating plug OFF - triggering emergency stop")
                add_status_message("Scene terminated - killswitch activated (TEST)")
                trigger_audio_notification("Scene terminated by killswitch")
                trigger_popup_notification('killswitch', 'activated', "Killswitch Activated - Scene Terminated (TEST)")

                # Call optional API endpoint
                api_endpoint = settings.get('killswitch', {}).get('api_endpoint', '')
                if api_endpoint:
                    call_webhook(api_endpoint, "Killswitch API (TEST)")

                # Stop the scene
                scene_active = False
                scene_end_time = None
                scene_delay_end_time = None
                scene_in_delay = False
                scene_execution_start_time = None

                return jsonify({
                    'success': True,
                    'message': 'Killswitch triggered - scene terminated'
                })
            else:
                # Scene not running, just test the plug status
                switchbot_api = None
                if settings.get('switchbot', {}).get('token'):
                    try:
                        switchbot_api = SwitchBot(
                            token=settings['switchbot']['token'],
                            secret=settings['switchbot']['secret']
                        )

                        # Test killswitch plug status
                        status = check_killswitch_status(switchbot_api, plug_id)

                        add_status_message(f"Killswitch plug test - Status: {'ON' if status else 'OFF/ERROR'}")

                        return jsonify({
                            'success': True,
                            'message': f'Killswitch plug responded - Status: {"ON" if status else "OFF/ERROR"}',
                            'status': status
                        })

                    except Exception as e:
                        add_status_message(f"Killswitch plug test failed - {str(e)}")
                        return jsonify({'success': False, 'message': f'Test failed: {str(e)}'})
                else:
                    return jsonify({'success': False, 'message': 'Switchbot API not configured'})

        elif test_type == 'api':
            api_endpoint = settings.get('killswitch', {}).get('api_endpoint', '')

            if not api_endpoint:
                return jsonify({'success': False, 'message': 'Killswitch API endpoint not configured'})

            success = call_webhook(api_endpoint, "Test Killswitch API")

            return jsonify({
                'success': success,
                'message': f'Killswitch API test {"successful" if success else "failed"}'
            })
        else:
            return jsonify({'success': False, 'message': 'Invalid test type'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/test_custom_payload', methods=['POST'])
def test_custom_payload():
    """Test a custom API payload"""
    try:
        data = request.get_json()
        endpoint = data.get('endpoint')
        method = data.get('method', 'POST')
        payload = data.get('payload', '{}')

        if not endpoint:
            return jsonify({'success': False, 'error': 'No endpoint provided'})

        # Parse JSON payload
        try:
            payload_data = json.loads(payload)
        except json.JSONDecodeError as e:
            return jsonify({'success': False, 'error': f'Invalid JSON: {str(e)}'})

        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'PiLock-TestClient/1.0'
        }

        # Make the request
        if method.upper() == 'GET':
            response = requests.get(endpoint, headers=headers, timeout=10)
        elif method.upper() == 'POST':
            response = requests.post(endpoint, json=payload_data, headers=headers, timeout=10)
        elif method.upper() == 'PUT':
            response = requests.put(endpoint, json=payload_data, headers=headers, timeout=10)
        elif method.upper() == 'PATCH':
            response = requests.patch(endpoint, json=payload_data, headers=headers, timeout=10)
        elif method.upper() == 'DELETE':
            response = requests.delete(endpoint, headers=headers, timeout=10)
        else:
            return jsonify({'success': False, 'error': f'Unsupported method: {method}'})

        # Get response text, truncate if too long
        response_text = response.text[:500] if response.text else 'No response body'
        if len(response.text) > 500:
            response_text += '... (truncated)'

        return jsonify({
            'success': True,
            'status_code': response.status_code,
            'response': response_text
        })

    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'Request timeout (10 seconds)'})
    except requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'error': 'Connection error - check endpoint URL'})
    except requests.exceptions.RequestException as e:
        return jsonify({'success': False, 'error': f'Request error: {str(e)}'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Unexpected error: {str(e)}'})

@app.route('/trigger1', methods=['GET', 'POST'])
def trigger_contact_sensor_1():
    """Trigger contact sensor 1 modifiers via API"""
    return trigger_contact_sensor_api(1)

@app.route('/trigger2', methods=['GET', 'POST'])
def trigger_contact_sensor_2():
    """Trigger contact sensor 2 modifiers via API"""
    return trigger_contact_sensor_api(2)

@app.route('/trigger3', methods=['GET', 'POST'])
def trigger_contact_sensor_3():
    """Trigger contact sensor 3 modifiers via API"""
    return trigger_contact_sensor_api(3)

@app.route('/trigger4', methods=['GET', 'POST'])
def trigger_contact_sensor_4():
    """Trigger contact sensor 4 modifiers via API"""
    return trigger_contact_sensor_api(4)

def trigger_contact_sensor_api(sensor_num):
    """Common function to trigger contact sensor modifiers via API"""
    try:
        # Only trigger if scene is active
        if not scene_active:
            return jsonify({
                'success': False,
                'message': f'Contact sensor {sensor_num} triggered but no scene is active'
            })

        settings = load_settings()
        scene_state = load_scene_state()

        # Initialize devices (similar to how it's done in run_scene)
        pishock_shockers = []
        for i in range(1, 5):
            if scene_state.get(f'pishock_{i}_enabled', False):
                pishock_shockers.append({
                    'name': settings.get(f'pishock_{i}_name', ''),
                    'api_key': settings.get(f'pishock_{i}_api_key', ''),
                    'username': settings.get(f'pishock_{i}_username', ''),
                    'code': settings.get(f'pishock_{i}_code', ''),
                    'sharecode': settings.get(f'pishock_{i}_sharecode', '')
                })
            else:
                pishock_shockers.append(None)

        switchbot_devices = []
        for i in range(1, 5):
            if scene_state.get(f'switchbot_{i}_enabled', False):
                switchbot_devices.append({
                    'device_id': settings.get(f'switchbot_{i}_device_id', ''),
                    'token': settings.get('switchbot_token', ''),
                    'secret': settings.get('switchbot_secret', '')
                })
            else:
                switchbot_devices.append(None)

        # Check for modifiers triggered by this sensor
        triggered_modifiers = []
        for modifier_i in range(1, 5):
            if (scene_state.get(f'modifier_{modifier_i}_enabled', False) and
                scene_state.get(f'modifier_{modifier_i}_contact_sensor', '') == str(sensor_num)):

                triggered_modifiers.append(modifier_i)
                add_status_message(f"API triggered Contact Sensor {sensor_num} - Modifier {modifier_i} activated")
                execute_modifier_action(modifier_i, scene_state, settings,
                                       pishock_shockers=pishock_shockers,
                                       switchbot_devices=switchbot_devices)

        if triggered_modifiers:
            return jsonify({
                'success': True,
                'message': f'Contact sensor {sensor_num} triggered via API - Activated modifiers: {", ".join(map(str, triggered_modifiers))}'
            })
        else:
            return jsonify({
                'success': True,
                'message': f'Contact sensor {sensor_num} triggered via API but no modifiers configured for this sensor'
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error triggering contact sensor {sensor_num}: {str(e)}'
        })

def get_scene_status():
    global scene_active, scene_end_time, scene_delay_end_time, scene_in_delay, scene_execution_start_time
    if scene_active:
        if scene_in_delay and scene_delay_end_time:
            # During delay phase, show seconds remaining in delay
            remaining = max(0, int((scene_delay_end_time - datetime.now()).total_seconds()))
            return {
                'status': 'Waiting',
                'remaining_minutes': remaining // 60,
                'remaining_seconds': remaining % 60
            }
        elif not scene_in_delay and scene_end_time:
            # During scene execution, show scene time remaining
            remaining = max(0, int((scene_end_time - datetime.now()).total_seconds()))
            return {
                'status': 'Running', 
                'remaining_minutes': remaining // 60,
                'remaining_seconds': remaining % 60
            }
    return {'status': 'Idle', 'remaining_minutes': 0, 'remaining_seconds': 0}

def run_scene(dry_run=False):
    global scene_active, scene_end_time, scene_delay_end_time, scene_in_delay, scene_execution_start_time
    global original_device_states

    if dry_run:
        print("SCENE: Loading settings and scene state (DRY RUN MODE)")
    else:
        print("SCENE: Loading settings and scene state")
    settings = load_settings()
    scene_state = load_scene_state()

    # Save original device states before scene starts
    original_device_states = {
        'pishock': {i: scene_state.get(f'pishock_{i}_enabled', False) for i in range(1, 5)},
        'switchbot': {i: scene_state.get(f'switchbot_{i}_enabled', False) for i in range(1, 5)},
        'custom': {i: scene_state.get(f'custom_{i}_enabled', False) for i in range(1, 5)}
    }
    print(f"SCENE: Saved original device states: {original_device_states}")

    scene_active = True
    scene_in_delay = False  # Initialize delay flag
    executed_modifiers.clear()  # Reset executed modifiers for new scene
    status_messages.clear()  # Clear status log for new scene
    
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
    
    # Set up timing for delay and scene phases
    initial_delay = scene_state['initial_delay']
    
    if initial_delay > 0:
        # Set delay end time and scene end time separately
        scene_delay_end_time = datetime.now() + timedelta(seconds=initial_delay)
        scene_end_time = datetime.now() + timedelta(seconds=initial_delay + duration)
        scene_in_delay = True
    else:
        # No delay, go straight to scene execution
        scene_delay_end_time = None
        scene_end_time = datetime.now() + timedelta(seconds=duration)
        scene_in_delay = False
    
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
        
        # Sleep in small increments to allow stopping during delay
        delay_elapsed = 0
        while delay_elapsed < initial_delay and scene_active:
            time.sleep(1)
            delay_elapsed += 1
        
        if not scene_active:
            return  # Scene was stopped during delay
            
        scene_in_delay = False  # Clear delay flag
        # Update scene end time for just the scene duration (not including delay)
        scene_end_time = datetime.now() + timedelta(seconds=duration)
        add_status_message("Initial delay complete - scene starting now...")
    
    # Mark when actual scene execution starts
    scene_execution_start_time = datetime.now()

    # Announce scene start with duration
    duration_minutes = duration // 60
    trigger_audio_notification(f"Scene starting - Duration {duration_minutes} minutes")

    # Engage lock
    if settings.get('lock', {}).get('engage_webhook'):
        if dry_run:
            print("LOCK: Engaging lock via webhook (DRY RUN)")
        else:
            print("LOCK: Engaging lock via webhook")
        call_webhook(settings.get('lock', {}).get('engage_webhook'), "Activate Lock: ", dry_run)
        trigger_popup_notification('lock', 'engage', "Lock Engaged" + (" (DRY RUN)" if dry_run else ""))
    
    # Initialize APIs
    global monitoring_pishock_shockers, monitoring_switchbot_devices, monitoring_switchbot_api, monitoring_pishock_api, device_counts, device_max_counts
    switchbot_api = None
    pishock_api = None
    monitoring_pishock_shockers = {}  # Reset global references
    monitoring_switchbot_devices = {}  # Reset global references
    monitoring_switchbot_api = None
    monitoring_pishock_api = None
    device_counts = {}
    device_max_counts = {}

    if dry_run:
        print("API: Skipping real API initialization (DRY RUN MODE)")
        add_status_message("API initialization skipped (DRY RUN)")
        # In dry run mode, simulate device initialization for enabled devices
        for i in range(1, 5):
            if scene_state.get(f'switchbot_{i}_enabled', False):
                monitoring_switchbot_devices[i] = f"dry_run_device_{i}"  # Placeholder
                add_status_message(f"Switchbot {i} ready (DRY RUN)")
            if scene_state.get(f'pishock_{i}_enabled', False):
                monitoring_pishock_shockers[i] = f"dry_run_shocker_{i}"  # Placeholder
                add_status_message(f"Haptic Module {i} ready (DRY RUN)")
    else:
        # Initialize Switchbot API
        if settings.get('switchbot', {}).get('token'):
            try:
                print("API: Initializing Switchbot API")
                monitoring_switchbot_api = SwitchBot(
                    token=settings['switchbot']['token'],
                    secret=settings['switchbot']['secret']
                )

                # Initialize Switchbot devices
                for i in range(1, 5):
                    device_id = settings.get('switchbot', {}).get(f'device_{i}_id', '')
                    if device_id and scene_state.get(f'switchbot_{i}_enabled', False):
                        try:
                            monitoring_switchbot_devices[i] = monitoring_switchbot_api.device(id=device_id)
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
                monitoring_pishock_api = PiShockAPI(
                    settings['pishock']['username'],
                    settings['pishock']['api_key']
                )

                # Initialize PiShock devices
                for i in range(1, 5):
                    sharecode = settings.get('pishock', {}).get(f'sharecode_{i}', '')
                    if sharecode and scene_state.get(f'pishock_{i}_enabled', False):
                        try:
                            monitoring_pishock_shockers[i] = monitoring_pishock_api.shocker(sharecode)
                            print(f"API: PiShock device {i} initialized (Sharecode: {sharecode})")
                            add_status_message(f"Haptic Module {i} ready")
                        except Exception as e:
                            print(f"API ERROR: PiShock device {i} initialization failed - {e}")
                            add_status_message(f"Haptic Module {i} failed to initialize")
            except Exception as e:
                print(f"API ERROR: PiShock API initialization failed - {e}")
                add_status_message("Haptic API initialization failed")

    # Initialize counters for all devices (no repeat limits - unlimited usage)
    for i in range(1, 5):
        device_counts[f'pishock_{i}'] = 0
        device_max_counts[f'pishock_{i}'] = None  # Unlimited repeats

    for i in range(1, 5):
        device_counts[f'switchbot_{i}'] = 0
        device_max_counts[f'switchbot_{i}'] = None  # Unlimited repeats

    for i in range(1, 5):
        device_counts[f'custom_{i}'] = 0
        device_max_counts[f'custom_{i}'] = None  # Unlimited repeats

    # Initialize contact sensor state tracking for modifiers
    global contact_sensor_states, contact_sensor_devices, contact_sensor_monitor_thread
    contact_sensor_states = {}
    contact_sensor_devices = {}

    # Initialize contact sensors for monitoring - only if in CLOSED state
    for i in range(1, 5):
        sensor_id = settings.get('contact_sensors', {}).get(f'sensor_{i}_id', '')
        if sensor_id and monitoring_switchbot_api:
            try:
                # Get initial state first
                initial_state = check_contact_sensor_status(monitoring_switchbot_api, sensor_id)

                # Only add sensor if it's CLOSED (False means closed)
                if not initial_state:  # Closed state
                    contact_sensor_devices[i] = monitoring_switchbot_api.device(id=sensor_id)
                    contact_sensor_states[i] = initial_state
                    print(f"CONTACT SENSOR: Sensor {i} initialized (ID: {sensor_id}) - State: CLOSED")
                    add_status_message(f"Contact Sensor {i} ready - CLOSED")
                else:  # Open state - ignore
                    print(f"CONTACT SENSOR: Sensor {i} (ID: {sensor_id}) is OPEN - ignoring for scene")
                    add_status_message(f"Contact Sensor {i} ignored - not in CLOSED state")
            except Exception as e:
                print(f"CONTACT SENSOR ERROR: Failed to initialize sensor {i} - {e}")
                add_status_message(f"Contact Sensor {i} error - ignoring for scene")

    # Start contact sensor monitoring thread if any sensors are configured
    if contact_sensor_devices and not dry_run:
        contact_sensor_monitor_thread = threading.Thread(target=monitor_contact_sensors, daemon=True)
        contact_sensor_monitor_thread.start()
        print("CONTACT SENSOR MONITOR: Background monitoring thread started")
    elif contact_sensor_devices and dry_run:
        print("CONTACT SENSOR MONITOR: Skipping background thread (DRY RUN)")

    start_time = time.time()
    print(f"SCENE: Scene execution starting - will run for {duration} seconds")

    # Get killswitch settings
    killswitch_plug_id = settings.get('killswitch', {}).get('plug_id', '')
    killswitch_api_endpoint = settings.get('killswitch', {}).get('api_endpoint', '')
    killswitch_enabled = False  # Track if killswitch is actually monitoring

    # Verify killswitch is ON and connected before enabling monitoring
    if killswitch_plug_id and monitoring_switchbot_api:
        try:
            killswitch_status = check_killswitch_status(monitoring_switchbot_api, killswitch_plug_id)
            if killswitch_status:  # Plug is ON
                killswitch_enabled = True
                print(f"KILLSWITCH: Plug verified ON (ID: {killswitch_plug_id}) - monitoring enabled")
                add_status_message("Killswitch monitoring enabled")
            else:  # Plug is OFF or disconnected
                print(f"KILLSWITCH: Plug is OFF or disconnected (ID: {killswitch_plug_id}) - ignoring for scene")
                add_status_message("Killswitch ignored - plug not ON")
                killswitch_plug_id = ''  # Disable monitoring
        except Exception as e:
            print(f"KILLSWITCH ERROR: Failed to verify plug status - {e}")
            add_status_message("Killswitch error - ignoring for scene")
            killswitch_plug_id = ''  # Disable monitoring

    # Use scene_end_time for loop condition so modifiers can extend the scene
    while datetime.now() < scene_end_time and scene_active:
        # Reload scene state each iteration to pick up modifier changes
        scene_state = load_scene_state()

        # Check killswitch status every loop iteration
        if killswitch_plug_id and not check_killswitch_status(monitoring_switchbot_api, killswitch_plug_id):
            print("KILLSWITCH: Plug turned off - terminating scene")
            add_status_message("Scene terminated - killswitch activated")
            trigger_audio_notification("Scene terminated by killswitch")
            trigger_popup_notification('killswitch', 'activated', "Killswitch Activated - Scene Terminated")
            call_killswitch_api(killswitch_api_endpoint)
            break

        # Note: Contact sensor monitoring is now handled by a separate background thread
        # to avoid blocking during device activation delays

        current_time = time.time() - start_time
        
        # Process PiShock devices
        for i in range(1, 5):
            device_key = f'pishock_{i}'
            if (scene_state.get(f'{device_key}_enabled', False) and
                i in monitoring_pishock_shockers and
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

                        if dry_run:
                            print(f"PISHOCK {i} (DRY RUN): Triggering shock (intensity: {intensity}, duration: {duration_val}s)")
                            add_status_message(f"Haptic Module {i} activated ({device_counts[device_key] + 1} times) (DRY RUN)")
                            # Trigger notifications for dry run
                            trigger_popup_notification('pishock', i, f"Intensity: {intensity} | Duration: {duration_val}s (DRY RUN)")
                            trigger_audio_notification(f"Shock {intensity} dry run")
                        else:
                            # Trigger notifications 2 seconds before vibration
                            trigger_popup_notification('pishock', i, f"Intensity: {intensity} | Duration: {duration_val}s")
                            trigger_audio_notification(f"Shock {intensity}")
                            print(f"PISHOCK {i}: Pre-notification sent, waiting 2 seconds...")
                            add_status_message(f"Haptic Module {i} notification sent, vibration in 2 seconds...")

                            # Wait 2 seconds
                            time.sleep(2)

                            # Execute vibration
                            monitoring_pishock_shockers[i].vibrate(duration=duration_val, intensity=intensity)
                            print(f"PISHOCK {i}: Vibration executed, waiting 1 second before shock...")

                            # Wait 1 second after vibration
                            time.sleep(1)

                            # Execute shock
                            monitoring_pishock_shockers[i].shock(duration=duration_val, intensity=intensity)
                            print(f"PISHOCK {i}: Shock delivered (intensity: {intensity}, duration: {duration_val}s)")
                            add_status_message(f"Haptic Module {i} activated ({device_counts[device_key] + 1} times)")

                        device_counts[device_key] += 1
                    except Exception as e:
                        print(f"PISHOCK {i} ERROR: Trigger failed - {e}")
                        add_status_message(f"Haptic Module {i} failed to activate")
        
        # Process Switchbot devices
        for i in range(1, 5):
            device_key = f'switchbot_{i}'
            if (scene_state.get(f'{device_key}_enabled', False) and
                i in monitoring_switchbot_devices and
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

                        if dry_run:
                            print(f"SWITCHBOT {i} (DRY RUN): Triggering press (duration: {duration_val}s)")
                            add_status_message(f"Switchbot {i} activated ({device_counts[device_key] + 1} times) (DRY RUN)")
                        else:
                            print(f"SWITCHBOT {i}: Triggering press (duration: {duration_val}s)")
                            monitoring_switchbot_devices[i].press()
                            add_status_message(f"Switchbot {i} activated ({device_counts[device_key] + 1} times)")

                        device_counts[device_key] += 1
                        # Trigger popup notification
                        trigger_popup_notification('switchbot', i, f"Button Press | Duration: {duration_val}s" + (" (DRY RUN)" if dry_run else ""))
                        # Trigger audio notification
                        trigger_audio_notification(f"Switchbot {i}" + (" dry run" if dry_run else ""))
                        # Note: Switchbot press duration is handled internally, no need for blocking sleep
                    except Exception as e:
                        print(f"SWITCHBOT {i} ERROR: Trigger failed - {e}")
                        add_status_message(f"Switchbot {i} failed to activate")

        # Process Custom Accessories
        for i in range(1, 5):
            device_key = f'custom_{i}'
            if (scene_state.get(f'{device_key}_enabled', False) and
                (device_max_counts[device_key] is None or device_counts[device_key] < device_max_counts[device_key])):

                # Get endpoint configuration
                endpoint_url = settings.get('custom_accessories', {}).get(f'endpoint_{i}', '')
                payload = settings.get('custom_accessories', {}).get(f'payload_{i}', '{}')
                method = settings.get('custom_accessories', {}).get(f'method_{i}', 'POST')

                if endpoint_url:  # Only process if endpoint is configured
                    if scene_state.get(f'{device_key}_interval_type') == 'fixed':
                        next_interval = scene_state.get(f'{device_key}_interval_fixed', 5)
                    else:
                        next_interval = random.randint(
                            scene_state.get(f'{device_key}_interval_random_min', 2),
                            scene_state.get(f'{device_key}_interval_random_max', 10)
                        )

                    if current_time >= next_interval * (device_counts[device_key] + 1):
                        try:
                            if dry_run:
                                print(f"CUSTOM {i} (DRY RUN): Triggering API call ({method} {endpoint_url})")
                            else:
                                print(f"CUSTOM {i}: Triggering API call ({method} {endpoint_url})")
                            success = call_custom_api(endpoint_url, method, payload, i, f"Custom Accessory {i}", dry_run)

                            if success:
                                device_counts[device_key] += 1
                                add_status_message(f"Custom {i} activated ({device_counts[device_key]} times)" + (" (DRY RUN)" if dry_run else ""))
                                # Trigger popup notification
                                trigger_popup_notification('custom', i, f"{method} API Call | Endpoint: {endpoint_url}" + (" (DRY RUN)" if dry_run else ""))
                                # Trigger audio notification
                                trigger_audio_notification(f"Custom {i}" + (" dry run" if dry_run else ""))
                        except Exception as e:
                            print(f"CUSTOM {i} ERROR: API call failed - {e}")
                            add_status_message(f"Custom {i} failed to activate")

        time.sleep(1)  # Check every second
    
    # Disengage lock
    if settings.get('lock', {}).get('disengage_webhook'):
        if dry_run:
            print("LOCK: Disengaging lock via webhook (DRY RUN)")
        else:
            print("LOCK: Disengaging lock via webhook")
        call_webhook(settings.get('lock', {}).get('disengage_webhook'), "Lock disengaged", dry_run)
        trigger_popup_notification('lock', 'disengage', "Lock Disengaged" + (" (DRY RUN)" if dry_run else ""))
    
    # Check if scene was stopped manually or completed naturally
    if scene_active:  # Scene completed normally
        if dry_run:
            print("SCENE: Scene completed successfully (DRY RUN)")
            add_status_message("Scene completed (DRY RUN)")
            trigger_audio_notification("Scene complete dry run")
        else:
            print("SCENE: Scene completed successfully")
            add_status_message("Scene completed")
            trigger_audio_notification("Scene complete")
    else:
        if dry_run:
            print("SCENE: Scene stopped by user (DRY RUN)")
        else:
            print("SCENE: Scene stopped by user")
        add_status_message("Scene stopped")

    # Restore original device states
    if original_device_states:
        print(f"SCENE: Restoring original device states: {original_device_states}")
        scene_state = load_scene_state()

        for i in range(1, 5):
            scene_state[f'pishock_{i}_enabled'] = original_device_states['pishock'][i]
            scene_state[f'switchbot_{i}_enabled'] = original_device_states['switchbot'][i]
            scene_state[f'custom_{i}_enabled'] = original_device_states['custom'][i]

        save_scene_state(scene_state)
        add_status_message("Device states restored to pre-scene configuration")
        print("SCENE: Device states restored successfully")

    # Clean up scene state
    scene_active = False
    scene_end_time = None
    scene_delay_end_time = None
    scene_in_delay = False
    scene_execution_start_time = None

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PiLock Web Application')
    parser.add_argument('--port', type=int, default=5001, help='Port to run the server on (default: 5001)')
    args = parser.parse_args()
    
    app.run(debug=True, host='0.0.0.0', port=args.port)