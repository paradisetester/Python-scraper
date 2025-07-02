import time
import json
import re
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from concurrent.futures import ThreadPoolExecutor
import database as db
import urllib.parse

# --- Setup basic console logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Helper Functions for Data Cleaning ---
def clean_mileage(mileage_text):
    if not mileage_text:
        return None
    # Extract only the numbers from the mileage text
    numbers = re.sub(r'[^0-9]', '', mileage_text)
    return int(numbers) if numbers else None

def clean_payment(payment_text):
    if not payment_text:
        return None
    # Extract only the numbers from the payment text
    numbers = re.sub(r'[^0-9]', '', payment_text)
    return int(numbers) if numbers else None

def parse_car_title(title):
    """
    Parse car title to extract year, make, and model.
    Example: "2021 Ford Bronco Sport" -> {"year": "2021", "make": "Ford", "model": "Bronco Sport"}
    """
    if not title:
        return {"year": None, "make": None, "model": None}
    
    parts = title.strip().split()
    if not parts:
        return {"year": None, "make": None, "model": None}
    
    # First part is usually the year
    year = parts[0] if parts[0].isdigit() and len(parts[0]) == 4 else None
    
    if year and len(parts) > 1:
        # Second part is usually the make
        make = parts[1]
        # Everything after make is the model
        model = " ".join(parts[2:]) if len(parts) > 2 else None
        return {"year": year, "make": make, "model": model}
    
    return {"year": None, "make": None, "model": None}

# --- Driver Setup ---
def setup_driver(headless=True):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-webgl")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--log-level=3")
    options.add_argument("--window-size=1920,1080")
    # Add additional stability options for parallel execution
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-features=TranslateUI")
    options.add_argument("--disable-ipc-flooding-protection")
    options.add_argument("--memory-pressure-off")
    options.add_argument("--max_old_space_size=4096")
    # Add parallel execution specific options
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--disable-remote-fonts")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-client-side-phishing-detection")
    options.add_argument("--disable-component-extensions-with-background-pages")
    options.add_argument("--disable-domain-reliability")
    options.add_argument("--disable-features=AudioServiceOutOfProcess")
    options.add_argument("--disable-hang-monitor")
    options.add_argument("--disable-prompt-on-repost")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-sync-preferences")
    options.add_argument("--metrics-recording-only")
    options.add_argument("--no-first-run")
    options.add_argument("--safebrowsing-disable-auto-update")
    options.add_argument("--enable-automation")
    options.add_argument("--password-store=basic")
    options.add_argument("--use-mock-keychain")
    # Add user agent to avoid detection
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)  # Reduced from 60 to 30 seconds
    driver.set_script_timeout(30)
    
    # Add additional error handling
    try:
        # Test the driver is working
        driver.get("data:text/html,<html><body>Test</body></html>")
    except Exception as e:
        try:
            driver.quit()
        except:
            pass
        raise e
    
    return driver

# --- Utility Functions ---
def load_page_with_retry(driver, url, max_retries=3):
    for attempt in range(max_retries):
        try:
            driver.get(url)
            return True
        except TimeoutException:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return False
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return False
    return False

def get_detail_text(driver, selector, attribute=None, max_retries=2):
    for _ in range(max_retries):
        try:
            # Use a shorter wait as this function is called many times.
            element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            if attribute:
                return element.get_attribute(attribute)
            
            # Use JS to get textContent, which is more robust for dynamic content
            text = driver.execute_script("return arguments[0].textContent;", element)
            return text.strip()

        except TimeoutException:
            return None # Element not found, return None immediately
        except StaleElementReferenceException:
            # If element is stale, retry once.
            time.sleep(0.5)
            continue
        except Exception as e:
            return None
    return None

