"""
Skill Gap Analysis - Compare resume skills against market demand
"""

from typing import List, Dict, Set
from pathlib import Path
import os


class SkillGapAnalyzer:
    """Analyze skill gaps between resume and market demand"""
    
    def __init__(self, market_skills: Dict[str, int] = None):
        """
        Initialize analyzer with market demand data
        
        Args:
            market_skills: Dictionary of {skill_name: demand_count}
        """
        self.market_skills = market_skills or {}
    
    def set_market_demand(self, market_skills: Dict[str, int]):
        """Update market demand data"""
        self.market_skills = market_skills
    
    def analyze_gap(self, resume_skills: List[str], top_n: int = 50) -> Dict:
        """
        Analyze skill gap between resume and market demand
        
        Args:
            resume_skills: List of skills from resume
            top_n: Number of top market skills to consider
            
        Returns:
            Dictionary with gap analysis results
        """
        # Convert resume skills to set for faster lookup
        resume_skills_set = {skill.lower() for skill in resume_skills}
        
        # Get top N demanded skills from market
        sorted_market = sorted(
            self.market_skills.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]
        
        market_skills_dict = dict(sorted_market)
        market_skills_set = {skill.lower() for skill in market_skills_dict.keys()}
        
        # Find matching skills
        matching_skills = []
        for skill in resume_skills:
            skill_lower = skill.lower()
            if skill_lower in market_skills_set:
                # Find original cased version from market
                for market_skill in market_skills_dict.keys():
                    if market_skill.lower() == skill_lower:
                        matching_skills.append({
                            "skill": market_skill,
                            "demand_count": market_skills_dict[market_skill],
                            "status": "In Demand"
                        })
                        break
        
        # Find missing skills (in market but not in resume)
        missing_skills = []
        for market_skill, count in market_skills_dict.items():
            if market_skill.lower() not in resume_skills_set:
                # Categorize priority based on demand
                if count > len(sorted_market) * 0.3:  # Top 30%
                    priority = "High"
                elif count > len(sorted_market) * 0.1:  # Top 10-30%
                    priority = "Medium"
                else:
                    priority = "Low"
                
                missing_skills.append({
                    "skill": market_skill,
                    "demand_count": count,
                    "priority": priority,
                    "recommendation": self._generate_recommendation(market_skill, priority, count)
                })
        
        # Sort missing skills by demand
        missing_skills.sort(key=lambda x: x['demand_count'], reverse=True)
        
        # Calculate gap percentage
        total_market_skills = len(market_skills_dict)
        missing_count = len(missing_skills)
        gap_percentage = (missing_count / total_market_skills * 100) if total_market_skills > 0 else 0
        
        # Generate summary
        return {
            "resume_skills": resume_skills,
            "resume_skill_count": len(resume_skills),
            "market_total_skills": total_market_skills,
            "matching_skills": matching_skills,
            "matching_count": len(matching_skills),
            "missing_skills": missing_skills,
            "missing_count": missing_count,
            "gap_percentage": round(gap_percentage, 2),
            "overall_assessment": self._generate_assessment(gap_percentage, len(matching_skills)),
            "top_priorities": missing_skills[:10]  # Top 10 skills to learn
        }
    
    def _generate_recommendation(self, skill: str, priority: str, count: int) -> str:
        """Generate learning recommendation for a skill"""
        recommendations = {
            "High": f"Highly recommended - {skill} is mentioned in many job postings ({count} times). Learning this skill could significantly improve your job prospects.",
            "Medium": f"Consider learning - {skill} appears regularly in job postings ({count} times) and would be a valuable addition.",
            "Low": f"Optional skill - {skill} is mentioned in some positions ({count} times). Nice to have but not critical."
        }
        return recommendations.get(priority, "Consider adding this skill to your toolkit.")
    
    def _generate_assessment(self, gap_percentage: float, matching_count: int) -> str:
        """Generate overall assessment message"""
        if gap_percentage < 20 and matching_count >= 10:
            return "Excellent! Your skills are well-aligned with market demand."
        elif gap_percentage < 40 and matching_count >= 5:
            return "Good skill set! Some areas for improvement identified."
        elif gap_percentage < 60:
            return "Moderate skill gap. Consider focusing on high-priority missing skills."
        else:
            return "Significant skill gap detected. Focus on learning in-demand skills."
    
    def get_skill_match_rate(self, resume_skills: List[str]) -> float:
        """
        Calculate percentage of resume skills that match market demand
        
        Args:
            resume_skills: List of skills from resume
            
        Returns:
            Match rate as percentage (0-100)
        """
        if not resume_skills or not self.market_skills:
            return 0.0
        
        resume_skills_set = {skill.lower() for skill in resume_skills}
        market_skills_set = {skill.lower() for skill in self.market_skills.keys()}
        
        matches = len(resume_skills_set.intersection(market_skills_set))
        match_rate = (matches / len(resume_skills)) * 100
        
        return round(match_rate, 2)
    
    def suggest_learning_path(self, resume_skills: List[str], max_skills: int = 5) -> List[Dict]:
        """
        Suggest a prioritized learning path
        
        Args:
            resume_skills: List of current skills
            max_skills: Maximum number of skills to suggest
            
        Returns:
            List of suggested skills with learning order
        """
        analysis = self.analyze_gap(resume_skills)
        missing = analysis['missing_skills']
        
        # Get high priority skills first
        high_priority = [s for s in missing if s['priority'] == 'High']
        medium_priority = [s for s in missing if s['priority'] == 'Medium']
        
        # Build learning path
        learning_path = []
        
        # Add high priority skills first
        for i, skill_info in enumerate(high_priority[:max_skills], 1):
            learning_path.append({
                "order": i,
                "skill": skill_info['skill'],
                "priority": skill_info['priority'],
                "demand": skill_info['demand_count'],
                "reason": f"High market demand ({skill_info['demand_count']} mentions)"
            })
        
        # Fill remaining with medium priority
        remaining = max_skills - len(learning_path)
        if remaining > 0:
            for i, skill_info in enumerate(medium_priority[:remaining], len(learning_path) + 1):
                learning_path.append({
                    "order": i,
                    "skill": skill_info['skill'],
                    "priority": skill_info['priority'],
                    "demand": skill_info['demand_count'],
                    "reason": f"Growing demand ({skill_info['demand_count']} mentions)"
                })
        
        return learning_path


