# Skill Gap Radar v2.0 - Refactoring Summary

## 🎯 Project Overview

Complete system refactoring to transition from CSV-based job data with optional Hive storage to a real-time API-based architecture with Parquet-only storage and NLP-powered resume analysis.

---

## ✅ Completed Tasks

### 1. **Job Data Collection System** ✓

**File**: `spark_jobs/job_api_collector.py` (NEW - 280 lines)

**Features**:
- Multi-API integration:
  - **RemoteOK** (free, no authentication required)
  - **Adzuna** (requires ADZUNA_APP_ID, ADZUNA_APP_KEY)
  - **JSearch/RapidAPI** (requires JSEARCH_API_KEY)
- Unified job schema normalization
- Configurable collection interval (default: 300 seconds)
- Kafka streaming output to `job_postings` topic
- CLI arguments: `--query`, `--interval`, `--kafka-server`, `--kafka-topic`, `--once`

**Example Usage**:
```bash
# Free tier (RemoteOK only)
python spark_jobs/job_api_collector.py --query "data scientist" --interval 300

# With API keys (all sources)
export ADZUNA_APP_ID="your_id"
export ADZUNA_APP_KEY="your_key"
export JSEARCH_API_KEY="your_key"
python spark_jobs/job_api_collector.py --query "python developer" --interval 600
```

---

### 2. **Spark Streaming Processor** ✓

**File**: `spark_jobs/job_stream_processor.py` (COMPLETELY REWRITTEN)

**Changes**:
- ❌ **Removed**: All Hive imports and code (HiveManager, user_data_manager)
- ❌ **Removed**: CSV file processing logic
- ✅ **Added**: Kafka consumer for `job_postings` topic
- ✅ **Added**: Parquet output with partitioning by source and date
- ✅ **Added**: 30-second trigger intervals

**Data Output**:
- Raw jobs → `../data/processed_jobs/raw_jobs/` (partitioned by source, date)
- Skill demand → `../data/processed_jobs/skill_demand/`

**Integration**:
- Reads from Kafka using unified job schema
- Extracts skills using existing `skill_extractor` module
- Posts top 20 skills to dashboard via HTTP POST `http://localhost:8000/update`

---

### 3. **NLP-Based Resume Parser** ✓

**Files**: 
- `resume_processing/resume_parser.py` (NEW - 270 lines)
- `resume_processing/__init__.py` (NEW)

**Features**:
- **PDF-only** support via `pdfplumber` library
- **spaCy NLP** (`en_core_web_sm` model) for intelligent extraction
- **80+ curated skills** across categories:
  - Programming languages (Python, Java, JavaScript, etc.)
  - Frameworks (React, Django, TensorFlow, etc.)
  - Databases (PostgreSQL, MongoDB, Redis, etc.)
  - Cloud platforms (AWS, Azure, GCP)
  - Big data tools (Spark, Hadoop, Kafka, etc.)
  - DevOps (Docker, Kubernetes, Terraform, etc.)

**Extraction Methods**:
1. Direct keyword matching
2. Noun phrase extraction
3. Named entity recognition

**API**:
```python
from resume_processing.resume_parser import ResumeParser

parser = ResumeParser()
result = parser.analyze_resume('resume.pdf')

# Returns:
{
    "success": True,
    "text": "...",
    "skills": ["python", "sql", "docker", ...],
    "skill_count": 12,
    "word_count": 450
}
```

---

### 4. **Skill Gap Analyzer** ✓

**Files**:
- `analysis/skill_gap.py` (NEW - 280 lines)
- `analysis/__init__.py` (NEW)

**Features**:
- Priority-based classification:
  - **High Priority**: >30% market demand (critical skills)
  - **Medium Priority**: 10-30% demand (important skills)
  - **Low Priority**: <10% demand (nice to have)
- Gap percentage calculation
- Overall assessment (Excellent/Good/Moderate/Significant gap)
- Top 5 prioritized learning recommendations

