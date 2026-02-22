import os
from strategist import generate_strategy

if __name__ == "__main__":
    if not os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") == "your_api_key_here":
        print("Please set your GEMINI_API_KEY in the .env file before running this test.")
        exit(1)

    print("Testing Strategist Agent RAG pipeline...")
    
    # Mock user context from Database
    mock_db_context = """
    Recent Logs:
    - Weight: 185.5 lb, Body Fat: 15.2%
    - Meal: 2 slices pizza, 1 soda (Estimated 800 kcal)
    """
    
    query = "Based on my recent logs, what should I eat for dinner to align with ayurvedic principles, and at what time?"
    
    print("\nQuerying:")
    print(f"User Context: {mock_db_context.strip()}")
    print(f"Question: {query}")
    print("\n--- Generating Strategy ---")
    
    try:
        response = generate_strategy(user_query=query, user_context=mock_db_context)
        print("\nResponse:\n")
        print(response)
    except Exception as e:
        print(f"Failed to generate strategy: {e}")
