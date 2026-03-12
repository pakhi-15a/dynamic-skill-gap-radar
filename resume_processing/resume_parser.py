"""
Resume Parser - Extract text from PDF and extract skills using NLP
Uses pdfplumber for PDF extraction and spaCy for NLP
"""

import pdfplumber
import spacy
from typing import List, Dict, Set
import re
from pathlib import Path


class ResumeParser:
    """Parse PDF resumes and extract skills using NLP"""
    
    def __init__(self):
        """Initialize spaCy NLP model"""
        try:
            self.nlp = spacy.load("en_core_web_sm")
            print("✓ Loaded spaCy model: en_core_web_sm")
        except OSError:
            print("✗ spaCy model 'en_core_web_sm' not found")
            print("  Install with: python -m spacy download en_core_web_sm")
            raise
        
        # Comprehensive skill dictionary
        self.skill_keywords = {
            # Programming Languages
            "Python", "Java", "JavaScript", "C++", "C#", "Go", "Rust", "Swift",
            "Kotlin", "TypeScript", "Ruby", "PHP", "R", "Scala", "Perl", "Shell",
            
            # Web Frameworks
            "React", "Angular", "Vue.js", "Django", "Flask", "FastAPI", "Spring",
            "Node.js", "Express", "Next.js", "Laravel", "Rails", "ASP.NET",
            
            # Data Science & ML
            "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
            "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "Pandas", "NumPy",
            "Matplotlib", "Seaborn", "OpenCV", "NLTK", "SpaCy", "Hugging Face",
            
            # Databases
            "SQL", "MySQL", "PostgreSQL", "MongoDB", "Redis", "Cassandra",
            "Oracle", "SQLite", "DynamoDB", "Elasticsearch", "Neo4j",
            
            # Cloud & DevOps
            "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Jenkins", "GitLab",
            "CircleCI", "Terraform", "Ansible", "CloudFormation", "Prometheus",
            
            # Big Data
            "Spark", "Hadoop", "Kafka", "Airflow", "Flink", "Hive", "Presto",
            "Databricks", "Snowflake", "Redshift", "BigQuery",
            
            # Tools & Technologies
            "Git", "Linux", "Bash", "REST API", "GraphQL", "gRPC", "Microservices",
            "CI/CD", "Agile", "Scrum", "JIRA", "Tableau", "Power BI", "Looker",
            
            # Soft Skills
            "Leadership", "Communication", "Problem Solving", "TeamWork",
            "Project Management", "Critical Thinking", "Analytical Skills"
        }
        
        # Convert to lowercase for matching
        self.skill_keywords_lower = {skill.lower() for skill in self.skill_keywords}
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extract text from PDF file using pdfplumber
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text as string
        """
        try:
            text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            
            if not text.strip():
                raise ValueError("No text extracted from PDF")
            
            return text.strip()
        
        except Exception as e:
            raise Exception(f"Error extracting text from PDF: {e}")
    
    def extract_skills(self, text: str) -> List[str]:
        """
        Extract technical skills from text using NLP and pattern matching
        
        Args:
            text: Resume text
            
        Returns:
            List of extracted skills
        """
        skills = set()
        text_lower = text.lower()
        
        # Method 1: Direct keyword matching (case-insensitive)
        for skill in self.skill_keywords:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(skill.lower()) + r'\b'
            if re.search(pattern, text_lower):
                skills.add(skill)
        
        # Method 2: NLP-based extraction
        doc = self.nlp(text)
        
        # Extract noun phrases that might be skills
        for chunk in doc.noun_chunks:
            chunk_text = chunk.text.lower().strip()
            
            # Check if the chunk matches any known skill
            if chunk_text in self.skill_keywords_lower:
                # Find the original cased version
                for skill in self.skill_keywords:
                    if skill.lower() == chunk_text:
                        skills.add(skill)
                        break
            
            # Check for partial matches (e.g., "Python programming" → "Python")
            for skill in self.skill_keywords:
                if skill.lower() in chunk_text:
                    skills.add(skill)
            
        # Method 3: Extract entities that look like technologies
        for ent in doc.ents:
            if ent.label_ in ["PRODUCT", "ORG", "TECH"]:  # Common tech labels
                ent_text = ent.text.strip()
                if ent_text in self.skill_keywords:
                    skills.add(ent_text)
        
        return sorted(list(skills))
    
    def analyze_resume(self, pdf_path: str) -> Dict:
        """
        Complete resume analysis: extract text and skills
        
        Args:
            pdf_path: Path to PDF resume
            
        Returns:
            Dictionary with extracted text and skills
        """
        try:
            # Extract text
            text = self.extract_text_from_pdf(pdf_path)
            
            # Extract skills
            skills = self.extract_skills(text)
            
            # Calculate statistics
            word_count = len(text.split())
            
            return {
                "success": True,
                "text": text,
                "skills": skills,
                "skill_count": len(skills),
                "word_count": word_count,
                "file_path": pdf_path
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "skills": [],
                "skill_count": 0,
                "word_count": 0,
                "file_path": pdf_path
            }


# Standalone functions for backward compatibility
def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF file"""
    parser = ResumeParser()
    return parser.extract_text_from_pdf(pdf_path)


def extract_skills(text: str) -> List[str]:
    """Extract skills from text"""
    parser = ResumeParser()
    return parser.extract_skills(text)


def analyze_resume(pdf_path: str) -> Dict:
    """Analyze resume and return skills"""
    parser = ResumeParser()
    return parser.analyze_resume(pdf_path)


if __name__ == "__main__":
    """Test the resume parser"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python resume_parser.py <path_to_resume.pdf>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    if not Path(pdf_path).exists():
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)
    
    if not pdf_path.lower().endswith('.pdf'):
        print("Error: Only PDF files are supported")
        sys.exit(1)
    
    print(f"Analyzing resume: {pdf_path}\n")
    
    result = analyze_resume(pdf_path)
    
    if result["success"]:
        print(f"✓ Successfully analyzed resume")
        print(f"\nStatistics:")
        print(f"  - Word count: {result['word_count']}")
        print(f"  - Skills found: {result['skill_count']}")
        print(f"\nExtracted Skills:")
        for i, skill in enumerate(result['skills'], 1):
            print(f"  {i:2d}. {skill}")
        
        print(f"\nText Preview (first 300 chars):")
        print(f"  {result['text'][:300]}...")
    else:
        print(f"✗ Error: {result['error']}")
