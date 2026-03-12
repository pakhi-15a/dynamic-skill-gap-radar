# Skill Gap Radar 🎯

A real-time job market analysis system that helps job seekers identify skill gaps by comparing their resume against current market demand using live job API data.

## 🌟 Key Features

- **📄 NLP-Powered Resume Analysis**: Upload PDF resumes and extract skills using spaCy NLP (80+ skill categories)
- **📡 Real-Time Job Data**: Collect live job postings from RemoteOK, Adzuna, and JSearch APIs
- **🎯 Intelligent Gap Analysis**: Compare your skills against market demand with prioritized recommendations (High/Medium/Low)
- **📊 Live Dashboard**: WebSocket-based real-time visualization of skill demand trends
- **⚡ Streaming Architecture**: Apache Kafka + Spark Structured Streaming for continuous data processing
- **💾 Efficient Storage**: Parquet-based data lake with automatic partitioning by source and date
- **🎓 Learning Recommendations**: Personalized 5-skill learning path based on gap analysis

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│           Job APIs (Real-time Sources)              │
│  RemoteOK (Free)  │  Adzuna  │  JSearch (RapidAPI) │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP Requests (300s interval)
                       ▼
┌─────────────────────────────────────────────────────┐
│            Job API Collector (Python)               │
│  - Fetch jobs from multiple APIs                   │
│  - Normalize to unified schema                     │
│  - Stream to Kafka                                 │
└──────────────────────┬──────────────────────────────┘
                       │ Kafka Topic: job_postings
                       ▼
┌─────────────────────────────────────────────────────┐
│         Apache Kafka (Message Broker)               │
│              localhost:9092                         │
└──────────────────────┬──────────────────────────────┘
                       │ Consume Stream
                       ▼
┌─────────────────────────────────────────────────────┐
│      Spark Structured Streaming Processor           │
│  - Read from Kafka (30s triggers)                  │
│  - Extract skills from job descriptions            │
│  - Aggregate skill demand counts                   │
│  - Write to Parquet (partitioned)                  │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│          Parquet Data Lake                          │
│  data/processed_jobs/                              │
│    ├── raw_jobs/        (partitioned by source)    │
│    └── skill_demand/    (aggregated counts)        │
└──────────────────────┬──────────────────────────────┘
                       │ Query Parquet
                       ▼
┌─────────────────────────────────────────────────────┐
│         FastAPI Dashboard Server                    │
│  - GET  /market-skills      (read Parquet)         │
│  - POST /resume-analysis    (PDF upload + gap)     │
│  - WS   /ws                 (real-time updates)    │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP + WebSocket
                       ▼
┌─────────────────────────────────────────────────────┐
│            Web Dashboard (Browser)                  │
│  - Upload Resume (PDF only)                        │
│  - View Skill Gaps (prioritized)                   │
│  - Live Skill Demand Chart                         │
└─────────────────────────────────────────────────────┘
```

### Resume Analysis Flow

```
PDF Resume → pdfplumber (text extraction)
         ↓
    spaCy NLP (en_core_web_sm)
         ↓
   Skill Extraction (keywords + noun phrases + entities)
         ↓
  Market Comparison (from Parquet skill_demand/)
         ↓
    Gap Analysis (SkillGapAnalyzer)
         ↓
  Prioritized Results (High/Medium/Low + Learning Path)
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Java 8 or 11 (for Kafka & Spark)
- 8GB RAM
- 10GB disk space

### Installation (5 minutes)

```bash
# 1. Clone/navigate to repository
cd /home/pakhi/skill-gap-radar

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Download spaCy language model (REQUIRED)
python -m spacy download en_core_web_sm

# 4. Start Kafka (assumes $KAFKA_HOME set)
cd $KAFKA_HOME
bin/zookeeper-server-start.sh config/zookeeper.properties &
bin/kafka-server-start.sh config/server.properties &

# 5. Create Kafka topic
bin/kafka-topics.sh --create --topic job_postings \
  --bootstrap-server localhost:9092 \
  --partitions 3 --replication-factor 1
```

### Run the System

```bash
cd /home/pakhi/skill-gap-radar

# Terminal 1: Start Spark streaming processor
python spark_jobs/job_stream_processor.py

# Terminal 2: Start job collector (uses free RemoteOK API)
python spark_jobs/job_api_collector.py --query "data scientist" --interval 300

# Terminal 3: Start dashboard
python dashboard/server.py
```

**Access dashboard:** http://localhost:8000

---

## 📡 API Configuration

### Free Option (No Keys Required)

By default, the system uses **RemoteOK** which requires no API keys:

```bash
python spark_jobs/job_api_collector.py --query "python developer"
```

### Paid APIs (Optional - More Data)

For more comprehensive job data, configure these APIs:

#### Adzuna Setup
1. Sign up: https://developer.adzuna.com/
2. Get your App ID and Key
3. Set environment variables:
```bash
export ADZUNA_APP_ID="your_app_id"
export ADZUNA_APP_KEY="your_app_key"
```

