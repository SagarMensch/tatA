@echo off
call ocr_env\Scripts\activate.bat

echo Installing LayoutParser 0.3.4...
pip install layoutparser==0.3.4

echo Installing PyTorch for CPU...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

echo Installing OpenCV and PyMuPDF...
pip install opencv-python pymupdf

echo Verifying installations...
python -c "import paddle; import layoutparser; import cv2; import fitz; print('All ML modules loaded successfully!')"