**API**:
```python
from analysis.skill_gap import SkillGapAnalyzer

market_skills = {"python": 100, "sql": 80, "spark": 60, "aws": 50}
analyzer = SkillGapAnalyzer(market_skills)

gap = analyzer.analyze_gap(
    resume_skills=["python", "java"], 
    top_n=50
)

# Returns:
{
    "matching_skills": ["python"],
    "missing_skills": {
        "high_priority": [{"skill": "spark", "demand": 60, "priority": "High"}],
        "medium_priority": [{"skill": "sql", "demand": 80, "priority": "High"}],
        "low_priority": []
    },
    "gap_percentage": 50.0,
    "overall_assessment": "Moderate skill gap",
    "top_priorities": ["sql", "spark", "aws", ...],
    "recommendations": [...]
}
```

---

### 5. **Refactored Dashboard Server** ✓

**File**: `dashboard/server.py` (COMPLETELY REWRITTEN - 450 lines → 400+ lines)

**Changes**:
- ❌ **Removed**: All Hive-related imports and code
- ❌ **Removed**: Old imports from `spark_jobs/resume_parser`
- ❌ **Removed**: User profile management endpoints
- ❌ **Removed**: CSV-based data processing
- ✅ **Added**: Import from new `resume_processing` package
- ✅ **Added**: Import from new `analysis` package
- ✅ **Added**: NEW endpoint `GET /market-skills`
- ✅ **Added**: NEW endpoint `POST /resume-analysis`

**New Endpoints**:

#### GET /market-skills
- Returns top N demanded skills from Parquet files
- Falls back to in-memory data if Parquet not available
- Query parameter: `top_n` (default: 50)

```bash
curl http://localhost:8000/market-skills?top_n=20
```

#### POST /resume-analysis
- Accepts **PDF only** (enforced validation)
- Extracts skills using NLP-based parser
- Compares against market demand from Parquet
- Returns prioritized gap analysis with recommendations

```bash
curl -X POST http://localhost:8000/resume-analysis \
  -F "file=@resume.pdf"
```

**Legacy Endpoints** (for backward compatibility):
- `/api/skill_demand` → calls `/market-skills`
- `/api/upload_resume` → calls `/resume-analysis`

**WebSocket** `/ws`:
- Real-time skill demand updates
- Broadcasts to all connected clients when Spark processor posts updates

---

### 6. **Updated Dependencies** ✓

**File**: `requirements.txt` (UPDATED)

**Changes**:
- ❌ **Removed**: PyPDF2, python-docx (old resume parsing)
- ❌ **Removed**: pyhive, thrift, sasl (Hive dependencies - implied)
- ✅ **Added**: pdfplumber (PDF text extraction)
- ✅ **Added**: spacy (NLP processing)

**Installation**:
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

---

### 7. **Comprehensive Documentation** ✓

**Files**:
- `docs/SETUP.md` (COMPLETELY REWRITTEN - 631 lines → 500+ lines)
- `README.md` (COMPLETELY REWRITTEN)

**SETUP.md Contents**:
- System architecture diagram
- Step-by-step installation (5-minute quick start)
- API key configuration (RemoteOK free, Adzuna/JSearch paid)
- Kafka installation guide
- Usage examples for all components
- Troubleshooting section
- Testing procedures
- API reference

**README.md Contents**:
- Project overview and features
- Architecture diagrams (data flow, resume analysis flow)
- Quick start guide
- API configuration
- Usage examples with code
- Tech stack summary
- Project structure
- Key features explanation
- Testing procedures
- Troubleshooting
- Version history (v1.0.0 → v2.0.0)

---

## 📁 File Changes Summary

### Created Files (6 new)
1. `spark_jobs/job_api_collector.py` - Multi-API job collector
2. `resume_processing/resume_parser.py` - NLP-based PDF parser
3. `resume_processing/__init__.py` - Package init
4. `analysis/skill_gap.py` - Priority-based gap analyzer
5. `analysis/__init__.py` - Package init
6. `dashboard/server.py` - Refactored dashboard (replaced old version)

### Modified Files (3)
1. `spark_jobs/job_stream_processor.py` - Removed Hive, added Parquet
2. `requirements.txt` - Updated dependencies
3. `docs/SETUP.md` - Complete rewrite for new architecture
4. `README.md` - Complete rewrite with v2.0 features

### Backup Files Created (3)
1. `dashboard/server_old_backup.py` - Original server with Hive
2. `docs/SETUP_OLD_backup.md` - Original setup guide
3. `README_OLD_backup.md` - Original README

---

## 🏗️ New System Architecture

