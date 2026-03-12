"""
Job API Collector - Fetches job postings from multiple APIs and streams to Kafka
Supports: RemoteOK, Adzuna, JSearch APIs
"""

import requests
import json
import time
from datetime import datetime, timezone
from kafka import KafkaProducer
from typing import Dict, List, Optional
import os


class JobAPICollector:
    """Collects job postings from multiple APIs and sends to Kafka"""
    
    def __init__(self, kafka_bootstrap_servers='localhost:9092', kafka_topic='job_postings'):
        self.kafka_topic = kafka_topic
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        # API keys from environment variables
        self.adzuna_app_id = os.getenv('ADZUNA_APP_ID')
        self.adzuna_app_key = os.getenv('ADZUNA_APP_KEY')
        self.jsearch_api_key = os.getenv('JSEARCH_API_KEY')
        
    def unified_schema(self, title: str, company: str, description: str, 
                       source: str, location: Optional[str] = None,
                       salary: Optional[str] = None, url: Optional[str] = None) -> Dict:
        """Convert job data to unified schema"""
        return {
            'title': title,
            'company': company,
            'description': description,
            'source': source,
            'location': location,
            'salary': salary,
            'url': url,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def fetch_remoteok_jobs(self, query: str = 'python', limit: int = 50) -> List[Dict]:
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
            for job in data[1:limit+1]:
                if query.lower() in job.get('position', '').lower() or \
                   query.lower() in job.get('description', '').lower():
                    
                    unified_job = self.unified_schema(
                        title=job.get('position', 'Unknown'),
                        company=job.get('company', 'Unknown'),
                        description=job.get('description', ''),
                        source='remoteok',
                        location=job.get('location', 'Remote'),
                        salary=job.get('salary', None),
                        url=job.get('url', f"https://remoteok.com/remote-jobs/{job.get('slug', '')}")
                    )
                    jobs.append(unified_job)
            
            print(f"✓ Fetched {len(jobs)} jobs from RemoteOK")
            
        except Exception as e:
            print(f"✗ Error fetching RemoteOK jobs: {e}")
        
        return jobs
    
    def fetch_adzuna_jobs(self, query: str = 'python developer', 
                          country: str = 'us', limit: int = 50) -> List[Dict]:
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
                    url=job.get('redirect_url', '')
                )
                jobs.append(unified_job)
            
            print(f"✓ Fetched {len(jobs)} jobs from Adzuna")
            
        except Exception as e:
            print(f"✗ Error fetching Adzuna jobs: {e}")
        
        return jobs
    
    def fetch_jsearch_jobs(self, query: str = 'Python Developer', 
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
            params = {
                'query': query,
                'num_pages': '1',
                'page': '1'
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            for job in data.get('data', [])[:limit]:
                unified_job = self.unified_schema(
                    title=job.get('job_title', 'Unknown'),
                    company=job.get('employer_name', 'Unknown'),
                    description=job.get('job_description', ''),
                    source='jsearch',
                    location=job.get('job_city', '') + ', ' + job.get('job_country', ''),
                    salary=job.get('job_salary', None),
                    url=job.get('job_apply_link', '')
                )
                jobs.append(unified_job)
            
            print(f"✓ Fetched {len(jobs)} jobs from JSearch")
            
        except Exception as e:
            print(f"✗ Error fetching JSearch jobs: {e}")
        
        return jobs
    
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
    
    def collect_and_stream(self, query: str = 'python developer', interval: int = 300):
        """
        Main collection loop - fetches from all APIs and streams to Kafka
        
        Args:
            query: Job search query
            interval: Seconds between collections (default 5 minutes)
        """
        print(f"Starting Job API Collector...")
        print(f"Query: {query}")
        print(f"Kafka Topic: {self.kafka_topic}")
        print(f"Collection Interval: {interval} seconds")
        print("-" * 50)
        
        while True:
            try:
                all_jobs = []
                
                # Fetch from RemoteOK (no key needed)
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fetching jobs...")
                remoteok_jobs = self.fetch_remoteok_jobs(query=query)
                all_jobs.extend(remoteok_jobs)
                
                # Fetch from Adzuna (if credentials available)
                adzuna_jobs = self.fetch_adzuna_jobs(query=query)
                all_jobs.extend(adzuna_jobs)
                
                # Fetch from JSearch (if credentials available)
                jsearch_jobs = self.fetch_jsearch_jobs(query=query)
                all_jobs.extend(jsearch_jobs)
                
                # Send to Kafka
                if all_jobs:
                    sent = self.send_to_kafka(all_jobs)
                    print(f"✓ Sent {sent}/{len(all_jobs)} jobs to Kafka topic '{self.kafka_topic}'")
                else:
                    print("⚠ No jobs fetched from any source")
                
                print(f"\nNext collection in {interval} seconds...")
                time.sleep(interval)
                
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
                        help='Job search query (default: python developer)')
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
        # Run once
        print("Running single collection...")
        all_jobs = []
        all_jobs.extend(collector.fetch_remoteok_jobs(query=args.query))
        all_jobs.extend(collector.fetch_adzuna_jobs(query=args.query))
        all_jobs.extend(collector.fetch_jsearch_jobs(query=args.query))
        
        if all_jobs:
            sent = collector.send_to_kafka(all_jobs)
            print(f"Sent {sent} jobs to Kafka")
        else:
            print("No jobs fetched")
    else:
        # Continuous loop
        collector.collect_and_stream(query=args.query, interval=args.interval)


if __name__ == '__main__':
    main()
