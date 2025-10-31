import requests
from bs4 import BeautifulSoup
import json
import time
import re
from typing import List, Dict, Set, Optional
from dataclasses import dataclass, asdict
import hashlib
from urllib.parse import urljoin

@dataclass
class Pantry:
    """Data class for food pantry information"""
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    hours: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    source_url: Optional[str] = None
    source_site: Optional[str] = None
    
    def get_fingerprint(self) -> str:
        """Generate a unique fingerprint for duplicate detection"""
        name_norm = self.name.lower().strip() if self.name else ""
        addr_norm = self.address.lower().strip() if self.address else ""
        phone_norm = re.sub(r'\D', '', self.phone) if self.phone else ""
        
        fingerprint_str = f"{name_norm}|{addr_norm}|{phone_norm}|{self.zip or ''}"
        return hashlib.md5(fingerprint_str.encode()).hexdigest()
    
    def merge_with(self, other: 'Pantry') -> 'Pantry':
        """Merge data from another pantry entry, keeping most complete info"""
        merged_data = {}
        for field in self.__dataclass_fields__:
            self_val = getattr(self, field)
            other_val = getattr(other, field)
            
            if self_val and other_val:
                merged_data[field] = self_val if len(str(self_val)) >= len(str(other_val)) else other_val
            else:
                merged_data[field] = self_val or other_val
        
        return Pantry(**merged_data)


class DeduplicatedPantryDatabase:
    """Manages pantry data with automatic deduplication"""
    
    def __init__(self):
        self.pantries: Dict[str, Pantry] = {}
        self.fingerprints: Set[str] = set()
    
    def add_pantry(self, pantry: Pantry) -> bool:
        """Add pantry, merging with existing if duplicate found. Returns True if new."""
        fingerprint = pantry.get_fingerprint()
        
        if fingerprint in self.fingerprints:
            existing = self.pantries[fingerprint]
            self.pantries[fingerprint] = existing.merge_with(pantry)
            return False
        else:
            self.pantries[fingerprint] = pantry
            self.fingerprints.add(fingerprint)
            return True
    
    def get_all(self) -> List[Dict]:
        """Get all pantries as list of dicts"""
        return [asdict(p) for p in self.pantries.values()]
    
    def get_stats(self) -> Dict:
        """Get statistics about the database"""
        pantries = list(self.pantries.values())
        return {
            'total': len(pantries),
            'with_website': sum(1 for p in pantries if p.website),
            'with_phone': sum(1 for p in pantries if p.phone),
            'with_email': sum(1 for p in pantries if p.email),
            'with_hours': sum(1 for p in pantries if p.hours),
            'sources': {}
        }


