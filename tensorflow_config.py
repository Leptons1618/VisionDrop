import os
import logging
from absl import logging as absl_logging

def configure_tensorflow():
    """Configure TensorFlow settings and enable GPU support"""
    # Basic TensorFlow settings
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    
    # Ensure CUDA is visible
    os.environ['CUDA_VISIBLE_DEVICES'] = '0'
    
    # Clear any existing GPU memory
    try:
        import tensorflow as tf
        physical_devices = tf.config.list_physical_devices('GPU')
        if physical_devices:
            for device in physical_devices:
                try:
                    tf.config.experimental.set_memory_growth(device, True)
                    logger = logging.getLogger(__name__)
                    logger.info(f"Memory growth enabled for GPU: {device}")
                except RuntimeError as e:
                    logger.warning(f"Error configuring GPU device: {e}")
        else:
            logger = logging.getLogger(__name__)
            logger.warning("No GPU devices found. Please check CUDA installation.")
            logger.info("Common fixes:\n"
                       "1. Install NVIDIA drivers\n"
                       "2. Install CUDA Toolkit 12.1\n"
                       "3. Install cuDNN v8.9.2\n"
                       "4. Set PATH environment variables")
    except:
        logger = logging.getLogger(__name__)
        logger.error("Failed to configure TensorFlow GPU support")
    
    # NVIDIA GPU optimizations
    os.environ['CUDA_CACHE_PATH'] = '.cuda_cache'
    os.environ['TF_GPU_THREAD_MODE'] = 'gpu_private'
    os.environ['TF_GPU_THREAD_COUNT'] = '4'  # Adjust based on your GPU
    os.environ['TF_USE_CUDNN_BATCHNORM_SPATIAL_PERSISTENT'] = '1'
    os.environ['TF_ENABLE_CUDA_DEVICE_HOST_MEMORY_TRANSFER_OPTIMIZATION'] = '1'
    
    # Initialize absl logging to suppress MediaPipe warnings
    absl_logging.set_verbosity(absl_logging.ERROR)
    
    # Performance optimizations
    os.environ['MEDIAPIPE_DISABLE_GPU'] = '1'  # Use CPU for MediaPipe
    
    # Configure TensorFlow Lite XNNPACK
    os.environ['TENSORFLOW_INTER_OP_PARALLELISM'] = '1'
    os.environ['TENSORFLOW_INTRA_OP_PARALLELISM'] = '1'
    
    # Configure logging
    logging.getLogger('tensorflow').setLevel(logging.ERROR)
    logging.getLogger('mediapipe').setLevel(logging.ERROR)
    
    try:
        import tensorflow as tf
        
        # Configure GPU memory growth
        gpus = tf.config.experimental.list_physical_devices('GPU')
        if gpus:
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
                
            # Set memory limit to 80% of GPU memory
            tf.config.set_logical_device_configuration(
                gpus[0],
                [tf.config.LogicalDeviceConfiguration(memory_limit=1024 * 4)]  # 4GB limit
            )
            
            logger = logging.getLogger(__name__)
            logger.info(f"GPU enabled: {tf.test.gpu_device_name()}")
            logger.info(f"Found {len(gpus)} GPU(s), using RTX 4050")
            
            # Enable mixed precision for better performance
            tf.keras.mixed_precision.set_global_policy('mixed_float16')
            logger.info("Mixed precision enabled for better GPU performance")
    except:
        logger = logging.getLogger(__name__)
        logger.warning("Could not configure GPU. Falling back to CPU.")
    
    # Disable eager execution for better performance
    try:
        import tensorflow as tf
        if hasattr(tf, 'compat') and hasattr(tf.compat, 'v1'):
            tf.compat.v1.disable_eager_execution()
    except:
        pass

    logger = logging.getLogger(__name__)
    logger.info("TensorFlow configured with optimized settings")
