from flask import Blueprint, request, jsonify
import cv2
import numpy as np
import base64
import io
from PIL import Image
import logging
from src.models.coronary_reconstructor import CoronaryReconstructor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

coronary_bp = Blueprint('coronary', __name__)

# Global reconstructor instance
reconstructor = CoronaryReconstructor()

@coronary_bp.route('/upload', methods=['POST'])
def upload_images():
    """
    Upload and process medical images for vessel extraction.
    """
    try:
        if 'images' not in request.files:
            return jsonify({'error': 'No images provided'}), 400
        
        files = request.files.getlist('images')
        if len(files) == 0:
            return jsonify({'error': 'No images selected'}), 400
        
        processed_images = []
        vessel_results = []
        
        for i, file in enumerate(files):
            if file.filename == '':
                continue
                
            # Read image
            image_data = file.read()
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                logger.error(f"Failed to decode image {i}")
                continue
            
            # Extract vessel centerlines
            vessel_tree = reconstructor.extract_vessel_centerlines(image)
            
            # Convert image to base64 for frontend display
            _, buffer = cv2.imencode('.jpg', image)
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            
            processed_images.append({
                'index': i,
                'filename': file.filename,
                'image_data': f"data:image/jpeg;base64,{img_base64}",
                'shape': image.shape
            })
            
            # Convert numpy arrays to lists for JSON serialization
            vessel_result = {
                'num_branches': vessel_tree['num_branches'],
                'total_length': vessel_tree['total_length'],
                'bifurcations_count': len(vessel_tree['bifurcations']),
                'branches': []
            }
            
            # Convert branch paths to lists
            for branch in vessel_tree['branches']:
                if len(branch['path']) > 0:
                    vessel_result['branches'].append({
                        'type': branch['type'],
                        'length': branch['length'],
                        'path': branch['path'].tolist()
                    })
            
            vessel_results.append(vessel_result)
        
        return jsonify({
            'success': True,
            'message': f'Processed {len(processed_images)} images',
            'images': processed_images,
            'vessel_analysis': vessel_results
        })
        
    except Exception as e:
        logger.error(f"Error processing images: {str(e)}")
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

