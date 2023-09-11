from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver import Chrome
from selenium import webdriver
import selenium

# import undetected_chromedriver as uc
from browsermobproxy import Server
from time import sleep
import pandas as pd
import traceback
import argparse
import datetime
import zipfile
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

DOCKER = False
if DOCKER:
	from pyvirtualdisplay import Display
	disp = Display(backend="xvnc", size=(1920,1080), rfbport=1212) # 1212 has to be a random port number
	disp.start()

ROOT_DIRECTORY = os.getcwd()



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


def readHeaderBiddingSites():
	global ROOT_DIRECTORY;
	filepath = os.path.join(ROOT_DIRECTORY, "data", "hb_domains.csv")
	df_hb = pd.read_csv(filepath)
	return {str(df_hb.iloc[i]["tranco_domain"]): int(df_hb.iloc[i]["tranco_rank"]) for i in range(len(df_hb)) if bool(df_hb.iloc[i]["hb_status"])}


def getChromeOptionsObject():
	global ROOT_DIRECTORY;
	chrome_options = Options()
	chrome_options.binary_location = "/usr/bin/google-chrome-stable" 
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
	extension_dir = os.path.join(ROOT_DIRECTORY, "consent-extension", "Consent-O-Matic", "Extension")
	chrome_options.add_argument('--load-extension={}'.format(extension_dir))
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


def configureProxy(port, profile_name, profile_dir):
	'''
	Instatiate and start browsermobproxy to collect HAR files and accordingly configure chrome options
	Killing open ports:
		- lsof -i:<port>
		- kill -9 <PID>
	'''
	global ROOT_DIRECTORY;
	
	try:
		print("Total browsermobproxy instances currently running:", os.system("ps -aux | grep browsermob | wc -l"))
		os.system("ps -eo etimes,pid,args --sort=-start_time | grep browsermob | awk '{print $2}' | sudo xargs kill")
		print("Total browsermobproxy instances currently running:", os.system("ps -aux | grep browsermob | wc -l"))
		print("Killed all the zombie instances of browsermobproxy from previous visit!")
		for proc in psutil.process_iter():
			if proc.name() == "browsermob-proxy":
				proc.kill()
	except:
		pass
	try:
		from signal import SIGTERM # or SIGKILL
		for proc in process_iter():
			for conns in proc.connections(kind='inet'):
				if conns.laddr.port == 8022:
					proc.send_signal(SIGTERM)
	except:
		pass
	
	try:
		proxy.close()
	except:
		pass
	try:
		server.close()
	except:
		pass
	try:
		server = Server(os.path.join(ROOT_DIRECTORY, "data", "browsermob-proxy-2.1.4", "bin", "browsermob-proxy"), options={'port': port})
		server.start()
		sleep(10)
		proxy = server.create_proxy()
	except BaseException as error:
		print("\nAn exception occurred:", traceback.format_exc(), "in configureProxy()")
		# logger.write("\n[ERROR] configureProxy():\n" + str(traceback.format_exc()))
		return None, None, None

	# Instantiate chromedriver options
	chrome_options = getChromeOptionsObject()

	# Associate proxy-related settings to the chromedriver
	chrome_options.add_argument("--proxy-server={}".format(proxy.proxy))
	chrome_options.add_argument("--ignore-ssl-errors=yes")
	chrome_options.add_argument("--use-littleproxy false")
	chrome_options.add_argument("--proxy=127.0.0.1:%s" % port)
	chrome_options.add_argument("--user-data-dir=%s" % profile_dir)
	# chrome_options.add_argument("--profile-directory=%s" % profile_name)
	
	return server, proxy, chrome_options


def killBrowermobproxyInstances():
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


