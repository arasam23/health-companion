import os
from dotenv import load_dotenv
from typing import List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

# We will use gemini-3.0-pro-exp (or whichever equivalent the user can access)
LLM_MODEL = "gemini-2.5-pro" 
EMBEDDING_MODEL = "models/gemini-embedding-001"

llm = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=0.2)
embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)

KNOWLEDGE_BASE_DIR = "knowledge_base"
CHROMA_DB_DIR = "./chroma_db"

def initialize_vector_store() -> Chroma:
    """Loads documents, splits them, and stores them in a local Chroma vector database."""
    print(f"Loading documents from {KNOWLEDGE_BASE_DIR}...")
    
    # Load text files
    txt_loader = DirectoryLoader(KNOWLEDGE_BASE_DIR, glob="**/*.txt", loader_cls=TextLoader)
    txt_docs = txt_loader.load()
    print(f"Loaded {len(txt_docs)} text documents.")
    
    # Load PDF files
    pdf_loader = DirectoryLoader(KNOWLEDGE_BASE_DIR, glob="**/*.pdf", loader_cls=PyPDFLoader)
    pdf_docs = pdf_loader.load()
    print(f"Loaded {len(pdf_docs)} PDF documents.")
    
    documents = txt_docs + pdf_docs
    
    if not documents:
        print("No documents found in knowledge base. Creating empty store.")
        return Chroma(embedding_function=embeddings, persist_directory=CHROMA_DB_DIR)

    # Split text into chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(documents)
    
    print(f"Loaded {len(documents)} documents, split into {len(splits)} chunks.")
    
    # Create and persist Vector DB
    vectorstore = Chroma.from_documents(
        documents=splits,
        embedding=embeddings,
        persist_directory=CHROMA_DB_DIR
    )
    return vectorstore

def get_vector_store() -> Chroma:
    """Retrieves the existing vector store or initializes a new one if it doesn't exist."""
    if os.path.exists(CHROMA_DB_DIR):
        return Chroma(persist_directory=CHROMA_DB_DIR, embedding_function=embeddings)
    else:
        return initialize_vector_store()

def generate_strategy(user_query: str, user_context: str = "") -> str:
    """
    Given a user query and their current biometric/meal context, 
    queries the vector database and generates a personalized strategy.
    """
    vectorstore = get_vector_store()
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    
    template = """You are an expert personalized Health Companion and Ayurvedic Strategist.
    Use the following pieces of retrieved context from the user's health knowledge base to formulate a strategy or answer the question.
    Also consider the user's current health logs/context provided below.
    If you don't know the answer, just say that you don't know based on the provided texts. Do not make up medical advice.

    Provided Knowledge Base Context:
    {context}

    User's Current Health Context (From Database Logs):
    {user_context}

    Question/Query: {question}

    Answer:"""
    
    prompt = ChatPromptTemplate.from_template(template)
    
    # Formatting function for retrieved docs
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    # Construct the RAG chain
    rag_chain = (
        {"context": retriever | format_docs, "user_context": RunnablePassthrough(), "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    # Invoke the chain passing the dict manually since RunnablePassthrough is tricky with multiple arguments
    # Instead, we will construct the input dictionary explicitly:
    rag_chain_input = {
        "user_context": user_context,
        "question": user_query
    }
    
    # We need a slightly different pipeline structure to handle the dictionary input correctly for the retriever
    retrieved_docs = retriever.invoke(user_query)
    formatted_context = format_docs(retrieved_docs)
    
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({
        "context": formatted_context,
        "user_context": user_context,
        "question": user_query
    })
    
    return response

if __name__ == "__main__":
    # Initialize the store manually if run directly
    initialize_vector_store()
    print("Vector store initialized successfully.")
