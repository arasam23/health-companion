import os
import sqlite3
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from db import get_connection

load_dotenv()

# We will use gemini-3.0-pro-exp (or whichever equivalent the user can access via API key)
# For now, default to gemini-2.5-pro or 1.5 if 3.0 preview isn't widely available in the SDK yet.
LLM_MODEL = os.getenv("HEALTH_LLM_MODEL", "gemini-pro-latest")

llm = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=0)

# --- Define Pydantic Schemas for Structured Output ---

class BiometricsOutput(BaseModel):
    weight_lb: Optional[float] = Field(description="Weight in pounds")
    bmi: Optional[float] = Field(description="Body Mass Index")
    metabolic_age: Optional[int] = Field(description="Metabolic Age in years")
    bmr_kcal: Optional[int] = Field(description="Basal Metabolic Rate in kcal")
    body_fat_percentage: Optional[float] = Field(description="Body fat percentage")
    subcutaneous_fat_percentage: Optional[float] = Field(description="Subcutaneous fat percentage")
    visceral_fat_rating: Optional[int] = Field(description="Visceral fat rating")
    skeletal_muscle_percentage: Optional[float] = Field(description="Skeletal muscle percentage")
    muscle_mass_lb: Optional[float] = Field(description="Muscle mass in pounds")
    fat_free_body_weight_lb: Optional[float] = Field(description="Fat free body weight in pounds")
    bone_mass_lb: Optional[float] = Field(description="Bone mass in pounds")
    body_water_percentage: Optional[float] = Field(description="Body water percentage")
    protein_percentage: Optional[float] = Field(description="Protein percentage")
    status_tags: Optional[dict] = Field(description="Key-value pairs of the metric name and its status label (e.g. 'High', 'Acceptable', 'Standard').")

class MealOutput(BaseModel):
    items: str = Field(description="A comma separated string of food items identified in the image.")
    calories: int = Field(description="Estimated total calories of the meal.")

# --- Extraction Functions ---

def extract_biometrics(image_path: str) -> Optional[BiometricsOutput]:
    """Uses Gemini to extract biometrics from an image."""
    import base64
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")
        
    structured_llm = llm.with_structured_output(BiometricsOutput)
    
    message = HumanMessage(
        content=[
            {"type": "text", "text": "Extract the biometric data from this screenshot and return it as JSON."},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
            }
        ]
    )
    
    try:
        result = structured_llm.invoke([message])
        return result
    except Exception as e:
        print(f"Error extracting biometrics: {e}")
        return None

def extract_meal(image_path: str) -> Optional[MealOutput]:
    """Uses Gemini to extract meal info from an image."""
    import base64
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")
        
    structured_llm = llm.with_structured_output(MealOutput)
    
    message = HumanMessage(
        content=[
            {"type": "text", "text": "Analyze this meal image. Identify the items and provide a total calorie estimate."},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
            }
        ]
    )
    
    try:
        result = structured_llm.invoke([message])
        return result
    except Exception as e:
        print(f"Error extracting meal: {e}")
        return None

# --- Database Insertion ---

def log_biometrics(data: BiometricsOutput) -> str:
    """Inserts biometrics into SQLite."""
    import json
    conn = get_connection()
    cursor = conn.cursor()
    
    tags_json = json.dumps(data.status_tags) if data.status_tags else None
    
    cursor.execute('''
        INSERT INTO biometrics (
            weight_lb, bmi, metabolic_age, bmr_kcal, body_fat_percentage,
            subcutaneous_fat_percentage, visceral_fat_rating, skeletal_muscle_percentage,
            muscle_mass_lb, fat_free_body_weight_lb, bone_mass_lb,
            body_water_percentage, protein_percentage, status_tags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.weight_lb, data.bmi, data.metabolic_age, data.bmr_kcal, data.body_fat_percentage,
        data.subcutaneous_fat_percentage, data.visceral_fat_rating, data.skeletal_muscle_percentage,
        data.muscle_mass_lb, data.fat_free_body_weight_lb, data.bone_mass_lb,
        data.body_water_percentage, data.protein_percentage, tags_json
    ))
    
    conn.commit()
    conn.close()
    return "Biometrics successfully logged."

def log_meal(data: MealOutput) -> str:
    """Inserts meal data into SQLite."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO meals (items, calories, notes) VALUES (?, ?, ?)
    ''', (data.items, data.calories, "Pending review by Brain/Strategist"))
    
    conn.commit()
    conn.close()
    return f"Meal logged: {data.items} ({data.calories} kcal)"

if __name__ == "__main__":
    # Simple test placeholder
    print("Logger module ready.")
