from django.shortcuts import render
from scanner.models import QRCode
import qrcode
from django.core.files.storage import FileSystemStorage
from io import BytesIO
from django.core.files.base import ContentFile
from django.conf import settings
from pathlib import Path
from pyzbar.pyzbar import decode
from PIL import Image
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Generate QR Code View
def generate_qr(request):
    qr_image_url = None
    if request.method == 'POST':
        mobile_number = request.POST.get('mobile_generate')
        data = request.POST.get('qr_data')
        
        # Validate the mobile number
        if not mobile_number or len(mobile_number) != 10 or not mobile_number.isdigit():
            return render(request, 'scanner/generate.html', {'error': 'Invalid mobile number'})
        
        # Check if QR code already exists in the database
        if QRCode.objects.filter(data=data, mobile_number=mobile_number).exists():
            return render(request, 'scanner/generate.html', {'error': 'QR code already exists'})
        
        try:
            # Generate the QR code image with data and mobile number
            qr_content = f"{data} | {mobile_number}"
            qr = qrcode.make(qr_content)
            qr_image_io = BytesIO()  # Create a BytesIO stream
            qr.save(qr_image_io, format='PNG')  # Save the QR code image to qr_image_io
            qr_image_io.seek(0)  # Reset the position of the stream
            
            # Define the storage location for the QR code images
            qr_storage_path = settings.MEDIA_ROOT / 'qr_codes'
            fs = FileSystemStorage(location=qr_storage_path, base_url='/media/qr_codes/')
            
            # Ensure directory exists
            Path(qr_storage_path).mkdir(parents=True, exist_ok=True)
            
            filename = f"{data}_{mobile_number}.png"
            qr_image_content = ContentFile(qr_image_io.read(), name=filename)
            file_path = fs.save(filename, qr_image_content)
            qr_image_url = fs.url(filename)
            
            # Save the QR code data and mobile number in the database
            QRCode.objects.create(data=data, mobile_number=mobile_number)
        except Exception as e:
            logger.exception("Error generating QR code")
            return render(request, 'scanner/generate.html', {'error': 'An error occurred while generating the QR code.'})
    
    return render(request, 'scanner/generate.html', {'qr_image_url': qr_image_url})


# Scan QR Code View
def scan_qr(request):
    result = None
    if request.method == 'POST' and request.FILES.get('qr_image'):
        mobile_number = request.POST.get('mobile_number')
        qr_image = request.FILES.get('qr_image')
        
        # Validate the mobile number
        if not mobile_number or len(mobile_number) != 10 or not mobile_number.isdigit():
            return render(request, 'scanner/scanner.html', {'error': 'Invalid mobile number'})
        
        # Save the uploaded image temporarily
        fs = FileSystemStorage()
        filename = fs.save(qr_image.name, qr_image)
        image_path = Path(fs.location) / filename
        
        try:
            # Open the image and decode it 
            image = Image.open(image_path)
            decoded_objects = decode(image)
            
            if decoded_objects:
                # Get the data from the first decoded object
                qr_content = decoded_objects[0].data.decode('utf-8').strip()
                qr_parts = [part.strip() for part in qr_content.split('|')]
                
                if len(qr_parts) != 2:
                    result = "Invalid QR Code format."
                else:
                    qr_data, qr_mobile_number = qr_parts
                    
                    # Check if the data exists in the QRCode model with the provided mobile number
                    qr_entry = QRCode.objects.filter(data=qr_data, mobile_number=qr_mobile_number).first()
                    
                    if qr_entry and qr_mobile_number == mobile_number:
                        result = "Scan Success: Valid QR Code for the provided mobile number"
                        
                        # Delete the specific QR Code entry from the database
                        qr_entry.delete()
                        
                        # Delete QR Code image from the 'media/qr_codes' directory
                        qr_image_path = settings.MEDIA_ROOT / 'qr_codes' / f"{qr_data}_{qr_mobile_number}.png"
                        if qr_image_path.exists():
                            qr_image_path.unlink()
                    else:
                        result = "Scan Failed: Invalid QR Code or mobile number mismatch"
            else:
                result = "No QR Code detected in the image."
        except Exception as e:
            logger.exception("Error scanning QR code")
            result = f"Error processing the image: {str(e)}"
        finally:
            # Ensure the uploaded image is deleted regardless of the result
            if image_path.exists():
                image_path.unlink(missing_ok=True)
        
    return render(request, 'scanner/scanner.html', {'result': result})
