import os
from typing import List, Optional
from dotenv import load_dotenv
from models import LogEntry, Student, User
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "ccl")

print("MONGO_URI:", MONGO_URI)
class MongoCloudDB:
    def __init__(self):
        if not MONGO_URI:
            raise RuntimeError("MONGO_URI must be set to use MongoCloudDB")

        self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        try:
            self.client.server_info()
        except ServerSelectionTimeoutError as e:
            raise RuntimeError("Unable to connect to MongoDB. Check MONGO_URI.") from e

        self.db = self.client[MONGO_DB_NAME]
        self.general_info = self.db["general_info"]
        self.students = self.db["students"]
        self.learned_facts = self.db["learned_facts"]
        self.admin_logs = self.db["admin_logs"]
        self.users = self.db["users"]

        # Ensure useful indexes
        self.students.create_index("secret_key", unique=True)
        self.users.create_index("username", unique=True)
        self.general_info.create_index("topic", unique=True)

    def retrieve_context(self, chat_history: List[dict]) -> str:
        recent_user_msgs = [m["content"].lower() for m in chat_history if m["role"] == "user"][-10:]
        combined_text = " ".join(recent_user_msgs)
        context_pieces = []

        # 1. Match General Info
        for doc in self.general_info.find():
            topic = doc.get("topic", "").lower()
            if topic and topic in combined_text:
                context_pieces.append(f"[General Info] {doc.get('info')}")

        # 2. Match Private Student Information (if exact secret key was sent)
        combined_words = set(
            combined_text.replace(",", " ").replace(".", " ").replace("!", " ").split()
        )
        student = self.students.find_one({"secret_key": {"$in": list(combined_words)}})
        if student:
            context_pieces.append(
                f"[Private Data Auth Success] Name: {student.get('name')}, Major: {student.get('major')}, GPA: {student.get('gpa')}, Enrolled: {student.get('enrollment_year')}"
            )

        # 3. Supply Learned Facts
        facts = list(self.learned_facts.find())
        if facts:
            facts_str = " ".join(f"Fact {i+1}: {f.get('fact')}" for i, f in enumerate(facts))
            context_pieces.append(f"[Learned Facts to remember about User] {facts_str}")

        return " | ".join(context_pieces) if context_pieces else "No specific database information found."

    def add_general_info(self, topic: str, info: str):
        self.general_info.update_one(
            {"topic": topic.lower()},
            {"$set": {"topic": topic.lower(), "info": info}},
            upsert=True,
        )

    def add_student(self, student: Student):
        self.students.update_one(
            {"secret_key": student.secret_key},
            {"$set": student.dict()},
            upsert=True,
        )

    def add_learned_fact(self, fact: str):
        self.learned_facts.insert_one({"fact": fact})

    def get_learned_facts(self) -> List[dict]:
        return list(self.learned_facts.find({}, {"_id": 0}))

    def get_students_count(self) -> int:
        return self.students.count_documents({})

    def save_invalid_log(self, log_entry: LogEntry):
        self.admin_logs.insert_one(log_entry.dict())

    def get_admin_logs(self) -> List[LogEntry]:
        docs = list(self.admin_logs.find())
        results = []
        for doc in docs:
            d = {k: v for k, v in doc.items() if k != "_id"}
            results.append(LogEntry(**d))
        return results

    def delete_log(self, log_id: str):
        self.admin_logs.delete_one({"id": log_id})

    def add_user(self, user: User):
        self.users.update_one({"username": user.username}, {"$set": user.dict()}, upsert=True)

    def get_user(self, username: str) -> Optional[User]:
        doc = self.users.find_one({"username": username})
        if not doc:
            return None
        return User(**{k: v for k, v in doc.items() if k != "_id"})


