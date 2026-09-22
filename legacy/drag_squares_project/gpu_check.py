import os
import sys
import logging
from subprocess import check_output, CalledProcessError
from importlib.metadata import version as get_version, PackageNotFoundError

def check_nvidia_smi():
    """Check NVIDIA GPU using nvidia-smi"""
    try:
        nvidia_output = check_output(['nvidia-smi']).decode()
        print("\n=== NVIDIA GPU Information ===")
        print(nvidia_output)
        return True
    except (CalledProcessError, FileNotFoundError):
        print("\nNVIDIA System Management Interface (nvidia-smi) not found or failed.")
        print("Please ensure NVIDIA drivers are properly installed.")
        return False

def check_cuda_version():
    """Check CUDA version and availability"""
    print("\n=== CUDA Configuration ===")
    
    # Check CUDA environment variables
    cuda_path = os.environ.get('CUDA_PATH')
    if cuda_path:
        print(f"CUDA Path: {cuda_path}")
    else:
        print("CUDA_PATH environment variable not set")
    
    # Check nvcc version
    try:
        nvcc_output = check_output(['nvcc', '--version']).decode()
        print("\nNVCC Version:")
        print(nvcc_output)
    except (CalledProcessError, FileNotFoundError):
        print("NVCC (CUDA compiler) not found in PATH")

def check_tensorflow_gpu():
    """Check TensorFlow GPU support"""
    print("\n=== TensorFlow GPU Support ===")
    try:
        import tensorflow as tf
        print(f"TensorFlow version: {tf.__version__}")
        print("\nAvailable devices:")
        for device in tf.config.list_physical_devices():
            print(f"  {device}")
        
        gpu_devices = tf.config.list_physical_devices('GPU')
        if gpu_devices:
            for gpu in gpu_devices:
                print(f"\nGPU device: {gpu}")
                try:
                    tf.config.experimental.get_memory_info(gpu)
                    print("Memory growth enabled: Yes")
                except:
                    print("Memory growth enabled: No")
        else:
            print("\nNo TensorFlow-compatible GPU detected")
    except ImportError:
        print("TensorFlow not installed")

def check_pytorch_gpu():
    """Check PyTorch GPU support"""
    print("\n=== PyTorch GPU Support ===")
    try:
        import torch
        print(f"PyTorch version: {torch.__version__}")
        print(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"CUDA version: {torch.version.cuda}")
            print(f"Current device: {torch.cuda.current_device()}")
            print(f"Device name: {torch.cuda.get_device_name(0)}")
            print(f"Device count: {torch.cuda.device_count()}")
    except ImportError:
        print("PyTorch not installed")

def check_opencv_gpu():
    """Check OpenCV GPU support"""
    print("\n=== OpenCV GPU Support ===")
    try:
        import cv2
        print(f"OpenCV version: {cv2.__version__}")
        print(f"CUDA enabled build: {cv2.cuda.getCudaEnabledDeviceCount() > 0}")
        if cv2.cuda.getCudaEnabledDeviceCount() > 0:
            print(f"Number of CUDA devices: {cv2.cuda.getCudaEnabledDeviceCount()}")
    except ImportError:
        print("OpenCV not installed")
    except AttributeError:
        print("OpenCV not compiled with CUDA support")

def check_system_info():
    """Check system information"""
    print("\n=== System Information ===")
    # Check Python version
    print(f"Python version: {sys.version}")
    
    # Check installed packages
    print("\nRelevant installed packages:")
    required_packages = ['tensorflow', 'torch', 'opencv-python', 'numpy']
    for package in required_packages:
        try:
            print(f"{package}: {get_version(package)}")
        except PackageNotFoundError:
            print(f"{package}: Not installed")

def main():
    """Run all GPU checks"""
    print("=== GPU Configuration Check ===")
    
    # Setup basic logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Run all checks
    check_system_info()
    check_nvidia_smi()
    check_cuda_version()
    check_tensorflow_gpu()
    check_pytorch_gpu()
    check_opencv_gpu()
    
    print("\n=== Check Complete ===")
    print("\nIf no GPU is detected, please ensure:")
    print("1. NVIDIA drivers are installed")
    print("2. CUDA toolkit is installed (version 11.x or 12.x)")
    print("3. cuDNN is installed")
    print("4. Environment variables are set correctly")
    print("5. GPU-enabled versions of frameworks are installed")

if __name__ == "__main__":
    main()
