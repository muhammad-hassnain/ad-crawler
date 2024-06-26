from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver import Chrome
from selenium import webdriver
import threading
import selenium

import undetected_chromedriver as uc
from browsermobproxy import Server
from time import sleep
import pandas as pd
import traceback
import argparse
import datetime
import zipfile
import random
import psutil
import codecs
import time
import sys
import os

sys.path.insert(0, './code/')
from FullPageScreenshotCollector import *
from CustomPopupManager import *
from BidCollector import *
from AdCollector import *

DOCKER = True
# if DOCKER:
# 	from pyvirtualdisplay import Display
# 	disp = Display(backend="xvnc", size=(1920,1080), rfbport=1212) # 1212 has to be a random port number
# 	disp.start()

ROOT_DIRECTORY = os.getcwd()

def inject_start_button(driver):
    # Load a blank page
    driver.get("about:blank")

    # Create a button element
    button_script = """
    var btn = document.createElement('button');
    btn.id = 'startCrawlButton';
    btn.innerText = 'Start Crawling';
    btn.style.position = 'fixed';
    btn.style.top = '50%';
    btn.style.left = '50%';
    btn.style.transform = 'translate(-50%, -50%)';
    btn.style.padding = '10px 20px';
    btn.style.fontSize = '20px';
    document.body.appendChild(btn);
    """
    driver.execute_script(button_script)
    
    # Attach an event listener to the button
    click_listener_script = """
    document.getElementById('startCrawlButton').addEventListener('click', function() {
        console.log('Button clicked, changing title.');
        document.title = 'startCrawlClicked';
    });
    """
    driver.execute_script(click_listener_script)

def parseArguments():
	global ROOT_DIRECTORY;
	# Example: python3 ad-crawler.py --profile="Test" --proxyport=8022 --chromedatadir="/home/yvekaria/.config/google-chrome/ProfileTest"
	parser = argparse.ArgumentParser()
	parser.add_argument("-p", "--profile", type=str, required=True, help="Enter the type of profile being crawled. Valid inputs are ['TV-Blank', 'TV-Trained', 'HB-Checker']")
	parser.add_argument("-px", "--proxyport", type=int, required=True, help="Enter the port on which browsermob-proxy is to be run.")
	parser.add_argument("-c", "--chromedatadir", type=str, required=True, help="Enter the Chrome's data directory path: Open Chrome's latest stable version installed => Type chrome://version => Input 'Profile Path' without")
	if DOCKER:
		# Example docker run -d -e PYTHONUNBUFFERED=1 -v $(pwd):/root -v /home/yvekaria/.config/google-chrome/Test:/profile -p 20000:1212 --shm-size=10g ad-crawler python3.11 ad-crawler.py -p "Test" -px 8022 -c "/home/yvekaria/.config/google-chrome/Test" -mp "/root"
		parser.add_argument("-mp", "--mountpath", type=str, required=False, help="Mounted path from docker run command")
	args = parser.parse_args()
	return args

# Function to open the URL and set a flag when done
def open_url(url, driver, done_flag):
	print(time.time(), "Started")
	try:
		driver.get(url)
	except Exception as e:
		print(f"Error loading {url}: {e}")
	finally:
		done_flag.set()

def handle_popups(cpm_obj, driver, pop_flag):
	try:
		cpm_obj.managePopups(driver)
	except Exception as e:
		print(f"Error handling popups: {e}")
	finally:
		pop_flag.set()

def handle_consent(cpm_obj, driver, consent_flag):
	try:
		cpm_obj.acceptMissedConsents(driver)
	except Exception as e:
		print(f"Error handling popups: {e}")
	finally:
		consent_flag.set()
	
def readHeaderBiddingSites():
	global ROOT_DIRECTORY;
	filepath = os.path.join(ROOT_DIRECTORY, "data", "hb_domains.csv")
	df_hb = pd.read_csv(filepath)
	return {str(df_hb.iloc[i]["tranco_domain"]): int(df_hb.iloc[i]["tranco_rank"]) for i in range(len(df_hb)) if bool(df_hb.iloc[i]["hb_status"])}

