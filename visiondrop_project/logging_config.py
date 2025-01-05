import logging
import os
from datetime import datetime
from absl import logging as absl_logging

def setup_logging():
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Configure logging
    log_filename = f"logs/visiondrop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Configure standard logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )

    # Configure absl logging
    absl_logging.set_verbosity(absl_logging.ERROR)
    absl_logging.use_absl_handler()
    
    # Suppress external libraries logging
    logging.getLogger('tensorflow').setLevel(logging.ERROR)
    logging.getLogger('mediapipe').setLevel(logging.ERROR)
    logging.getLogger('absl').setLevel(logging.ERROR)