class MockCloudDB:
    def __init__(self):
        # General Information (Expanded DB)
        self.general_info = {
            "admissions": "Admissions are open until August 1st. Requirements: GPA 3.0+.",
            "library": "Library hours are 8 AM to 10 PM on weekdays, 10 AM to 6 PM on weekends.",
            "tuition": "Tuition is $15,000 per semester.",
            "dorm": "Dorm applications open in May. No pets allowed.",
            "hackathon": "Annual Tech Hackathon is scheduled for October 15th in the Main Hall.",
            "football": "Homecoming football game is on November 5th.",
            "career fair": "Spring Career Fair is March 20th in the Student Union.",
            "graduation": "Graduation ceremony is on May 30th at the Stadium.",
            "orientation": "Freshman orientation starts August 20th.",
            "cafeteria": "Main cafeteria is open from 7 AM to 8 PM daily with vegan options."
        }
        
        # Private Student Database (10 Students)
        self.students = {
            "SEC111": Student(name="Nitesh", secret_key="SEC111", gpa=3.8, major="Computer Science", enrollment_year=2024),
            "SEC222": Student(name="Alice", secret_key="SEC222", gpa=3.5, major="Biology", enrollment_year=2023),
            "SEC333": Student(name="Bob", secret_key="SEC333", gpa=2.9, major="Business", enrollment_year=2022),
            "SEC444": Student(name="Charlie", secret_key="SEC444", gpa=3.9, major="Engineering", enrollment_year=2025),
            "SEC555": Student(name="Diana", secret_key="SEC555", gpa=3.2, major="Arts", enrollment_year=2024),
            "SEC666": Student(name="Eve", secret_key="SEC666", gpa=4.0, major="Mathematics", enrollment_year=2023),
            "SEC777": Student(name="Frank", secret_key="SEC777", gpa=2.5, major="Physics", enrollment_year=2022),
            "SEC888": Student(name="Grace", secret_key="SEC888", gpa=3.7, major="Chemistry", enrollment_year=2025),
            "SEC999": Student(name="Heidi", secret_key="SEC999", gpa=3.4, major="History", enrollment_year=2024),
            "SEC000": Student(name="Ivan", secret_key="SEC000", gpa=3.1, major="Philosophy", enrollment_year=2023)
        }
        
        self.learned_facts = []  # Dynamic memory
        self.admin_logs = []
        self.users = {}

    def retrieve_context(self, chat_history: List[dict]) -> str:
        # Collect recent context to see if secret keys or facts apply (increased to 10 messages)
        recent_user_msgs = [m["content"].lower() for m in chat_history if m["role"] == "user"][-10:]
        combined_text = " ".join(recent_user_msgs)
        context_pieces = []
        
        # 1. Match General Info
        for key, fact in self.general_info.items():
            if key in combined_text:
                context_pieces.append(f"[General Info] {fact}")
                
        # 2. Match Private Student Information (if exact secret key was sent)
        # We need to split the user messages into words to avoid substring matching (e.g. SEC22 matching SEC222)
        combined_words = set(combined_text.replace(",", " ").replace(".", " ").replace("!", " ").split())
        for secret_key, student in self.students.items():
            if secret_key.lower() in combined_words:
                context_pieces.append(f"[Private Data Auth Success] Name: {student.name}, Major: {student.major}, GPA: {student.gpa}, Enrolled: {student.enrollment_year}")
                
        # 3. Supply Learned Facts
        if self.learned_facts:
            facts_str = " ".join(f"Fact {i+1}: {fact}" for i, fact in enumerate(self.learned_facts))
            context_pieces.append(f"[Learned Facts to remember about User] {facts_str}")
            
        return " | ".join(context_pieces) if context_pieces else "No specific database information found."

    def add_general_info(self, topic: str, info: str):
        self.general_info[topic.lower()] = info
        
    def add_student(self, student: Student):
        self.students[student.secret_key] = student
        
    def add_learned_fact(self, fact: str):
        self.learned_facts.append(fact)

    def get_learned_facts(self) -> List[dict]:
        return [{"fact": fact} for fact in self.learned_facts]

    def get_students_count(self) -> int:
        return len(self.students)

    def save_invalid_log(self, log_entry: LogEntry):
        self.admin_logs.append(log_entry)

    def get_admin_logs(self):
        return self.admin_logs
        
    def delete_log(self, log_id: str):
        self.admin_logs = [log for log in self.admin_logs if log.id != log_id]

    def add_user(self, user: User):
        self.users[user.username] = user

    def get_user(self, username: str) -> Optional[User]:
        return self.users.get(username)

# Singleton instance for DB (prefers MongoDB if configured)
try:
    db = MongoCloudDB()
    print("[database] Connected to MongoDB")
except Exception as e:
    print(f"[database] MongoDB not available ({e}). Using fallback in-memory DB.")
    db = MockCloudDB()