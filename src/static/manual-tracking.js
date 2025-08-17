// Manual Vessel Tracking Interface
class ManualTracker {
    constructor() {
        this.images = [];
        this.currentImageIndex = 0;
        this.trackingData = {};
        this.zoomLevel = 1;
        this.panOffset = { x: 0, y: 0 };
        this.isDragging = false;
        this.lastMousePos = { x: 0, y: 0 };
        
        this.canvas = null;
        this.ctx = null;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.setupCanvas();
    }
    
    setupEventListeners() {
        // File upload
        const fileInput = document.getElementById('fileInput');
        const uploadArea = document.getElementById('uploadArea');
        const browseLink = uploadArea.querySelector('.browse-link');
        
        browseLink.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', (e) => this.handleFileUpload(e));
        
        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            this.handleFileUpload(e);
        });
        
        // Start tracking button
        document.getElementById('startTrackingBtn').addEventListener('click', () => {
            this.startTracking();
        });
        
        // Image selector
        document.getElementById('imageSelector').addEventListener('change', (e) => {
            this.switchImage(parseInt(e.target.value));
        });
        
        // Zoom controls
        document.getElementById('zoomInBtn').addEventListener('click', () => this.zoomIn());
        document.getElementById('zoomOutBtn').addEventListener('click', () => this.zoomOut());
        document.getElementById('resetZoomBtn').addEventListener('click', () => this.resetZoom());
        
        // Point controls
        document.getElementById('undoPointBtn').addEventListener('click', () => this.undoLastPoint());
        document.getElementById('clearPointsBtn').addEventListener('click', () => this.clearAllPoints());
        
        // 3D reconstruction
        document.getElementById('reconstruct3DBtn').addEventListener('click', () => this.reconstruct3D());
        
        // Angle inputs
        document.getElementById('laoRaoAngle').addEventListener('change', () => this.updateAngles());
        document.getElementById('cranialCaudalAngle').addEventListener('change', () => this.updateAngles());
    }
    
    setupCanvas() {
        this.canvas = document.getElementById('trackingCanvas');
        this.ctx = this.canvas.getContext('2d');
        
        // Canvas event listeners
        this.canvas.addEventListener('click', (e) => this.handleCanvasClick(e));
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('wheel', (e) => this.handleWheel(e));
        
        // Pan functionality
        this.canvas.addEventListener('mousedown', (e) => {
            if (e.button === 1 || e.ctrlKey) { // Middle mouse or Ctrl+click for panning
                this.isDragging = true;
                this.lastMousePos = { x: e.clientX, y: e.clientY };
                this.canvas.style.cursor = 'grabbing';
            }
        });
        
        this.canvas.addEventListener('mousemove', (e) => {
            if (this.isDragging) {
                const deltaX = e.clientX - this.lastMousePos.x;
                const deltaY = e.clientY - this.lastMousePos.y;
                
                this.panOffset.x += deltaX;
                this.panOffset.y += deltaY;
                
                this.lastMousePos = { x: e.clientX, y: e.clientY };
                this.redrawCanvas();
            }
        });
        
        this.canvas.addEventListener('mouseup', () => {
            this.isDragging = false;
            this.canvas.style.cursor = 'crosshair';
        });
    }
    
    handleFileUpload(e) {
        const files = e.target?.files || e.dataTransfer?.files;
        if (!files) return;
        
        Array.from(files).forEach(file => {
            if (file.type.startsWith('image/')) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const img = new Image();
                    img.onload = () => {
                        this.images.push({
                            file: file,
                            image: img,
                            name: file.name,
                            angles: { lao_rao: 0, cranial_caudal: 0 }
                        });
                        this.updateUploadedImages();
                        this.updateImageSelector();
                    };
                    img.src = e.target.result;
                };
                reader.readAsDataURL(file);
            }
        });
    }
    
    updateUploadedImages() {
        const container = document.getElementById('uploadedImages');
        container.innerHTML = '';
        
        this.images.forEach((imgData, index) => {
            const div = document.createElement('div');
            div.className = 'uploaded-image';
            div.innerHTML = `
                <img src="${imgData.image.src}" alt="${imgData.name}">
                <button class="remove-btn" onclick="tracker.removeImage(${index})">×</button>
            `;
            container.appendChild(div);
        });
        
        const startBtn = document.getElementById('startTrackingBtn');
        if (this.images.length >= 2) {
            startBtn.style.display = 'block';
        } else {
            startBtn.style.display = 'none';
        }
    }
    
    removeImage(index) {
        this.images.splice(index, 1);
        this.updateUploadedImages();
        this.updateImageSelector();
    }
    
    updateImageSelector() {
        const selector = document.getElementById('imageSelector');
        selector.innerHTML = '';
        
        this.images.forEach((imgData, index) => {
            const option = document.createElement('option');
            option.value = index;
            option.textContent = `Image ${index + 1}: ${imgData.name}`;
            selector.appendChild(option);
        });
        
        document.getElementById('imageCount').textContent = this.images.length;
    }
    
    startTracking() {
        if (this.images.length < 2) {
            alert('Please upload at least 2 images for tracking.');
            return;
        }
        
        document.getElementById('uploadSection').style.display = 'none';
        document.getElementById('trackingInterface').style.display = 'grid';
        
        this.currentImageIndex = 0;
        this.initializeTrackingData();
        this.loadCurrentImage();
        this.updateImageSelector();
    }
    
    initializeTrackingData() {
        this.trackingData = {};
        this.images.forEach((_, index) => {
            this.trackingData[index] = {
                points: [],
                angles: { lao_rao: 0, cranial_caudal: 0 },
                branches: {
                    main_vessel: [],
                    branch_1: [],
                    branch_2: [],
                    bifurcation: []
                }
            };
        });
    }
    
    switchImage(index) {
        if (index >= 0 && index < this.images.length) {
            this.currentImageIndex = index;
            this.loadCurrentImage();
            this.updateAngleInputs();
        }
    }
    
    loadCurrentImage() {
        if (!this.images[this.currentImageIndex]) return;
        
        const img = this.images[this.currentImageIndex].image;
        const container = document.getElementById('viewerContainer');
        
        // Resize canvas to fit container while maintaining aspect ratio
        const containerRect = container.getBoundingClientRect();
        const maxWidth = containerRect.width - 40;
        const maxHeight = containerRect.height - 40;
        
        const scale = Math.min(maxWidth / img.width, maxHeight / img.height);
        
        this.canvas.width = img.width * scale;
        this.canvas.height = img.height * scale;
        
        this.resetZoom();
        this.redrawCanvas();
    }
    
    redrawCanvas() {
        if (!this.images[this.currentImageIndex]) return;
        
        const img = this.images[this.currentImageIndex].image;
        
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Apply zoom and pan transformations
        this.ctx.save();
        this.ctx.scale(this.zoomLevel, this.zoomLevel);
        this.ctx.translate(this.panOffset.x / this.zoomLevel, this.panOffset.y / this.zoomLevel);
        
        // Draw image
        this.ctx.drawImage(img, 0, 0, this.canvas.width / this.zoomLevel, this.canvas.height / this.zoomLevel);
        
        // Draw tracking points
        this.drawTrackingPoints();
        
        this.ctx.restore();
    }
    
    drawTrackingPoints() {
        const currentData = this.trackingData[this.currentImageIndex];
        if (!currentData) return;
        
        const colors = {
            main_vessel: '#ff6b6b',
            branch_1: '#4ecdc4',
            branch_2: '#45b7d1',
            bifurcation: '#f9ca24'
        };
        
        // Draw points for each branch type
        Object.keys(currentData.branches).forEach(branchType => {
            const points = currentData.branches[branchType];
            const color = colors[branchType];
            
            points.forEach((point, index) => {
                this.ctx.fillStyle = color;
                this.ctx.strokeStyle = '#fff';
                this.ctx.lineWidth = 2;
                
                this.ctx.beginPath();
                this.ctx.arc(point.x, point.y, 6, 0, 2 * Math.PI);
                this.ctx.fill();
                this.ctx.stroke();
                
                // Draw point number
                this.ctx.fillStyle = '#fff';
                this.ctx.font = '12px Arial';
                this.ctx.textAlign = 'center';
                this.ctx.fillText(index + 1, point.x, point.y + 4);
            });
            
            // Draw lines connecting points
            if (points.length > 1) {
                this.ctx.strokeStyle = color;
                this.ctx.lineWidth = 3;
                this.ctx.setLineDash([5, 5]);
                
                this.ctx.beginPath();
                this.ctx.moveTo(points[0].x, points[0].y);
                for (let i = 1; i < points.length; i++) {
                    this.ctx.lineTo(points[i].x, points[i].y);
                }
                this.ctx.stroke();
                this.ctx.setLineDash([]);
            }
        });
    }
    
    handleCanvasClick(e) {
        if (this.isDragging) return;
        
        const rect = this.canvas.getBoundingClientRect();
        const x = (e.clientX - rect.left - this.panOffset.x) / this.zoomLevel;
        const y = (e.clientY - rect.top - this.panOffset.y) / this.zoomLevel;
        
        const trackingMode = document.getElementById('trackingMode').value;
        
        // Add point to current branch
        const currentData = this.trackingData[this.currentImageIndex];
        currentData.branches[trackingMode].push({ x, y });
        
        this.redrawCanvas();
        this.updatePointCount();
        this.checkReconstructionReadiness();
    }
    
    handleMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = Math.round((e.clientX - rect.left - this.panOffset.x) / this.zoomLevel);
        const y = Math.round((e.clientY - rect.top - this.panOffset.y) / this.zoomLevel);
        
        document.getElementById('coordinates').textContent = `x: ${x}, y: ${y}`;
    }
    
    handleWheel(e) {
        e.preventDefault();
        
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        const wheel = e.deltaY < 0 ? 1 : -1;
        const zoom = Math.exp(wheel * 0.1);
        
        // Zoom towards mouse position
        const newZoom = Math.max(0.1, Math.min(5, this.zoomLevel * zoom));
        
        if (newZoom !== this.zoomLevel) {
            this.panOffset.x = mouseX - (mouseX - this.panOffset.x) * (newZoom / this.zoomLevel);
            this.panOffset.y = mouseY - (mouseY - this.panOffset.y) * (newZoom / this.zoomLevel);
            
            this.zoomLevel = newZoom;
            this.updateZoomDisplay();
            this.redrawCanvas();
        }
    }
    
    zoomIn() {
        this.zoomLevel = Math.min(5, this.zoomLevel * 1.2);
        this.updateZoomDisplay();
        this.redrawCanvas();
    }
    
    zoomOut() {
        this.zoomLevel = Math.max(0.1, this.zoomLevel / 1.2);
        this.updateZoomDisplay();
        this.redrawCanvas();
    }
    
    resetZoom() {
        this.zoomLevel = 1;
        this.panOffset = { x: 0, y: 0 };
        this.updateZoomDisplay();
        this.redrawCanvas();
    }
    
    updateZoomDisplay() {
        document.getElementById('zoomLevel').textContent = Math.round(this.zoomLevel * 100) + '%';
    }
    
    undoLastPoint() {
        const trackingMode = document.getElementById('trackingMode').value;
        const currentData = this.trackingData[this.currentImageIndex];
        
        if (currentData.branches[trackingMode].length > 0) {
            currentData.branches[trackingMode].pop();
            this.redrawCanvas();
            this.updatePointCount();
            this.checkReconstructionReadiness();
        }
    }
    
    clearAllPoints() {
        const currentData = this.trackingData[this.currentImageIndex];
        Object.keys(currentData.branches).forEach(branchType => {
            currentData.branches[branchType] = [];
        });
        
        this.redrawCanvas();
        this.updatePointCount();
        this.checkReconstructionReadiness();
    }
    
    updatePointCount() {
        const currentData = this.trackingData[this.currentImageIndex];
        let totalPoints = 0;
        
        Object.values(currentData.branches).forEach(branch => {
            totalPoints += branch.length;
        });
        
        document.getElementById('pointCount').textContent = totalPoints;
    }
    
    updateAngles() {
        const laoRao = parseFloat(document.getElementById('laoRaoAngle').value) || 0;
        const cranialCaudal = parseFloat(document.getElementById('cranialCaudalAngle').value) || 0;
        
        this.trackingData[this.currentImageIndex].angles = {
            lao_rao: laoRao,
            cranial_caudal: cranialCaudal
        };
    }
    
    updateAngleInputs() {
        const angles = this.trackingData[this.currentImageIndex].angles;
        document.getElementById('laoRaoAngle').value = angles.lao_rao;
        document.getElementById('cranialCaudalAngle').value = angles.cranial_caudal;
    }
    
    checkReconstructionReadiness() {
        let readyImages = 0;
        let totalPoints = 0;
        
        Object.values(this.trackingData).forEach(data => {
            let imagePoints = 0;
            Object.values(data.branches).forEach(branch => {
                imagePoints += branch.length;
            });
            
            if (imagePoints > 0) {
                readyImages++;
                totalPoints += imagePoints;
            }
        });
        
        const reconstructBtn = document.getElementById('reconstruct3DBtn');
        const statusDiv = document.getElementById('reconstructionStatus');
        
        if (readyImages >= 2 && totalPoints >= 6) {
            reconstructBtn.disabled = false;
            statusDiv.innerHTML = `
                <p style="color: #48bb78;">✅ Ready for 3D reconstruction!</p>
                <p>Images with tracking: ${readyImages}/${this.images.length}</p>
                <p>Total points tracked: ${totalPoints}</p>
            `;
        } else {
            reconstructBtn.disabled = true;
            statusDiv.innerHTML = `
                <p>Track vessel points across multiple images to enable 3D reconstruction</p>
                <p>Images with tracking: ${readyImages}/${this.images.length}</p>
                <p>Total points tracked: ${totalPoints}</p>
                <p style="color: #e53e3e;">Need at least 2 images with 3+ points each</p>
            `;
        }
    }
    
    async reconstruct3D() {
        const reconstructBtn = document.getElementById('reconstruct3DBtn');
        const resultsDiv = document.getElementById('reconstructionResults');
        
        reconstructBtn.disabled = true;
        reconstructBtn.textContent = 'Reconstructing...';
        
        try {
            // Prepare data for API
            const reconstructionData = {
                images: [],
                tracking_data: this.trackingData
            };
            
            // Convert images to base64
            for (let i = 0; i < this.images.length; i++) {
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                const img = this.images[i].image;
                
                canvas.width = img.width;
                canvas.height = img.height;
                ctx.drawImage(img, 0, 0);
                
                const base64 = canvas.toDataURL('image/jpeg', 0.8);
                reconstructionData.images.push(base64);
            }
            
            // Send to API
            const response = await fetch('/api/coronary/manual-reconstruct', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(reconstructionData)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            
            if (result.success) {
                this.displayReconstructionResults(result);
                resultsDiv.style.display = 'block';
            } else {
                throw new Error(result.error || 'Reconstruction failed');
            }
            
        } catch (error) {
            console.error('Reconstruction error:', error);
            alert(`3D reconstruction failed: ${error.message}`);
        } finally {
            reconstructBtn.disabled = false;
            reconstructBtn.textContent = 'Generate 3D Model';
        }
    }
    
    displayReconstructionResults(result) {
        const statsDiv = document.getElementById('resultStats');
        const canvas3D = document.getElementById('reconstruction3D');
        const ctx3D = canvas3D.getContext('2d');
        
        // Display statistics
        statsDiv.innerHTML = `
            <div><strong>Reconstruction Method:</strong> ${result.method}</div>
            <div><strong>Points Processed:</strong> ${result.total_points}</div>
            <div><strong>3D Branches:</strong> ${result.branches_3d?.length || 0}</div>
            <div><strong>Bifurcations:</strong> ${result.bifurcations?.length || 0}</div>
            <div><strong>Success Rate:</strong> ${Math.round(result.confidence * 100)}%</div>
        `;
        
        // Simple 3D visualization
        this.render3DVisualization(ctx3D, result.branches_3d || []);
    }
    
    render3DVisualization(ctx, branches3D) {
        const width = ctx.canvas.width;
        const height = ctx.canvas.height;
        
        // Clear canvas
        ctx.fillStyle = '#1a202c';
        ctx.fillRect(0, 0, width, height);
        
        if (branches3D.length === 0) {
            ctx.fillStyle = '#718096';
            ctx.font = '16px Arial';
            ctx.textAlign = 'center';
            ctx.fillText('No 3D data to display', width/2, height/2);
            return;
        }
        
        // Simple 3D projection
        const centerX = width / 2;
        const centerY = height / 2;
        const scale = 0.5;
        
        branches3D.forEach((branch, index) => {
            const color = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#f9ca24'][index % 4];
            
            if (branch.points && branch.points.length > 1) {
                ctx.strokeStyle = color;
                ctx.lineWidth = 3;
                ctx.beginPath();
                
                branch.points.forEach((point, i) => {
                    // Simple orthographic projection (ignore Z for now)
                    const x = centerX + point[0] * scale;
                    const y = centerY + point[1] * scale;
                    
                    if (i === 0) {
                        ctx.moveTo(x, y);
                    } else {
                        ctx.lineTo(x, y);
                    }
                });
                
                ctx.stroke();
                
                // Draw points
                ctx.fillStyle = color;
                branch.points.forEach(point => {
                    const x = centerX + point[0] * scale;
                    const y = centerY + point[1] * scale;
                    
                    ctx.beginPath();
                    ctx.arc(x, y, 4, 0, 2 * Math.PI);
                    ctx.fill();
                });
            }
        });
        
        // Add labels
        ctx.fillStyle = '#e2e8f0';
        ctx.font = '12px Arial';
        ctx.textAlign = 'left';
        ctx.fillText('3D Vessel Reconstruction', 10, 20);
        ctx.fillText(`${branches3D.length} branches reconstructed`, 10, 35);
    }
}

// Initialize the tracker when the page loads
let tracker;
document.addEventListener('DOMContentLoaded', () => {
    tracker = new ManualTracker();
});

