// Global variables
let uploadedFiles = [];
let analysisType = 'single';
let currentResults = null;

// DOM elements
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const angleSection = document.getElementById('angleSection');
const angleConfig = document.getElementById('angleConfig');
const resultsSection = document.getElementById('resultsSection');
const singleResults = document.getElementById('singleResults');
const multiResults = document.getElementById('multiResults');
const loadingOverlay = document.getElementById('loadingOverlay');
const loadingMessage = document.getElementById('loadingMessage');
const errorModal = document.getElementById('errorModal');
const errorMessage = document.getElementById('errorMessage');

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    checkAnalysisType();
});

function initializeEventListeners() {
    // File upload events
    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleDrop);
    fileInput.addEventListener('change', handleFileSelect);
    
    // Browse link click
    document.querySelector('.browse-link').addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.click();
    });
    
    // Analysis type change
    document.querySelectorAll('input[name="analysisType"]').forEach(radio => {
        radio.addEventListener('change', checkAnalysisType);
    });
}

function checkAnalysisType() {
    analysisType = document.querySelector('input[name="analysisType"]:checked').value;
    
    if (analysisType === 'multi') {
        angleSection.style.display = 'block';
        generateAngleInputs();
    } else {
        angleSection.style.display = 'none';
    }
}

function handleDragOver(e) {
    e.preventDefault();
    uploadArea.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    
    const files = Array.from(e.dataTransfer.files);
    processFiles(files);
}

function handleFileSelect(e) {
    const files = Array.from(e.target.files);
    processFiles(files);
}

function processFiles(files) {
    // Filter for image files
    const imageFiles = files.filter(file => file.type.startsWith('image/'));
    
    if (imageFiles.length === 0) {
        showError('Please select valid image files.');
        return;
    }
    
    if (analysisType === 'single' && imageFiles.length > 1) {
        showError('Please select only one image for single image analysis.');
        return;
    }
    
    if (analysisType === 'multi' && imageFiles.length < 2) {
        showError('Please select at least 2 images for multi-view reconstruction.');
        return;
    }
    
    uploadedFiles = imageFiles;
    updateUploadDisplay();
    
    if (analysisType === 'multi') {
        generateAngleInputs();
    }
    
    // Auto-process for single image analysis
    if (analysisType === 'single') {
        processSingleImage();
    }
}

function updateUploadDisplay() {
    const uploadContent = uploadArea.querySelector('.upload-content');
    
    if (uploadedFiles.length > 0) {
        uploadContent.innerHTML = `
            <i class="fas fa-check-circle upload-icon" style="color: #27ae60;"></i>
            <h3>${uploadedFiles.length} Image${uploadedFiles.length > 1 ? 's' : ''} Selected</h3>
            <p>Click to select different images</p>
            ${analysisType === 'multi' ? '<button class="btn btn-primary" onclick="processMultiView()" style="margin-top: 15px;">Start 3D Reconstruction</button>' : ''}
        `;
    }
}

function generateAngleInputs() {
    if (uploadedFiles.length === 0) return;
    
    angleConfig.innerHTML = '';
    
    uploadedFiles.forEach((file, index) => {
        const angleGroup = document.createElement('div');
        angleGroup.className = 'angle-input-group';
        angleGroup.innerHTML = `
            <h4>Image ${index + 1}: ${file.name}</h4>
            <div class="angle-inputs">
                <div class="input-group">
                    <label>LAO/RAO Angle (°)</label>
                    <input type="number" id="lao_rao_${index}" min="-90" max="50" value="0" step="0.1">
                </div>
                <div class="input-group">
                    <label>Cranial/Caudal Angle (°)</label>
                    <input type="number" id="cranial_caudal_${index}" min="-40" max="40" value="0" step="0.1">
                </div>
            </div>
        `;
        angleConfig.appendChild(angleGroup);
    });
}

async function processSingleImage() {
    if (uploadedFiles.length === 0) return;
    
    showLoading('Analyzing coronary arteries...');
    
    try {
        const formData = new FormData();
        formData.append('image', uploadedFiles[0]);
        
        const response = await fetch('/api/coronary/analyze-single', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            displaySingleImageResults(result);
        } else {
            throw new Error(result.error || 'Analysis failed');
        }
        
    } catch (error) {
        console.error('Error processing single image:', error);
        showError(`Analysis failed: ${error.message}`);
    } finally {
        hideLoading();
    }
}

