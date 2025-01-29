import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import tldextract
import re
from colorama import Fore, Style, init

# Initialize colorama for coloring terminal output
init(autoreset=True)

def get_full_domain(url):
    """Extracts the full domain (including TLD) from a URL."""
    extracted = tldextract.extract(url)
    return f"{extracted.domain}.{extracted.suffix}"

def check_link(url, source_page, link_text, headers, skip_facebook, broken_links):
    """Check if the link is broken."""
    if skip_facebook and "facebook.com" in url:
        return
    if url.startswith("javascript:"):
        return

    try:
        response = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
        status_code = response.status_code
        final_url = response.url
        
        # Ignore 403 errors and Facebook-specific 400 errors
        if status_code == 403 or ("facebook.com" in url and status_code == 400):
            return

        if not (200 <= status_code < 400):
            broken_links.append((final_url, status_code, source_page, link_text))
            color = Fore.RED if status_code == 404 else Fore.YELLOW
            print(f"{color}[BROKEN] {final_url} (Status: {status_code})\n\t Found on: {source_page}\n\t Link text: {link_text}")
    
    except requests.RequestException:
        pass  # Suppress errors for skipped links or timeouts

def fetch_robots_txt(base_url, headers):
    """Fetch and parse the robots.txt file to extract URLs (Sitemaps and others)."""
    robots_txt_url = urljoin(base_url, '/robots.txt')
    try:
        response = requests.get(robots_txt_url, headers=headers, timeout=5)
        if response.status_code == 200:
            urls = re.findall(r"Sitemap:\s*(\S+)", response.text, re.IGNORECASE)
            urls += re.findall(r"Allow:\s*(\S+)", response.text, re.IGNORECASE)
            urls += re.findall(r"Disallow:\s*(\S+)", response.text, re.IGNORECASE)
            return urls
        else:
            return []
    except requests.RequestException:
        return []

def crawl_and_check_links(base_url):
    session = requests.Session()
    session.max_redirects = 2  # Limit to 2 redirects

    headers = {
        "Accept-Encoding": "identity; q=1",
        "Connection": "Keep-Alive",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }

    visited = set()
    links_checked = 0
    skip_facebook = False
    broken_links = []
    base_domain = get_full_domain(base_url)

    def crawl(url):
        nonlocal links_checked, skip_facebook
        if url in visited:
            return

        visited.add(url)
        links_checked += 1
        print(f"Links checked: {links_checked}", end="\r")

        try:
            response = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
            if response.status_code != 200:
                return

            soup = BeautifulSoup(response.text, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link.get("href")
                link_text = link.text.strip() or "[No text]"
                full_url = urljoin(url, href)

                link_domain = get_full_domain(full_url)
                if "facebook.com" in full_url and not skip_facebook:
                    response = requests.get(full_url, headers=headers, timeout=5, allow_redirects=True)
                    if response.status_code == 400:
                        print(f"{Fore.CYAN}Facebook link {full_url} returned 400 error. Stopping checks for Facebook links.")
                        skip_facebook = True

                if link_domain != base_domain:
                    check_link(full_url, url, link_text, headers, skip_facebook, broken_links)
                elif not href.endswith(('.jpg', '.jpeg', '.png', '.gif', '.svg', '.css', '.js', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx')) and not href.startswith(('mailto:', 'tel:', '#')): 
                    crawl(full_url) 

        except requests.RequestException:
            pass  # Suppress errors for skipped links or timeouts

    urls_from_robots = fetch_robots_txt(base_url, headers)
    if urls_from_robots:
        print(f"Found URLs in robots.txt: {urls_from_robots}")
        for url in urls_from_robots:
            full_url = urljoin(base_url, url)
            crawl(full_url)
    else:
        print(f"No relevant URLs found in robots.txt for {base_url}. Starting crawl from the base URL.")
        crawl(base_url)

    print("\nCrawl Completed.")
    print(f"Total links checked: {links_checked}")
    print(f"Total broken links found: {len(broken_links)}")

    if broken_links:
        print("\nBroken links summary:")
        for link in broken_links:
            color = Fore.RED if link[1] == 404 else Fore.YELLOW
            print(f"{color}- {link[0]} (Status: {link[1]}), Found on: {link[2]}, Link text: {link[3]}")

if __name__ == "__main__":
    target_url = input("Enter the base URL to crawl (e.g., https://example.com), Note - Please try HTTP if HTTPS shows no results: ").strip()
    if not target_url.startswith("http"):
        print("Error: Please provide a full URL starting with http or https.")
    else:
        crawl_and_check_links(target_url)
