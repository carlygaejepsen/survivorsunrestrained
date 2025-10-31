from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
import time
from threading import Thread, Event
import json
from datetime import datetime
import os
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

app = Flask(__name__)
CORS(app)

# Google Places API key - optional, only for on-demand enhancement
GOOGLE_PLACES_API_KEY = os.environ.get('GOOGLE_PLACES_API_KEY', '')

# Global state for tracking scraping progress
scraping_state = {
    'is_scraping': False,
    'current': 0,
    'total': 0,
    'status': '',
    'data': [],
    'stop_event': Event()
}


class NominatimGeocoder:
    """Free geocoding using Nominatim (OpenStreetMap)"""
    
    def __init__(self):
        self.geolocator = Nominatim(user_agent="food_pantry_scraper/1.0")
    
    def geocode_address(self, address, city, state, zip_code):
        """Get coordinates from address - FREE!"""
        try:
            # Build full address
            full_address = f"{address}, {city}, {state} {zip_code}, USA"
            
            # Geocode with timeout
            location = self.geolocator.geocode(full_address, timeout=10)
            
            if location:
                return {
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'geocoded_address': location.address
                }
            
            # Try without street address if first attempt fails
            fallback_address = f"{city}, {state} {zip_code}, USA"
            location = self.geolocator.geocode(fallback_address, timeout=10)
            
            if location:
                return {
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'geocoded_address': location.address,
                    'note': 'Geocoded to city center (exact address not found)'
                }
            
            return None
            
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Geocoding error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected geocoding error: {e}")
            return None