def getChromeOptionsObject():
	global ROOT_DIRECTORY;
	chrome_options = Options()
	# chrome_options.binary_location = "/usr/bin/google-chrome-stable"
	# chrome_options.add_argument("--headless")
	# chrome_options.add_argument("--disable-gpu")
	# chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
	# chrome_options.add_experimental_option('useAutomationExtension', False)
	chrome_options.add_argument("--no-sandbox")
	chrome_options.add_argument("--disable-dev-shm-usage")
	chrome_options.add_argument("--remote-debugging-port=9222")
	chrome_options.add_argument("--window-size=1536,864")
	chrome_options.add_argument("--start-maximized")
	chrome_options.add_argument("--disable-infobars")
	chrome_options.add_argument("--disable-notifications")
	chrome_options.add_argument("--disable-popup-blocking")
	chrome_options.add_argument("--ignore-certificate-errors")
	chrome_options.add_argument("--disable-blink-features=AutomationControlled")
	extension_dir = os.path.join(ROOT_DIRECTORY, "consent-extension", "Consent-O-Matic", "Extension")
	chrome_options.add_argument('--load-extension={}'.format(extension_dir))
	prefs = {
		"translate_whitelists": {"lt": "en"},
		"translate_whitelists": {"fr": "en"},
		"translate_whitelists": {"ro": "en"},
		"translate_whitelists": {"pl": "en"},
		"translate_whitelists": {"de": "en"},
		"translate_whitelists": {"hu": "en"},
		"translate_whitelists": {"sr": "en"},
		"translate_whitelists": {"cs": "en"},
		"translate_whitelists": {"cz": "en"},
		"translate_whitelists": {"sk": "en"},
		"translate_whitelists": {"es": "en"},
		"translate_whitelists": {"da": "en"},
		"translate_whitelists": {"pt": "en"},
		"translate":{"enabled": True}
	}
	chrome_options.add_experimental_option("prefs", prefs)
	chrome_options.add_argument("--lang=en")
	return chrome_options

def exploreFullPage(webdriver_):
	'''
	Scroll to bottom and back up to the top for all ads to load and become viewable
	'''
	try:
		page_height = int(webdriver_.execute_script("return document.body.scrollHeight"))
		for i in range(1, page_height, 10):
			try:
				webdriver_.execute_script("window.scrollTo(0, {});".format(i))
				sleep(0.05)
			except:
				continue
		sleep(2)
		webdriver_.execute_script("window.scrollTo(0, 0);")
	except:
		pass
	# Wait for new ads to completely load
	sleep(6)
	return

def configureProxy(profile_name, profile_dir):
	# Instantiate chromedriver options
	chrome_options = getChromeOptionsObject()

	# Associate proxy-related settings to the chromedriver
	chrome_options.add_argument("--user-data-dir=%s" % profile_dir)
	chrome_options.add_argument("--profile-directory=%s" % profile_name)
	
	return chrome_options

def killBrowsermobproxyInstances():
	for process in psutil.process_iter():
		try:
			process_info = process.as_dict(attrs=['name', 'cmdline'])
			if process_info.get('name') in ('java', 'java.exe'):
				for cmd_info in process_info.get('cmdline'):
					if cmd_info == '-Dapp.name=browsermob-proxy':
						process.kill()
		except psutil.NoSuchProcess:
			pass
	return

