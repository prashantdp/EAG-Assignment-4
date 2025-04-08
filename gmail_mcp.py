# mac_keynote_client.py
import os
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import asyncio
import google.generativeai as genai # Corrected import
from concurrent.futures import TimeoutError
import shlex # Needed if parameters might contain spaces
import sys

# Load environment variables from .env file
load_dotenv()

# Access your API key and initialize Gemini client correctly
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables or .env file")

# Configure the Generative AI client
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.0-flash') # Use a capable model


max_iterations = 5 # Increased max iterations for potentially more steps
last_response = None
iteration = 0
iteration_history = [] # Store history of calls and results


async def generate_with_timeout(prompt_parts: list, timeout=30): # Increased timeout
    """Generate content with a timeout using the configured model."""
    print(f"--- Starting LLM generation (Iteration {iteration + 1}) ---")
    # print(f"Sending Prompt:\n{prompt_parts}") # Debug: Print the full prompt being sent
    try:
        response = await asyncio.wait_for(
            model.generate_content_async(prompt_parts),
            timeout=timeout
        )
        # print(f"LLM Raw Response: {response}") # Debug: Print raw response
        print("--- LLM generation completed ---")
        return response
    except TimeoutError:
        print("--- LLM generation timed out! ---")
        raise
    except Exception as e:
        print(f"--- Error in LLM generation: {e} ---")
        # print(f"LLM Error Details: {getattr(e, 'response', 'No response object')}") # Debug errors
        raise


def reset_state():
    """Reset global variables"""
    global last_response, iteration, iteration_history
    last_response = None
    iteration = 0
    iteration_history = []
    print("--- Global state reset ---")


print("--- Global state reset ---")