async function processMultiView() {
    if (uploadedFiles.length < 2) {
        showError('Please select at least 2 images for multi-view reconstruction.');
        return;
    }
    
    // Collect angle data
    const angles = [];
    for (let i = 0; i < uploadedFiles.length; i++) {
        const laoRao = parseFloat(document.getElementById(`lao_rao_${i}`).value);
        const cranialCaudal = parseFloat(document.getElementById(`cranial_caudal_${i}`).value);
        
        angles.push({
            lao_rao: laoRao,
            cranial_caudal: cranialCaudal
        });
    }
    
    showLoading('Performing 3D reconstruction...');
    
    try {
        // Convert images to base64
        const imagePromises = uploadedFiles.map(file => fileToBase64(file));
        const imageDataArray = await Promise.all(imagePromises);
        
        const requestData = {
            images: imageDataArray,
            angles: angles
        };
        
        const response = await fetch('/api/coronary/reconstruct', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            displayMultiViewResults(result);
        } else {
            throw new Error(result.error || '3D reconstruction failed');
        }
        
    } catch (error) {
        console.error('Error processing multi-view reconstruction:', error);
        showError(`3D reconstruction failed: ${error.message}`);
    } finally {
        hideLoading();
    }
}

function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

function displaySingleImageResults(result) {
    currentResults = result;
    
    // Show results section
    resultsSection.style.display = 'block';
    singleResults.style.display = 'block';
    multiResults.style.display = 'none';
    
    // Display images
    document.getElementById('originalImage').src = result.original_image;
    document.getElementById('overlayImage').src = result.overlay_image;
    
    // Display analysis statistics
    const analysisStats = document.getElementById('analysisStats');
    analysisStats.innerHTML = `
        <div class="stat-item">
            <span class="stat-value">${result.analysis.num_branches}</span>
            <span class="stat-label">Branches</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">${result.analysis.total_length}</span>
            <span class="stat-label">Total Length</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">${result.analysis.bifurcations_count}</span>
            <span class="stat-label">Bifurcations</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">${result.analysis.image_shape[0]}×${result.analysis.image_shape[1]}</span>
            <span class="stat-label">Image Size</span>
        </div>
    `;
    
    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

function displayMultiViewResults(result) {
    currentResults = result;
    
    // Show results section
    resultsSection.style.display = 'block';
    singleResults.style.display = 'none';
    multiResults.style.display = 'block';
    
    // Display reconstruction information
    const reconstructionInfo = document.getElementById('reconstructionInfo');
    reconstructionInfo.innerHTML = `
        <div class="analysis-stats">
            <div class="stat-item">
                <span class="stat-value">${result.num_views_used}</span>
                <span class="stat-label">Views Used</span>
            </div>
            <div class="stat-item">
                <span class="stat-value">${result.num_branches}</span>
                <span class="stat-label">3D Branches</span>
            </div>
            <div class="stat-item">
                <span class="stat-value">${result.bifurcations.length}</span>
                <span class="stat-label">Bifurcations</span>
            </div>
            <div class="stat-item">
                <span class="stat-value">${result.reconstruction_method}</span>
                <span class="stat-label">Method</span>
            </div>
        </div>
    `;
    
    // Render 3D visualization
    render3DVisualization(result);
    
    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

function render3DVisualization(result) {
    const canvas = document.getElementById('threeDCanvas');
    const ctx = canvas.getContext('2d');
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Set up basic 3D projection parameters
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const scale = 0.5;
    
    // Draw background
    const gradient = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, Math.max(canvas.width, canvas.height) / 2);
    gradient.addColorStop(0, '#f8f9fa');
    gradient.addColorStop(1, '#e9ecef');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Draw coordinate axes
    drawAxes(ctx, centerX, centerY, scale);
    
    // Draw 3D branches
    if (result.branches_3d && result.branches_3d.length > 0) {
        result.branches_3d.forEach((branch, index) => {
            draw3DBranch(ctx, branch.points, centerX, centerY, scale, index);
        });
    }
    
    // Draw bifurcations
    if (result.bifurcations && result.bifurcations.length > 0) {
        result.bifurcations.forEach(bifurcation => {
            draw3DBifurcation(ctx, bifurcation.position, centerX, centerY, scale);
        });
    }
    
    // Add legend
    drawLegend(ctx, canvas.width, canvas.height);
}

function drawAxes(ctx, centerX, centerY, scale) {
    ctx.strokeStyle = '#dee2e6';
    ctx.lineWidth = 1;
    
    // X-axis
    ctx.beginPath();
    ctx.moveTo(centerX - 100 * scale, centerY);
    ctx.lineTo(centerX + 100 * scale, centerY);
    ctx.stroke();
    
    // Y-axis
    ctx.beginPath();
    ctx.moveTo(centerX, centerY - 100 * scale);
    ctx.lineTo(centerX, centerY + 100 * scale);
    ctx.stroke();
    
    // Axis labels
    ctx.fillStyle = '#6c757d';
    ctx.font = '12px Inter';
    ctx.fillText('X', centerX + 105 * scale, centerY + 5);
    ctx.fillText('Y', centerX + 5, centerY - 105 * scale);
}

function draw3DBranch(ctx, points, centerX, centerY, scale, branchIndex) {
    if (!points || points.length < 2) return;
    
    // Color based on branch index
    const colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6'];
    const color = colors[branchIndex % colors.length];
    
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    
    ctx.beginPath();
    
    for (let i = 0; i < points.length; i++) {
        const point = points[i];
        // Simple orthographic projection (ignore Z for now)
        const x = centerX + point[0] * scale * 0.1;
        const y = centerY - point[1] * scale * 0.1;
        
        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    }
    
    ctx.stroke();
    
    // Draw start point
    if (points.length > 0) {
        const startPoint = points[0];
        const x = centerX + startPoint[0] * scale * 0.1;
        const y = centerY - startPoint[1] * scale * 0.1;
        
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, 2 * Math.PI);
        ctx.fill();
    }
}