# Function to perform bot mitigation techniques
def perform_bot_mitigation(driver, profile, hb_domain, hb_rank, experimental_path, iteration, logger):
	
	# Bot mitigation 1: Move mouse randomly around a number of times
	print("Performing Bot Mitigation 1")
	RANDOM_SLEEP_LOW, RANDOM_SLEEP_HIGH, NUM_MOUSE_MOVES = 1, 8, 10
	num_moves, num_fails = 0, 0
	
	while num_moves < NUM_MOUSE_MOVES + 1 and num_fails < NUM_MOUSE_MOVES:
		try:
			move_max = random.randint(0, 350)
			x = random.randint(-move_max, move_max)
			y = random.randint(-move_max, move_max)
			action = ActionChains(driver)
			action.move_by_offset(x, y)
			action.perform()
			num_moves += 1
		except:
			# MoveTargetOutOfBoundsException
			num_fails += 1
			pass

	# Bot mitigation 2: Scroll smoothly in random intervals down the page and then back to the top
	print("Performing Bot Mitigation 2")
	SCROLL_MAX = 50
	try:
		scroll_count = 0
		page_height = int(driver.execute_script('return Math.max( document.body.scrollHeight, document.body.offsetHeight, document.documentElement.clientHeight, document.documentElement.scrollHeight, document.documentElement.offsetHeight );'))
		for i in range(1, page_height, 250):
			scroll_count += 1
			if scroll_count > SCROLL_MAX:
				break;
			if scroll_count%5 == 0:
				# Perform bid collection
				bid_file_path = os.path.join(experimental_path, str(hb_domain)+"_"+str(iteration)+"_bids.json")
				bid_object = BidCollector(profile, hb_domain, hb_rank, bid_file_path)
				bid_object.collectBids(driver, logger)
				print(scroll_count, "Bid data collected")
			page_height = int(driver.execute_script('return Math.max( document.body.scrollHeight, document.body.offsetHeight, document.documentElement.clientHeight, document.documentElement.scrollHeight, document.documentElement.offsetHeight );'))
			try:
				driver.execute_script("window.scrollTo(0, {});".format(i))
				sleep(random.randrange(0, 5))
			except:
				continue
	except:
		pass
	sleep(10)  # Wait at the bottom

	try:
		scroll_count = 0
		page_height = int(driver.execute_script('return Math.max( document.body.scrollHeight, document.body.offsetHeight, document.documentElement.clientHeight, document.documentElement.scrollHeight, document.documentElement.offsetHeight );'))
		for i in range(page_height, 0, -250):
			scroll_count += 1
			if scroll_count > SCROLL_MAX:
				break;
			if scroll_count%5 == 0:
				# Perform bid collection
				bid_file_path = os.path.join(experimental_path, str(hb_domain)+"_"+str(iteration)+"_bids.json")
				bid_object = BidCollector(profile, hb_domain, hb_rank, bid_file_path)
				bid_object.collectBids(driver, logger)
				print(scroll_count, "Bid data collected")
			page_height = int(driver.execute_script('return Math.max( document.body.scrollHeight, document.body.offsetHeight, document.documentElement.clientHeight, document.documentElement.scrollHeight, document.documentElement.offsetHeight );'))
			try:
				driver.execute_script("window.scrollTo(0, {});".format(i))
				sleep(random.randrange(0, 5))
			except:
				continue
	except:
		pass
	sleep(10)  # Wait at the top

	# Bot mitigation 3: Randomly wait so page visits happen with irregularity between consectutive websites
	print("Performing Bot Mitigation 3")
	sleep(random.randrange(RANDOM_SLEEP_LOW, RANDOM_SLEEP_HIGH))
	
	return