#### JSearch Setup (RapidAPI)
1. Sign up: https://rapidapi.com/
2. Subscribe to JSearch: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
3. Get API key and set:
```bash
export JSEARCH_API_KEY="your_rapidapi_key"
```

When API keys are configured, the collector automatically uses all available sources.

---

## 📖 Usage Examples

### Collecting Job Data

```bash
# Basic usage (RemoteOK, loops every 5 minutes)
python spark_jobs/job_api_collector.py --query "machine learning engineer"

# Run once and exit
python spark_jobs/job_api_collector.py --query "devops" --once

# Custom interval (10 minutes)
python spark_jobs/job_api_collector.py --query "data engineer" --interval 600
```

### Analyzing Resumes

#### Via Web Interface
1. Open http://localhost:8000
2. Click "Upload Resume"
3. Select your PDF resume
4. View results:
   - **Extracted skills** (NLP-based)
   - **Matching skills** (already in demand)
   - **Missing skills** (High/Medium/Low priority)
   - **Learning recommendations** (top 5 skills to focus on)

#### Via API

```bash
# Upload and analyze resume
curl -X POST http://localhost:8000/resume-analysis \
  -F "file=@/path/to/resume.pdf"

# Get current market skills
curl http://localhost:8000/market-skills?top_n=50

# Get system stats
curl http://localhost:8000/api/stats
```

#### Example Response

```json
{
  "success": true,
  "file_name": "john_doe_resume.pdf",
  "word_count": 450,
  "resume_skills": ["python", "sql", "pandas", "docker"],
  "skill_count": 4,
  "gap_analysis": {
    "matching_skills": ["python", "sql"],
    "missing_skills": {
      "high_priority": [
        {"skill": "spark", "demand": 45, "priority": "High"},
        {"skill": "aws", "demand": 38, "priority": "High"}
      ],
      "medium_priority": [
        {"skill": "kubernetes", "demand": 22, "priority": "Medium"}
      ],
      "low_priority": [
        {"skill": "airflow", "demand": 8, "priority": "Low"}
      ]
    },
    "gap_percentage": 60.0,
    "overall_assessment": "Moderate skill gap",
    "top_priorities": ["spark", "aws", "kubernetes", "terraform", "scala"],
    "recommendations": [
      {
        "skill": "spark",
        "priority": "High",
        "reason": "Very high demand (45 occurrences)"
      }
    ]
  }
}
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| **Job Collection** | Python, requests, RemoteOK/Adzuna/JSearch APIs |
| **Message Broker** | Apache Kafka |
| **Stream Processing** | Apache Spark Structured Streaming |
| **Data Storage** | Parquet (partitioned data lake) |
| **Resume Parsing** | pdfplumber, spaCy (en_core_web_sm) |
| **Gap Analysis** | Custom SkillGapAnalyzer (priority-based) |
| **Backend API** | FastAPI, uvicorn |
| **Real-time Updates** | WebSockets |
| **Frontend** | HTML5, JavaScript, Chart.js |

---

## 📁 Project Structure

```
skill-gap-radar/
├── spark_jobs/
│   ├── job_api_collector.py        # Fetch jobs from APIs → Kafka
│   ├── job_stream_processor.py     # Kafka → Spark → Parquet
│   ├── skill_extractor.py          # Extract skills from text
│   └── test_spark.py               # Verify Spark setup
├── resume_processing/
│   ├── resume_parser.py            # NLP-based PDF skill extraction
│   └── __init__.py
├── analysis/
│   ├── skill_gap.py                # SkillGapAnalyzer class
│   └── __init__.py
├── dashboard/
│   ├── server.py                   # FastAPI backend (refactored v2.0)
│   ├── index.html                  # Web dashboard interface
│   └── server_old_backup.py        # Old version (with Hive)
├── data/
│   ├── processed_jobs/
│   │   ├── raw_jobs/               # Partitioned by source, date
│   │   └── skill_demand/           # Aggregated skill counts
│   └── raw/                        # Legacy CSV files (not used in v2.0)
├── docs/
│   └── SETUP.md                    # Comprehensive setup guide
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

---

## 🔍 Key Features Explained

### 1. NLP-Based Skill Extraction

Uses **spaCy en_core_web_sm** for intelligent skill extraction:

- **Direct keyword matching**: 80+ curated skill keywords
- **Noun phrase extraction**: Captures multi-word skills ("machine learning", "web development")
- **Named entity recognition**: Identifies technologies and frameworks

Categories covered:
- Programming languages (Python, Java, JavaScript, etc.)
- Frameworks (React, Django, Spring, etc.)
- Databases (PostgreSQL, MongoDB, Redis, etc.)
- Cloud platforms (AWS, Azure, GCP)
- Big data (Spark, Hadoop, Kafka, etc.)
- ML/AI (TensorFlow, PyTorch, scikit-learn, etc.)
- Tools (Docker, Kubernetes, Git, etc.)

### 2. Priority-Based Gap Analysis

The **SkillGapAnalyzer** classifies missing skills into priorities:

- **High Priority**: >30% market demand - Critical skills to learn
- **Medium Priority**: 10-30% demand - Important for advancement
- **Low Priority**: <10% demand - Nice to have