@coronary_bp.route('/reconstruct', methods=['POST'])
def reconstruct_3d():
    """
    Perform 3D reconstruction from multiple views.
    """
    try:
        data = request.json
        
        if not data or 'images' not in data or 'angles' not in data:
            return jsonify({'error': 'Missing images or angle data'}), 400
        
        images_data = data['images']
        angles_data = data['angles']
        
        if len(images_data) < 2:
            return jsonify({'error': 'At least 2 images required for 3D reconstruction'}), 400
        
        if len(images_data) != len(angles_data):
            return jsonify({'error': 'Number of images must match number of angle sets'}), 400
        
        # Decode images from base64 and optimize size
        images = []
        max_dimension = 800  # Maximum width or height for web processing
        
        for i, img_data in enumerate(images_data):
            # Remove data URL prefix if present
            if img_data.startswith('data:image'):
                img_data = img_data.split(',')[1]
            
            # Decode base64
            img_bytes = base64.b64decode(img_data)
            img_array = np.frombuffer(img_bytes, np.uint8)
            image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            if image is not None:
                # Optimize image size for faster processing
                height, width = image.shape[:2]
                if max(height, width) > max_dimension:
                    scale = max_dimension / max(height, width)
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
                    logger.info(f"Resized image {i+1} from {width}x{height} to {new_width}x{new_height}")
                
                images.append(image)
            else:
                logger.warning(f"Failed to decode image {i+1}")
        
        if len(images) < 2:
            return jsonify({'error': 'Failed to decode sufficient images for reconstruction'}), 400
        
        # Validate angles format
        angles = []
        for angle_set in angles_data:
            if 'lao_rao' not in angle_set or 'cranial_caudal' not in angle_set:
                return jsonify({'error': 'Invalid angle format. Need lao_rao and cranial_caudal'}), 400
            angles.append(angle_set)
        
        # Perform 3D reconstruction with timeout handling
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("3D reconstruction timed out")
        
        try:
            # Set timeout for the entire reconstruction process (90 seconds)
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(90)
            
            result = reconstructor.reconstruct_from_views(images, angles)
            
            # Clear the alarm
            signal.alarm(0)
            
        except TimeoutError:
            logger.error("3D reconstruction timed out after 90 seconds")
            return jsonify({
                'error': '3D reconstruction timed out. Try with fewer images or smaller image sizes.',
                'suggestion': 'For better performance, use 2-4 images with resolution under 800x800 pixels.'
            }), 408  # Request Timeout
        except Exception as e:
            signal.alarm(0)  # Clear alarm on any exception
            raise e
        
        # Convert result to JSON-serializable format
        json_result = {
            'success': result['success'],
            'num_views_used': result['num_views_used'],
            'num_branches': result['num_branches'],
            'reconstruction_method': result['reconstruction_method'],
            'branches_3d': [],
            'bifurcations': []
        }
        
        # Convert 3D branches
        for branch in result['branches_3d']:
            json_result['branches_3d'].append({
                'type': branch['type'],
                'confidence': branch['confidence'],
                'views_used': branch['views_used'],
                'points': branch['points'].tolist()
            })
        
        # Convert bifurcations
        for bifurcation in result['bifurcations']:
            json_result['bifurcations'].append({
                'position': bifurcation['position'],
                'degree': bifurcation['degree'],
                'confidence': bifurcation['confidence']
            })
        
        return jsonify(json_result)
        
    except Exception as e:
        logger.error(f"Error in 3D reconstruction: {str(e)}")
        return jsonify({'error': f'3D reconstruction failed: {str(e)}'}), 500

@coronary_bp.route('/analyze-single', methods=['POST'])
def analyze_single_image():
    """
    Analyze a single image for vessel extraction and visualization.
    """
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No image selected'}), 400
        
        # Read and process image
        image_data = file.read()
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return jsonify({'error': 'Invalid image format'}), 400
        
        # Extract vessel centerlines
        vessel_tree = reconstructor.extract_vessel_centerlines(image)
        
        # Create visualization overlay
        overlay = image.copy()
        
        # Draw vessel centerlines
        for branch in vessel_tree['branches']:
            if len(branch['path']) > 1:
                points = branch['path'].astype(np.int32)
                # Draw branch path
                for i in range(len(points) - 1):
                    cv2.line(overlay, 
                            (points[i][1], points[i][0]), 
                            (points[i+1][1], points[i+1][0]), 
                            (0, 255, 0), 2)
        
        # Draw bifurcations
        for bifurcation in vessel_tree['bifurcations']:
            pos = bifurcation['position']
            cv2.circle(overlay, (int(pos[1]), int(pos[0])), 5, (0, 0, 255), -1)
        
        # Convert images to base64
        _, orig_buffer = cv2.imencode('.jpg', image)
        orig_base64 = base64.b64encode(orig_buffer).decode('utf-8')
        
        _, overlay_buffer = cv2.imencode('.jpg', overlay)
        overlay_base64 = base64.b64encode(overlay_buffer).decode('utf-8')
        
        # Prepare result
        result = {
            'success': True,
            'original_image': f"data:image/jpeg;base64,{orig_base64}",
            'overlay_image': f"data:image/jpeg;base64,{overlay_base64}",
            'analysis': {
                'num_branches': vessel_tree['num_branches'],
                'total_length': vessel_tree['total_length'],
                'bifurcations_count': len(vessel_tree['bifurcations']),
                'image_shape': image.shape
            }
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error analyzing single image: {str(e)}")
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

@coronary_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'Coronary Reconstruction API',
        'version': '1.0.0'
    })