def main(args):

	global ROOT_DIRECTORY, DOCKER;

	profile = args.profile
	proxy_port = args.proxyport
	chrome_profile_dir = args.chromedatadir.replace("Default", profile)
	if DOCKER:
		ROOT_DIRECTORY = args.mountpath
	

	# Reading Top 100 Header Bidding supported websites
	# hb_dict stores mapping of hb_domain to hb_rank (tranco_rank)
	hb_dict = readHeaderBiddingSites()
	
	current_time = time.time()
	try:
		# kill -9 $(ps aux | grep '[c]hrome' | awk '{print $2}')
		# ps aux | grep chrome
		# driver = uc.Chrome(service=Service(ChromeDriverManager().install()), version_main=114, options=configureProxy(profile, chrome_profile_dir)) #executable_path=‘chromedriver’ #114
		
		# driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=configureProxy(profile, chrome_profile_dir))
		
		options = Options()
		options.add_argument(f"user-data-dir={chrome_profile_dir}")
		options.add_argument("--no-sandbox") # This option is often necessary in containerized environments
		options.add_argument("--disable-dev-shm-usage") # Overcomes limited resource problems
		# options.add_argument("--remote-debugging-port=9222")
		# options.add_argument("--window-size=1536,864")
		# options.add_argument("--start-maximized")
		options.add_argument("--disable-infobars")
		options.add_argument("--disable-notifications")
		options.add_argument("--disable-popup-blocking")
		options.add_argument("--ignore-certificate-errors")
		options.add_argument("--disable-blink-features=AutomationControlled")
		extension_dir = os.path.join(ROOT_DIRECTORY, "consent-extension", "Consent-O-Matic", "Extension")
		options.add_argument('--load-extension={}'.format(extension_dir))
		prefs = {
			"translate_whitelists": {"lt": "en"},
			"translate_whitelists": {"fr": "en"},
			"translate_whitelists": {"ro": "en"},
			"translate_whitelists": {"pl": "en"},
			"translate_whitelists": {"de": "en"},
			"translate_whitelists": {"hu": "en"},
			"translate_whitelists": {"sr": "en"},
			"translate_whitelists": {"cs": "en"},
			"translate_whitelists": {"cz": "en"},
			"translate_whitelists": {"sk": "en"},
			"translate_whitelists": {"es": "en"},
			"translate_whitelists": {"da": "en"},
			"translate_whitelists": {"pt": "en"},
			"translate":{"enabled": True}
		}
		options.add_experimental_option("prefs", prefs)
		options.add_argument("--lang=en")
	
		driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

		# Example usage
		# ROOT_DIRECTORY = "/path/to/your/root/directory"  # Set this to the directory containing your extension
		# chrome_options = get_configured_chrome_options(user_data_dir=chrome_profile_dir)
		# driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

		inject_start_button(driver)
		while driver.title != 'startCrawlClicked':
			# print("I am waiting")
			time.sleep(1)
		# print('i am done waiting')
		# sleep(15)
		driver.refresh()
	except BaseException as error:
		print("Chromedriver loading issue: " + str(error))
		exit()

	print("\nChromedriver successfully loaded for" , profile )

	for iteration in [1, 2, 3]:
		for idx, (hb_domain, hb_rank) in enumerate(hb_dict.items()):
			print("i" , profile, "has moved to next")
			
			# if iteration >= 3 and hb_domain == "google.com":
			# 	continue

			# if iteration == 1 and idx < 13:
			# 	continue

			# if iteration <=1 or iteration == 2 and idx < 72:
			# 	continue
			
			start_time = time.time()
			print("\n\nStarting to crawl:", iteration, idx, hb_domain, hb_rank , "for" , profile)

			experimental_path = os.path.join(ROOT_DIRECTORY, "output", profile, str(hb_domain)+"_"+str(iteration))
			if not(os.path.exists(experimental_path)):
				os.makedirs(experimental_path)


			# Log issues and crawl progress in this file
			logger = open(os.path.join(experimental_path, str(hb_domain)+"_"+str(iteration)+"_logs.txt"), "w")
			ct = datetime.datetime.now()
			logger.write("\n\nCrawl {} Start Time: {} [TS:{}] [{}]".format(iteration, ct, ct.timestamp(), hb_domain))
			print("Error logging started ...")
			

			# Start the chromedriver instance
			'''
			current_time = time.time()
			try:
				# driver = uc.Chrome(service=Service(ChromeDriverManager().install()), version_main=114, options=chrome_options) #executable_path=‘chromedriver’
				driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=configureProxy(profile, chrome_profile_dir))
			except BaseException as error:
				continue
			logger.write("\nChromedriver successfully loaded! [Time: {}]".format(time.time()-current_time))
			print("\nChromedriver successfully loaded!")
			'''
			attempt = 0
			while(1):
				# Visit the current domain
				current_time = time.time()
				website = "https://" + str(hb_domain)
				try:
					print("Website:", website , "for" , profile)
					# driver.get(website)
					
					# Threading to open the URL and wait for a maximum of timeout seconds
					done_flag = threading.Event()
					thread = threading.Thread(target=open_url, args=(website, driver, done_flag))
					thread.start()

					# Timeout for each URL (in seconds) before moving to next URL
					timeout = 120
					
					# Wait for the thread to finish or until the timeout is reached
					thread.join(timeout)
					
					# If the thread is still running (URL not loaded within timeout), stop it and proceed
					if not done_flag.is_set():
						print(time.time(), "Timed out while trying to load" , website , "for" , profile)
						logger.write("\n[TIMEOUT] main()::ad-crawler: {}\nTimeout of 120secs occurred while getting the domain: {} in Iteration: {} | {} [Time: {}]".format(str(traceback.format_exc()), hb_domain, iteration, profile, time.time()-current_time))
						raise BaseException("Raising BaseException while getting URL due to timeout issue")
					else:
						print(f"Successfully loaded: {website} for" , profile)
						logger.write("\nSuccessfully got the webpage ... [Time: {}]".format(time.time()-current_time))
						pass
					break
				except BaseException as e:
					logger.write("\n[ERROR] main()::ad-crawler: {}\nException occurred while getting the domain: {} in Iteration: {} | {} [Time: {}]".format(str(traceback.format_exc()), hb_domain, iteration, profile, time.time()-current_time))
					attempt+=1
					'''
					try:
						driver.quit()
					except:
						print("\n[ERROR] main()::Webdriver-Intitialization: {}".format(str(traceback.format_exc())))
						logger.write("\n[ERROR] main()::Webdriver-Intitialization: {} for domain: {} in Iteration: {}| {} [Time: {}]".format(str(traceback.format_exc()), hb_domain, iteration, profile, time.time()-current_time))
						continue
					'''
			
			print("\nChromedriver successfully loaded website for" , profile)
			# Wait for page to completely load
			sleep(10)
			print("Visiting and loading webpage ... for" , profile)
			logger.write("\nVisiting and loading webpage ... [Time: {}]".format(time.time()-current_time))
			
			# if hb_domain == "google.com":
			# 	sleep(300)
			
			
			# Read custom popup handling rules
			current_time = time.time()
			f = open(os.path.join(ROOT_DIRECTORY, "data", "custom-popup-xpaths.txt"), "r")
			prules = f.read().split("\n")
			f.close()
			prule_dict = {prule.split(" | ")[0]: list(prule.split(" | ")[1:]) for prule in prules}


			cpm = CustomPopupManager(hb_domain, prule_dict)
			pop_flag = threading.Event()
			thread = threading.Thread(target=handle_popups, args=(cpm, driver, pop_flag))
			thread.start()
			timeout = 150
			thread.join(timeout)
			# If the thread is still running, stop it and proceed
			if not pop_flag.is_set():
				print(time.time(), "Timed out while trying to give consent for" , profile)
				logger.write("\n[TIMEOUT] main()::ad-crawler: {}\nTimeout of 200secs occurred while handling consent in managePopups() for the domain: {} in Iteration: {} | {} [Time: {}]".format(str(traceback.format_exc()), hb_domain, iteration, profile, time.time()-current_time))
			else:
				print("Successfully completed managePopups() for" , profile)
				logger.write("\nSuccessfully completed managePopups() ... [Time: {}]".format(time.time()-current_time))
				pass
			# cpm.managePopups(driver)


			consent_flag = threading.Event()
			thread = threading.Thread(target=handle_consent, args=(cpm, driver, consent_flag))
			thread.start()
			timeout = 150
			thread.join(timeout)
			# If the thread is still running, stop it and proceed
			if not consent_flag.is_set():
				print(time.time(), "Timed out while trying to give consent for" , profile)
				logger.write("\n[TIMEOUT] main()::ad-crawler: {}\nTimeout of 200secs occurred while handling consent in acceptMissedConsents() for the domain: {} in Iteration: {} | {} [Time: {}]".format(str(traceback.format_exc()), hb_domain, iteration, profile, time.time()-current_time))
			else:
				print("Successfully completed acceptMissedConsents() for " , profile)
				logger.write("\nSuccessfully completed acceptMissedConsents() ... [Time: {}]".format(time.time()-current_time))
				pass
			# cpm.acceptMissedConsents(driver)
			
			logger.write("\nPopup-Consent-1 handled!")
			# exploreFullPage(driver)
			perform_bot_mitigation(driver, profile, hb_domain, hb_rank, experimental_path, iteration, logger)
			logger.write("\nWebpage explored fully.")
			
			consent_flag = threading.Event()
			thread = threading.Thread(target=handle_consent, args=(cpm, driver, consent_flag))
			thread.start()
			timeout = 150
			thread.join(timeout)

			# If the thread is still running, stop it and proceed
			if not consent_flag.is_set():
				print(time.time(), "Timed out while trying to give consent for" , profile)
				logger.write("\n[TIMEOUT] main()::ad-crawler: {}\nTimeout of 200secs occurred while handling consent in acceptMissedConsents() for the domain: {} in Iteration: {} | {} [Time: {}]".format(str(traceback.format_exc()), hb_domain, iteration, profile, time.time()-current_time))
			else:
				print("Successfully completed acceptMissedConsents() for", profile)
				logger.write("\nSuccessfully completed acceptMissedConsents() ... [Time: {}]".format(time.time()-current_time))
				pass
			# cpm.acceptMissedConsents(driver)


			pop_flag = threading.Event()
			thread = threading.Thread(target=handle_popups, args=(cpm, driver, pop_flag))
			thread.start()
			timeout = 120
			thread.join(timeout)
			# If the thread is still running, stop it and proceed
			if not pop_flag.is_set():
				print(time.time(), "Timed out while trying to give consent for" , profile)
				logger.write("\n[TIMEOUT] main()::ad-crawler: {}\nTimeout of 200secs occurred while handling consent in managePopups() for the domain: {} in Iteration: {} | {} [Time: {}]".format(str(traceback.format_exc()), hb_domain, iteration, profile, time.time()-current_time))
			else:
				print("Successfully completed managePopups() for" , profile)
				logger.write("\nSuccessfully completed managePopups() ... [Time: {}]".format(time.time()-current_time))
				pass
			# cpm.managePopups(driver)
			logger.write("\nPopup-Consent-2 handled! [Time: {}]".format(time.time()-current_time))

			'''
			# Read filterlist rules
			f = open(os.path.join(ROOT_DIRECTORY, "data", "EasyList", "easylist.txt"), "r")
			rules = f.read().split("\n")
			f.close()
			rules = [rule[2:] for rule in rules[18:] if rule.startswith("##")]
			'''

			# # Save DOM of the webpage
			# current_time = time.time()
			# try:
			# 	dom_filepath = os.path.join(experimental_path, str(hb_domain)+"_"+str(iteration)+"_DOM.html")
			# 	fdom = codecs.open(dom_filepath, "w", "utf−8")
			# 	fdom.write(driver.page_source)
			# 	fdom.close()
			# 	logger.write("\nDOM saved. [Time: {}]".format(time.time()-current_time))
			# 	print("DOM saved i am " , profile)
			# except BaseException as e:
			# 	print("\n[ERROR] DOM-Capture: {}".format(str(traceback.format_exc())) , "i am", profile)
			# 	logger.write("\n[ERROR] main()::DOM-Capture: {} for domain: {} in iteration: {} | {} [Time: {}]".format(str(traceback.format_exc()), hb_domain, iteration, profile, time.time()-current_time))
			# 	pass


			# Perform bid collection
			bid_file_path = os.path.join(experimental_path, str(hb_domain)+"_"+str(iteration)+"_bids.json")
			bid_object = BidCollector(profile, hb_domain, hb_rank, bid_file_path)
			bid_object.collectBids(driver, logger)
			print("Bid data collected I am" , profile)
			
			
			# Take fullpage screenshot of the webpage
			current_time = time.time()
			screenshot_output_path = os.path.join(experimental_path, str(hb_domain)+"_"+str(iteration)+"_ss-before.png")
			ss_object = FullPageScreenshotCollector(profile, hb_domain, hb_rank, screenshot_output_path)
			ss_object.captureFullScreenshot(driver, logger)
			logger.write("\nFull page screnshot successfully captured. [Time: {}]".format(time.time()-current_time))
			try:
				driver.execute_script("window.scrollTo(0, 0);")
			except:
				pass
			sleep(10)
			print("Fullpage screenshot of the webpage captured I am" , profile)

			
			'''			
			# Collect ads on the website
			print("Starting to collect ads ...")
			ad_path = os.path.join(experimental_path, "ads")
			if not(os.path.exists(ad_path)):
				os.makedirs(ad_path)

			EASYLIST_DIR = os.path.join(ROOT_DIRECTORY, "data", "EasyList")
			ad_object = AdCollector(profile, iteration, hb_domain, hb_rank, rules, ad_path, EASYLIST_DIR, logger)
			ad_object.collectAds(driver)
			print("Ad collection complete!")


			# Take fullpage screenshot of the webpage
			current_time = time.time()
			screenshot_output_path = os.path.join(experimental_path, str(hb_domain)+"_"+str(iteration)+"_ss-after.png")
			ss_object = FullPageScreenshotCollector(profile, hb_domain, hb_rank, screenshot_output_path)
			ss_object.captureFullScreenshot(driver, logger)
			logger.write("\nFull page screnshot successfully captured. [Time: {}]".format(time.time()-current_time))
			# Move to the top and wait for dynamically updated ads to completely load
			try:
				driver.execute_script("window.scrollTo(0, 0);")
			except:
				pass
			print("Fullpage screenshot of the webpage captured")
			'''


			end_time = time.time()
			total_time = end_time - start_time
			print("Total time to crawl domain: {} in Iteration: {} is {}".format(hb_domain, iteration, total_time), "i am" , profile)
			logger.write("\nTotal time to crawl domain: {} in Iteration: {} is {}\n".format(hb_domain, iteration, total_time))
			print("i" , profile, "is moving to next")

	driver.quit()
	
	# End



if __name__ == "__main__":

	args = parseArguments()
	main(args)