class FoodPantriesScraper:
    """Scraper for foodpantries.org"""
    
    def __init__(self):
        self.base_url = "https://www.foodpantries.org"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_state_urls(self) -> Dict[str, Dict]:
        """Get all state listing URLs"""
        try:
            response = self.session.get(self.base_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            states = {}
            for link in soup.find_all('a', href=re.compile(r'/st/')):
                state_name = link.text.strip()
                href = link['href']
                state_url = href if href.startswith('http') else self.base_url + href
                match = re.search(r'\((\d+)\)', state_name)
                count = int(match.group(1)) if match else 0
                clean_name = re.sub(r'\(\d+\)', '', state_name).strip()
                states[clean_name] = {'url': state_url, 'count': count}
            
            return states
        except Exception as e:
            print(f"Error fetching states: {e}")
            return {}
    
    def scrape_state_page(self, state_url: str) -> List[str]:
        """Get all pantry URLs from a state page (via city pages)"""
        try:
            response = self.session.get(state_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            city_urls = []
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if '/ci/' in href:
                    city_url = href if href.startswith('http') else self.base_url + href
                    if city_url not in city_urls:
                        city_urls.append(city_url)
            
            pantry_urls = []
            for city_url in city_urls:
                try:
                    city_response = self.session.get(city_url, timeout=10)
                    city_soup = BeautifulSoup(city_response.content, 'html.parser')
                    
                    for link in city_soup.find_all('a', href=True):
                        href = link.get('href', '')
                        if '/li/' in href:
                            pantry_url = href if href.startswith('http') else self.base_url + href
                            if pantry_url not in pantry_urls:
                                pantry_urls.append(pantry_url)
                    
                    time.sleep(0.3)
                except Exception as e:
                    print(f"Error fetching city {city_url}: {e}")
            
            return pantry_urls
        except Exception as e:
            print(f"Error scraping state page: {e}")
            return []
    
    def scrape_pantry_details(self, pantry_url: str) -> Optional[Pantry]:
        """Scrape details from a single pantry page"""
        try:
            response = self.session.get(pantry_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            page_text = soup.get_text()
            
            # Extract name
            name = None
            name_match = re.search(r'^([^\n]+)\s*Contact Information', page_text, re.MULTILINE)
            if name_match:
                name = name_match.group(1).strip()
            
            if not name:
                return None
            
            # Extract contact info
            address = city = state = zip_code = None
            contact_section = re.search(
                r'Contact Information\s*(.+?)\s*([^,\n]+),\s*([A-Z]{2})\s*-\s*(\d{5})',
                page_text, re.DOTALL
            )
            if contact_section:
                address = contact_section.group(1).strip()
                city = contact_section.group(2).strip()
                state = contact_section.group(3)
                zip_code = contact_section.group(4)
            
            # Extract phone
            phone = None
            phone_match = re.search(r'Phone:\s*(\([0-9]{3}\)\s*[0-9]{3}-[0-9]{4})', page_text)
            if phone_match:
                phone = phone_match.group(1).strip()
            
            # Extract fax
            fax = None
            fax_match = re.search(r'Fax Number:\s*(\([0-9]{3}\)\s*[0-9]{3}-[0-9]{4})', page_text)
            if fax_match:
                fax = fax_match.group(1).strip()
            
            # Extract hours
            hours = None
            hours_patterns = [
                r'(?:Pantry|Food Pantry|Distribution)?\s*Hours?:\s*([^\n]+(?:\n(?![A-Z][a-z]+:)[^\n]+)*)',
            ]
            for pattern in hours_patterns:
                hours_match = re.search(pattern, page_text, re.IGNORECASE)
                if hours_match:
                    hours_text = hours_match.group(1).strip()
                    if len(hours_text) < 500:
                        hours = hours_text
                        break
            
            # Extract requirements
            requirements = None
            req_match = re.search(
                r'Requirements?:\s*([^\n]+(?:\n(?![A-Z][a-z]+:)[^\n]+)*)',
                page_text, re.IGNORECASE
            )
            if req_match:
                req_text = req_match.group(1).strip()
                if len(req_text) < 500:
                    requirements = req_text
            
            # Extract email and website - FIXED
            email = None
            website = None
            
            for link in soup.find_all('a', href=True):
                href = link.get('href', '').strip()
                
                if 'mailto:' in href:
                    email_addr = href.replace('mailto:', '').strip()
                    if '@' in email_addr and not email:
                        email = email_addr
                
                elif href.startswith('http') and 'foodpantries.org' not in href:
                    link_text = link.get_text().strip().lower()
                    parent_text = link.parent.get_text().strip() if link.parent else ""
                    
                    if any(indicator in link_text for indicator in ['website', 'visit', 'home', 'more info']):
                        website = href
                        break
                    elif 'website' in parent_text.lower():
                        website = href
                        break
            
            return Pantry(
                name=name,
                address=address,
                city=city,
                state=state,
                zip=zip_code,
                phone=phone,
                fax=fax,
                email=email,
                website=website,
                hours=hours,
                requirements=requirements,
                source_url=pantry_url,
                source_site='foodpantries.org'
            )
            
        except Exception as e:
            print(f"Error scraping {pantry_url}: {e}")
            return None


class Network211Scraper:
    """Scraper for 211 sites using CommunityOS platform"""
    
    COMMUNITYOS_SITES = {
        'wisconsin': 'https://211wisconsin.communityos.org',
        'pennsylvania': 'https://pa211.communityos.org',
        'indiana': 'https://in211.communityos.org',
        'ventura': 'https://211ventura.org',
        'sacramento': 'https://211sacramento.org',
    }
    
    def __init__(self, region: str = 'wisconsin'):
        if region.lower() not in self.COMMUNITYOS_SITES:
            raise ValueError(f"Unknown region. Available: {list(self.COMMUNITYOS_SITES.keys())}")
        
        self.base_url = self.COMMUNITYOS_SITES[region.lower()]
        self.region = region
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def search_food_pantries(self, limit: int = None) -> List[str]:
        """Search for food pantries and return detail URLs"""
        try:
            # Try multiple search approaches
            pantry_urls = []
            
            # Approach 1: Taxonomy search (food pantry taxonomy)
            search_url = f"{self.base_url}/cm/search"
            params = {
                'q': 'food pantry',
                'category': 'food'
            }
            
            response = self.session.get(search_url, params=params, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract pantry links
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                
                if any(pattern in href for pattern in [
                    '211searchprofile',
                    '/zf/profile',
                    '/cm/profile',
                    '/service/'
                ]):
                    full_url = urljoin(self.base_url, href)
                    if full_url not in pantry_urls:
                        pantry_urls.append(full_url)
            
            # Look for result cards with data attributes
            for card in soup.find_all(['div', 'article'], class_=re.compile(r'result|card|listing')):
                for link in card.find_all('a', href=True):
                    href = link.get('href', '')
                    if '/profile' in href or '/service' in href:
                        full_url = urljoin(self.base_url, href)
                        if full_url not in pantry_urls:
                            pantry_urls.append(full_url)
            
            if limit:
                pantry_urls = pantry_urls[:limit]
            
            return pantry_urls
            
        except Exception as e:
            print(f"Error searching {self.region}: {e}")
            return []
    
    def scrape_pantry_detail(self, url: str) -> Optional[Pantry]:
        """Scrape details from a pantry profile page"""
        try:
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            page_text = soup.get_text(separator='\n')
            
            # Extract name
            name = None
            h1 = soup.find('h1')
            if h1:
                name = h1.get_text().strip()
            
            if not name:
                title = soup.find('title')
                if title:
                    name = title.get_text().strip().split('|')[0].strip()
            
            if not name:
                return None
            
            # Extract address
            address = city = state = zip_code = None
            addr_pattern = r'([^\n]+)\n([^,\n]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)'
            addr_match = re.search(addr_pattern, page_text)
            if addr_match:
                address = addr_match.group(1).strip()
                city = addr_match.group(2).strip()
                state = addr_match.group(3)
                zip_code = addr_match.group(4)
            
            # Extract phone
            phone = None
            phone_patterns = [
                r'Phone:?\s*(\(\d{3}\)\s*\d{3}-\d{4})',
                r'Phone:?\s*(\d{3}-\d{3}-\d{4})',
                r'Tel:?\s*(\(\d{3}\)\s*\d{3}-\d{4})',
            ]
            for pattern in phone_patterns:
                phone_match = re.search(pattern, page_text, re.IGNORECASE)
                if phone_match:
                    phone = phone_match.group(1).strip()
                    break
            
            # Extract email
            email = None
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', page_text)
            if email_match:
                email = email_match.group(0)
            
            # Extract website
            website = None
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if href.startswith('http') and 'communityos.org' not in href and '211' not in href:
                    link_text = link.get_text().strip().lower()
                    if 'website' in link_text or 'visit' in link_text or 'home' in link_text:
                        website = href
                        break
            
            # Extract hours
            hours = None
            hours_patterns = [
                r'Hours?:?\s*([^\n]+(?:\n(?![A-Z][a-z]+:)[^\n]+){0,5})',
                r'Open:?\s*([^\n]+(?:\n(?![A-Z][a-z]+:)[^\n]+){0,3})',
            ]
            for pattern in hours_patterns:
                hours_match = re.search(pattern, page_text, re.IGNORECASE)
                if hours_match:
                    hours_text = hours_match.group(1).strip()
                    if len(hours_text) < 500:
                        hours = hours_text
                        break
            
            # Extract description
            description = None
            desc_patterns = [
                r'Description:?\s*([^\n]+(?:\n(?![A-Z][a-z]+:)[^\n]+){0,10})',
                r'Service Description:?\s*([^\n]+(?:\n(?![A-Z][a-z]+:)[^\n]+){0,10})',
            ]
            for pattern in desc_patterns:
                desc_match = re.search(pattern, page_text, re.IGNORECASE)
                if desc_match:
                    desc_text = desc_match.group(1).strip()
                    if len(desc_text) < 1000:
                        description = desc_text
                        break
            
            # Extract requirements
            requirements = None
            req_patterns = [
                r'Eligibility:?\s*([^\n]+(?:\n(?![A-Z][a-z]+:)[^\n]+){0,5})',
                r'Requirements?:?\s*([^\n]+(?:\n(?![A-Z][a-z]+:)[^\n]+){0,5})',
            ]
            for pattern in req_patterns:
                req_match = re.search(pattern, page_text, re.IGNORECASE)
                if req_match:
                    req_text = req_match.group(1).strip()
                    if len(req_text) < 500:
                        requirements = req_text
                        break
            
            return Pantry(
                name=name,
                address=address,
                city=city,
                state=state,
                zip=zip_code,
                phone=phone,
                email=email,
                website=website,
                hours=hours,
                description=description,
                requirements=requirements,
                source_url=url,
                source_site=f'211 {self.region}'
            )
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None


class MultiSourceScraper:
    """Coordinates scraping from multiple sources with deduplication"""
    
    def __init__(self):
        self.database = DeduplicatedPantryDatabase()
        self.source_counts = {}
    
    def scrape_state(self, state_name: str, limit: int = None, 
                    sources: List[str] = None):
        """Scrape from multiple sources for a state"""
        if sources is None:
            sources = ['foodpantries.org']
        
        for source in sources:
            print(f"\n{'='*60}")
            print(f"Scraping {source} for {state_name}")
            print(f"{'='*60}")
            
            if source == 'foodpantries.org':
                self._scrape_foodpantries(state_name, limit)
            
            elif source.startswith('211-'):
                region = source.replace('211-', '')
                self._scrape_211(region, limit)
            
            else:
                print(f"Unknown source: {source}")
    
    def _scrape_foodpantries(self, state_name: str, limit: int = None):
        """Scrape foodpantries.org"""
        try:
            scraper = FoodPantriesScraper()
            states = scraper.get_state_urls()
            
            if state_name not in states:
                print(f"State '{state_name}' not found in foodpantries.org")
                return
            
            state_url = states[state_name]['url']
            pantry_urls = scraper.scrape_state_page(state_url)
            print(f"Found {len(pantry_urls)} pantries")
            
            if limit:
                pantry_urls = pantry_urls[:limit]
            
            for i, url in enumerate(pantry_urls, 1):
                print(f"Scraping {i}/{len(pantry_urls)}")
                pantry = scraper.scrape_pantry_details(url)
                
                if pantry:
                    is_new = self.database.add_pantry(pantry)
                    status = "✓ NEW" if is_new else "⊙ MERGED"
                    print(f"  {status}: {pantry.name}")
                    
                    source = pantry.source_site
                    self.source_counts[source] = self.source_counts.get(source, 0) + 1
                
                time.sleep(0.5)
                
        except Exception as e:
            print(f"Error scraping foodpantries.org: {e}")
    
    def _scrape_211(self, region: str, limit: int = None):
        """Scrape 211 region"""
        try:
            scraper = Network211Scraper(region)
            pantry_urls = scraper.search_food_pantries(limit=limit)
            print(f"Found {len(pantry_urls)} pantries")
            
            for i, url in enumerate(pantry_urls, 1):
                print(f"Scraping {i}/{len(pantry_urls)}")
                pantry = scraper.scrape_pantry_detail(url)
                
                if pantry:
                    is_new = self.database.add_pantry(pantry)
                    status = "✓ NEW" if is_new else "⊙ MERGED"
                    print(f"  {status}: {pantry.name}")
                    
                    source = pantry.source_site
                    self.source_counts[source] = self.source_counts.get(source, 0) + 1
                
                time.sleep(0.5)
                
        except Exception as e:
            print(f"Error scraping 211 {region}: {e}")
    
    def get_results(self) -> Dict:
        """Get all results with statistics"""
        stats = self.database.get_stats()
        stats['sources'] = self.source_counts
        
        return {
            'pantries': self.database.get_all(),
            'stats': stats
        }
    
    def save_results(self, filename: str):
        """Save results to JSON file"""
        results = self.get_results()
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Saved {results['stats']['total']} unique pantries to {filename}")


# Example usage
if __name__ == "__main__":
    print("="*60)
    print("Multi-Source Food Pantry Scraper")
    print("="*60)
    print("\nAvailable sources:")
    print("  - foodpantries.org (national)")
    print("  - 211-wisconsin")
    print("  - 211-pennsylvania")
    print("  - 211-indiana")
    print("  - 211-ventura")
    print("  - 211-sacramento")
    
    # Example: Scrape from multiple sources
    scraper = MultiSourceScraper()
    
    # Scrape Wisconsin from both sources
    print("\n" + "="*60)
    print("Scraping Wisconsin (limited to 5 each for testing)")
    print("="*60)
    
    scraper.scrape_state('Wisconsin', limit=5, sources=['foodpantries.org'])
    scraper.scrape_state('Wisconsin', limit=5, sources=['211-wisconsin'])
    
    # Get and display results
    results = scraper.get_results()
    
    print("\n" + "="*60)
    print("SCRAPING COMPLETE")
    print("="*60)
    print(f"\nStatistics:")
    for key, value in results['stats'].items():
        print(f"  {key}: {value}")
    
    # Save to file
    scraper.save_results('wisconsin_pantries_multi_source.json')
    
    # Display sample
    if results['pantries']:
        print("\nSample pantry data:")
        print(json.dumps(results['pantries'][0], indent=2))