def compare_resume_to_market(resume_skills: List[str], market_skills: Dict[str, int]) -> Dict:
    """
    Convenience function to analyze skill gap
    
    Args:
        resume_skills: List of skills from resume
        market_skills: Dictionary of market demand {skill: count}
        
    Returns:
        Skill gap analysis results
    """
    analyzer = SkillGapAnalyzer(market_skills)
    return analyzer.analyze_gap(resume_skills)


if __name__ == "__main__":
    """Test the skill gap analyzer"""
    
    # Sample market demand data
    market_skills = {
        "Python": 850,
        "SQL": 720,
        "Machine Learning": 600,
        "AWS": 550,
        "Docker": 480,
        "Kubernetes": 420,
        "Java": 400,
        "React": 380,
        "TensorFlow": 350,
        "Django": 320,
        "PostgreSQL": 300,
        "MongoDB": 280,
        "Git": 750,
        "Linux": 650,
        "Spark": 290
    }
    
    # Sample resume skills
    resume_skills = [
        "Python", "SQL", "Git", "Linux", "Flask",
        "JavaScript", "HTML", "CSS", "REST API"
    ]
    
    print("Skill Gap Analysis Demo")
    print("=" * 60)
    print(f"\nResume Skills ({len(resume_skills)}):")
    print(", ".join(resume_skills))
    
    print(f"\nMarket Demand (Top {len(market_skills)} skills)")
    
    # Analyze
    analyzer = SkillGapAnalyzer(market_skills)
    analysis = analyzer.analyze_gap(resume_skills, top_n=15)
    
    print(f"\n{'='*60}")
    print("ANALYSIS RESULTS")
    print(f"{'='*60}")
    
    print(f"\nOverall Assessment:")
    print(f"  {analysis['overall_assessment']}")
    
    print(f"\nStatistics:")
    print(f"  - Resume Skills: {analysis['resume_skill_count']}")
    print(f"  - Matching Skills: {analysis['matching_count']}")
    print(f"  - Missing Skills: {analysis['missing_count']}")
    print(f"  - Gap Percentage: {analysis['gap_percentage']}%")
    
    print(f"\n✓ Matching Skills ({len(analysis['matching_skills'])}):")
    for skill_info in analysis['matching_skills']:
        print(f"  • {skill_info['skill']:<20} (Demand: {skill_info['demand_count']})")
    
    print(f"\n✗ Top 10 Missing Skills:")
    for i, skill_info in enumerate(analysis['top_priorities'], 1):
        print(f"  {i:2d}. {skill_info['skill']:<20} [{skill_info['priority']:>6}] (Demand: {skill_info['demand_count']})")
    
    print(f"\nSuggested Learning Path:")
    learning_path = analyzer.suggest_learning_path(resume_skills, max_skills=5)
    for item in learning_path:
        print(f"  {item['order']}. {item['skill']:<20} - {item['reason']}")
    
    print(f"\n{'='*60}")
