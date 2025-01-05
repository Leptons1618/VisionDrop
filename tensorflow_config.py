import os
import logging

def configure_tensorflow():
    """Configure TensorFlow settings and suppress warnings"""
    # Suppress TensorFlow logging and warnings
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # 0=all, 1=INFO, 2=WARNING, 3=ERROR
    os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Disable oneDNN custom operations
    
    # Performance optimizations
    os.environ['TF_GPU_THREAD_MODE'] = 'gpu_private'
    os.environ['TF_GPU_THREAD_COUNT'] = '1'
    os.environ['TF_XLA_FLAGS'] = '--tf_xla_enable_xla_devices'
    os.environ['TF_USE_CUDNN_BATCHNORM_SPATIAL_PERSISTENT'] = '1'
    os.environ['TF_ENABLE_WINOGRAD_NONFUSED'] = '1'
    
    # Memory configuration
    os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # Use CPU only for MediaPipe
    os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'
    
    # Configure logging
    logging.getLogger('tensorflow').setLevel(logging.ERROR)
    
    # Optional: Configure GPU memory growth
    try:
        import tensorflow as tf
        gpus = tf.config.experimental.list_physical_devices('GPU')
        if gpus:
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
            logging.getLogger(__name__).info(f"Found {len(gpus)} GPU(s), configured memory growth")
    except:
        pass

    # Disable eager execution for better performance
    try:
        import tensorflow as tf
        if hasattr(tf, 'compat') and hasattr(tf.compat, 'v1'):
            tf.compat.v1.disable_eager_execution()
    except:
        pass

    logger = logging.getLogger(__name__)
    logger.info("TensorFlow configured with optimized settings")
