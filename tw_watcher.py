import os
import sys
import time
import requests
from playwright.sync_api import sync_playwright

# Secret Validation
REQUIRED_SECRETS = ["TW_EMAIL", "TW_PASSWORD", "DISCORD_WEBHOOK", "DISCORD_USER_ID"]
missing = []

for secret in REQUIRED_SECRETS:
    if not os.getenv(secret):
        missing.append(secret)
if missing:
    print(f"Error: Missing the following Github Secrets: {', '.joing(missing)}")
    sys.exit(1)
# --- CONFIGURATION (Pulled from GitHub Secrets) ---
GAME_URL = "https://www.twilightwars.com/games"
LOGIN_URL = "https://www.twilightwars.com/login"
MY_ID = "692344a032cabf12d025732b" 

USER_EMAIL = os.getenv("TW_EMAIL")
USER_PASS = os.getenv("TW_PASSWORD")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")
DISCORD_USER_ID = os.getenv("DISCORD_USER_ID")

def send_discord_ping(game_count):
    # Construct the message with the mention syntax
    message = f"<@{DISCORD_USER_ID}> 🚨 It is your turn in **{game_count}** games on Twilight Wars!"
    
    payload = {
        "content": message,
        "username": "Twilight Watcher",
        "avatar_url": "https://i.imgur.com/4M34hi2.png" # Optional: add a cool icon
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            print("Discord notification sent successfully!")
        else:
            print(f"Failed to send Discord notification: {response.status_code}")
    except Exception as e:
        print(f"Error connecting to Discord: {e}")

def login_and_get_session(p):
    print("Attempting fresh login with the dedicated submit button...")
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    
    try:
        page.goto(LOGIN_URL, wait_until="networkidle")
        
        # 1. Fill the fields using their IDs
        page.wait_for_selector("#email")
        page.fill("#email", USER_EMAIL)
        page.fill("#password", USER_PASS)
        
        # 2. Click the specific button that is linked to the form
        # We use a CSS selector that looks for a button with type='submit'
        print("Clicking the detached submit button...")
        page.click("button[type='submit']")
        
        # 3. Wait for the game summary to load
        print("Waiting for redirect to games list...")
        page.wait_for_selector("ti-game-summary", timeout=60000)
        
        # Save the session for next time
        context.storage_state(path="auth.json")
        print("Login Successful! Session saved.")
        
    except Exception as e:
        # Save a screenshot to the root folder so GitHub can find it
        page.screenshot(path="login_failed.png", full_page=True)
        print(f"Login failed: {e}")
        raise e 
    finally:
        browser.close()

def run_watcher():
    with sync_playwright() as p:
        # If no session file exists (first run), log in
        if not os.path.exists("auth.json"):
            login_and_get_session(p)

        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state="auth.json")
        page = context.new_page()

        try:
            page.goto(GAME_URL, wait_until="networkidle")
            
            # If we see the login button instead of games, our session expired
            if page.locator("ti-game-summary").count() == 0:
                print("Session expired. Re-authenticating...")
                browser.close()
                login_and_get_session(p)
                return run_watcher() # Restart the check with new session

            # Normal check logic
            time.sleep(5) 
            my_slots = page.locator(f"div.player[user-id='{MY_ID}']").all()
            turns = sum(1 for s in my_slots if s.locator("span.turn-indicator").count() > 0)

            if turns > 0:
                send_discord_ping(turns)
            else:
                print("Checked: No turns found.")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_watcher()
