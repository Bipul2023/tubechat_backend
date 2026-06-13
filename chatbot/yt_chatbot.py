# myapp/services.py
import os
import asyncio

from urllib.parse import urlparse, parse_qs
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFaceEndpointEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnableParallel
from langchain_core.messages import HumanMessage, AIMessage
from operator import itemgetter
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
from qdrant_client.http.models import Distance, VectorParams
from chatbot.chatbot_utils import extract_video_id, get_youtube_transcript
from dotenv import load_dotenv

load_dotenv()

# QDRANT_HOST=os.getenv("QDRANT_HOST")
# QDRANT_PORT=os.getenv("QDRANT_PORT")

# QDRANT_CLIENT = QdrantClient(url=f"http://{QDRANT_HOST}:{QDRANT_PORT}")
QDRANT_CLIENT = QdrantClient(
    url=os.getenv("QDRANT_ENDPOINT"),
    api_key=os.getenv("QDRANT_APIKEY"),
)

# Hugging Face model for embedding generation
HF_TOKEN=os.getenv("HF_TOKEN")
print("Initializing global embeddings model...")
# global_embeddings = HuggingFaceEmbeddings(
#     model_name="sentence-transformers/all-MiniLM-L6-v2",
#     model_kwargs={"device": "cpu", "token": HF_TOKEN}
# )
global_embeddings = HuggingFaceEndpointEmbeddings(
    model="sentence-transformers/all-MiniLM-L6-v2",
    huggingfacehub_api_token=HF_TOKEN,
)
print("Embeddings model initialized.")



async def aget_or_create_vectorstore(video_id: str):
    """Checks if a collection exists in Qdrant. If not, fetches transcript and creates it."""
    
    # Sanitize the video ID to make a clean Qdrant collection name
    # e.g., "dQw4w9WgXcQ" becomes "video_dQw4w9WgXcQ"
    collection_name = f"video_{video_id}".replace("-", "_")

    # 1. Check if the collection already exists in Qdrant
    if QDRANT_CLIENT.collection_exists(collection_name):
        print(f"Loading existing database for {video_id}...")
        return QdrantVectorStore(
            client=QDRANT_CLIENT,
            collection_name=collection_name,
            embedding=global_embeddings
        )

    # 2. Otherwise, fetch data and create it from scratch
    print(f"Creating new database for {video_id}...")
    
    # Create the empty Qdrant collection explicitly setting 384 dimensions for MiniLM
    QDRANT_CLIENT.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )

    try:
        transcript = await get_youtube_transcript(video_id)
    except Exception as e:
        # Clean up the empty collection if transcript fetching fails
        QDRANT_CLIENT.delete_collection(collection_name)
        raise ValueError(f"Could not fetch transcript: {e}")

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunks = splitter.split_text(transcript)

    # 3. Initialize the VectorStore and insert the chunked texts
    vectorstore = QdrantVectorStore(
        client=QDRANT_CLIENT,
        collection_name=collection_name,
        embedding=global_embeddings
    )

    await asyncio.to_thread(
        lambda: vectorstore.add_texts(texts=chunks)
    )
    
    return vectorstore

def format_docs(docs):
    return "\n\n".join([doc.page_content for doc in docs])


# Lowered temperature to 0.2 to prevent hallucinations and keep answers factual
model = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0.2)
async def _abuild_chain(url, query, raw_history):
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Invalid YouTube URL")

    # 1. Convert JSON history into LangChain Message objects (limit to last 10 messages to keep context window focused)
    chat_history = []
    recent_history = raw_history[-10:] if len(raw_history) > 10 else raw_history
    for msg in recent_history:
        if msg.get("role") == "user":
            chat_history.append(HumanMessage(content=msg.get("content")))
        elif msg.get("role") in ["ai", "assistant"]:
            chat_history.append(AIMessage(content=msg.get("content")))

    # 2. Get Vector Database
    vectorstore = await aget_or_create_vectorstore(video_id)
    
    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 5, "fetch_k": 20, "lambda_mult": 0.5}
    )

    # 3. Build an Enhanced System Prompt
    system_prompt = """You are an intelligent YouTube video assistant embedded in a web chat application. 
    Use the provided video transcript context to answer the user's question accurately.

    CRITICAL FORMATTING RULES:
    1. STRICT SPACING: You MUST use double newlines (\n\n) between every single paragraph, heading, and bullet point. Never bundle text together.
    2. STRUCTURE: Use bullet points (-) for lists and break down complex information into easily digestible parts.
    3. MARKDOWN: Use **bold** text to emphasize key terms.
    4. LINKS: If the user asks for the video link, output it as: [Watch Video]({url})
    5. NO HALLUCINATION: If the answer is not in the context, explicitly say: "I don't have enough information from the video to answer that."

    Context:
    {context}"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}")
    ])

    
    
    parallel_chain = RunnableParallel(
        context=itemgetter("question") | retriever | format_docs,
        question=itemgetter("question"),
        chat_history=itemgetter("chat_history"),
        url=itemgetter("url") # Extract URL from the input dictionary
    )

    chain = parallel_chain | prompt | model | StrOutputParser()
    return chain, chat_history

async def process_chat_request(url, query, raw_history):
    chain, chat_history = await _abuild_chain(url, query, raw_history)
    
    # 4. Invoke Chain with URL included
    result = await chain.ainvoke({
        "question": query,
        "chat_history": chat_history,
        "url": url
    })
    
    return result

async def stream_chat_request(url, query, raw_history):
    chain, chat_history = await _abuild_chain(url, query, raw_history)
    
    # Yield tokens as they arrive, passing the URL
    async for chunk in chain.astream({
        "question": query,
        "chat_history": chat_history,
        "url": url
    }):
        yield chunk



if __name__ == "__main__":
    async def main():
        chat_history = []
        url = input("Enter Youtube URL: ")
        while True:
            if url == "exit":
                break
            query = input("You: ")
            if query == "exit":
                break
            result = await process_chat_request(url, query, chat_history)
            print("AI:", result)
            chat_history.append({"role": "user", "content": query})
            chat_history.append({"role": "ai", "content": result})
            print(chat_history)
            print("="*60)
            
    asyncio.run(main())