class GooglePlacesEnhancer:
    """Enhance pantry data with Google Places API"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://maps.googleapis.com/maps/api/place"
    
    def search_place(self, name, address, city, state):
        """Search for a place and get enhanced data"""
        if not self.api_key:
            return None
        
        try:
            # Build search query
            query = f"{name} {address} {city} {state}"
            
            # Text search
            search_url = f"{self.base_url}/textsearch/json"
            params = {
                'query': query,
                'key': self.api_key
            }
            
            response = requests.get(search_url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] == 'OK' and len(data['results']) > 0:
                place = data['results'][0]
                
                # Get detailed info
                place_id = place['place_id']
                details_url = f"{self.base_url}/details/json"
                details_params = {
                    'place_id': place_id,
                    'fields': 'name,formatted_address,formatted_phone_number,website,opening_hours,geometry,url',
                    'key': self.api_key
                }
                
                details_response = requests.get(details_url, params=details_params, timeout=10)
                details_data = details_response.json()
                
                if details_data['status'] == 'OK':
                    result = details_data['result']
                    return {
                        'google_place_id': place_id,
                        'google_name': result.get('name'),
                        'google_address': result.get('formatted_address'),
                        'google_phone': result.get('formatted_phone_number'),
                        'google_website': result.get('website'),
                        'google_maps_url': result.get('url'),
                        'latitude': result.get('geometry', {}).get('location', {}).get('lat'),
                        'longitude': result.get('geometry', {}).get('location', {}).get('lng'),
                        'google_hours': result.get('opening_hours', {}).get('weekday_text', [])
                    }
            
            return None
        except Exception as e:
            print(f"Google Places API error: {e}")
            return None
    
    def enhance_pantry_data(self, pantry):
        """Add Google Places data to existing pantry data"""
        if not pantry.get('name') or not pantry.get('city'):
            return pantry
        
        google_data = self.search_place(
            pantry.get('name', ''),
            pantry.get('address', ''),
            pantry.get('city', ''),
            pantry.get('state', '')
        )
        
        if google_data:
            # Merge data, preferring more complete information
            if not pantry.get('phone') and google_data.get('google_phone'):
                pantry['phone'] = google_data['google_phone']
            
            if not pantry.get('website') and google_data.get('google_website'):
                pantry['website'] = google_data['google_website']
            
            if not pantry.get('hours') and google_data.get('google_hours'):
                pantry['hours'] = '\n'.join(google_data['google_hours'])
            
            # Add coordinates and Google-specific data
            pantry.update({
                'latitude': google_data.get('latitude'),
                'longitude': google_data.get('longitude'),
                'google_place_id': google_data.get('google_place_id'),
                'google_maps_url': google_data.get('google_maps_url')
            })
        
        return pantry


class FoodPantriesScraper:
    def __init__(self):
        self.base_url = "https://www.foodpantries.org"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_state_urls(self):
        """Get all state listing URLs"""
        try:
            response = self.session.get(self.base_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            states = {}
            for link in soup.find_all('a', href=re.compile(r'/st/')):
                state_name = link.text.strip()
                href = link['href']
                # Handle both relative and absolute URLs
                if href.startswith('http'):
                    state_url = href
                else:
                    state_url = self.base_url + href
                match = re.search(r'\((\d+)\)', state_name)
                count = int(match.group(1)) if match else 0
                clean_name = re.sub(r'\(\d+\)', '', state_name).strip()
                states[clean_name] = {'url': state_url, 'count': count}
            
            return states
        except Exception as e:
            print(f"Error fetching states: {e}")
            return {}
    
    def scrape_state_page(self, state_url):
        """Get all pantry URLs from a state page - goes through city pages"""
        try:
            print(f"Fetching state page: {state_url}")
            response = self.session.get(state_url, timeout=10)
            print(f"Status code: {response.status_code}")
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # First, get all city URLs
            city_urls = []
            all_links = soup.find_all('a', href=True)
            print(f"Found {len(all_links)} total links on page")
            
            for link in all_links:
                href = link.get('href', '')
                # City pages are like /ci/city-name
                if '/ci/' in href:
                    if href.startswith('http'):
                        city_url = href
                    else:
                        city_url = self.base_url + href
                    if city_url not in city_urls:
                        city_urls.append(city_url)
            
            print(f"Found {len(city_urls)} cities")
            
            # Now get pantries from each city
            pantry_urls = []
            for i, city_url in enumerate(city_urls):
                print(f"Fetching city {i+1}/{len(city_urls)}: {city_url}")
                try:
                    city_response = self.session.get(city_url, timeout=10)
                    city_soup = BeautifulSoup(city_response.content, 'html.parser')
                    
                    for link in city_soup.find_all('a', href=True):
                        href = link.get('href', '')
                        # Pantry detail pages are like /li/pantry-name
                        if '/li/' in href:
                            if href.startswith('http'):
                                pantry_url = href
                            else:
                                pantry_url = self.base_url + href
                            if pantry_url not in pantry_urls:
                                pantry_urls.append(pantry_url)
                    
                    time.sleep(0.3)  # Be polite between city requests
                except Exception as e:
                    print(f"Error fetching city {city_url}: {e}")
            
            print(f"Found {len(pantry_urls)} total pantry URLs")
            return pantry_urls
        except Exception as e:
            print(f"Error scraping state page: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def scrape_pantry_details(self, pantry_url):
        """Scrape details from a single pantry page"""
        try:
            response = self.session.get(pantry_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            page_text = soup.get_text()
            
            data = {
                'url': pantry_url,
                'name': None,
                'address': None,
                'city': None,
                'state': None,
                'zip': None,
                'phone': None,
                'fax': None,
                'email': None,
                'website': None,
                'hours': None,
                'description': None,
                'requirements': None,
                'scraped_at': datetime.now().isoformat()
            }
            
            # Extract name - it's the first large heading in the page
            # Usually appears before "Contact Information"
            name_match = re.search(r'^([^\n]+)\s*Contact Information', page_text, re.MULTILINE)
            if name_match:
                data['name'] = name_match.group(1).strip()
            
            # Extract Contact Information section
            # Pattern: Contact Information<address><city, state - zip><phone><fax>
            contact_section = re.search(
                r'Contact Information\s*(.+?)\s*([^,\n]+),\s*([A-Z]{2})\s*-\s*(\d{5})',
                page_text,
                re.DOTALL
            )
            if contact_section:
                data['address'] = contact_section.group(1).strip()
                data['city'] = contact_section.group(2).strip()
                data['state'] = contact_section.group(3)
                data['zip'] = contact_section.group(4)
            
            # Extract phone - look for "Phone:" label
            phone_match = re.search(r'Phone:\s*(\([0-9]{3}\)\s*[0-9]{3}-[0-9]{4})', page_text)
            if phone_match:
                data['phone'] = phone_match.group(1).strip()
            
            # Extract fax
            fax_match = re.search(r'Fax Number:\s*(\([0-9]{3}\)\s*[0-9]{3}-[0-9]{4})', page_text)
            if fax_match:
                data['fax'] = fax_match.group(1).strip()
            
            # Extract hours - various patterns on these pages
            # Look for common patterns like "Hours:", "Pantry Hours:", etc.
            hours_patterns = [
                r'(?:Pantry|Food Pantry|Distribution)?\s*Hours?:\s*([^\n]+(?:\n(?![A-Z][a-z]+:)[^\n]+)*)',
                r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)[^\n]*(?:\d{1,2}:\d{2}[ap]m)[^\n]*'
            ]
            
            for pattern in hours_patterns:
                hours_match = re.search(pattern, page_text, re.IGNORECASE)
                if hours_match:
                    hours_text = hours_match.group(0 if 'day' in pattern.lower() else 1).strip()
                    # Clean up and limit length
                    if len(hours_text) < 500:
                        data['hours'] = hours_text
                        break
            
            # Extract requirements
            req_match = re.search(
                r'Requirements?:\s*([^\n]+(?:\n(?![A-Z][a-z]+:)[^\n]+)*)',
                page_text,
                re.IGNORECASE
            )
            if req_match:
                req_text = req_match.group(1).strip()
                if len(req_text) < 500:
                    data['requirements'] = req_text
            
            # Extract email and website from actual links
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if 'mailto:' in href:
                    email = href.replace('mailto:', '').strip()
                    if '@' in email and not data['email']:
                        data['email'] = email
                elif href.startswith('http') and 'foodpantries.org' not in href:
                    # External website link
                    if not data['website'] or len(href) < len(data['website']):
                        data['website'] = href
            
            return data
            
        except Exception as e:
            print(f"Error scraping {pantry_url}: {e}")
            import traceback
            traceback.print_exc()
            return None


def scrape_in_background(state, limit=None, geocode=True):
    """Run scraping in background thread"""
    global scraping_state
    
    scraper = FoodPantriesScraper()
    geocoder = NominatimGeocoder() if geocode else None
    scraping_state['stop_event'].clear()
    
    try:
        # Get state URL
        scraping_state['status'] = 'Fetching state information...'
        states = scraper.get_state_urls()
        
        if state not in states:
            scraping_state['status'] = f'State "{state}" not found'
            scraping_state['is_scraping'] = False
            return
        
        # Get pantry URLs
        scraping_state['status'] = f'Finding pantries in {state}...'
        state_url = states[state]['url']
        pantry_urls = scraper.scrape_state_page(state_url)
        
        if not pantry_urls:
            scraping_state['status'] = 'No pantries found'
            scraping_state['is_scraping'] = False
            return
        
        # Apply limit if specified
        if limit:
            pantry_urls = pantry_urls[:limit]
        
        scraping_state['total'] = len(pantry_urls)
        scraping_state['data'] = []
        
        # Scrape each pantry
        for i, url in enumerate(pantry_urls):
            # Check if stop requested
            if scraping_state['stop_event'].is_set():
                scraping_state['status'] = 'Stopped by user'
                break
            
            scraping_state['current'] = i + 1
            scraping_state['status'] = f'Scraping pantry {i + 1} of {len(pantry_urls)}...'
            
            data = scraper.scrape_pantry_details(url)
            if data:
                # Add free geocoding if enabled
                if geocoder and data.get('address') and data.get('city') and data.get('state'):
                    scraping_state['status'] = f'Geocoding {i + 1}/{len(pantry_urls)} (FREE)...'
                    geo_data = geocoder.geocode_address(
                        data.get('address', ''),
                        data.get('city', ''),
                        data.get('state', ''),
                        data.get('zip', '')
                    )
                    if geo_data:
                        data.update(geo_data)
                    time.sleep(1)  # Nominatim rate limit: 1 request per second
                
                scraping_state['data'].append(data)
            
            # Be polite to foodpantries.org
            time.sleep(0.5)
        
        if not scraping_state['stop_event'].is_set():
            scraping_state['status'] = f'Completed! Scraped {len(scraping_state["data"])} pantries'
        
    except Exception as e:
        scraping_state['status'] = f'Error: {str(e)}'
        import traceback
        traceback.print_exc()
    finally:
        scraping_state['is_scraping'] = False


@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('.', 'index.html')

@app.route('/api/states', methods=['GET'])
def get_states():
    """Get list of all available states"""
    try:
        scraper = FoodPantriesScraper()
        states = scraper.get_state_urls()
        return jsonify({
            'success': True,
            'states': states
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/scrape', methods=['POST'])
def start_scrape():
    """Start scraping a state"""
    global scraping_state
    
    if scraping_state['is_scraping']:
        return jsonify({
            'success': False,
            'error': 'Scraping already in progress'
        }), 400
    
    data = request.get_json()
    state = data.get('state')
    limit = data.get('limit')
    geocode = data.get('geocode', True)  # Default: enable free geocoding
    
    if not state:
        return jsonify({
            'success': False,
            'error': 'State is required'
        }), 400
    
    # Reset state
    scraping_state['is_scraping'] = True
    scraping_state['current'] = 0
    scraping_state['total'] = 0
    scraping_state['status'] = 'Starting...'
    scraping_state['data'] = []
    
    # Start scraping in background
    thread = Thread(target=scrape_in_background, args=(state, limit, geocode))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': 'Scraping started'
    })


@app.route('/api/enhance', methods=['POST'])
def enhance_pantry():
    """On-demand Google Places enhancement for a single pantry"""
    if not GOOGLE_PLACES_API_KEY:
        return jsonify({
            'success': False,
            'error': 'Google Places API key not configured'
        }), 400
    
    data = request.get_json()
    pantry = data.get('pantry')
    
    if not pantry:
        return jsonify({
            'success': False,
            'error': 'Pantry data required'
        }), 400
    
    try:
        enhancer = GooglePlacesEnhancer(GOOGLE_PLACES_API_KEY)
        enhanced = enhancer.enhance_pantry_data(pantry)
        
        return jsonify({
            'success': True,
            'pantry': enhanced
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current scraping status"""
    return jsonify({
        'is_scraping': scraping_state['is_scraping'],
        'current': scraping_state['current'],
        'total': scraping_state['total'],
        'status': scraping_state['status'],
        'data_count': len(scraping_state['data'])
    })

