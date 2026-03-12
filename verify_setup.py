"""
Quick verification script to test imports and basic functionality
Run this to verify the v2.0 refactoring is working correctly
"""

import sys
from pathlib import Path

print("="*60)
print("Skill Gap Radar v2.0 - Component Verification")
print("="*60)

# Test imports
print("\n1. Testing imports...")

try:
    import pdfplumber
    print("   ✓ pdfplumber installed")
except ImportError as e:
    print(f"   ✗ pdfplumber not installed: {e}")
    
try:
    import spacy
    print("   ✓ spacy installed")
    try:
        nlp = spacy.load('en_core_web_sm')
        print("   ✓ en_core_web_sm model loaded")
    except OSError:
        print("   ✗ en_core_web_sm model not found")
        print("     Run: python -m spacy download en_core_web_sm")
except ImportError as e:
    print(f"   ✗ spacy not installed: {e}")

try:
    from kafka import KafkaProducer, KafkaConsumer
    print("   ✓ kafka-python installed")
except ImportError as e:
    print(f"   ✗ kafka-python not installed: {e}")

try:
    from pyspark.sql import SparkSession
    print("   ✓ pyspark installed")
except ImportError as e:
    print(f"   ✗ pyspark not installed: {e}")

try:
    from fastapi import FastAPI
    print("   ✓ fastapi installed")
except ImportError as e:
    print(f"   ✗ fastapi not installed: {e}")

# Test module imports
print("\n2. Testing custom modules...")

sys.path.append(str(Path(__file__).parent))

try:
    from resume_processing.resume_parser import ResumeParser
    print("   ✓ resume_processing.resume_parser imported")
except Exception as e:
    print(f"   ✗ Error importing resume_parser: {e}")

try:
    from analysis.skill_gap import SkillGapAnalyzer
    print("   ✓ analysis.skill_gap imported")
except Exception as e:
    print(f"   ✗ Error importing skill_gap: {e}")

try:
    from spark_jobs.job_api_collector import JobAPICollector
    print("   ✓ spark_jobs.job_api_collector imported")
except Exception as e:
    print(f"   ✗ Error importing job_api_collector: {e}")

# Test data directories
print("\n3. Checking data directories...")

data_dir = Path(__file__).parent / "data" / "processed_jobs"
if data_dir.exists():
    print(f"   ✓ Data directory exists: {data_dir}")
else:
    print(f"   ! Data directory will be created: {data_dir}")

raw_jobs = data_dir / "raw_jobs"
if raw_jobs.exists():
    print(f"   ✓ raw_jobs directory exists")
else:
    print(f"   ! raw_jobs directory not created yet (will be created on first run)")

skill_demand = data_dir / "skill_demand"
if skill_demand.exists():
    print(f"   ✓ skill_demand directory exists")
else:
    print(f"   ! skill_demand directory not created yet (will be created on first run)")

# Test functionality
print("\n4. Testing basic functionality...")

try:
    from analysis.skill_gap import SkillGapAnalyzer
    
    # Mock market data
    market_skills = {
        "python": 100,
        "sql": 80,
        "spark": 60,
        "aws": 50,
        "docker": 40
    }
    
    analyzer = SkillGapAnalyzer(market_skills)
    result = analyzer.analyze_gap(["python", "java"], top_n=10)
    
    print("   ✓ SkillGapAnalyzer works")
    print(f"     - Matching skills: {result['matching_skills']}")
    print(f"     - Gap percentage: {result['gap_percentage']}%")
    print(f"     - Top priorities: {result['top_priorities'][:3]}")
except Exception as e:
    print(f"   ✗ SkillGapAnalyzer test failed: {e}")

# Environment check
print("\n5. Checking environment...")

import os

kafka_home = os.environ.get('KAFKA_HOME')
if kafka_home:
    print(f"   ✓ KAFKA_HOME set: {kafka_home}")
else:
    print(f"   ! KAFKA_HOME not set (you'll need to provide full path to Kafka)")

adzuna_id = os.environ.get('ADZUNA_APP_ID')
adzuna_key = os.environ.get('ADZUNA_APP_KEY')
if adzuna_id and adzuna_key:
    print(f"   ✓ Adzuna API credentials configured")
else:
    print(f"   ! Adzuna API credentials not set (optional, falls back to RemoteOK)")

jsearch_key = os.environ.get('JSEARCH_API_KEY')
if jsearch_key:
    print(f"   ✓ JSearch API key configured")
else:
    print(f"   ! JSearch API key not set (optional, falls back to RemoteOK)")

# Summary
print("\n" + "="*60)
print("Verification Complete!")
print("="*60)
print("\nNext steps:")
print("1. If any dependencies are missing, run: pip install -r requirements.txt")
print("2. If spaCy model is missing, run: python -m spacy download en_core_web_sm")
print("3. Start Kafka and create topic 'job_postings'")
print("4. Run: python spark_jobs/job_api_collector.py --query 'test' --once")
print("5. Run: python spark_jobs/job_stream_processor.py")
print("6. Run: python dashboard/server.py")
print("7. Open: http://localhost:8000")
print("\nFor detailed instructions, see: docs/SETUP.md")
print("="*60)
