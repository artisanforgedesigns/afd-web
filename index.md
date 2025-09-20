---
layout: home
---

# PiLock User Guide

Complete documentation for PiLock device configuration and usage.

**Quick Links:**
- [Getting Started](#getting-started) - Set up your device in minutes
- [Settings Configuration](#settings-configuration) - Configure device integrations
- [GitHub Repository](https://github.com/blenington/afd/afd-web) - View source code

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Settings Configuration](#settings-configuration)
3. [Dashboard & Scene Configuration](#dashboard--scene-configuration)
4. [Basic Usage](#basic-usage)
5. [Frequently Asked Questions](#frequently-asked-questions)

---

## Getting Started

### First Run

> **💡 Quick Start Tip:** The entire setup process typically takes 5-10 minutes. Make sure you have your WiFi password ready!

1. **Power On**: Plug your device into a standard USB power supply and wait for the PiLock Wifi network to appear (This may take up to 60 seconds)

2. **Connect to Setup Network**: Connect to the PiLock wifi network and wait for the captive portal page to pop up. This may take up to 120 seconds but you can also navigate to the page directly:
   ```
   http://192.168.4.1
   ```

3. **Configure WiFi**: Select your wifi network (must be 2.4 GHz), enter your password, click "Connect" and wait for the board to reboot

4. **Access Your Device**: Reconnect to your home network and navigate to:
   ```
   http://pilock.local:5001
   ```
   > **ℹ️ Note:** If this doesn't work, check your router's device list to find the IP address

5. **You're Done!** Your PiLock will automatically connect to your network from now on 

---

## Settings Configuration

Before using PiLock, you need to configure your device settings. Click the **SETTINGS** button from the dashboard to access the configuration page.

### 🔘 Switchbot Account

> **⚠️ Important:** You'll need the SwitchBot mobile app installed and your devices already set up before proceeding.

**What you need:**
- Switchbot Token
- Switchbot Secret
- Device IDs for each Switchbot device you want to control

**How to obtain Switchbot credentials:**

1. **Download the SwitchBot app** and set up your devices
2. **Get API credentials:**
   - Open the SwitchBot app
   - Go to Profile → Preferences → App Version (tap 10 times to unlock developer options)
   - Go back to Profile → Preferences → Developer Options
   - Copy your **Token** and **Secret**

3. **Find Device IDs:**
   - In the switchbot app, click on a device, go to the device settings, click on "Device Info" and copy the BLE MAC (without ':' characters) The ID that you will paste into your settings should look like this: F1377ACE514C

**Configuration:**
- **Token**: Your SwitchBot API token
- **Secret**: Your SwitchBot API secret  
- **Device 1-4 IDs**: The device IDs for each SwitchBot you want to control

### ⚡ Haptic Account (PiShock)

**What you need:**
- PiShock username
- PiShock API key
- Share codes for each PiShock device

**How to obtain PiShock credentials:**

1. **Create a PiShock account** at [pishock.com](https://pishock.com)
2. **Get API Key:**
   - Log into your PiShock account
   - Go to Account Settings → API
   - Copy your **API Key**
3. **Get Share Codes:**
   - In your PiShock account, go to your device
   - Generate or find the **Share Code** for each device
   - Each device needs its own share code

**Configuration:**
- **Username**: Your PiShock account username
- **API Key**: Your PiShock API key
- **Sharecode 1-4**: Share codes for each PiShock device you want to control

### MagLock Configuration


**How to obtain eWeLink webhook URLs:**

1. Navigate to the following URL (NOTE: you may need to pay for the $9 eWeLink plan to access this feature now) https://web.ewelink.cc/#/home
2. Create a new scene. Add "Webhook" as the IF condition  and for the THEN condition, select your MagLock Wireless ID and select OFF
3. Repeat step two if you'd like to set up a webhook to turn your MagLock device ON
4. Test the URLs manually by pasting them into any web browser (these will work on any device, anywhere in the world). Confirm that your MagLock Wireless device turns on and off as expected when using the webhooks

**Configuration:**
- **Lock**: Webhook URL to lock the device
- **Unlock**: Webhook URL to dunlock the device

---

## Dashboard & Scene Configuration

The dashboard is your main control center for creating and managing scenes.

### Scene Configuration Panel

**Scene Duration:**
- Set how long your scene should run
- Format: `5` (fixed 5 minutes) or `2-10` (random between 2-10 minutes)

**Initial Delay:**  
- Delay before the scene starts (in minutes)
- Gives you time to prepare after hitting START

**Device Controls:**

Each device type (PiShock 1-4, Switchbot 1-4) has these options:

- **Enable checkbox**: Turn the device on/off for this scene
- **Interval**: How often the device triggers
  - Format: `30` (every 30 seconds) or `15-60` (random between 15-60 seconds)
- **Repeat**: Maximum number of times to trigger (leave blank for unlimited)
- **Intensity** (PiShock only): Shock intensity level
  - Format: `25` (fixed intensity) or `10-50` (random between 10-50)
- **Duration**: How long each activation lasts
  - Format: `1` (1 second) or `1-3` (random between 1-3 seconds)

### Status Feed

The left panel shows real-time status updates:
- Scene start/stop events
- Device activations
- Countdown timers

---

## Basic Usage

### Creating Your First Scene

1. **Configure Settings** (one-time setup):
   - Click "SETTINGS" 
   - Enter your device credentials
   - Click "💾 SAVE SETTINGS"

2. **Set Up a Scene**:
   - On the dashboard, set **Scene Duration** (e.g., `5` for 5 minutes)
   - Set **Initial Delay** if desired (e.g., `1` for 1-minute delay)
   - Enable devices you want to use (check the boxes)
   - Configure intervals and intensities for enabled devices
   - Click "💾 SAVE CONFIGURATION"

3. **Run the Scene**:
   - Click "🚀 START SCENE"
   - Watch the status display show countdown
   - Devices will activate according to your configuration
   - Click "⏹ STOP SCENE" to stop early if needed

### Understanding Status Display

- **⏳ Waiting**: Scene is in initial delay phase - countdown shows seconds remaining until scene starts
- **⚡ Running**: Scene is active - countdown shows minutes:seconds remaining in scene
- **⚡ Idle**: No scene is currently running

### Scene Control Buttons

- **🚀 START SCENE**: Begin a new scene (disabled if scene is already running)
- **⏹ STOP SCENE**: Stop the current scene immediately
- **💾 SAVE CONFIGURATION**: Save your scene settings
- **🔄 RESET CONFIG**: Reset all settings to defaults

---

## Frequently Asked Questions

### General Usage

**Q: The scene won't start - what's wrong?**
A: Check that:
- At least one device is enabled (checkbox checked)
- Your API credentials are correct in Settings
- Device IDs/share codes are valid
- You clicked "SAVE CONFIGURATION" after making changes

**Q: Can I run multiple scenes at once?**
A: No, only one scene can run at a time. Stop the current scene before starting a new one.

**Q: What happens if I lose internet connection during a scene?**
A: The scene will continue running, but device commands may fail. Check the status feed for error messages.

### Device Configuration

**Q: My PiShock device isn't responding**
A: Verify:
- Share code is correct (not the device ID)
- API key is valid
- Username matches your PiShock account
- Device is online and charged

**Q: Switchbot commands aren't working**
A: Check:
- Token and secret are correct
- Device ID is the actual device ID (not device name)
- Device is within Bluetooth/Hub range
- SwitchBot app can control the device

**Q: My smart lock isn't responding to webhook calls**
A: Ensure:
- Webhook URLs start with `https://us-apia.coolkit.cc/v2/`
- Webhooks are properly configured in eWeLink app
- Lock device is online and responsive in eWeLink app

### Scene Behavior

**Q: Why do my devices trigger at different times than expected?**
A: PiLock uses the interval as "time between triggers", not "triggers per minute". A 30-second interval means the device activates every 30 seconds.

**Q: What does "random" mean for intervals and intensity?**
A: Random values are calculated for each trigger. For example, `10-30` intensity will choose a random number between 10 and 30 for each activation.

**Q: Can I have unlimited device triggers?**
A: Yes, leave the "Repeat" field empty for unlimited triggers during the scene duration.

**Q: The countdown shows wrong time**
A: During the delay phase, countdown shows seconds remaining in delay. During scene execution, it shows time remaining in the scene.


### Updates

**Q: How do I check for updates?**
A: On the Settings page, click "🔍 CHECK FOR UPDATES". If an update is available, you'll see UPDATE and CANCEL buttons.

**Q: Will updating overwrite my settings?**
A: No, updates only change the application code. Your settings and scene configurations in the `data/` folder are preserved.

---

## Need More Help? 
Contact artisanforgedesigns@gmail.com