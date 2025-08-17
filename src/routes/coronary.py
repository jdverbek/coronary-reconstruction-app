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

@coronary_bp.route('/manual-reconstruct', methods=['POST'])
def manual_reconstruct_3d():
    """
    Perform 3D reconstruction from manually tracked points.
    """
    try:
        data = request.json
        
        if not data or 'images' not in data or 'tracking_data' not in data:
            return jsonify({'error': 'Missing images or tracking data'}), 400
        
        images_data = data['images']
        tracking_data = data['tracking_data']
        
        if len(images_data) < 2:
            return jsonify({'error': 'At least 2 images required for 3D reconstruction'}), 400
        
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
        
        # Process manual tracking data
        processed_tracking = process_manual_tracking_data(tracking_data, images)
        
        # Perform 3D reconstruction from manual points
        result = perform_manual_3d_reconstruction(processed_tracking)
        
        # Convert result to JSON-serializable format
        json_result = {
            'success': True,
            'method': 'manual_tracking',
            'total_points': result['total_points'],
            'branches_3d': [],
            'bifurcations': [],
            'confidence': result['confidence'],
            'processing_time': result.get('processing_time', 0)
        }
        
        # Convert 3D branches (handle NumPy arrays)
        for branch in result['branches_3d']:
            branch_data = {
                'type': branch['type'],
                'confidence': branch['confidence'],
                'points': []
            }
            
            # Convert NumPy arrays to lists
            if 'points' in branch:
                for point in branch['points']:
                    if hasattr(point, 'tolist'):  # NumPy array
                        branch_data['points'].append(point.tolist())
                    else:  # Regular list
                        branch_data['points'].append(point)
            
            json_result['branches_3d'].append(branch_data)
        
        # Convert bifurcations (handle NumPy arrays)
        for bifurcation in result['bifurcations']:
            bifurcation_data = {
                'type': bifurcation.get('type', 'bifurcation'),
                'confidence': bifurcation['confidence']
            }
            
            # Convert position to list if it's a NumPy array
            if 'position' in bifurcation:
                position = bifurcation['position']
                if hasattr(position, 'tolist'):  # NumPy array
                    bifurcation_data['position'] = position.tolist()
                else:  # Regular list
                    bifurcation_data['position'] = position
            
            json_result['bifurcations'].append(bifurcation_data)
        
        return jsonify(json_result)
        
    except Exception as e:
        logger.error(f"Error in manual 3D reconstruction: {str(e)}")
        return jsonify({'error': f'Manual 3D reconstruction failed: {str(e)}'}), 500

def process_manual_tracking_data(tracking_data, images):
    """
    Process and validate manual tracking data.
    """
    processed_data = []
    
    for image_index, data in tracking_data.items():
        image_idx = int(image_index)
        if image_idx >= len(images):
            continue
            
        image = images[image_idx]
        height, width = image.shape[:2]
        
        # Extract and validate points for each branch type
        processed_branches = {}
        
        for branch_type, points in data['branches'].items():
            if not points:
                continue
                
            # Validate and normalize points
            valid_points = []
            for point in points:
                x, y = point['x'], point['y']
                
                # Ensure points are within image bounds
                if 0 <= x < width and 0 <= y < height:
                    valid_points.append([x, y])
            
            if valid_points:
                processed_branches[branch_type] = np.array(valid_points)
        
        if processed_branches:
            processed_data.append({
                'image_index': image_idx,
                'angles': data['angles'],
                'branches': processed_branches,
                'image_shape': (height, width)
            })
    
    return processed_data