async def main():
    reset_state()
    print("--- Starting main execution ---")
    try:
        print("Establishing connection to MCP server...")
        server_params = StdioServerParameters(
            # command=sys.executable, # Use sys.executable to ensure correct python interpreter
            command="uv",
            args=[
                "--directory",
                "/Users/deeptiprashant/Documents/Prashant/learning/Agentic AI/EAG/session4/gmail-mcp-server/src/",
                "run",
                "gmail",
                "--creds-file-path",
                "/Users/deeptiprashant/Documents/Prashant/learning/Agentic AI/EAG/session4/credentials.json",
                "--token-path",
                "/Users/deeptiprashant/Documents/Prashant/learning/Agentic AI/EAG/session4/token.json"
            ]  # Run the Gmail MCP server script
        )

        async with stdio_client(server_params) as (read, write):
            print("Connection established, creating session...")
            async with ClientSession(read, write) as session:
                print("Session created, initializing...")
                await session.initialize()

                print("Requesting tool list...")
                tools_result = await session.list_tools()
                tools = tools_result.tools
                print(f"Successfully retrieved {len(tools)} tools.")

                print("Creating system prompt...")
                tools_description = []
                for i, tool in enumerate(tools):
                    try:
                        params = tool.inputSchema.get('properties', {})
                        desc = getattr(tool, 'description', 'No description available')
                        name = getattr(tool, 'name', f'tool_{i}')
                        param_details = [f"{p_name}: {p_info.get('type', 'unknown')}" for p_name, p_info in params.items()]
                        params_str = ', '.join(param_details) if param_details else 'no parameters'
                        tools_description.append(f"{i+1}. {name}({params_str}) - {desc}")
                    except Exception as e:
                        print(f"Warning: Error processing tool {i} ({getattr(tool, 'name', 'unknown')}): {e}")
                        tools_description.append(f"{i+1}. Error processing tool {getattr(tool, 'name', 'unknown')}")

                tools_description_str = "\n".join(tools_description)
                print("--- Available Tools ---")
                print(tools_description_str)
                print("-----------------------")
                system_prompt = f"""
                You are an agent controlling Gmail on macOS. You have access to tools to interact with Gmail.

                Available tools:
                {tools_description_str}

                Your goal is to follow the user's request step-by-step.
                You MUST respond with EXACTLY ONE line in one of these formats (no additional text, explanations, or markdown formatting):

                1. --- Behavior Guidelines ---

                - Use FUNCTION_CALL syntax: e.g., 
                    FUNCTION_CALL: send-email 
                    ARGS: ["aaa","bbb","ccc"]
                - Arguments are passed separately in structured format (not inside the tool name).
                - Always confirm with the user before sending or deleting emails.
                - Respond conversationally when appropriate, otherwise use FUNCTION_CALLs.
                - Use FUNCTION_CALL followed by arguments in ARGS.
                - Do not include arguments in the FUNCTION_CALL line.

                2. --- When the entire user request is fully completed:---
                - FINAL_ANSWER: Task completed successfully
                
            
                Begin!
                """

                # Define the user's overall request
                user_query = "Send email to prashantraodp@gmail.com with subject MCP Test and body hello"
                print(f"\n--- User Query ---\n{user_query}\n------------------")

                global iteration, last_response, iteration_history

                current_prompt_parts = [system_prompt, f"\nUser Query: {user_query}"]

                while iteration < max_iterations:
                    print(f"\n<<< Iteration {iteration + 1} >>>")

                    # Add history to prompt (except for the very first turn)
                    if iteration_history:
                        history_str = "\n".join(iteration_history)
                        current_prompt_parts = [system_prompt, f"\nUser Query: {user_query}", f"\nHistory:\n{history_str}\n\nWhat is the next step?"]
                    else:
                        current_prompt_parts = [system_prompt, f"\nUser Query: {user_query}", "\nWhat is the first step?"]

                    try:
                        response = await generate_with_timeout(current_prompt_parts)
                        response_text = response.text.strip()
                        print(f"LLM Raw Response Line: '{response_text}'")  # Debug

                        # Sometimes models add ``` or markdown, try to strip it
                        if response_text.startswith("```") and response_text.endswith("```"):
                            response_text = response_text[3:-3].strip()
                        if response_text.startswith("`") and response_text.endswith("`"):
                            response_text = response_text[1:-1].strip()

                    except Exception as e:
                        print(f"Failed to get LLM response: {e}")
                        iteration_history.append(f"Iteration {iteration + 1}: Failed to get LLM response: {e}")
                        break  # Stop if LLM fails

                    if response_text.startswith("FUNCTION_CALL:"):
                        try:
                            # Parse the FUNCTION_CALL response
                            _, function_info = response_text.split(":", 1)
                            parts = function_info.split("ARGS:")
                            func_name = parts[0].strip()
                            if len(parts) > 1:
                                args_str = parts[1].strip()
                                params = eval(args_str)  # Convert ARGS string to a Python list
                            else:
                                params = []

                            print(f"Attempting to call: {func_name} with params: {params}")

                            # Find the tool in the available tools list
                            tool = next((t for t in tools if t.name == func_name), None)
                            if not tool:
                                raise ValueError(f"Unknown tool '{func_name}' requested by the LLM.")

                            # Prepare arguments based on the tool's input schema
                            arguments = {}
                            schema_properties = tool.inputSchema.get('properties', {})
                            expected_params = list(schema_properties.keys())

                            if len(params) != len(expected_params):
                                raise ValueError(
                                    f"Parameter count mismatch for tool '{func_name}'. "
                                    f"Expected {len(expected_params)} ({', '.join(expected_params)}), got {len(params)}."
                                )

                            for i, (param_name, param_info) in enumerate(schema_properties.items()):
                                value_str = params[i]
                                param_type = param_info.get('type', 'string')
                                try:
                                    if param_type == 'integer':
                                        arguments[param_name] = int(value_str)
                                    elif param_type == 'number':  # float
                                        arguments[param_name] = float(value_str)
                                    elif param_type == 'boolean':
                                        arguments[param_name] = value_str.lower() in ['true', '1']
                                    else:  # Default to string
                                        arguments[param_name] = value_str
                                except ValueError:
                                    raise ValueError(
                                        f"Could not convert parameter '{param_name}' (value: '{value_str}') "
                                        f"to expected type '{param_type}'."
                                    )

                            # Execute the tool with the prepared arguments
                            print(f"Executing MCP tool '{func_name}' with arguments: {arguments}")
                            result = await session.call_tool(func_name, arguments=arguments)
                            print(f"MCP Raw Result: {result}")  # Debug

                            # Extract text result
                            if result.content and isinstance(result.content, list) and hasattr(result.content[0], 'text'):
                                iteration_result = result.content[0].text
                            else:
                                iteration_result = "Tool executed but returned no standard text content."
                            print(f"Tool Result Text: {iteration_result}")

                            # Add to history
                            iteration_history.append(f"Iteration {iteration + 1}: Called {func_name}({arguments}). Result: {iteration_result}")
                            last_response = iteration_result  # Store for potential future context (though history is better)

                            # Check for errors reported by the tool itself
                            if "error" in iteration_result.lower():
                                print(f"Tool reported an error: {iteration_result}. Stopping execution.")
                                break

                        except Exception as e:
                            print(f"Error during function call processing: {e}")
                            import traceback
                            traceback.print_exc()  # Print full traceback for debugging
                            iteration_history.append(f"Iteration {iteration + 1}: Client Error processing '{response_text}': {e}")
                            break  # Stop on client-side processing errors
                        
    finally:
                            print("\n--- Final Execution History ---")
                            for line in iteration_history:
                                print(line)
                            print("-----------------------------")
                            reset_state()  # Ensure reset happens even on error
                            print("--- Main execution finished ---")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExecution interrupted by user.")
