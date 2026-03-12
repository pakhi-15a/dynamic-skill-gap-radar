"""
Spark Streaming Job Processor - Reads job postings from Kafka, extracts skills,
and saves to Parquet files
"""

import requests
import pyspark
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, lower, current_timestamp, to_date
from pyspark.sql.types import StructType, StructField, StringType
import json
import sys
import os
from pathlib import Path
from datetime import datetime

# Add current directory to path to import modules
sys.path.append(str(Path(__file__).parent))

try:
    from skill_extractor import TECH_SKILLS, extract_skills
    print("✓ Successfully imported skill_extractor module")
    USING_SKILL_EXTRACTOR = True
except ImportError:
    print("⚠ Warning: Could not import skill_extractor, using fallback skills list")
    USING_SKILL_EXTRACTOR = False
    # Fallback to basic skills list
    TECH_SKILLS = [
        "python", "sql", "spark", "java", "scala", "aws", "azure", "gcp",
        "machine learning", "deep learning", "tensorflow", "pytorch", "docker",
        "kubernetes", "airflow", "kafka", "hadoop", "tableau", "power bi",
        "r", "pandas", "numpy", "scikit-learn", "git", "linux", "flask",
        "django", "react", "node.js", "mongodb", "postgresql", "mysql"
    ]

# Initialize Spark Session
print("Initializing Spark Session...")


def resolve_kafka_package() -> str:
    """Resolve a Spark Kafka connector package compatible with current PySpark."""
    override = os.getenv("SPARK_KAFKA_PACKAGE")
    if override:
        return override

    spark_version = pyspark.__version__.split("+")[0]
    major_version = int(spark_version.split(".")[0])
    scala_suffix = "2.13" if major_version >= 4 else "2.12"

    return f"org.apache.spark:spark-sql-kafka-0-10_{scala_suffix}:{spark_version}"


KAFKA_PACKAGE = resolve_kafka_package()
print(f"Using Kafka connector package: {KAFKA_PACKAGE}")

spark = SparkSession.builder \
    .appName("JobStreamProcessor") \
    .config("spark.jars.packages", KAFKA_PACKAGE) \
    .config("spark.sql.streaming.checkpointLocation", "/tmp/spark_checkpoint") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

print("✓ Spark Streaming started")
print("✓ Using Parquet storage (Hive removed)")
print("=" * 60)

# Output directory for Parquet files
OUTPUT_DIR = "../data/processed_jobs/"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Store current skill demand for API access
current_skill_demand = {}

# Define schema for job postings (matching job_api_collector.py unified schema)
job_schema = StructType([
    StructField("title", StringType(), True),
    StructField("company", StringType(), True),
    StructField("description", StringType(), True),
    StructField("source", StringType(), True),
    StructField("location", StringType(), True),
    StructField("salary", StringType(), True),
    StructField("url", StringType(), True),
    StructField("timestamp", StringType(), True)
])

# Read from Kafka
print("Connecting to Kafka topic 'job_postings'...")
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "localhost:9092") \
    .option("subscribe", "job_postings") \
    .option("startingOffsets", "latest") \
    .load()

# Parse JSON from Kafka
print("Parsing Kafka messages...")
jobs_df = df.select(
    from_json(col("value").cast("string"), job_schema).alias("job")
).select("job.*")

# Add processing timestamp
jobs_df = jobs_df.withColumn("processed_at", current_timestamp())
jobs_df = jobs_df.withColumn("date", to_date(col("processed_at")))


def process_batch_and_save(batch_df, batch_id):
    """
    Process each batch: extract skills, save to Parquet, send to dashboard
    """
    global current_skill_demand
    
    print(f"\n{'='*60}")
    print(f"Processing Batch {batch_id} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    if batch_df.isEmpty():
        print("⚠ Empty batch, skipping...")
        return
    
    # Show batch info
    count = batch_df.count()
    print(f"✓ Batch size: {count} jobs")
    
    # Save raw jobs to Parquet (partitioned by source and date)
    try:
        batch_df.write \
            .mode("append") \
            .partitionBy("source", "date") \
            .parquet(OUTPUT_DIR + "raw_jobs/")
        print(f"✓ Saved {count} jobs to Parquet (raw_jobs/)")
    except Exception as e:
        print(f"✗ Error saving to Parquet: {e}")
    
    # Extract skills from batch
    skill_counts = {}
    
    batch_data = batch_df.select("title", "company", "description", "source").collect()
    
    for row in batch_data:
        try:
            # Concatenate title and description for skill extraction
            job_text = ""
            if row.title:
                job_text += str(row.title).lower() + " "
            if row.description:
                job_text += str(row.description).lower() + " "
            
            # Extract skills
            if USING_SKILL_EXTRACTOR:
                job_skills = extract_skills(job_text)
                for skill, count in job_skills.items():
                    skill_counts[skill] = skill_counts.get(skill, 0) + count
            else:
                # Fallback: simple pattern matching
                for skill in TECH_SKILLS:
                    if skill.lower() in job_text:
                        skill_counts[skill] = skill_counts.get(skill, 0) + 1
        
        except Exception as e:
            print(f"✗ Error extracting skills from job: {e}")
            continue
    
    # Save skill demand to Parquet
    if skill_counts:
        try:
            # Convert to DataFrame
            skill_data = [
                {"skill": skill, "count": count, "timestamp": datetime.now().isoformat()}
                for skill, count in skill_counts.items()
            ]
            
            skill_df = spark.createDataFrame(skill_data)
            skill_df.write \
                .mode("append") \
                .parquet(OUTPUT_DIR + "skill_demand/")
            
            print(f"✓ Saved {len(skill_counts)} skill counts to Parquet (skill_demand/)")
        except Exception as e:
            print(f"✗ Error saving skills to Parquet: {e}")
    
    # Get top 20 skills for dashboard
    top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    
    if top_skills:
        skills = [s[0].title() for s in top_skills]
        counts = [s[1] for s in top_skills]
        
        # Update global skill demand
        current_skill_demand = dict(zip(skills, counts))
        
        print(f"\nTop 10 Skills:")
        for i, (skill, count) in enumerate(top_skills[:10], 1):
            print(f"  {i:2d}. {skill.title():<20} {count:>4} mentions")
        
        # Send to dashboard via WebSocket
        data = {
            "skills": skills,
            "counts": counts
        }
        
        try:
            response = requests.post(
                "http://localhost:8000/update",
                json=data,
                timeout=2
            )
            if response.status_code == 200:
                print(f"✓ Sent skill data to dashboard")
            else:
                print(f"⚠ Dashboard responded with status {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"⚠ Could not reach dashboard: {e}")
    else:
        print("⚠ No skills extracted from batch")
    
    print(f"{'='*60}\n")


# Start streaming query with foreachBatch
print("\nStarting streaming query...")
print(f"Output directory: {OUTPUT_DIR}")
print(f"Checkpoint: /tmp/spark_checkpoint")
print("\nWaiting for jobs from Kafka...")
print("(Press Ctrl+C to stop)\n")

query = jobs_df.writeStream \
    .foreachBatch(process_batch_and_save) \
    .outputMode("append") \
    .trigger(processingTime='30 seconds') \
    .start()

# Wait for termination
try:
    query.awaitTermination()
except KeyboardInterrupt:
    print("\n\nStopping stream processor...")
    query.stop()
    spark.stop()
    print("✓ Stream processor stopped")


print("Stream processor running... Waiting for data from Kafka...")
query.awaitTermination()