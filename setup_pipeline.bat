@echo off
echo Installing required base packages...
pip install PyMuPDF opencv-python pillow

echo Installing PaddlePaddle for Windows CPU...
pip install paddlepaddle

echo Installing PaddleOCR...
pip install paddleocr

echo Installing LayoutParser with PaddleDetection backend...
pip install layoutparser[paddledetection]

echo Done!
