import json
import os
import inspect

def load_cogs_info_json(file_name: str) -> dict:
    """
    Load configuration data from a JSON file located in the directory of the calling cog.
    
    Args:
        file_name (str): The name of the JSON file.
        
    Returns:
        dict: The loaded configuration data.
    """
    # Get the frame of the caller
    caller_frame = inspect.stack()[1]
    # Get the module object of the caller
    caller_module = inspect.getmodule(caller_frame[0])
    # Get the directory of the caller module
    caller_dir = os.path.dirname(os.path.abspath(caller_module.__file__))
    # Construct the full path to the JSON file
    config_path = os.path.join(caller_dir, file_name)
    
    with open(config_path, 'r') as f:
        return json.load(f)