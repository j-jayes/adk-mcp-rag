import os
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from google.genai import types
from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from .tools import PromptLoader, MCPTools

# Modifying here to try with agent tools.
from google.adk.tools.agent_tool import AgentTool
from .sub_agents.unit_conversion import unit_conversion_agent


# Load environment variables from .env file in the parent directory
load_dotenv('./docker/.env', override=True)

# Global variable to store agent and toolset
global_root_agent = None
global_toolset = None

# adding this to work with evals: 
agent = None


class Agents():
    """Manages agents"""

    def __init__(self):
        self.prompt_loaders = PromptLoader()
        self.prompt_configs = self.prompt_loaders._load_base_config()
        self.mcp_tools = MCPTools()

    async def get_tool_async(self):
        """Creates an ADK Agent equipped with tools from the MCP Server."""
        toolset = await self.mcp_tools.get_tools_async(os.getenv('QRANT_MCP_SSE'))
        return toolset

    def get_tool(self):
        """Synchronous version of get_tool_async."""
        return self.mcp_tools.get_tools(os.getenv('QRANT_MCP_SSE'))
    
    # --- RAG Agent Definition ---
    async def get_rag_agent_async(self):
        """Creates an ADK Agent equipped with tools from the MCP Server asynchronously."""
        toolset = await self.mcp_tools.get_tools_async(os.getenv('QRANT_MCP_SSE', 'http://localhost:8000/sse'))
        root_agent = LlmAgent(
            # model=LiteLlm(
            #     model='gpt-4o-mini', 
            # ),
            model='gemini-2.0-flash',
            name='ask_rag_agent',
            instruction=self.prompt_configs['ask_rag_agent']['instruction_prompt'],
            tools=[
                toolset,
                AgentTool(agent=unit_conversion_agent)
            ],
            generate_content_config=types.GenerateContentConfig(
                temperature=0.2,
            )
        )
        return root_agent, toolset
    
    def get_rag_agent(self):
        """Creates an ADK Agent equipped with tools from the MCP Server synchronously."""
        global global_root_agent, global_toolset
        
        # If agent already initialized, return it
        if global_root_agent is not None and global_toolset is not None:
            return global_root_agent, global_toolset
            
        # Use the persistent thread approach to get tools
        toolset = self.mcp_tools.get_tools(os.getenv('QRANT_MCP_SSE', 'http://localhost:8000/sse'))
        
        # Create the agent
        root_agent = LlmAgent(
            # model=LiteLlm(
            #     model='gpt-4o-mini', 
            # ),
            model='gemini-2.0-flash',
            name='ask_rag_agent',
            instruction=self.prompt_configs['ask_rag_agent']['instruction_prompt'],
            tools=[
                toolset,
                AgentTool(agent=unit_conversion_agent)
            ],
            generate_content_config=types.GenerateContentConfig(
                temperature=0.2,
            )
        )
        
        # Store in global variables for reuse
        global_root_agent = root_agent
        global_toolset = toolset
        
        return root_agent, toolset

# Initialize the agent using the persistent thread approach
try:
    # Try to get the agent synchronously
    agents = Agents()
    root_agent, toolset = agents.get_rag_agent()
    # Expose the agent instance at module level for `adk eval`
    agent = root_agent
except Exception as e:
    # Log the error but don't crash
    print(f"Error initializing agent: {e}")
    # Set empty values to prevent further errors
    root_agent = None
    toolset = None