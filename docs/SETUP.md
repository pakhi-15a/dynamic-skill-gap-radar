# Skill Gap Radar - Setup Guide v2.0

Complete setup guide for the real-time job market analysis and resume skill gap analyzer.

## 📋 System Architecture

```
Job APIs (RemoteOK, Adzuna, JSearch)
         ↓
   Kafka Broker (job_postings topic)
         ↓
  Spark Streaming Processor
         ↓
   Parquet Files (/data/processed_jobs/)
         ↓
  FastAPI Dashboard (WebSocket + REST)
```

**New Features (v2.0):**
- Real-time job data from APIs (RemoteOK, Adzuna, JSearch)
- NLP-based resume parsing (pdfplumber + spaCy)
- Parquet-only storage (Hive removed)
- Skill gap analysis with prioritized recommendations

## ☑️ Prerequisites

- **Python 3.8+** (tested with 3.12)
- **Java 8 or 11** (for Kafka & Spark)
- **8GB RAM** minimum
- **10GB disk space**

## 🚀 Quick Start (5 Minutes)

### 1. Install Dependencies

```bash
cd /home/pakhi/skill-gap-radar

# Install Python packages
pip install -r requirements.txt

# Download spaCy language model (REQUIRED for NLP)
python -m spacy download en_core_web_sm
```

**Verify:**
```bash
python -c "import pdfplumber, spacy; nlp=spacy.load('en_core_web_sm'); print('✓ All dependencies OK')"
```

### 2. Start Kafka

```bash
# If Kafka is already installed at $KAFKA_HOME:
cd $KAFKA_HOME

# Terminal 1: Start Zookeeper
bin/zookeeper-server-start.sh config/zookeeper.properties

# Terminal 2: Start Kafka
bin/kafka-server-start.sh config/server.properties

# Terminal 3: Create topic
bin/kafka-topics.sh --create --topic job_postings \
  --bootstrap-server localhost:9092 \
  --partitions 3 --replication-factor 1
```

**Don't have Kafka?** See [Kafka Installation](#kafka-installation) below.

### 3. Start the System

```bash
cd /home/pakhi/skill-gap-radar

# Terminal 4: Start Spark streaming processor
python spark_jobs/job_stream_processor.py

# Terminal 5: Start job collector (uses RemoteOK by default, no API key needed)
python spark_jobs/job_api_collector.py --query "data scientist" --interval 300

# Terminal 6: Start dashboard
python dashboard/server.py
```

### 4. Access Dashboard

Open browser: http://localhost:8000

You should see:
- Real-time skill demand chart updating every 30 seconds
- Upload resume button (PDF only)

---

## 📡 API Configuration

### Free Option (No Keys Required)

**RemoteOK API** works out of the box:
```bash
python spark_jobs/job_api_collector.py --query "python developer" --interval 300
```

### Paid APIs (More Job Data)

#### Adzuna Setup
1. Sign up: https://developer.adzuna.com/
2. Get your App ID and App Key
3. Set environment variables:

```bash
export ADZUNA_APP_ID="your_app_id_here"
export ADZUNA_APP_KEY="your_app_key_here"
```

#### JSearch Setup (RapidAPI)
1. Sign up: https://rapidapi.com/
2. Subscribe to JSearch API: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
3. Get your API key
4. Set environment variable:

```bash
export JSEARCH_API_KEY="your_rapidapi_key_here"
```

#### Permanent Configuration

Add to `~/.bashrc` or `~/.zshrc`:
```bash
export ADZUNA_APP_ID="your_app_id"
export ADZUNA_APP_KEY="your_app_key"
export JSEARCH_API_KEY="your_rapidapi_key"
```

Or create `.env` file in project root:
```bash
cd /home/pakhi/skill-gap-radar
cat > .env << 'EOF'
ADZUNA_APP_ID=your_app_id
ADZUNA_APP_KEY=your_app_key
JSEARCH_API_KEY=your_rapidapi_key
EOF
```

---

## 🔧 Detailed Installation

### Kafka Installation

#### Option 1: Quick Install (Recommended)

```bash
# Download Kafka 3.6.0
cd /tmp
wget https://downloads.apache.org/kafka/3.6.0/kafka_2.13-3.6.0.tgz
tar -xzf kafka_2.13-3.6.0.tgz

# Move to /opt
sudo mv kafka_2.13-3.6.0 /opt/kafka

# Add to PATH
echo 'export KAFKA_HOME=/opt/kafka' >> ~/.bashrc
echo 'export PATH=$PATH:$KAFKA_HOME/bin' >> ~/.bashrc
source ~/.bashrc

# Start services
cd $KAFKA_HOME

# Terminal 1
bin/zookeeper-server-start.sh config/zookeeper.properties

# Terminal 2
bin/kafka-server-start.sh config/server.properties
```

