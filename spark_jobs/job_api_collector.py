"""
Job API Collector - Fetches job postings from APIs/scrapers and streams to Kafka.

Sources:
- RemoteOK (API)
- Adzuna (API)
- JSearch (API)
- Arbeitnow (API)
- Wellfound (ethical scraping)
- HackerNews Who Is Hiring (Algolia API)

The collector supports dashboard-controlled filters persisted to
config/collection_filters.json.
"""

import json
import os
import re
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import requests
from bs4 import BeautifulSoup
from kafka import KafkaProducer


DEFAULT_FILTERS = {
    "categories": ["data science", "software engineer"],
    "regions": ["us", "remote"],
    "enabled": True,
    "refresh_interval": 10800,
    "sources": [
        "remoteok",
        "arbeitnow",
        "wellfound",
        "hackernews",
        "adzuna",
        "jsearch",
    ],
}

CATEGORY_QUERY_MAP = {
    "data science": "data scientist",
    "software engineer": "software engineer",
    "ml engineer": "machine learning engineer",
    "machine learning": "machine learning engineer",
    "data analyst": "data analyst",
    "devops engineer": "devops engineer",
    "devops": "devops engineer",
    "full stack developer": "full stack developer",
    "full stack": "full stack developer",
    "sde": "software development engineer",
}

REGION_COUNTRY_MAP = {
    "us": "us",
    "uk": "gb",
    "gb": "gb",
    "eu": "de",
    "germany": "de",
    "de": "de",
    "canada": "ca",
    "ca": "ca",
    "australia": "au",
    "au": "au",
}