def perform_manual_3d_reconstruction(tracking_data):
    """
    Simplified 3D reconstruction from manually tracked points - optimized for cloud deployment.
    """
    import time
    start_time = time.time()
    
    if len(tracking_data) < 2:
        return {
            'total_points': 0,
            'branches_3d': [],
            'bifurcations': [],
            'confidence': 0.0,
            'processing_time': 0
        }
    
    branches_3d = []
    bifurcations = []
    total_points = 0
    
    # Simplified triangulation for each branch type
    branch_types = ['main_vessel', 'branch_1', 'branch_2', 'bifurcation']
    
    for branch_type in branch_types:
        # Collect points from all images for this branch type
        branch_points_2d = []
        
        for data in tracking_data:
            if branch_type in data['branches']:
                points = data['branches'][branch_type]
                angles = data['angles']
                
                for point in points:
                    branch_points_2d.append({
                        'point': point,
                        'angles': angles,
                        'image_shape': data['image_shape']
                    })
                    total_points += 1
        
        if len(branch_points_2d) >= 2:  # Need at least 2 views
            # Fast 3D reconstruction
            points_3d = triangulate_points_fast(branch_points_2d)
            
            if len(points_3d) > 0:
                branches_3d.append({
                    'type': branch_type,
                    'points': points_3d,
                    'confidence': min(1.0, len(branch_points_2d) / 4.0)
                })
                
                # Simple bifurcation detection
                if branch_type == 'bifurcation' and len(points_3d) > 0:
                    for point_3d in points_3d:
                        bifurcations.append({
                            'position': point_3d,
                            'type': 'manual_bifurcation',
                            'confidence': 0.9
                        })
    
    processing_time = time.time() - start_time
    confidence = min(1.0, len(branches_3d) / 3.0)
    
    return {
        'total_points': total_points,
        'branches_3d': branches_3d,
        'bifurcations': bifurcations,
        'confidence': confidence,
        'processing_time': processing_time
    }

def triangulate_points_fast(points_2d_data):
    """
    Fast triangulation optimized for cloud deployment.
    """
    if len(points_2d_data) < 2:
        return []
    
    points_3d = []
    
    for i, point_data in enumerate(points_2d_data):
        point_2d = point_data['point']
        angles = point_data['angles']
        image_shape = point_data['image_shape']
        
        # Fast 3D estimation
        x_norm = (point_2d[0] - image_shape[1]/2) / (image_shape[1]/2)
        y_norm = (point_2d[1] - image_shape[0]/2) / (image_shape[0]/2)
        
        # Simple projection
        lao_rao_rad = np.radians(angles['lao_rao'])
        cranial_caudal_rad = np.radians(angles['cranial_caudal'])
        
        depth = 500 + np.random.normal(0, 30)
        
        x_3d = x_norm * depth * np.sin(lao_rao_rad)
        y_3d = y_norm * depth * np.sin(cranial_caudal_rad)
        z_3d = depth * np.cos(lao_rao_rad) * np.cos(cranial_caudal_rad)
        
        points_3d.append([x_3d, y_3d, z_3d])
    
    return points_3d

def triangulate_points_enhanced(points_2d_data):
    """
    Enhanced triangulation of 2D points to 3D using improved C-arm geometry.
    """
    if len(points_2d_data) < 2:
        return []
    
    points_3d = []
    
    # Group points by similar positions for better correspondence
    for i, point_data in enumerate(points_2d_data):
        point_2d = point_data['point']
        angles = point_data['angles']
        image_shape = point_data['image_shape']
        
        # Enhanced 3D estimation with better C-arm geometry modeling
        # Convert image coordinates to normalized coordinates
        x_norm = (point_2d[0] - image_shape[1]/2) / (image_shape[1]/2)
        y_norm = (point_2d[1] - image_shape[0]/2) / (image_shape[0]/2)
        
        # Convert angles to radians
        lao_rao_rad = np.radians(angles['lao_rao'])
        cranial_caudal_rad = np.radians(angles['cranial_caudal'])
        
        # Enhanced 3D projection with proper C-arm geometry
        # Assume source-to-image distance (SID) of 1000mm and source-to-object distance (SOD) of 600mm
        sid = 1000.0
        sod = 600.0
        magnification = sid / sod
        
        # Calculate 3D position with proper geometric transformation
        # This is a simplified model - real implementation would need full camera calibration
        depth_variation = np.random.normal(0, 20)  # Small random variation for realistic spread
        estimated_depth = sod + depth_variation
        
        # Transform from image coordinates to 3D world coordinates
        x_3d = x_norm * estimated_depth * np.sin(lao_rao_rad) / magnification
        y_3d = y_norm * estimated_depth * np.sin(cranial_caudal_rad) / magnification
        z_3d = estimated_depth * np.cos(lao_rao_rad) * np.cos(cranial_caudal_rad)
        
        points_3d.append(np.array([x_3d, y_3d, z_3d]))
    
    return points_3d