#### Option 2: Background Services

```bash
# Start as background processes
cd $KAFKA_HOME
bin/zookeeper-server-start.sh config/zookeeper.properties > /tmp/zookeeper.log 2>&1 &
sleep 10
bin/kafka-server-start.sh config/server.properties > /tmp/kafka.log 2>&1 &
sleep 10

# Verify running
jps | grep -E "Kafka|QuorumPeer"
```

#### Create Topic

```bash
cd $KAFKA_HOME
bin/kafka-topics.sh --create --topic job_postings \
  --bootstrap-server localhost:9092 \
  --partitions 3 --replication-factor 1

# Verify
bin/kafka-topics.sh --list --bootstrap-server localhost:9092
```

**Expected:** `job_postings` appears in list.

### Verify Spark Installation

```bash
# Test Spark
python spark_jobs/test_spark.py

# Expected output:
# ✓ Spark session created
# ✓ DataFrame created
# ✓ Basic operations work
# SUCCESS: Spark is properly configured
```

---

## 🎯 Usage Guide

### Collecting Job Data

#### Basic Usage (RemoteOK, no API key)
```bash
python spark_jobs/job_api_collector.py --query "python developer"
```

#### Custom Configuration
```bash
# Run once (don't loop)
python spark_jobs/job_api_collector.py --query "machine learning" --once

# Custom interval (seconds)
python spark_jobs/job_api_collector.py --query "data engineer" --interval 600

# Custom Kafka settings
python spark_jobs/job_api_collector.py \
  --query "devops" \
  --kafka-server localhost:9092 \
  --kafka-topic job_postings \
  --interval 300
```

#### Query Tips
- Be specific: "python data scientist" better than "jobs"
- Location-aware: "remote software engineer"
- Skills-focused: "react developer", "aws cloud engineer"

### Processing Job Data

```bash
# Start processor (processes every 30 seconds)
python spark_jobs/job_stream_processor.py
```

**What it does:**
1. Reads jobs from Kafka topic
2. Extracts skills from job descriptions
3. Saves raw jobs to Parquet: `data/processed_jobs/raw_jobs/`
4. Saves skill demand to Parquet: `data/processed_jobs/skill_demand/`
5. Sends top 20 skills to dashboard via HTTP POST

### Analyzing Resumes

#### Via Web Interface
1. Open: http://localhost:8000
2. Click "Upload Resume"
3. Select PDF file (only PDF supported)
4. View results:
   - Extracted skills (NLP-based)
   - Matching market skills
   - Missing skills (prioritized: High/Medium/Low)
   - Recommended learning path

#### Via API

```bash
# Upload resume
curl -X POST http://localhost:8000/resume-analysis \
  -F "file=@/path/to/resume.pdf"

# Get market skills
curl http://localhost:8000/market-skills?top_n=50

# System stats
curl http://localhost:8000/api/stats
```

---

## 📊 Data Storage

### Directory Structure

```
data/
├── processed_jobs/
│   ├── raw_jobs/               # All job postings (partitioned by source, date)
│   │   ├── source=remoteok/
│   │   ├── source=adzuna/
│   │   └── source=jsearch/
│   └── skill_demand/           # Aggregated skill counts
│       └── *.parquet
└── raw/                        # Legacy CSV files (not used in v2.0)
```

### Querying Parquet Files

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("QueryData").getOrCreate()

# Read all jobs
jobs_df = spark.read.parquet("data/processed_jobs/raw_jobs")
jobs_df.show()

# Read skill demand
skills_df = spark.read.parquet("data/processed_jobs/skill_demand")
skills_df.groupBy("skill").sum("count").orderBy("sum(count)", ascending=False).show(20)

spark.stop()
```

---

## 🧪 Testing

### Test Individual Components

```bash
# Test Spark
python spark_jobs/test_spark.py