function draw3DBifurcation(ctx, position, centerX, centerY, scale) {
    const x = centerX + position[0] * scale * 0.1;
    const y = centerY - position[1] * scale * 0.1;
    
    // Draw bifurcation point
    ctx.fillStyle = '#e74c3c';
    ctx.beginPath();
    ctx.arc(x, y, 5, 0, 2 * Math.PI);
    ctx.fill();
    
    // Draw highlight ring
    ctx.strokeStyle = '#c0392b';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(x, y, 8, 0, 2 * Math.PI);
    ctx.stroke();
}

function drawLegend(ctx, canvasWidth, canvasHeight) {
    const legendX = 20;
    const legendY = canvasHeight - 80;
    
    // Legend background
    ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
    ctx.fillRect(legendX - 10, legendY - 10, 150, 60);
    ctx.strokeStyle = '#dee2e6';
    ctx.strokeRect(legendX - 10, legendY - 10, 150, 60);
    
    // Legend items
    ctx.font = '12px Inter';
    ctx.fillStyle = '#495057';
    
    // Vessel branches
    ctx.strokeStyle = '#3498db';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(legendX, legendY);
    ctx.lineTo(legendX + 20, legendY);
    ctx.stroke();
    ctx.fillText('Vessel Branches', legendX + 25, legendY + 4);
    
    // Bifurcations
    ctx.fillStyle = '#e74c3c';
    ctx.beginPath();
    ctx.arc(legendX + 10, legendY + 20, 3, 0, 2 * Math.PI);
    ctx.fill();
    ctx.fillStyle = '#495057';
    ctx.fillText('Bifurcations', legendX + 25, legendY + 24);
}

function showLoading(message) {
    loadingMessage.textContent = message;
    loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    loadingOverlay.style.display = 'none';
}

function showError(message) {
    errorMessage.textContent = message;
    errorModal.style.display = 'flex';
}

function closeModal() {
    errorModal.style.display = 'none';
}

// Close modal when clicking outside
errorModal.addEventListener('click', function(e) {
    if (e.target === errorModal) {
        closeModal();
    }
});

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeModal();
    }
});

// Health check on load
fetch('/api/coronary/health')
    .then(response => response.json())
    .then(data => {
        console.log('Coronary API Health:', data);
    })
    .catch(error => {
        console.warn('Coronary API health check failed:', error);
    });