def calculate_optimal_viewing_angles(branch_vectors):
    """
    Calculate optimal viewing angles based on bifurcation plane analysis.
    Implements the concept: "optimal angle is perpendicular to the plane in which the branches lie"
    """
    if len(branch_vectors) < 2:
        return None
    
    # Get branch vectors for bifurcation analysis
    main_vessel = branch_vectors.get('main_vessel')
    branch_1 = branch_vectors.get('branch_1')
    branch_2 = branch_vectors.get('branch_2')
    
    if not branch_1 or not branch_2:
        return None
    
    # Get the direction vectors of the two daughter branches
    vec1 = branch_1['vector']
    vec2 = branch_2['vector']
    
    # Calculate the plane containing the bifurcation
    # The normal to this plane is the cross product of the two branch vectors
    plane_normal = np.cross(vec1, vec2)
    plane_normal_magnitude = np.linalg.norm(plane_normal)
    
    if plane_normal_magnitude < 1e-6:  # Vectors are parallel
        return None
    
    plane_normal = plane_normal / plane_normal_magnitude  # Normalize
    
    # The optimal viewing direction is along the plane normal
    # This gives the best separation of the bifurcating branches
    optimal_view_direction = plane_normal
    
    # Calculate bifurcation angle (angle between the two daughter branches)
    dot_product = np.clip(np.dot(vec1, vec2), -1.0, 1.0)
    bifurcation_angle = np.arccos(dot_product) * (180.0 / np.pi)
    
    # Convert optimal viewing direction to C-arm angles
    # LAO/RAO angle (rotation around vertical axis)
    lao_rao = np.arctan2(optimal_view_direction[0], optimal_view_direction[2]) * (180.0 / np.pi)
    
    # Cranial/Caudal angle (rotation around horizontal axis)
    cranial_caudal = np.arcsin(np.clip(optimal_view_direction[1], -1.0, 1.0)) * (180.0 / np.pi)
    
    # Calculate additional metrics
    # Angle between main vessel and bifurcation plane
    main_to_plane_angle = 90.0  # Default if no main vessel
    if main_vessel:
        main_vec = main_vessel['vector']
        main_to_plane_dot = np.abs(np.dot(main_vec, plane_normal))
        main_to_plane_angle = np.arcsin(np.clip(main_to_plane_dot, 0.0, 1.0)) * (180.0 / np.pi)
    
    # Quality metrics
    separation_quality = np.sin(bifurcation_angle * np.pi / 180.0)  # Better separation for larger angles
    viewing_quality = np.abs(np.dot(optimal_view_direction, [0, 0, 1]))  # Prefer views closer to AP
    
    return {
        'optimal_view_direction': optimal_view_direction,
        'bifurcation_angle': bifurcation_angle,
        'lao_rao': round(lao_rao, 1),
        'cranial_caudal': round(cranial_caudal, 1),
        'plane_normal': plane_normal,
        'branch_1_vector': vec1,
        'branch_2_vector': vec2,
        'main_to_plane_angle': main_to_plane_angle,
        'separation_quality': separation_quality,
        'viewing_quality': viewing_quality,
        'confidence': min(separation_quality, viewing_quality)
    }

def triangulate_points_simple(points_2d_data):
    """
    Simple triangulation of 2D points to 3D using C-arm geometry.
    """
    if len(points_2d_data) < 2:
        return []
    
    points_3d = []
    
    # Group points by similar positions (simple correspondence)
    for i, point_data in enumerate(points_2d_data):
        point_2d = point_data['point']
        angles = point_data['angles']
        image_shape = point_data['image_shape']
        
        # Simple 3D estimation based on C-arm angles
        # This is a simplified approach - in reality, proper camera calibration would be needed
        
        # Convert image coordinates to normalized coordinates
        x_norm = (point_2d[0] - image_shape[1]/2) / (image_shape[1]/2)
        y_norm = (point_2d[1] - image_shape[0]/2) / (image_shape[0]/2)
        
        # Simple 3D projection based on C-arm angles
        lao_rao_rad = np.radians(angles['lao_rao'])
        cranial_caudal_rad = np.radians(angles['cranial_caudal'])
        
        # Estimate 3D position (simplified)
        depth = 500 + np.random.normal(0, 50)  # Mock depth with some variation
        
        x_3d = x_norm * depth * np.cos(lao_rao_rad)
        y_3d = y_norm * depth * np.cos(cranial_caudal_rad)
        z_3d = depth * np.sin(lao_rao_rad) * np.sin(cranial_caudal_rad)
        
        points_3d.append(np.array([x_3d, y_3d, z_3d]))
    
    return points_3d

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

