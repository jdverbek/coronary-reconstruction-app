# Coronary Artery 3D Reconstruction Web Application

A professional web application for coronary artery analysis and 3D reconstruction from medical images. This application provides advanced vessel extraction, bifurcation analysis, and multi-view 3D reconstruction capabilities.

## Features

- **Single Image Analysis**: Upload one medical image for vessel extraction and visualization
- **Multi-View 3D Reconstruction**: Upload multiple images with C-arm angle configuration for 3D reconstruction
- **Real-time Processing**: Backend API processes images using advanced computer vision algorithms
- **Interactive Visualization**: Results display with original vs overlay images and 3D canvas visualization
- **Modern Interface**: Professional, responsive design with drag & drop upload functionality

## Technology Stack

- **Backend**: Flask with CORS support
- **Frontend**: HTML5, CSS3, JavaScript with modern animations
- **Image Processing**: OpenCV, scikit-image, NetworkX, SciPy
- **Deployment**: Ready for Render deployment

## API Endpoints

- `GET /api/coronary/health` - Health check endpoint
- `POST /api/coronary/analyze-single` - Single image vessel analysis
- `POST /api/coronary/reconstruct` - Multi-view 3D reconstruction
- `POST /api/coronary/upload` - Multiple image upload and processing

## Local Development

1. Clone the repository:
```bash
git clone <repository-url>
cd coronary-reconstruction-app
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python src/main.py
```

5. Open your browser and navigate to `http://localhost:5000`

## Deployment on Render

### Quick Deploy
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

### Manual Deployment

1. Fork this repository to your GitHub account

2.  Create a new Web Service on [Render](https://render.com):
    
    *   Connect your GitHub repository
    *   Set the build command: `pip install -r requirements.txt`
    *   Set the start command: `gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 --chdir . src.wsgi:app`
    *   Set environment variables if needed

3. Deploy and access your application via the provided Render URL

## Environment Variables

- `PORT`: Port number for the application (automatically set by Render)
- `FLASK_ENV`: Set to 'development' for debug mode, 'production' for production

## Medical Image Processing Capabilities

### Vessel Extraction
- Frangi vesselness filtering for enhanced vessel detection
- Skeletonization for centerline extraction
- Graph-based vessel tree analysis
- Bifurcation detection and characterization

### 3D Reconstruction
- Multi-view stereo reconstruction
- C-arm calibration with LAO/RAO and Cranial/Caudal angles
- Bundle adjustment for improved accuracy
- Murray's law validation for bifurcation analysis

### Supported Image Formats
- JPEG, PNG, BMP, TIFF
- Grayscale and color medical images
- DICOM support (with preprocessing)

## Usage

### Single Image Analysis
1. Select "Single Image Analysis" mode
2. Upload a medical image using drag & drop or file browser
3. View the extracted vessel overlay and analysis statistics

### Multi-View 3D Reconstruction
1. Select "Multi-View 3D Reconstruction" mode
2. Upload 2 or more medical images from different viewing angles
3. Configure C-arm angles for each image:
   - LAO/RAO angle: -90° to +50°
   - Cranial/Caudal angle: -40° to +40°
4. Click "Start 3D Reconstruction" to process
5. View the 3D visualization and reconstruction statistics

## Project Structure

```
coronary-reconstruction-app/
├── src/
│   ├── models/
│   │   ├── coronary_reconstructor.py  # Main reconstruction class
│   │   └── user.py                    # User model
│   ├── routes/
│   │   ├── coronary.py               # Coronary analysis API routes
│   │   └── user.py                   # User API routes
│   ├── static/
│   │   ├── index.html                # Main frontend interface
│   │   ├── styles.css                # Modern CSS styling
│   │   └── script.js                 # Frontend JavaScript
│   └── main.py                       # Flask application entry point
├── requirements.txt                   # Python dependencies
├── Procfile                          # Render deployment configuration
└── README.md                         # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with advanced computer vision and medical imaging techniques
- Uses state-of-the-art vessel extraction algorithms
- Implements robust 3D reconstruction methods for medical applications