Provides:
- Match percentage (skills you have vs. market needs)
- Top 5 recommended skills based on demand
- Overall assessment (Excellent/Good/Moderate/Significant gap)

### 3. Real-Time Data Pipeline

- Jobs collected every 5 minutes (configurable)
- Spark processes data in 30-second micro-batches
- Dashboard updates via WebSockets immediately
- Parquet files auto-partition by source and date for efficient queries

### 4. Unified Job Schema

All API sources normalized to:
```python
{
    "title": str,
    "company": str,
    "description": str,
    "source": str,
    "location": str,
    "salary": str,
    "url": str,
    "timestamp": str
}
```

---

## 🧪 Testing

### Verify Installation

```bash
# Test Spark
python spark_jobs/test_spark.py

# Test resume parser
python -c "
from resume_processing.resume_parser import ResumeParser
import tempfile
# Test with sample PDF
"

# Test skill gap analyzer
python -c "
from analysis.skill_gap import SkillGapAnalyzer
market = {'python': 100, 'sql': 80, 'spark': 60}
analyzer = SkillGapAnalyzer(market)
result = analyzer.analyze_gap(['python', 'java'])
print(result)
"
```

### Check Data Flow

```bash
# 1. Verify Kafka topic
cd $KAFKA_HOME
bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 \
  --topic job_postings --from-beginning --max-messages 5

# 2. Check Parquet files
ls -lh data/processed_jobs/raw_jobs/
ls -lh data/processed_jobs/skill_demand/

# 3. Query Parquet data
python -c "
from pyspark.sql import SparkSession
spark = SparkSession.builder.appName('Test').getOrCreate()
df = spark.read.parquet('data/processed_jobs/skill_demand')
df.show()
"
```

---

## 📊 Data Storage Details

### Parquet Structure

```
data/processed_jobs/
├── raw_jobs/
│   ├── source=remoteok/
│   │   └── date=2024-01-15/
│   │       └── part-00000.parquet
│   ├── source=adzuna/
│   └── source=jsearch/
└── skill_demand/
    └── part-00000.parquet
```

### Schema

**raw_jobs:**
```
- title: string
- company: string  
- description: string
- source: string
- location: string
- salary: string
- url: string
- timestamp: string
```

**skill_demand:**
```
- skill: string
- count: long
- timestamp: string
```

---

## 🔧 Troubleshooting

### Common Issues

**Issue**: `OSError: [E050] Can't find model 'en_core_web_sm'`

**Solution**:
```bash
python -m spacy download en_core_web_sm
```

---

**Issue**: `kafka.errors.NoBrokersAvailable`

**Solution**:
```bash
# Check Kafka is running
jps | grep Kafka

# Start if not running
cd $KAFKA_HOME
bin/kafka-server-start.sh config/server.properties &
```

---

**Issue**: No jobs appearing in dashboard

**Solution**:
```bash
# Check all components running
ps aux | grep -E "job_api_collector|job_stream_processor|server.py"

# Check Kafka has messages
cd $KAFKA_HOME
bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 \
  --topic job_postings --from-beginning --max-messages 1
```

See [docs/SETUP.md](docs/SETUP.md) for comprehensive troubleshooting guide.

---

## 📈 Scaling Considerations

- **Kafka Partitions**: Increase from 3 to 10+ for higher throughput
- **Spark Executors**: Adjust memory in `job_stream_processor.py`
- **API Rate Limits**: Use multiple API sources, increase collection interval
- **Storage**: Parquet auto-partitions by source and date - old data can be archived

---

## 🎓 Learning Resources

- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Spark Structured Streaming Guide](https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html)
- [spaCy NLP Documentation](https://spacy.io/usage)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## 📝 Version History

### v2.0.0 (Current)
- ✨ Real-time job data from APIs (RemoteOK, Adzuna, JSearch)
- ✨ NLP-based resume parsing (pdfplumber + spaCy)
- ✨ Priority-based skill gap analysis (High/Medium/Low)
- ✨ Parquet-only storage (removed Hive dependency)
- ✨ PDF-only resume uploads
- ✨ Learning path recommendations
- 🔧 Modular architecture (resume_processing/, analysis/)

### v1.0.0
- CSV-based job data (LinkedIn, Indeed, Glassdoor)
- Optional Apache Hive integration
- Regex-based skill extraction
- Multi-format resume support (PDF, DOCX, TXT)
- User profile management

---

## 📄 License

This project is for educational purposes.

---

## 👥 Contributing

Contributions welcome! Areas for improvement:
- Add more job API sources
- Enhance skill extraction with transformers
- Add skill popularity trends over time
- Resume format recommendations
- Multi-language support

---

## 🎯 Use Cases

1. **Job Seekers**: Identify which skills to learn for target roles
2. **Career Changers**: Understand skill gaps when switching fields
3. **Students**: Align coursework with market demands
4. **Recruiters**: Understand current skill market trends
5. **Educators**: Design curricula based on industry needs

---

**Built with ❤️ using Apache Kafka, Spark, FastAPI, and spaCy**

For detailed setup instructions, see [docs/SETUP.md](docs/SETUP.md)