# Test resume parser
python -c "
from resume_processing.resume_parser import ResumeParser
parser = ResumeParser()
result = parser.analyze_resume('path/to/resume.pdf')
print(f\"Skills found: {result['skills']}\")
"

# Test skill gap analyzer
python -c "
from analysis.skill_gap import SkillGapAnalyzer
market = {'python': 100, 'sql': 80, 'spark': 60}
analyzer = SkillGapAnalyzer(market)
gap = analyzer.analyze_gap(['python', 'java'], top_n=10)
print(gap)
"
```

### Test API Collector (Dry Run)

```bash
# Collect a few jobs without sending to Kafka
python spark_jobs/job_api_collector.py --query "software engineer" --once
```

Watch for output showing jobs collected from each API source.

---

## 🔍 Troubleshooting

### Issue: spaCy model not found

**Error:** `OSError: [E050] Can't find model 'en_core_web_sm'`

**Solution:**
```bash
python -m spacy download en_core_web_sm
```

### Issue: Kafka connection refused

**Error:** `kafka.errors.NoBrokersAvailable`

**Solutions:**
1. Check Kafka is running: `jps | grep Kafka`
2. Check Zookeeper is running: `jps | grep QuorumPeer`
3. Verify port: `netstat -an | grep 9092`
4. Check logs: `tail -f $KAFKA_HOME/logs/server.log`

### Issue: No jobs appearing in dashboard

**Checklist:**
1. ✓ Job collector running? `ps aux | grep job_api_collector`
2. ✓ Stream processor running? `ps aux | grep job_stream_processor`
3. ✓ Kafka messages present? 
   ```bash
   $KAFKA_HOME/bin/kafka-console-consumer.sh \
     --bootstrap-server localhost:9092 \
     --topic job_postings --from-beginning --max-messages 5
   ```
4. ✓ Dashboard running? `curl http://localhost:8000/health`

### Issue: API rate limits

**Error:** `HTTP 429 Too Many Requests`

**Solutions:**
- Increase `--interval` (e.g., 600 seconds = 10 minutes)
- Use multiple API sources (distribute load)
- Check API documentation for rate limits

### Issue: PDF parsing fails

**Error:** `Error parsing resume`

**Solutions:**
1. Ensure PDF is text-based (not scanned image)
2. Check file is valid PDF: `file /path/to/resume.pdf`
3. Try different PDF if generated from proprietary software

---

## 🚦 System Health Checks

### Quick Status Check

```bash
# Check all processes
echo "=== Kafka ==="
jps | grep -E "Kafka|QuorumPeer"

echo "=== Python Processes ==="
ps aux | grep -E "job_api_collector|job_stream_processor|server.py" | grep -v grep

echo "=== Network Ports ==="
netstat -an | grep -E "9092|8000"

echo "=== Data Directories ==="
ls -lh data/processed_jobs/
```

### View Logs

```bash
# Kafka logs
tail -f $KAFKA_HOME/logs/server.log

# Check job data
ls -lh data/processed_jobs/raw_jobs/
ls -lh data/processed_jobs/skill_demand/
```

---

## 📚 API Reference

### Dashboard Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard HTML |
| GET | `/health` | System health check |
| GET | `/market-skills?top_n=50` | Get top N demanded skills |
| POST | `/resume-analysis` | Upload PDF and get gap analysis |
| GET | `/api/stats` | System statistics |
| WS | `/ws` | WebSocket for real-time updates |

### Example API Calls

```bash
# Health check
curl http://localhost:8000/health

# Get top 20 skills
curl http://localhost:8000/market-skills?top_n=20

# Upload resume
curl -X POST http://localhost:8000/resume-analysis \
  -F "file=@resume.pdf" \
  | jq '.gap_analysis'

# Get stats
curl http://localhost:8000/api/stats | jq .
```

---

## 🎓 Architecture Notes

### Data Flow

1. **Collection:** `job_api_collector.py` fetches jobs from APIs every N seconds
2. **Streaming:** Jobs sent to Kafka topic `job_postings`
3. **Processing:** `job_stream_processor.py` consumes Kafka, extracts skills
4. **Storage:** Raw jobs + skill demand saved to Parquet files
5. **Dashboard:** Reads Parquet files, serves to frontend
6. **Resume Analysis:** PDF → NLP extraction → Gap analysis → Results

### Key Design Decisions

- **No Hive:** Replaced with Parquet for simplicity, portability
- **No CSV:** All data from real-time APIs
- **PDF Only:** Focused on most common resume format
- **NLP-based:** spaCy provides better skill extraction than regex
- **Modular:** Separate packages for resume processing and analysis

### Scaling Considerations

- Kafka partitions: Increase for higher throughput
- Spark resources: Configure executor memory in `job_stream_processor.py`
- API rate limits: Add more sources or increase intervals
- Storage: Parquet files auto-partition by source and date

---

## 📞 Support

For issues or questions:
1. Check [Troubleshooting](#-troubleshooting) section
2. Review logs in `/tmp/` and `$KAFKA_HOME/logs/`
3. Verify all prerequisites installed correctly

---

**Version:** 2.0.0  
**Last Updated:** 2024  
**Architecture:** Real-time API-based with NLP skill extraction