def main(args):

	global ROOT_DIRECTORY, DOCKER;

	profile = args.profile
	proxy_port = args.proxyport
	chrome_profile_dir = args.chromedatadir.replace("Default", profile)
	if DOCKER:
		ROOT_DIRECTORY = args.mountpath
	

	# Reading Top 104 Header Bidding supported websites
	# hb_dict stores mapping of hb_domain to hb_rank (tranco_rank)
	hb_dict = readHeaderBiddingSites()

	for iteration in [1, 2, 3]:
		for idx, (hb_domain, hb_rank) in enumerate(hb_dict.items()):
	
			start_time = time.time()
			print("\n\nStarting to crawl:", iteration, idx, hb_domain, hb_rank)
	
			experimental_path = os.path.join(ROOT_DIRECTORY, "output", profile, str(hb_domain)+"_"+str(iteration))
			if not(os.path.exists(experimental_path)):
				os.makedirs(experimental_path)
	
	
			# Log issues and crawl progress in this file
			logger = open(os.path.join(experimental_path, str(hb_domain)+"_"+str(iteration)+"_logs.txt"), "w")
			ct = datetime.datetime.now()
			logger.write("\n\nCrawl {} Start Time: {} [TS:{}] [{}]".format(iteration, ct, ct.timestamp(), hb_domain))
			print("Error logging started ...")
	
	
			# Start the proxy server to facilitate capturing HAR file
			server, proxy, chrome_options = configureProxy(proxy_port, profile, chrome_profile_dir)
			if server is None:
				try:
					proxy.close()
				except:
					pass
				try:
					server.close()
				except:
					pass
				logger.write("Server issue while its initialization.")
				continue
			logger.write("\nBrowsermob-proxy successfully configured for domain: {} | {}!".format(hb_domain, profile))
			print("\nBrowsermob-proxy successfully configured for domain: {} | {}!!".format(hb_domain, profile))
			
	
			# Start the chromedriver instance
			try:
				# driver = uc.Chrome(service=Service(ChromeDriverManager().install()), version_main=114, options=chrome_options) #executable_path=‘chromedriver’
				driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
			except BaseException as error:
				proxy.close()
				server.stop()
				killBrowermobproxyInstances()
				logger.write("\n[ERROR] main()::Webdriver-Intitialization: {} for domain: {} in Iteration: {} | {}".format(str(traceback.format_exc()), hb_domain, iteration, profile))
				continue
			logger.write("\nChromedriver successfully loaded!")
			print("\nChromedriver successfully loaded!")
	
	
			# Start capturing HAR
			har_filepath = os.path.join(experimental_path, str(hb_domain)+"_"+str(iteration)+"_har.json")
			try:
				proxy.new_har(har_filepath, options={'captureHeaders': True,'captureContent':True})
			except BaseException as error:
				logger.write("\n[ERROR] main()::HarCaptureStart: {}\n for domain: {} in Iteration: {} | {}".format(str(traceback.format_exc()), hb_domain, iteration, profile))
				pass
			logger.write("\nHAR capture started!")
			print("Starting HAR Capture")
	
	
			# Visit the current domain
			website = "http://" + str(hb_domain)
			try:
				print("Website:", website)
				driver.get(website)
			except BaseException as e:
				logger.write("\n[ERROR] main()::ad-crawler: {}\nException occurred while getting the domain: {} in Iteration: {} | {}.".format(str(traceback.format_exc()), hb_domain, iteration, profile))
				try:
					driver.quit()
					proxy.close()
					server.stop()
					killBrowermobproxyInstances()
				except:
					print("\n[ERROR] main()::Webdriver-Intitialization: {}".format(str(traceback.format_exc())))
					logger.write("\n[ERROR] main()::Webdriver-Intitialization: {} for domain: {} in Iteration: {}| {}".format(str(traceback.format_exc()), hb_domain, iteration, profile))
					continue
				print("\nChromedriver successfully loaded!")
				continue
			# Wait for page to completely load
			sleep(10)
			print("Visiting and loading webpage ...")
			logger.write("\nVisiting and loading webpage ...")
	
	
			# Read custom popup handling rules
			f = open(os.path.join(ROOT_DIRECTORY, "data", "custom-popup-xpaths.txt"), "r")
			prules = f.read().split("\n")
			f.close()
			prule_dict = {prule.split(" | ")[0]: list(prule.split(" | ")[1:]) for prule in prules}
	
	
			cpm = CustomPopupManager(hb_domain, prule_dict)
			cpm.managePopups(driver)
	
	
			cpm.acceptMissedConsents(driver)
			logger.write("\nPopup-Consent-1 handled!")
			exploreFullPage(driver)
			logger.write("\nWebpage explored fully.")
			cpm.acceptMissedConsents(driver)
	
	
			cpm.managePopups(driver)
			logger.write("\nPopup-Consent-2 handled!")
	
			
			# Read filterlist rules
			f = open(os.path.join(ROOT_DIRECTORY, "data", "EasyList", "easylist.txt"), "r")
			rules = f.read().split("\n")
			f.close()
			rules = [rule[2:] for rule in rules[18:] if rule.startswith("##")]
	
	
			# Save DOM of the webpage
			try:
				dom_filepath = os.path.join(experimental_path, str(hb_domain)+"_"+str(iteration)+"_DOM.html")
				fdom = codecs.open(dom_filepath, "w", "utf−8")
				fdom.write(driver.page_source)
				fdom.close()
				logger.write("\nDOM saved.")
				print("DOM saved")
			except BaseException as e:
				print("\n[ERROR] DOM-Capture: {}".format(str(traceback.format_exc())))
				logger.write("\n[ERROR] main()::DOM-Capture: {} for domain: {} in iteration: {}| {}".format(str(traceback.format_exc()), hb_domain, iteration, profile))
				pass
	
	
			# Perform bid collection
			bid_file_path = os.path.join(experimental_path, str(hb_domain)+"_"+str(iteration)+"_bids.json")
			bid_object = BidCollector(profile, hb_domain, hb_rank, bid_file_path)
			bid_object.collectBids(driver, logger)
			print("Bid data collected")
			
			
			# Take fullpage screenshot of the webpage
			screenshot_output_path = os.path.join(experimental_path, str(hb_domain)+"_"+str(iteration)+"_ss-before.png")
			ss_object = FullPageScreenshotCollector(profile, hb_domain, hb_rank, screenshot_output_path)
			ss_object.captureFullScreenshot(driver, logger)
			logger.write("\nFull page screnshot successfully captured.")
			try:
				driver.execute_script("window.scrollTo(0, 0);")
			except:
				pass
			sleep(10)
			print("Fullpage screenshot of the webpage captured")
	
			
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
			screenshot_output_path = os.path.join(experimental_path, str(hb_domain)+"_"+str(iteration)+"_ss-after.png")
			ss_object = FullPageScreenshotCollector(profile, hb_domain, hb_rank, screenshot_output_path)
			status = ss_object.captureFullScreenshot(driver, logger)
			if status:
				logger.write("\nFull page screnshot successfully captured.")
			else:
				logger.write("\n[ERROR] main()::FullPageScreenshotCollector: {}\nIssue in capturing full page screenshot for {} in Iteration: {} | {}.".format(str(traceback.format_exc()), hb_domain, iteration, profile))
			# Move to the top and wait for dynamically updated ads to completely load
			try:
				driver.execute_script("window.scrollTo(0, 0);")
			except:
				pass
			print("Fullpage screenshot of the webpage captured")
	
	
			# Complete HAR Collection and save .har file
			try:
				with open(har_filepath, 'w') as fhar:
					json.dump(proxy.har, fhar, indent=4)
				fhar.close()
				logger.write("\nHAR dump saved for domain: {} in Iteration: {} | {}".format(hb_domain, iteration, profile))
			except BaseException as error:
				logger.write("\n[ERROR] main()::HarWriter: {}\nException occured while dumping the HAR for domain: {} in Iteration: {} | {}".format(str(traceback.format_exc()), hb_domain, iteration, profile))
				pass
			print("Network traffic saved")
	
	
			end_time = time.time()
			total_time = end_time - start_time
			print("Total time to crawl domain: {} in Iteration: {} is {}".format(hb_domain, iteration, total_time))
			logger.write("\nTotal time to crawl domain: {} in Iteration: {} is {}\n".format(hb_domain, iteration, total_time))
	
	
			proxy.close()
			server.stop()
			driver.quit()
			killBrowermobproxyInstances()
	
			# End



if __name__ == "__main__":

	args = parseArguments()
	main(args)

