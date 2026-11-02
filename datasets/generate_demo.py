"""Create synthetic fixtures only in datasets/demo. Never writes real input CSVs."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "demo"
SKILLS = [
    ("git", "Git & version control", "Engineering", "Branches, commits and collaborative workflows"),
    ("linux", "Linux fundamentals", "Infrastructure", "Shell, processes and permissions"),
    ("python", "Python", "Programming", "Core language, data structures and modules"),
    ("javascript", "JavaScript", "Programming", "Language fundamentals and asynchronous execution"),
    ("sql", "SQL", "Data", "Relational queries and data modeling"),
    ("http", "HTTP & networking", "Engineering", "Client-server protocols and network fundamentals"),
    ("typescript", "TypeScript", "Programming", "Static types for JavaScript applications"),
    ("react", "React", "Frontend", "Component architecture and state management"),
    ("testing", "Software testing", "Quality", "Test design, unit tests and integration tests"),
    ("api", "API design", "Backend", "Resource modeling and service contracts"),
    ("fastapi", "FastAPI", "Backend", "Typed Python web APIs"),
    ("postgres", "PostgreSQL", "Data", "Indexes, transactions and relational design"),
    ("docker", "Docker", "Infrastructure", "Container builds and reproducible environments"),
    ("cicd", "CI/CD", "Infrastructure", "Automated quality gates and delivery pipelines"),
    ("kubernetes", "Kubernetes", "Infrastructure", "Container orchestration and service operations"),
    ("statistics", "Statistics", "Data Science", "Probability, estimation and inference"),
    ("pandas", "pandas & NumPy", "Data Science", "Vectorized data preparation and analysis"),
    ("ml", "Machine learning", "Data Science", "Model fitting, validation and evaluation"),
    ("nlp", "NLP", "Data Science", "Text representations and language models"),
    ("etl", "Data pipelines", "Data", "Reliable extraction, transformation and loading"),
    ("spark", "Apache Spark", "Data", "Distributed data processing"),
    ("security", "Application security", "Engineering", "Threat modeling, authentication and secure coding"),
    ("architecture", "System design", "Engineering", "Scalability, reliability and service boundaries"),
    ("observability", "Observability", "Infrastructure", "Metrics, traces and operational diagnosis"),
]
EDGES = [("javascript", "typescript"), ("typescript", "react"), ("http", "api"), ("python", "fastapi"), ("api", "fastapi"),
 ("sql", "postgres"), ("linux", "docker"), ("git", "cicd"), ("testing", "cicd"), ("docker", "cicd"),
 ("docker", "kubernetes"), ("http", "kubernetes"), ("python", "pandas"), ("statistics", "ml"), ("pandas", "ml"),
 ("ml", "nlp"), ("sql", "etl"), ("python", "etl"), ("etl", "spark"), ("http", "security"),
 ("api", "architecture"), ("postgres", "architecture"), ("linux", "observability"), ("http", "observability")]
ROLES = {
 "Backend Developer": ["python", "api", "fastapi", "postgres", "testing", "git", "architecture"],
 "Frontend Developer": ["javascript", "typescript", "react", "http", "testing", "git"],
 "Data Analyst": ["sql", "statistics", "pandas", "git"],
 "Data Scientist": ["python", "statistics", "pandas", "ml", "nlp", "git"],
 "Data Engineer": ["python", "sql", "postgres", "etl", "spark", "docker", "git"],
 "DevOps Engineer": ["linux", "docker", "kubernetes", "cicd", "observability", "git"],
 "QA Engineer": ["testing", "python", "api", "cicd", "git"],
}

def write(name, headers, rows):
    path = ROOT / name
    if path.exists():
        raise SystemExit(f"Refusing to overwrite {path}")
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)

if __name__ == "__main__":
    ROOT.mkdir(exist_ok=True)
    write("skills.csv", ["skill_id", "name", "category", "description"], SKILLS)
    write("skill_groups.csv", ["group_id", "name"], [("core", "Core engineering alternatives (ambiguous)")])
    write("skill_mapping.csv", ["skill_id", "group_id"], [(s, "core") for s in ["git", "linux", "http"]])
    write("skill_levels.csv", ["level", "name"], enumerate(["None", "Awareness", "Working", "Independent", "Advanced"]))
    write("prerequisites.csv", ["prerequisite_id", "skill_id"], EDGES)
    write("skill_dependents.csv", ["skill_id", "dependent_id"], EDGES)
    write("course_skills.csv", ["course_id", "skill_id"], [("demo-python", "python"), ("demo-data", "sql")])
    requirements = [(role, level, skill, "", 2 if level == "Junior" else 3) for role, skills in ROLES.items() for level in ["Junior", "Middle"] for skill in skills]
    requirements.append(("Backend Developer", "Middle", "", "core", 2))
    write("role_requirements.csv", ["role", "level", "skill_id", "group_id", "required_level"], requirements)
    for file, factor in [("role_skill_weights.csv", 1), ("skill_weights_by_role_final_v2.csv", 1.2)]:
        write(file, ["role", "skill_id", "weight"], [(role, skill[0], round(factor * (2 if skill[0] in core else 1), 2)) for role, core in ROLES.items() for skill in SKILLS])