# --- Car Detail Scraper ---
def scrape_car_details(driver, url):
    max_retries = 2  # Reduced from 3 to 2
    for attempt in range(max_retries):
        try:
            if not load_page_with_retry(driver, url):
                car_id = url.split('/vehicledetail/')[1].split('/')[0] if '/vehicledetail/' in url else url
                return {"id": car_id, "error": "Failed to load page"}

            # Wait for page to load with shorter timeout
            try:
                WebDriverWait(driver, 15).until(  # Reduced from 20 to 15
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".basics-section"))
                )
            except TimeoutException:
                return {"id": url.split('/vehicledetail/')[1].split('/')[0] if '/vehicledetail/' in url else url, "error": "Page structure not found"}
            
            # Wait for price element to be present
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "span[data-qa='primary-price']"))
                )
            except TimeoutException:
                pass
            
            car_id = url.split('/vehicledetail/')[1].split('/')[0] if '/vehicledetail/' in url else url
            title = get_detail_text(driver, "h1.listing-title")
            car_data = {
                "id": car_id,
                "title": title,
                "price": get_detail_text(driver, "span[data-qa='primary-price']")
            }

            # Parse title to extract year, make, and model
            title_parts = parse_car_title(title)
            car_data.update(title_parts)  # Add year, make, and model to car_data

            # --- Basics Section ---
            try:
                dl_element = WebDriverWait(driver, 8).until(  # Reduced from 10 to 8
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".basics-section dl.fancy-description-list"))
                )
                dt_elements = dl_element.find_elements(By.TAG_NAME, "dt")
                dd_elements = dl_element.find_elements(By.TAG_NAME, "dd")
                for dt, dd in zip(dt_elements, dd_elements):
                    try:
                        # Sanitize the key to be a valid database column name
                        raw_key = dt.text.strip().lower()
                        # Remove special characters and replace spaces with underscores
                        sanitized_key = re.sub(r'[^a-z0-9\s]', '', raw_key)
                        key = sanitized_key.replace(' ', '_')
                        
                        value = dd.text.strip()
                        if key and value:
                            # Clean mileage value if this is the mileage field
                            if key == 'mileage':
                                value = clean_mileage(value)
                            car_data[key] = value
                    except StaleElementReferenceException:
                        continue
            except Exception as e:
                pass
            
            # --- Features Section ---
            try:
                features_dl = WebDriverWait(driver, 8).until(  # Reduced from 10 to 8
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".features-section dl.fancy-description-list"))
                )
                features_dt_elements = features_dl.find_elements(By.TAG_NAME, "dt")
                features_dd_elements = features_dl.find_elements(By.TAG_NAME, "dd")
                for dt, dd in zip(features_dt_elements, features_dd_elements):
                    try:
                        category = dt.text.strip().lower().replace(" ", "_")
                        feature_items = dd.find_elements(By.CSS_SELECTOR, "ul.vehicle-features-list li")
                        features_list = [item.text.strip() for item in feature_items if item.text.strip()]
                        if category and features_list:
                            car_data[f"features_{category}"] = "; ".join(features_list)
                    except StaleElementReferenceException:
                        continue
            except Exception as e:
                pass
            
            # --- Additional Popular Features ---
            try:
                additional_features_element = driver.find_element(By.CSS_SELECTOR, ".auto-corrected-feature-list")
                additional_features_text = additional_features_element.text.strip()
                if additional_features_text:
                    car_data["additional_popular_features"] = additional_features_text
            except Exception as e:
                pass
            
            # --- All Features from Modal ---
            try:
                view_all_features_btn = driver.find_element(By.CSS_SELECTOR, "spark-button[data-target='#allFeaturesModal']")
                driver.execute_script("arguments[0].click();", view_all_features_btn)
                WebDriverWait(driver, 3).until(  # Reduced from 5 to 3
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".all-features-list"))
                )
                all_features_elements = driver.find_elements(By.CSS_SELECTOR, ".all-features-list .all-features-item")
                all_features_list = [element.text.strip() for element in all_features_elements if element.text.strip()]
                if all_features_list:
                    car_data["all_features"] = "; ".join(all_features_list)
                close_btn = driver.find_element(By.CSS_SELECTOR, ".sds-modal .btn-close")
                driver.execute_script("arguments[0].click();", close_btn)
            except Exception as e:
                pass
            
            # --- Images ---
            try:
                image_data = []
                images = driver.find_elements(By.CSS_SELECTOR, "gallery-thumbnails img")
                for img in images:
                    try:
                        src = img.get_attribute("src")
                        if src:
                            # Replace /small/ with /medium/ for a higher resolution image
                            src = src.replace('/small/', '/medium/')
                        
                        modal_src = img.get_attribute("modal-src")
                        alt = img.get_attribute("alt")
                        if src:
                            image_info = {
                                "src": src,
                                "modal_src": modal_src if modal_src else src,
                                "alt": alt if alt else ""
                            }
                            image_data.append(image_info)
                    except Exception as e:
                        continue
                if image_data:
                    car_data["images"] = json.dumps(image_data)
            except Exception as e:
                pass
            
            # --- Payment Information ---
            try:
                # Extract start payment amount - try multiple selectors
                payment_selectors = [
                    "#payment-result-value",
                    ".calculation-result.experience-embedded",
                    "[data-qa='payment-amount']",
                    ".payment-amount",
                    ".monthly-payment"
                ]
                
                payment_text = None
                for selector in payment_selectors:
                    try:
                        payment_element = driver.find_element(By.CSS_SELECTOR, selector)
                        payment_text = payment_element.text.strip()
                        if payment_text:
                            break
                    except:
                        continue
                
                if payment_text:
                    # Clean and store just the numeric payment amount
                    cleaned_payment = clean_payment(payment_text)
                    car_data["start_payment"] = cleaned_payment if cleaned_payment is not None else "Not available"
                else:
                    car_data["start_payment"] = "Not available"
                
                # Extract breakdown details - try multiple approaches
                breakdown_data = {}
                
                # Try different breakdown section selectors
                breakdown_selectors = [
                    ".breakdown-section-details--grid, .breakdown-section-details--summary-grid",
                    ".payment-breakdown",
                    ".loan-breakdown",
                    "[data-qa='payment-breakdown']"
                ]
                
                breakdown_found = False
                for selector in breakdown_selectors:
                    try:
                        breakdown_sections = driver.find_elements(By.CSS_SELECTOR, selector)
                        if breakdown_sections:
                            for section in breakdown_sections:
                                try:
                                    # Try different title/value selectors
                                    title_selectors = [
                                        "dt.breakdown-section-details--title",
                                        ".breakdown-title",
                                        "dt",
                                        ".title"
                                    ]
                                    value_selectors = [
                                        "dd.breakdown-section-details--value",
                                        ".breakdown-value",
                                        "dd",
                                        ".value"
                                    ]
                                    
                                    for title_sel, value_sel in zip(title_selectors, value_selectors):
                                        try:
                                            dt_elements = section.find_elements(By.CSS_SELECTOR, title_sel)
                                            dd_elements = section.find_elements(By.CSS_SELECTOR, value_sel)
                                            
                                            if dt_elements and dd_elements:
                                                for dt, dd in zip(dt_elements, dd_elements):
                                                    try:
                                                        title = dt.text.strip()
                                                        value = dd.text.strip()
                                                        if title and value:
                                                            # Clean the title for use as a key
                                                            clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', title).strip().lower().replace(' ', '_')
                                                            # Clean monetary values in the breakdown
                                                            if any(keyword in clean_title for keyword in ['price', 'payment', 'amount', 'paid', 'value']):
                                                                value = clean_payment(value)
                                                            breakdown_data[clean_title] = value
                                                    except StaleElementReferenceException:
                                                        continue
                                                break  # If we found elements with this selector pair, stop trying others
                                        except:
                                            continue
                                    
                                    if breakdown_data:
                                        breakdown_found = True
                                        break
                                except Exception as e:
                                    continue
                        
                        if breakdown_found:
                            break
                    except:
                        continue
                
                # Store breakdown as JSON string
                if breakdown_data:
                    car_data["payment_breakdown"] = json.dumps(breakdown_data)
                else:
                    car_data["payment_breakdown"] = "No breakdown available"
                    
            except Exception as e:
                car_data["start_payment"] = "Not available"
                car_data["payment_breakdown"] = "Not available"
                pass
            
            # --- Bodystyle Extraction from External Links Section ---
            try:
                a_tag = driver.find_element(By.CSS_SELECTOR, "a.sds-link--ext[data-linkname='check-recalls']")
                href = a_tag.get_attribute("href")

                # Only parse if URL has query part
                bodystyle = None
                if '?' in href:
                    parsed = urllib.parse.urlparse(href)
                    qs = urllib.parse.parse_qs(parsed.query)
                    bodystyle = qs.get('bodystyle', [None])[0]

                # Optional fallback
                if not bodystyle:
                    match = re.search(r'bodystyle=([^&]+)', href)
                    if match:
                        bodystyle = match.group(1)

                if bodystyle:
                    car_data['bodystyle'] = bodystyle
                else:
                    pass

            except Exception as e:
                pass
            
            # Add status and timestamp
            car_data["status_flag"] = "New Entry"
            car_data["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            return car_data
            
        except Exception as e:
            error_msg = str(e)
            if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait longer for connection issues
                    continue
            else:
                if attempt < max_retries - 1:
                    time.sleep(1)  # Reduced from 2 to 1 second for other errors
                    continue
            
            car_id = url.split('/vehicledetail/')[1].split('/')[0] if '/vehicledetail/' in url else url
            return {"id": car_id, "error": error_msg[:200]}  # Truncate error message
    return None

def build_url(filters, page):
    base_url = "https://www.cars.com/shopping/results/?"
    params = []
    if filters.get("stock_type"):
        params.append(f"stock_type={filters['stock_type']}")
    if filters.get("makes"):
        for make in filters["makes"]:
            params.append(f"makes[]={make}")
    if filters.get("models"):
        for model in filters["models"]:
            params.append(f"models[]={model}")
    if filters.get("list_price_min") is not None:
        params.append(f"list_price_min={filters['list_price_min']}")
    if filters.get("list_price_max") is not None:
        params.append(f"list_price_max={filters['list_price_max']}")
    if filters.get("zip_code"):
        params.append(f"zip={filters['zip_code']}")
    if filters.get("max_distance"):
        params.append(f"maximum_distance={filters['max_distance']}")
    if filters.get("year_min") is not None:
        params.append(f"year_min={filters['year_min']}")
    if filters.get("year_max") is not None:
        params.append(f"year_max={filters['year_max']}")
    if filters.get("mileage_max") is not None:
        params.append(f"mileage_max={filters['mileage_max']}")
    if filters.get("body_styles"):
        for style in filters["body_styles"]:
            params.append(f"body_style_slugs[]={style}")
    if filters.get("fuel_types"):
        for fuel in filters["fuel_types"]:
            params.append(f"fuel_slugs[]={fuel}")
    params.append(f"page={page}")
    return base_url + "&".join(params)

def scrape_cars(
    stock_type: str = 'all',
    makes=None,
    models=None,
    zip_code: str = '60606',
    max_distance: int = 50,
    list_price_min=None,
    list_price_max=None,
    year_min=None,
    year_max=None,
    mileage_max=None,
    body_styles=None,
    fuel_types=None,
    start_page: int = 1,
    end_page: int = 1
):
    """
    Main scraper function that saves to CSV and returns the filename and data.
    Accepts all new filter fields and loops from start_page to end_page.
    """
    filters = {
        "stock_type": stock_type,
        "makes": makes or [],
        "models": models or [],
        "zip_code": zip_code,
        "max_distance": max_distance,
        "list_price_min": list_price_min,
        "list_price_max": list_price_max,
        "year_min": year_min,
        "year_max": year_max,
        "mileage_max": mileage_max,
        "body_styles": body_styles or [],
        "fuel_types": fuel_types or []
    }
    logging.info("Scraping started with filters: %s", filters)
    main_driver = setup_driver()
    all_links = []
    try:
        for page in range(start_page, end_page + 1):
            url = build_url(filters, page)
            if not load_page_with_retry(main_driver, url):
                break
            WebDriverWait(main_driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.vehicle-card"))
            )
            last_height = main_driver.execute_script("return document.body.scrollHeight")
            while True:
                main_driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.5)
                new_height = main_driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            cards = main_driver.find_elements(By.CSS_SELECTOR, "div.vehicle-card")
            page_links = []
            for card in cards:
                try:
                    link = card.find_element(By.CSS_SELECTOR, "a.vehicle-card-link").get_attribute('href')
                    if link:
                        page_links.append(link)
                except:
                    continue
            all_links.extend(page_links)
            if not page_links:
                break
    finally:
        main_driver.quit()
    logging.info("Total links collected: %d", len(all_links))
    scraped_data = []
    max_workers = min(4, len(all_links))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        from queue import Queue
        driver_queue = Queue()
        for _ in range(max_workers):
            try:
                driver = setup_driver()
                driver_queue.put(driver)
            except Exception:
                pass
        def scrape_with_driver(link, car_index):
            driver = None
            try:
                driver = driver_queue.get(timeout=10)
                result = scrape_car_details(driver, link)
                return result if result and 'error' not in result else None
            except Exception:
                return None
            finally:
                if driver:
                    try:
                        driver.current_url
                        driver_queue.put(driver)
                    except:
                        try:
                            new_driver = setup_driver()
                            driver_queue.put(new_driver)
                        except Exception:
                            pass
        futures = []
        for i, link in enumerate(all_links):
            future = executor.submit(scrape_with_driver, link, i)
            futures.append(future)
        for i, future in enumerate(futures):
            try:
                result = future.result(timeout=60)
                if result:
                    scraped_data.append(result)
                if (i + 1) % 5 == 0:
                    logging.info("Progress: %d/%d cars processed", i + 1, len(all_links))
            except Exception:
                pass
        while not driver_queue.empty():
            try:
                driver = driver_queue.get_nowait()
                driver.quit()
            except:
                pass
    if scraped_data:
        db.update_wordpress_database(scraped_data)
        logging.info("Scraping process completed successfully! %d records updated.", len(scraped_data))
    else:
        logging.info("No data was scraped successfully.")
    return {"data": scraped_data} 