```
┌─────────────────────────────────────────────────┐
│     Job APIs (RemoteOK, Adzuna, JSearch)       │
└────────────────────┬────────────────────────────┘
                     │ job_api_collector.py
                     ▼
┌─────────────────────────────────────────────────┐
│        Apache Kafka (job_postings topic)       │
└────────────────────┬────────────────────────────┘
                     │ job_stream_processor.py
                     ▼
┌─────────────────────────────────────────────────┐
│     Spark Streaming (30-second triggers)       │
│     - Extract skills                           │
│     - Aggregate counts                         │
└────────────────────┬────────────────────────────┘
                     │
            ┌────────┴────────┐
            ▼                 ▼
    ┌─────────────┐   ┌──────────────┐
    │  raw_jobs/  │   │ skill_demand/│
    │  (Parquet)  │   │  (Parquet)   │
    └─────────────┘   └──────────────┘
            │                 │
            └────────┬────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│       FastAPI Dashboard (server.py)            │
│  - GET /market-skills                          │
│  - POST /resume-analysis                       │
│  - WS /ws (real-time updates)                  │
└─────────────────────────────────────────────────┘
```

### Resume Analysis Flow

```
PDF Upload
    ↓
pdfplumber (text extraction)
    ↓
spaCy NLP (en_core_web_sm)
    ↓
resume_processing.ResumeParser
    ↓
Extracted skills: ["python", "sql", "docker"]
    ↓
Read market demand from Parquet
    ↓
analysis.SkillGapAnalyzer
    ↓
Prioritized results:
  - Matching: ["python", "sql"]
  - Missing (High): ["spark", "aws"]
  - Missing (Medium): ["kubernetes"]
  - Recommendations: ["spark", "aws", ...]
```

---

## 🎯 Key Improvements

### 1. Real-Time Data
- **OLD**: Static CSV files
- **NEW**: Live API feeds updated every 5 minutes

### 2. Better Skill Extraction
- **OLD**: Regex pattern matching
- **NEW**: NLP with noun phrases + entities

### 3. Simplified Storage
- **OLD**: Optional Hive (complex setup)
- **NEW**: Parquet-only (portable, no dependencies)

### 4. Prioritized Recommendations
- **OLD**: Simple list of missing skills
- **NEW**: High/Medium/Low priority + learning path

### 5. Focused Resume Support
- **OLD**: PDF, DOCX, TXT (brittle)
- **NEW**: PDF only (robust, most common)

---

## 📊 Testing Checklist

### Component Tests
- [ ] Test Spark: `python spark_jobs/test_spark.py`
- [ ] Test resume parser:
  ```python
  from resume_processing.resume_parser import ResumeParser
  parser = ResumeParser()
  result = parser.analyze_resume('sample.pdf')
  print(result['skills'])
  ```
- [ ] Test gap analyzer:
  ```python
  from analysis.skill_gap import SkillGapAnalyzer
  analyzer = SkillGapAnalyzer({"python": 100, "sql": 80})
  gap = analyzer.analyze_gap(["python"])
  print(gap)
  ```

### Integration Tests
- [ ] Kafka running: `jps | grep Kafka`
- [ ] Topic created: `kafka-topics.sh --list --bootstrap-server localhost:9092`
- [ ] Job collector working: `python spark_jobs/job_api_collector.py --query "test" --once`
- [ ] Stream processor working: Check `data/processed_jobs/` for Parquet files
- [ ] Dashboard accessible: Open `http://localhost:8000`
- [ ] API endpoints:
  - [ ] `curl http://localhost:8000/health`
  - [ ] `curl http://localhost:8000/market-skills?top_n=10`
  - [ ] `curl -X POST http://localhost:8000/resume-analysis -F "file=@resume.pdf"`

### End-to-End Test
```bash
# Terminal 1: Start job collector
python spark_jobs/job_api_collector.py --query "data scientist" --interval 300

# Terminal 2: Start stream processor  
python spark_jobs/job_stream_processor.py

# Terminal 3: Start dashboard
python dashboard/server.py

# Browser: Open http://localhost:8000, upload resume, view results
```

---

## 🚀 Deployment Steps

### Prerequisites
```bash
# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm

# Set API keys (optional, for Adzuna/JSearch)
export ADZUNA_APP_ID="your_app_id"
export ADZUNA_APP_KEY="your_app_key"
export JSEARCH_API_KEY="your_api_key"
```

