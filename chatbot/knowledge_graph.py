import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from typing import List
from .chatbot_utils import get_youtube_transcript

# Set up logging for production readiness
logger = logging.getLogger(__name__)

async def generate_knowledge_graph(video_id: str) -> dict:
    """Fetches the transcript and extracts entities and relationships to form a dynamic knowledge graph."""
    try:
        logger.info(f"Fetching transcript for video ID: {video_id}")
        transcript = await get_youtube_transcript(video_id)
        logger.info("Transcript fetched successfully.")
    except Exception as e:
        logger.error(f"Transcript fetch failed for {video_id}: {e}")
        raise ValueError(f"Could not fetch transcript for knowledge graph: {e}")

    # Use a standard, valid Gemini 1.5 model. (Flash is perfect for fast extraction)
    kg_model = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite", 
        temperature=0.1
    )
    
    # Define the schema so the LLM includes the 'group' field, which react-force-graph uses for colors
    class Node(BaseModel):
        id: str = Field(description="Unique identifier for the node")
        label: str = Field(description="Display label for the node")
        group: int = Field(description="An integer representing the category or cluster of the node (e.g., 1, 2, 3) to color-code it")

    class Edge(BaseModel):
        source: str = Field(description="ID of the source node")
        target: str = Field(description="ID of the target node")
        label: str = Field(description="Relationship label between source and target")

    class KnowledgeGraph(BaseModel):
        nodes: List[Node] = Field(description="List of nodes in the graph")
        edges: List[Edge] = Field(description="List of edges representing relationships")

    # Use LangChain's built-in JSON parser with the schema
    json_parser = JsonOutputParser(pydantic_object=KnowledgeGraph)
    
    system_prompt = """You are an expert AI data extractor. Analyze the provided YouTube video transcript and build a Knowledge Graph.

    STEP 1: Identify the video genre and adapt your extraction strategy:
    - Educational/Tech: Extract concepts and their dependencies.
    - History/Narrative: Extract people, places, and events.
    - How-To/Tutorial: Extract tools, ingredients, and sequential steps.
    - Podcast/Debate: Extract core arguments and claims.

    STEP 2: Extract a maximum of 30 nodes and 40 edges to keep the graph readable.
    
    STEP 3: Return the output strictly matching the following JSON schema.
    
    {format_instructions}
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Transcript: {transcript}")
    ])

    # Chain the prompt, model, and the JSON parser together
    chain = prompt | kg_model | json_parser
    
    # Safe truncation (100k chars is well within Gemini 1.5's 1M-2M context, 
    # but good for keeping latency and costs down).
    max_chars = 100000
    truncated_transcript = transcript[:max_chars]

    try:
        # Pass the format instructions generated automatically by JsonOutputParser
        graph_data = await chain.ainvoke({
            "transcript": truncated_transcript,
            "format_instructions": json_parser.get_format_instructions()
        })
        
        logger.info("Knowledge Graph generated successfully.")
        return graph_data
        
    except Exception as e:
        logger.error(f"Failed to generate or parse knowledge graph: {e}")
        raise ValueError("Failed to parse knowledge graph data from AI.")