class JobAPICollector:
    """Collects job postings from multiple APIs and sends to Kafka"""
    
    def __init__(self, kafka_bootstrap_servers='localhost:9092', kafka_topic='job_postings'):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.config_dir = self.base_dir / "config"
        self.filters_file = self.config_dir / "collection_filters.json"
        self.logs_dir = self.base_dir / "logs"
        self.metrics_file = self.logs_dir / "source_metrics.json"

        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.kafka_topic = kafka_topic
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        # API keys from environment variables
        self.adzuna_app_id = os.getenv('ADZUNA_APP_ID')
        self.adzuna_app_key = os.getenv('ADZUNA_APP_KEY')
        self.jsearch_api_key = os.getenv('JSEARCH_API_KEY')

        if not self.filters_file.exists():
            self._write_json(self.filters_file, DEFAULT_FILTERS)

    def _write_json(self, path: Path, payload: Dict) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def _read_json(self, path: Path) -> Dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_filters(self) -> Dict:
        """Load filters from config file, with safe defaults."""
        try:
            filters = self._read_json(self.filters_file)
        except Exception:
            filters = dict(DEFAULT_FILTERS)

        categories = [c.strip().lower() for c in filters.get("categories", []) if str(c).strip()]
        regions = [r.strip().lower() for r in filters.get("regions", []) if str(r).strip()]
        sources = [s.strip().lower() for s in filters.get("sources", []) if str(s).strip()]

        if not categories:
            categories = list(DEFAULT_FILTERS["categories"])
        if not regions:
            regions = list(DEFAULT_FILTERS["regions"])
        if not sources:
            sources = list(DEFAULT_FILTERS["sources"])

        refresh_interval = int(filters.get("refresh_interval", DEFAULT_FILTERS["refresh_interval"]))
        enabled = bool(filters.get("enabled", True))

        return {
            "categories": categories,
            "regions": regions,
            "enabled": enabled,
            "refresh_interval": max(300, refresh_interval),
            "sources": sources,
            "last_updated": filters.get("last_updated"),
        }

    def build_queries(self, categories: List[str]) -> List[str]:
        """Map categories to provider-friendly search queries."""
        queries: List[str] = []
        for category in categories:
            queries.append(CATEGORY_QUERY_MAP.get(category, category))
        # Preserve order while deduplicating.
        return list(dict.fromkeys(queries))

    def build_country_codes(self, regions: List[str]) -> List[str]:
        """Map region filters to API country codes."""
        if "global" in regions:
            return ["us", "gb", "de"]

        countries = [REGION_COUNTRY_MAP[r] for r in regions if r in REGION_COUNTRY_MAP]
        if not countries:
            countries = ["us"]
        return list(dict.fromkeys(countries))

    def _contains_category(self, text: str, categories: List[str]) -> bool:
        text_l = (text or "").lower()
        if not text_l:
            return False
        for category in categories:
            mapped = CATEGORY_QUERY_MAP.get(category, category)
            if category in text_l or mapped in text_l:
                return True
        return False

    def _matches_region(self, location: str, regions: List[str]) -> bool:
        if not regions or "global" in regions:
            return True

        loc = (location or "").lower()
        if "remote" in regions and ("remote" in loc or not loc):
            return True
        if "us" in regions and any(token in loc for token in [" united states", " usa", " us", "new york", "california", "texas"]):
            return True
        if any(region in regions for region in ["uk", "gb"]) and any(token in loc for token in [" united kingdom", " uk", "london", "england", "gb"]):
            return True
        if any(region in regions for region in ["eu", "de", "germany"]) and any(token in loc for token in [" germany", "berlin", "munich", "europe", "eu"]):
            return True
        if "canada" in regions or "ca" in regions:
            if any(token in loc for token in [" canada", "toronto", "vancouver", "montreal"]):
                return True
        return False
        
    def unified_schema(self, title: str, company: str, description: str,
                       source: str, location: Optional[str] = None,
                       salary: Optional[str] = None, url: Optional[str] = None,
                       tags: Optional[List[str]] = None,
                       is_remote: bool = False) -> Dict:
        """Convert job data to unified schema"""
        return {
            'title': title,
            'company': company,
            'description': description,
            'source': source,
            'location': location,
            'salary': salary,
            'url': url,
            'tags': tags or [],
            'is_remote': is_remote,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def fetch_remoteok_jobs(self, categories: List[str], regions: List[str], limit: int = 50) -> List[Dict]:
        """
        Fetch jobs from RemoteOK API (no API key needed)
        API: https://remoteok.com/api
        """
        jobs = []
        try:
            url = 'https://remoteok.com/api'
            headers = {'User-Agent': 'Mozilla/5.0'}
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Skip first item (it's metadata)
            for job in data[1:limit + 1]:
                title = job.get('position', 'Unknown')
                description = job.get('description', '')
                tags = job.get('tags', [])
                location = job.get('location', 'Remote')

                text_blob = f"{title} {description} {' '.join(tags)}"
                if not self._contains_category(text_blob, categories):
                    continue
                if not self._matches_region(location, regions) and "remote" not in regions:
                    continue

                unified_job = self.unified_schema(
                    title=title,
                    company=job.get('company', 'Unknown'),
                    description=description,
                    source='remoteok',
                    location=location,
                    salary=job.get('salary', None),
                    url=job.get('url', f"https://remoteok.com/remote-jobs/{job.get('slug', '')}"),
                    tags=tags,
                    is_remote=True,
                )
                jobs.append(unified_job)
            
            print(f"✓ Fetched {len(jobs)} jobs from RemoteOK")
            
        except Exception as e:
            print(f"✗ Error fetching RemoteOK jobs: {e}")
        
        return jobs
    
    def fetch_adzuna_jobs(self, query: str = 'python developer',
                          countries: Optional[List[str]] = None, limit: int = 50) -> List[Dict]:
        """
        Fetch jobs from Adzuna API (requires API key)
        API: https://api.adzuna.com/
        Get keys: https://developer.adzuna.com/
        """
        jobs = []
        
        if not self.adzuna_app_id or not self.adzuna_app_key:
            print("⚠ Adzuna API credentials not found. Set ADZUNA_APP_ID and ADZUNA_APP_KEY")
            return jobs
        
        try:
            for country in (countries or ['us']):
                url = f'https://api.adzuna.com/v1/api/jobs/{country}/search/1'
                params = {
                    'app_id': self.adzuna_app_id,
                    'app_key': self.adzuna_app_key,
                    'results_per_page': limit,
                    'what': query,
                    'content-type': 'application/json'
                }

                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()

                data = response.json()

                for job in data.get('results', []):
                    unified_job = self.unified_schema(
                        title=job.get('title', 'Unknown'),
                        company=job.get('company', {}).get('display_name', 'Unknown'),
                        description=job.get('description', ''),
                        source='adzuna',
                        location=job.get('location', {}).get('display_name', 'Unknown'),
                        salary=job.get('salary_min', None),
                        url=job.get('redirect_url', ''),
                        tags=[query],
                        is_remote='remote' in (job.get('description', '') or '').lower(),
                    )
                    jobs.append(unified_job)

            print(f"✓ Fetched {len(jobs)} jobs from Adzuna")
            
        except Exception as e:
            print(f"✗ Error fetching Adzuna jobs: {e}")
        
        return jobs
    
    def fetch_jsearch_jobs(self, query: str = 'Python Developer',
                           regions: Optional[List[str]] = None,
                           limit: int = 50) -> List[Dict]:
        """
        Fetch jobs from JSearch API (RapidAPI) (requires API key)
        API: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
        """
        jobs = []
        
        if not self.jsearch_api_key:
            print("⚠ JSearch API key not found. Set JSEARCH_API_KEY")
            return jobs
        
        try:
            url = "https://jsearch.p.rapidapi.com/search"
            headers = {
                "X-RapidAPI-Key": self.jsearch_api_key,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
            }
            query_with_region = query
            if regions and 'global' not in regions:
                if 'remote' in regions:
                    query_with_region = f"{query} remote"
                elif 'us' in regions:
                    query_with_region = f"{query} in United States"
                elif 'gb' in regions or 'uk' in regions:
                    query_with_region = f"{query} in United Kingdom"
                elif 'de' in regions or 'eu' in regions:
                    query_with_region = f"{query} in Germany"

            params = {
                'query': query_with_region,
                'num_pages': '1',
                'page': '1'
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            for job in data.get('data', [])[:limit]:
                location = ((job.get('job_city') or '') + ', ' + (job.get('job_country') or '')).strip(', ')
                unified_job = self.unified_schema(
                    title=job.get('job_title', 'Unknown'),
                    company=job.get('employer_name', 'Unknown'),
                    description=job.get('job_description', ''),
                    source='jsearch',
                    location=location,
                    salary=job.get('job_salary', None),
                    url=job.get('job_apply_link', ''),
                    tags=[query],
                    is_remote=bool(job.get('job_is_remote', False)),
                )
                jobs.append(unified_job)
            
            print(f"✓ Fetched {len(jobs)} jobs from JSearch")
            
        except Exception as e:
            print(f"✗ Error fetching JSearch jobs: {e}")
        
        return jobs
    
    def fetch_arbeitnow_jobs(self, categories: List[str], regions: List[str], limit: int = 100) -> List[Dict]:
        """Fetch jobs from Arbeitnow API (no key required)."""
        jobs = []
        try:
            response = requests.get('https://www.arbeitnow.com/api/job-board-api', timeout=15)
            response.raise_for_status()
            payload = response.json()
            entries = payload.get('data', payload if isinstance(payload, list) else [])

            for item in entries[:limit]:
                title = item.get('title', 'Unknown')
                description = item.get('description', '')
                tags = item.get('tags', [])
                location = item.get('location', 'Unknown')

                text_blob = f"{title} {description} {' '.join(tags)}"
                if not self._contains_category(text_blob, categories):
                    continue
                if not self._matches_region(location, regions):
                    continue

                jobs.append(
                    self.unified_schema(
                        title=title,
                        company=item.get('company_name', 'Unknown'),
                        description=description,
                        source='arbeitnow',
                        location=location,
                        salary=None,
                        url=item.get('url', ''),
                        tags=tags,
                        is_remote=bool(item.get('remote', False)),
                    )
                )

            print(f"✓ Fetched {len(jobs)} jobs from Arbeitnow")
        except Exception as e:
            print(f"✗ Error fetching Arbeitnow jobs: {e}")

        return jobs

    def fetch_wellfound_jobs(self, categories: List[str], regions: List[str], limit: int = 40) -> List[Dict]:
        """Scrape Wellfound listings with conservative request behavior."""
        jobs: List[Dict] = []
        try:
            # Wellfound pages can change often; selectors are intentionally tolerant.
            url = 'https://wellfound.com/jobs'
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; SkillGapRadar/1.0)'}
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            cards = soup.select('div[data-test="JobSearchResult"], div.styles_jobListing__*')
            if not cards:
                cards = soup.find_all('div')

            for card in cards:
                if len(jobs) >= limit:
                    break

                text = card.get_text(' ', strip=True)
                if not text or len(text) < 20:
                    continue
                if not self._contains_category(text, categories):
                    continue

                title_el = card.find(['h2', 'h3', 'a'])
                title = title_el.get_text(' ', strip=True) if title_el else 'Unknown'
                company = 'Unknown'
                company_el = card.find('span')
                if company_el:
                    company = company_el.get_text(' ', strip=True)

                location = 'Unknown'
                loc_match = re.search(r'(Remote|United States|UK|Europe|Germany|India|Canada)', text, re.IGNORECASE)
                if loc_match:
                    location = loc_match.group(1)
                if not self._matches_region(location, regions):
                    continue

                href = ''
                link = card.find('a', href=True)
                if link:
                    href = link['href']
                    if href.startswith('/'):
                        href = f"https://wellfound.com{href}"

                jobs.append(
                    self.unified_schema(
                        title=title,
                        company=company,
                        description=text,
                        source='wellfound',
                        location=location,
                        salary=None,
                        url=href,
                        tags=[],
                        is_remote='remote' in text.lower(),
                    )
                )

                # Conservative delay for ethical scraping.
                time.sleep(0.2)

            print(f"✓ Fetched {len(jobs)} jobs from Wellfound")
        except Exception as e:
            print(f"✗ Error fetching Wellfound jobs: {e}")

        return jobs

    def _find_latest_hn_hiring_thread(self) -> Optional[str]:
        """Return latest Ask HN hiring thread objectID from Algolia."""
        try:
            params = {
                'query': 'Ask HN: Who is hiring?',
                'tags': 'ask_hn',
                'hitsPerPage': 5,
            }
            response = requests.get('https://hn.algolia.com/api/v1/search', params=params, timeout=15)
            response.raise_for_status()
            hits = response.json().get('hits', [])
            if not hits:
                return None
            return hits[0].get('objectID')
        except Exception:
            return None

    def fetch_hackernews_jobs(self, categories: List[str], regions: List[str], limit: int = 80) -> List[Dict]:
        """Fetch and parse jobs from latest HN Who Is Hiring thread."""
        jobs: List[Dict] = []
        thread_id = self._find_latest_hn_hiring_thread()
        if not thread_id:
            print("⚠ Could not find latest HN Who Is Hiring thread")
            return jobs

        try:
            response = requests.get(f'https://hn.algolia.com/api/v1/items/{thread_id}', timeout=20)
            response.raise_for_status()
            comments = response.json().get('children', [])

            for comment in comments:
                if len(jobs) >= limit:
                    break

                html_text = comment.get('text') or ''
                text = re.sub(r'<[^>]+>', ' ', html_text)
                text = unescape(re.sub(r'\s+', ' ', text)).strip()
                if not text:
                    continue
                if not self._contains_category(text, categories):
                    continue

                location = 'Remote' if 'remote' in text.lower() else 'Unknown'
                if not self._matches_region(location, regions):
                    continue

                # Common WIH format starts with company info before first '|'.
                first_chunk = text.split('|')[0].strip()
                company = first_chunk[:80] if first_chunk else 'Unknown'

                title = 'Software Engineer'
                for cat in categories:
                    if cat in text.lower():
                        title = CATEGORY_QUERY_MAP.get(cat, cat).title()
                        break

                jobs.append(
                    self.unified_schema(
                        title=title,
                        company=company,
                        description=text,
                        source='hackernews',
                        location=location,
                        salary=None,
                        url=f"https://news.ycombinator.com/item?id={comment.get('id')}",
                        tags=[],
                        is_remote='remote' in text.lower(),
                    )
                )

            print(f"✓ Fetched {len(jobs)} jobs from HackerNews")
        except Exception as e:
            print(f"✗ Error fetching HackerNews jobs: {e}")

        return jobs

    def deduplicate_jobs(self, jobs: List[Dict]) -> List[Dict]:
        """Remove duplicates across sources based on title/company/location."""
        seen: Set[Tuple[str, str, str]] = set()
        deduped: List[Dict] = []

        for job in jobs:
            key = (
                (job.get('title') or '').strip().lower(),
                (job.get('company') or '').strip().lower(),
                (job.get('location') or '').strip().lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(job)

        return deduped

    def send_to_kafka(self, jobs: List[Dict]) -> int:
        """Send jobs to Kafka topic"""
        sent_count = 0
        
        for job in jobs:
            try:
                self.producer.send(self.kafka_topic, value=job)
                sent_count += 1
            except Exception as e:
                print(f"✗ Error sending job to Kafka: {e}")
        
        self.producer.flush()
        return sent_count
    
    def collect_once_filtered(self, filters: Dict) -> Dict:
        """Run one filter-aware collection cycle and return cycle stats."""
        categories = filters.get('categories', DEFAULT_FILTERS['categories'])
        regions = filters.get('regions', DEFAULT_FILTERS['regions'])
        sources = filters.get('sources', DEFAULT_FILTERS['sources'])
        queries = self.build_queries(categories)
        countries = self.build_country_codes(regions)

        print(f"Categories: {categories}")
        print(f"Regions: {regions}")
        print(f"Sources: {sources}")
        print(f"Queries: {queries}")

        all_jobs: List[Dict] = []
        source_counts: Dict[str, int] = {}

        if 'remoteok' in sources:
            remoteok_jobs = self.fetch_remoteok_jobs(categories=categories, regions=regions)
            all_jobs.extend(remoteok_jobs)
            source_counts['remoteok'] = len(remoteok_jobs)

        if 'arbeitnow' in sources:
            arbeitnow_jobs = self.fetch_arbeitnow_jobs(categories=categories, regions=regions)
            all_jobs.extend(arbeitnow_jobs)
            source_counts['arbeitnow'] = len(arbeitnow_jobs)

        if 'wellfound' in sources:
            wellfound_jobs = self.fetch_wellfound_jobs(categories=categories, regions=regions)
            all_jobs.extend(wellfound_jobs)
            source_counts['wellfound'] = len(wellfound_jobs)

        if 'hackernews' in sources:
            hackernews_jobs = self.fetch_hackernews_jobs(categories=categories, regions=regions)
            all_jobs.extend(hackernews_jobs)
            source_counts['hackernews'] = len(hackernews_jobs)

        if 'adzuna' in sources:
            adzuna_total = 0
            for query in queries:
                jobs = self.fetch_adzuna_jobs(query=query, countries=countries, limit=30)
                adzuna_total += len(jobs)
                all_jobs.extend(jobs)
            source_counts['adzuna'] = adzuna_total

        if 'jsearch' in sources:
            jsearch_total = 0
            for query in queries:
                jobs = self.fetch_jsearch_jobs(query=query, regions=regions, limit=30)
                jsearch_total += len(jobs)
                all_jobs.extend(jobs)
            source_counts['jsearch'] = jsearch_total

        unique_jobs = self.deduplicate_jobs(all_jobs)
        sent = 0
        if unique_jobs:
            sent = self.send_to_kafka(unique_jobs)

        stats = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'filters': filters,
            'fetched_total': len(all_jobs),
            'deduplicated_total': len(unique_jobs),
            'sent_total': sent,
            'by_source': source_counts,
        }
        self._write_json(self.metrics_file, stats)
        return stats

    def collect_and_stream_filtered(self, interval: int = 300):
        """Continuous collection loop driven by collection_filters.json."""
        print(f"Starting Job API Collector...")
        print(f"Filter file: {self.filters_file}")
        print(f"Kafka Topic: {self.kafka_topic}")
        print(f"Base interval: {interval} seconds")
        print("-" * 50)

        while True:
            try:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fetching jobs...")
                filters = self.load_filters()

                if not filters.get('enabled', True):
                    print("Collection disabled in filter config.")
                else:
                    stats = self.collect_once_filtered(filters)
                    print(
                        f"✓ Sent {stats['sent_total']}/{stats['deduplicated_total']} "
                        f"deduplicated jobs to Kafka (fetched: {stats['fetched_total']})"
                    )

                loop_interval = filters.get('refresh_interval', interval)
                print(f"\nNext collection in {loop_interval} seconds...")
                time.sleep(loop_interval)

            except KeyboardInterrupt:
                print("\n\nStopping collector...")
                break
            except Exception as e:
                print(f"✗ Error in collection loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
        
        self.producer.close()
        print("Collector stopped.")


def main():
    """Run the job collector"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Job API Collector - Stream jobs to Kafka')
    parser.add_argument('--query', type=str, default='python developer',
                        help='Legacy fallback query for one-off mode')
    parser.add_argument('--interval', type=int, default=300,
                        help='Collection interval in seconds (default: 300)')
    parser.add_argument('--kafka-server', type=str, default='localhost:9092',
                        help='Kafka bootstrap server (default: localhost:9092)')
    parser.add_argument('--kafka-topic', type=str, default='job_postings',
                        help='Kafka topic name (default: job_postings)')
    parser.add_argument('--once', action='store_true',
                        help='Run once and exit (no loop)')
    
    args = parser.parse_args()
    
    collector = JobAPICollector(
        kafka_bootstrap_servers=args.kafka_server,
        kafka_topic=args.kafka_topic
    )
    
    if args.once:
        # Run once using current dashboard-controlled filters.
        print("Running single collection with filter config...")
        stats = collector.collect_once_filtered(collector.load_filters())
        print(json.dumps(stats, indent=2))
    else:
        # Continuous loop
        collector.collect_and_stream_filtered(interval=args.interval)


if __name__ == '__main__':
    main()