@app.route('/api/results', methods=['GET'])
def get_results():
    """Get scraped results"""
    return jsonify({
        'success': True,
        'count': len(scraping_state['data']),
        'data': scraping_state['data']
    })

@app.route('/api/stop', methods=['POST'])
def stop_scrape():
    """Stop the current scraping operation"""
    scraping_state['stop_event'].set()
    return jsonify({
        'success': True,
        'message': 'Stop signal sent'
    })

@app.route('/api/download', methods=['GET'])
def download_results():
    """Download results as JSON file"""
    from flask import Response
    
    json_data = json.dumps(scraping_state['data'], indent=2)
    
    return Response(
        json_data,
        mimetype='application/json',
        headers={
            'Content-Disposition': f'attachment;filename=food_pantries_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        }
    )

if __name__ == '__main__':
    print("="*50)
    print("Food Pantry Scraper Backend")
    print("="*50)
    print("\nServer starting on http://localhost:5000")
    print("\nAvailable endpoints:")
    print("  GET  /api/states   - Get list of states")
    print("  POST /api/scrape   - Start scraping")
    print("  GET  /api/status   - Get scraping status")
    print("  GET  /api/results  - Get results")
    print("  POST /api/stop     - Stop scraping")
    print("  GET  /api/download - Download JSON file")
    print("\n" + "="*50)
    
    app.run(debug=True, port=5000)