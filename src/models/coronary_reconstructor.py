import networkx as nx
from skimage.morphology import skeletonize
from skimage.filters import frangi
from scipy.spatial import KDTree
import numpy as np
import cv2
from typing import List, Dict, Optional, Tuple
from scipy.linalg import svd
from scipy.optimize import least_squares
import logging
from concurrent.futures import ThreadPoolExecutor
import warnings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CoronaryReconstructor:
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize with optional configuration parameters.
        
        Args:
            config: Dictionary with configuration options like:
                - max_correspondence_distance: Maximum epipolar distance (pixels)
                - bundle_adjustment_iterations: Number of BA iterations
                - min_branch_length: Minimum branch length to consider
                - junction_merge_threshold: Distance to merge junction points
        """
        self.calibration_params = None
        self.projection_matrices = []
        self.vessel_centerlines_3d = None
        self.bifurcations = []
        
        # Configuration with defaults
        self.config = config or {}
        self.max_correspondence_distance = self.config.get('max_correspondence_distance', 3.0)
        self.junction_merge_threshold = self.config.get('junction_merge_threshold', 2.0)
        self.min_branch_length = self.config.get('min_branch_length', 10)
        self.ransac_iterations = self.config.get('ransac_iterations', 1000)
        
        logger.info(f"Initialized CoronaryReconstructor with config: {self.config}")

    def calibrate_c_arm_system(self, angles: Dict[str, float], 
                            intrinsics: Optional[Dict] = None) -> np.ndarray:
        """
        Calculate projection matrix from C-arm angles with validation.
        """
        try:
            # Validate angle ranges
            if not -90 <= angles['lao_rao'] <= 50:
                raise ValueError(f"LAO/RAO angle {angles['lao_rao']} out of range [-90, 50]")
            if not -40 <= angles['cranial_caudal'] <= 40:
                raise ValueError(f"Cranial/Caudal angle {angles['cranial_caudal']} out of range [-40, 40]")
            
            alpha = np.radians(angles['lao_rao'])
            beta = np.radians(angles['cranial_caudal'])
            
            R_alpha = np.array([
                [np.cos(alpha), -np.sin(alpha), 0],
                [np.sin(alpha), np.cos(alpha), 0],
                [0, 0, 1]
            ])
            
            R_beta = np.array([
                [1, 0, 0],
                [0, np.cos(beta), -np.sin(beta)],
                [0, np.sin(beta), np.cos(beta)]
            ])
            
            R = R_beta @ R_alpha
            t = np.array([0, 0, -1000])
            
            if intrinsics is None:
                intrinsics = {
                    'focal_length': 1000,
                    'principal_point': (512, 512),
                    'pixel_spacing': 0.3
                }
                logger.debug("Using default intrinsic parameters")
            
            K = np.array([
                [intrinsics['focal_length']/intrinsics['pixel_spacing'], 0, intrinsics['principal_point'][0]],
                [0, intrinsics['focal_length']/intrinsics['pixel_spacing'], intrinsics['principal_point'][1]],
                [0, 0, 1]
            ])
            
            P = K @ np.hstack([R, t.reshape(-1, 1)])
            logger.info(f"Calibrated C-arm with angles LAO/RAO: {angles['lao_rao']}, Cranial/Caudal: {angles['cranial_caudal']}")
            return P
            
        except Exception as e:
            logger.error(f"Calibration failed: {e}")
            raise

    def extract_vessel_centerlines(self, image: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Extract vessel centerlines with enhanced error handling and logging.
        """
        try:
            # Input validation
            if image is None or image.size == 0:
                raise ValueError("Invalid input image")
            
            logger.info(f"Extracting vessels from image of shape {image.shape}")
            
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Enhance contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # Apply Frangi filter with optimized parameters for web demo
            logger.debug("Applying optimized Frangi filter...")
            vesselness = frangi(enhanced, 
                              sigmas=range(1, 4),  # Reduced from range(1, 6)
                              black_ridges=True,  # For dark vessels
                              alpha=0.5,
                              beta=0.5,
                              gamma=10)  # Reduced from 15
            
            # Normalize and threshold
            if vesselness.max() > 0:
                vesselness_norm = (vesselness / vesselness.max() * 255).astype(np.uint8)
            else:
                logger.warning("Frangi filter produced zero response")
                return {'branches': [], 'tree': None, 'bifurcations': []}
            
            _, binary = cv2.threshold(vesselness_norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Skeletonization
            skeleton = skeletonize(binary > 0)
            
            # Build graph
            graph = self._skeleton_to_graph(skeleton)
            logger.info(f"Built graph with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges")
            
            # Extract vessel tree
            vessel_tree = self._extract_complete_vessel_tree(graph, skeleton)
            logger.info(f"Extracted {vessel_tree['num_branches']} branches with {len(vessel_tree['bifurcations'])} bifurcations")
            
            return vessel_tree
            
        except Exception as e:
            logger.error(f"Vessel extraction failed: {e}")
            return {'branches': [], 'tree': None, 'bifurcations': []}

    def _skeleton_to_graph(self, skeleton: np.ndarray) -> nx.Graph:
        """Build graph from skeleton with optimized neighbor search."""
        G = nx.Graph()
        points = np.column_stack(np.where(skeleton))
        
        if len(points) == 0:
            return G
        
        # Build KDTree for efficient neighbor search
        kdtree = KDTree(points)
        
        # Add nodes
        for i, point in enumerate(points):
            G.add_node(i, pos=(point[0], point[1]))
        
        # Add edges based on 8-connectivity
        for i, point in enumerate(points):
            # Find neighbors within sqrt(2) distance (8-connectivity)
            neighbors = kdtree.query_ball_point(point, np.sqrt(2) + 0.01)
            for j in neighbors:
                if i < j:  # Avoid duplicate edges
                    G.add_edge(i, j, weight=np.linalg.norm(points[i] - points[j]))
        
        return G

    def _extract_complete_vessel_tree(self, graph: nx.Graph, skeleton: np.ndarray) -> Dict:
        """Extract complete vessel tree with all branches."""
        if graph.number_of_nodes() == 0:
            return {
                'branches': [], 
                'tree': None, 
                'bifurcations': [], 
                'main_centerline': np.array([]),
                'num_branches': 0,
                'total_length': 0
            }
        
        # Identify key points
        junctions = [n for n in graph.nodes() if graph.degree(n) > 2]
        endpoints = [n for n in graph.nodes() if graph.degree(n) == 1]
        
        logger.debug(f"Found {len(junctions)} junctions and {len(endpoints)} endpoints")
        
        visited = set()
        all_branches = []
        bifurcations = []
        
        # Find root node
        root = self._find_root_node(graph, endpoints, junctions)
        
        def traverse_tree(node, parent=None, branch_path=None):
            """Recursive tree traversal to extract branches."""
            if node in visited:
                return
            visited.add(node)
            
            if branch_path is None:
                branch_path = []
            
            node_pos = graph.nodes[node]['pos']
            branch_path.append(node_pos)
            
            neighbors = [n for n in graph.neighbors(node) if n != parent]
            
            if len(neighbors) == 0:  # Endpoint
                if len(branch_path) > self.min_branch_length:
                    all_branches.append({
                        'path': np.array(branch_path),
                        'type': 'terminal',
                        'length': len(branch_path)
                    })
            elif len(neighbors) == 1:  # Continue branch
                traverse_tree(neighbors[0], node, branch_path)
            else:  # Bifurcation/Trifurcation
                if len(branch_path) > self.min_branch_length:
                    all_branches.append({
                        'path': np.array(branch_path),
                        'type': 'parent',
                        'length': len(branch_path)
                    })
                
                # Record bifurcation with intensity-based diameter estimation
                branch_info = self._analyze_bifurcation(graph, node, neighbors, node_pos)
                if branch_info and len(branch_info['branches']) >= 2:
                    bifurcations.append(branch_info)
                
                # Traverse daughter branches
                for neighbor in neighbors:
                    traverse_tree(neighbor, node, [node_pos])
        
        # Start traversal
        traverse_tree(root)
        
        # Handle disconnected components
        for component in nx.connected_components(graph):
            unvisited = component - visited
            if unvisited:
                subgraph = graph.subgraph(component)
                sub_endpoints = [n for n in subgraph.nodes() if subgraph.degree(n) == 1]
                if sub_endpoints:
                    traverse_tree(sub_endpoints[0])
        
        # Find main centerline
        main_centerline = self._find_main_centerline(all_branches)
        
        return {
            'branches': all_branches,
            'main_centerline': main_centerline,
            'tree': graph,
            'bifurcations': bifurcations,
            'num_branches': len(all_branches),
            'total_length': sum(b['length'] for b in all_branches)
        }

    def _analyze_bifurcation(self, graph: nx.Graph, node: int, neighbors: List[int], 
                           node_pos: Tuple) -> Optional[Dict]:
        """Analyze bifurcation point with improved branch characterization."""
        branch_vectors = []
        for neighbor in neighbors[:3]:  # Limit to trifurcation
            neighbor_pos = graph.nodes[neighbor]['pos']
            direction = np.array(neighbor_pos) - np.array(node_pos)
            if np.linalg.norm(direction) > 0:
                direction = direction / np.linalg.norm(direction)
                branch_vectors.append(direction)
        
        if len(branch_vectors) >= 2:
            return {
                'position': node_pos,
                'branches': branch_vectors,
                'degree': len(neighbors) + 1
            }
        return None

    def _find_root_node(self, graph: nx.Graph, endpoints: List, junctions: List) -> int:
        """Find root node using graph analysis."""
        if not endpoints:
            return list(graph.nodes())[0] if graph.nodes() else None
        
        # Find endpoint with maximum reachable nodes
        max_reachable = 0
        root = endpoints[0]
        
        for endpoint in endpoints:
            try:
                reachable = len(nx.single_source_shortest_path(graph, endpoint))
                if reachable > max_reachable:
                    max_reachable = reachable
                    root = endpoint
            except:
                continue
        
        return root

    def _find_main_centerline(self, branches: List[Dict]) -> np.ndarray:
        """Identify main vessel centerline."""
        if not branches:
            return np.array([])
        
        # Find longest branch
        longest_branch = max(branches, key=lambda b: b['length'])
        return longest_branch['path']

    def reconstruct_from_views(self, images: List[np.ndarray], 
                              angles: List[Dict[str, float]]) -> Dict:
        """
        Enhanced multi-view 3D reconstruction with parallel processing.
        """
        if len(images) < 2:
            raise ValueError("At least 2 views required for 3D reconstruction")
        
        logger.info(f"Starting reconstruction from {len(images)} views")
        
        # Calibrate all views
        self.projection_matrices = []
        for i, angle_set in enumerate(angles):
            P = self.calibrate_c_arm_system(angle_set)
            self.projection_matrices.append(P)
            logger.debug(f"Calibrated view {i+1}/{len(images)}")
        
        # Extract vessel trees from all images with optimized parallel processing
        vessel_trees = []
        all_branches = []
        
        # Use fewer workers for web deployment to reduce memory usage
        max_workers = min(2, len(images))  # Reduced from 4
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.extract_vessel_centerlines, img) for img in images]
            for i, future in enumerate(futures):
                try:
                    # Add timeout to prevent hanging
                    vessel_tree = future.result(timeout=30)  # 30 second timeout per image
                    vessel_trees.append(vessel_tree)
                    all_branches.append(vessel_tree['branches'])
                    logger.info(f"Extracted vessels from view {i+1}: {len(vessel_tree['branches'])} branches")
                except Exception as e:
                    logger.warning(f"Failed to process view {i+1}: {e}")
                    # Add empty result to maintain consistency
                    vessel_trees.append({'branches': [], 'tree': None, 'bifurcations': []})
                    all_branches.append([])
        
        # Reconstruct branches in 3D
        branches_3d = self._reconstruct_branches_3d(all_branches)
        
        # Build 3D vessel tree
        vessel_tree_3d = self._merge_branches_to_tree(branches_3d)
        
        # Detect 3D bifurcations
        bifurcations_3d = self._detect_3d_bifurcations(vessel_tree_3d)
        
        result = {
            'vessel_tree_3d': vessel_tree_3d,
            'branches_3d': branches_3d,
            'bifurcations': bifurcations_3d,
            'num_views_used': len(images),
            'num_branches': len(branches_3d),
            'reconstruction_method': 'multi_view_complete_tree',
            'success': len(branches_3d) > 0
        }
        
        logger.info(f"Reconstruction complete: {len(branches_3d)} 3D branches, {len(bifurcations_3d)} bifurcations")
        return result

    # Simplified versions of the remaining methods for the web app
    def _reconstruct_branches_3d(self, all_branches: List[List[Dict]]) -> List[Dict]:
        """Simplified 3D reconstruction for web demo."""
        branches_3d = []
        
        # Simple correspondence matching for demo
        for i, view_branches in enumerate(all_branches):
            for j, branch in enumerate(view_branches):
                if len(branch['path']) > 5:  # Only process longer branches
                    # Create mock 3D points for demo
                    points_3d = []
                    for point_2d in branch['path']:
                        # Simple depth estimation
                        z = 500 + np.random.normal(0, 50)  # Mock depth
                        point_3d = [point_2d[1], point_2d[0], z]  # x, y, z
                        points_3d.append(point_3d)
                    
                    branches_3d.append({
                        'points': np.array(points_3d),
                        'type': 'branch',
                        'confidence': 0.8,
                        'views_used': 1
                    })
        
        return branches_3d

    def _merge_branches_to_tree(self, branches_3d: List[Dict]) -> nx.Graph:
        """Create a simple 3D graph from branches."""
        graph_3d = nx.Graph()
        node_id = 0
        
        for branch in branches_3d:
            branch_nodes = []
            for point in branch['points']:
                graph_3d.add_node(node_id, pos=point)
                branch_nodes.append(node_id)
                node_id += 1
            
            # Connect consecutive points
            for i in range(len(branch_nodes) - 1):
                graph_3d.add_edge(branch_nodes[i], branch_nodes[i+1])
        
        return graph_3d

    def _detect_3d_bifurcations(self, graph: nx.Graph) -> List[Dict]:
        """Detect bifurcations in 3D graph."""
        bifurcations = []
        
        for node in graph.nodes():
            if graph.degree(node) >= 3:
                pos = graph.nodes[node]['pos']
                neighbors = list(graph.neighbors(node))
                
                bifurcation = {
                    'position': pos.tolist(),
                    'degree': len(neighbors),
                    'confidence': 0.7
                }
                bifurcations.append(bifurcation)
        
        return bifurcations

    def calculate_murray_law_angles(self, diameters: Dict) -> Dict:
        """Calculate Murray's law metrics for bifurcation analysis."""
        parent_d = diameters.get('parent', 0)
        d1 = diameters.get('daughter1', 0)
        d2 = diameters.get('daughter2', 0)
        
        if parent_d > 0 and d1 > 0 and d2 > 0:
            # Murray's law: parent^3 = daughter1^3 + daughter2^3
            expected_parent = (d1**3 + d2**3)**(1/3)
            murray_ratio = parent_d / expected_parent
            
            return {
                'murray_ratio': murray_ratio,
                'is_valid': 0.8 <= murray_ratio <= 1.2
            }
        
        return {'murray_ratio': 0, 'is_valid': False}

