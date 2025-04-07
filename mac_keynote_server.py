# mac_keynote_server.py
import subprocess
import shlex
import sys
import time
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

# Instantiate an MCP server client
mcp = FastMCP("KeynoteController")

# Helper function to run AppleScript
def run_applescript(script: str) -> tuple[bool, str]:
    """Runs an AppleScript command and returns success status and output/error."""
    try:
        # Use subprocess.run for better control and capturing output/errors
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            check=False, # Don't raise exception on non-zero exit code
            timeout=15 # Add a timeout
        )
        if result.returncode == 0:
            print(f"AppleScript Success: Ran script ending with... {script[-50:]}")
            print(f"AppleScript Output: {result.stdout.strip()}")
            return True, result.stdout.strip()
        else:
            print(f"AppleScript Error (Return Code {result.returncode}): Ran script ending with... {script[-50:]}")
            print(f"AppleScript Stderr: {result.stderr.strip()}")
            return False, f"Error executing AppleScript (Code {result.returncode}): {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        print(f"AppleScript Error: Timeout expired for script ending with... {script[-50:]}")
        return False, "Error: AppleScript command timed out."
    except Exception as e:
        print(f"AppleScript Error: Exception for script ending with... {script[-50:]}")
        print(f"Exception details: {str(e)}")
        return False, f"Error running AppleScript: {str(e)}"

@mcp.tool()
async def open_keynote() -> dict:
    """Opens the Keynote application."""
    print("CALLED: open_keynote()")
    try:
        # Use 'open -a' which is standard for macOS
        result = subprocess.run(['open', '-a', 'Keynote'], check=True)
        time.sleep(2) # Give Keynote time to launch
        return {
            "content": [TextContent(type="text", text="Keynote opened successfully.")]
        }
    except FileNotFoundError:
         return {
            "content": [TextContent(type="text", text="Error: Keynote application not found.")]
        }
    except Exception as e:
        return {
            "content": [TextContent(type="text", text=f"Error opening Keynote: {str(e)}")]
        }

@mcp.tool()
async def create_blank_keynote_slide() -> dict:
    """Creates a new Keynote document (if none open) and ensures a blank slide exists."""
    print("CALLED: create_blank_keynote_slide()")
    script = """
    tell application "Keynote"
        activate
        if not (exists document 1) then
            -- Choose a basic theme, e.g., "White" or "Black". Theme names might vary by Keynote version/language.
            -- If unsure, check theme names in Keynote's chooser.
            try
                 make new document with properties {document theme:theme "White"}
            on error -- Fallback if theme name is wrong
                 make new document
            end try
            delay 1 -- Wait for document to be created
        end if

        tell document 1
            if not (exists slide 1) then
                -- Add a blank slide if none exist (e.g., if user closed the default first slide)
                make new slide with properties {base layout:slide layout "Blank"}
            else
                -- Or just ensure the first slide is selected and maybe clear it (optional)
                 set current slide to slide 1
                 -- Optional: Delete existing shapes on the first slide
                 -- delete every shape of slide 1
            end if
             return "Blank slide ensured in front document."
        end tell
    end tell
    """
    success, message = run_applescript(script)
    return {
        "content": [TextContent(type="text", text=message)]
    }

@mcp.tool()
async def draw_keynote_rectangle(x1: int, y1: int, width: int, height: int) -> dict:
    """
    Draws a rectangle shape on the current Keynote slide.
    Coordinates (x1, y1) are the top-left corner.
    Width and height determine the size.
    NOTE: Position and size are in points; you may need to adjust values significantly.
    """
    print(f"CALLED: draw_keynote_rectangle(x1={x1}, y1={y1}, width={width}, height={height})")
    script = f"""
    tell application "Keynote"
        if not (exists document 1) then
            return "Error: No Keynote document is open."
        end if
        tell front document
            tell current slide
                try
                    set newShape to make new shape with properties {{position:{{{x1}, {y1}}}, width:{width}, height:{height}}}
                    -- Optional: Customize appearance
                    -- tell newShape
                    --  set background color to {{65535, 0, 0}} -- Red
                    --  set opacity to 80
                    -- end tell
                    return "Rectangle drawn successfully at ({x1},{y1}) with size {width}x{height}."
                on error errMsg number errNum
                    return "Error drawing rectangle: " & errMsg & " (Error " & errNum & ")"
                end try
            end tell
        end tell
    end tell
    """
    success, message = run_applescript(script)
    return {
        "content": [TextContent(type="text", text=message)]
    }

@mcp.tool()
async def add_text_in_keynote(text: str, x: int, y: int, width: int, height: int) -> dict:
    """
    Adds a text box with the specified text to the current Keynote slide.
    (x, y) is the top-left position, width/height define the box size.
    NOTE: Position and size are in points; you may need to adjust values.
    """
    print(f"CALLED: add_text_in_keynote(text='{text}', x={x}, y={y}, width={width}, height={height})")
    
    # Properly escape text for AppleScript
    escaped_text = text.replace('"', '\\"')  # Escape double quotes for AppleScript

    script = f"""
    tell application "Keynote"
        if not (exists document 1) then
            return "Error: No Keynote document is open."
        end if
        tell front document
            tell current slide
                try
                    set newTextBox to make new text item with properties {{position:{{{x}, {y}}}, width:{width}, height:{height}, object text:"{escaped_text}"}}
                    -- Optional: Customize text appearance
                    -- tell object text of newTextBox
                    --  set font to "Helvetica"
                    --  set size to 24
                    --  set color to {{0, 0, 65535}} -- Blue
                    -- end tell
                    return "Text '{text}' added successfully in a box at ({x},{y})."
                on error errMsg number errNum
                    return "Error adding text: " & errMsg & " (Error " & errNum & ")"
                end try
            end tell
        end tell
    end tell
    """
    success, message = run_applescript(script)
    # Use the original text in the success message for clarity
    if success and message.startswith("Text"):
         message = f"Text '{text}' added successfully in a box at ({x},{y})."

    return {
        "content": [TextContent(type="text", text=message)]
    }

# Keep other non-Paint tools from the original example if needed, or remove them.
# Example: add tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    print(f"CALLED: add(a={a}, b={b})")
    return int(a + b)

# ... (add other math tools here if desired)


if __name__ == "__main__":
    print("STARTING MacOS Keynote Controller MCP Server")
    # Check if running with mcp dev command
    if len(sys.argv) > 1 and sys.argv[1] == "dev":
        mcp.run()  # Run without transport for dev server
    else:
        mcp.run(transport="stdio")  # Run with stdio for direct execution