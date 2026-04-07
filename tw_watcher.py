import os
import time
import requests
from playwright.sync_api import sync_playwright

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
    print("Attempting fresh login...")
    # We add 'slow_mo' to act more like a human
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    
    try:
        page.goto(LOGIN_URL)
        
        # 1. Be very specific with the selectors
        # If these fail, check the 'name' attributes on the login page again
        page.wait_for_selector("input[name='email']")
        page.fill("input[name='email']", USER_EMAIL)
        page.fill("input[name='password']", USER_PASS)
        
        # 2. Try clicking the button by its text to be safe
        page.click("button:has-text('Login'), button:has-text('Sign In'), button[type='submit']")
        
        print("Login clicked, waiting for redirect...")
        
        # 3. Increase timeout and wait for the games list to actually render
        page.wait_for_selector("ti-game-summary", timeout=45000)
        
        # Save the session
        context.storage_state(path="auth.json")
        print("Session refreshed and saved.")
        
    except Exception as e:
        # This is the "Black Box" recorder
        page.screenshot(path="login_failed.png")
        print(f"Login failed: {e}. Check 'login_failed.png' in GitHub artifacts.")
        raise e # Re-throw so the action shows as failed
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