### Start Kafka
```bash
cd $KAFKA_HOME

# Start Zookeeper
bin/zookeeper-server-start.sh config/zookeeper.properties &

# Start Kafka
bin/kafka-server-start.sh config/server.properties &

# Create topic
bin/kafka-topics.sh --create --topic job_postings \
  --bootstrap-server localhost:9092 \
  --partitions 3 --replication-factor 1
```

### Start Services
```bash
cd /home/pakhi/skill-gap-radar

# Terminal 1: Job collector (free tier)
python spark_jobs/job_api_collector.py --query "data scientist" --interval 300

# Terminal 2: Stream processor
python spark_jobs/job_stream_processor.py

# Terminal 3: Dashboard
python dashboard/server.py
```

### Access
- **Dashboard**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (FastAPI auto-generated)
- **Health Check**: http://localhost:8000/health

---

## 📝 Known Limitations & Future Enhancements

### Current Limitations
1. RemoteOK is free but limited to ~50 jobs per query
2. Adzuna/JSearch require paid API keys for production use
3. PDF parsing works best with text-based PDFs (not scanned images)
4. Skill extraction limited to 80+ predefined skills
5. No historical trend analysis (only current data)

### Future Enhancements
1. Add more job APIs (Indeed, LinkedIn, Glassdoor)
2. Integrate transformer models (BERT) for better skill extraction
3. Add skill popularity trends over time
4. Support resume format recommendations
5. Multi-language support (currently English only)
6. Add user authentication and profile management
7. Email notifications for new high-priority skills
8. Export gap analysis to PDF report

---

## 🔍 Troubleshooting Common Issues

### Issue: spaCy model not found
```bash
python -m spacy download en_core_web_sm
```

### Issue: Kafka connection refused
```bash
# Check if running
jps | grep -E "Kafka|QuorumPeer"

# Check port
netstat -an | grep 9092

# Restart if needed
cd $KAFKA_HOME
bin/kafka-server-start.sh config/server.properties
```

### Issue: No data in dashboard
1. Check job collector is running: `ps aux | grep job_api_collector`
2. Check Kafka messages: `kafka-console-consumer.sh --topic job_postings ...`
3. Check stream processor logs
4. Check Parquet files: `ls -lh data/processed_jobs/`

### Issue: PDF parsing fails
- Ensure PDF is text-based (not scanned)
- Try: `pdfplumber.open('resume.pdf').pages[0].extract_text()`
- Check file is valid: `file resume.pdf`

---

## 📞 Support & Documentation

- **Setup Guide**: See `docs/SETUP.md`
- **README**: See `README.md`
- **Code Comments**: All modules have docstrings
- **API Docs**: http://localhost:8000/docs (when server running)

---

## 🎓 Architecture Decisions

### Why Remove Hive?
- Complex setup with Python 3.12 compatibility issues
- Overkill for this use case
- Parquet provides similar benefits (columnar storage, compression)
- Better portability (no external dependencies)

### Why PDF Only?
- 95% of resumes are PDF format
- pdfplumber more robust than PyPDF2
- Simplified parsing logic
- Better error handling

### Why spaCy over Regex?
- Captures multi-word skills ("machine learning")
- Handles context better ("React" vs "react to")
- Extensible (can add custom entities)
- Industry standard for NLP

### Why 30-second Triggers?
- Balance between latency and resource usage
- Allows batching for efficiency
- Good for dashboard update frequency
- Configurable if needed

---

**Version**: 2.0.0  
**Date**: 2024  
**Status**: ✅ Complete and Ready for Testing

---

## 🎉 Summary

Successfully refactored Skill Gap Radar from CSV-based system with optional Hive to a real-time API-based architecture with:

- ✅ 3 API sources (RemoteOK, Adzuna, JSearch)
- ✅ NLP-powered resume parsing (pdfplumber + spaCy)
- ✅ Priority-based skill gap analysis
- ✅ Parquet-only storage (no Hive)
- ✅ Modular package structure
- ✅ Comprehensive documentation
- ✅ All Hive code removed
- ✅ All CSV logic removed
- ✅ New FastAPI endpoints
- ✅ Updated requirements

**Lines of Code**: ~1,200+ new/refactored lines
**Files Changed**: 10 files (6 new, 4 modified)
**Documentation**: 2 complete rewrites (README, SETUP)
