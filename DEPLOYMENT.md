# Deployment Guide

This guide will help you deploy the Coronary Artery 3D Reconstruction web application to GitHub and then to Render.

## Step 1: Push to GitHub

The code is already prepared and committed to a local git repository. Follow these steps to push it to GitHub:

### Option A: Using GitHub CLI (Recommended)

1. Authenticate with GitHub CLI:
```bash
gh auth login
```

2. Create and push the repository:
```bash
gh repo create coronary-reconstruction-app --public --description "Professional web application for coronary artery 3D reconstruction from medical images" --push
```

### Option B: Manual GitHub Repository Creation

1. Go to [GitHub](https://github.com) and create a new repository named `coronary-reconstruction-app`
2. Make it public
3. Don't initialize with README (we already have one)
4. Copy the repository URL
5. Add the remote and push:

```bash
git remote add origin https://github.com/YOUR_USERNAME/coronary-reconstruction-app.git
git branch -M main
git push -u origin main
```

## Step 2: Deploy to Render

### Quick Deploy Button
Once your repository is on GitHub, you can add this deploy button to your README:

```markdown
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/YOUR_USERNAME/coronary-reconstruction-app)
```

### Manual Render Deployment

1. **Sign up/Login to Render**
   - Go to [render.com](https://render.com)
   - Sign up or login with your GitHub account

2. **Create a New Web Service**
   - Click "New +" button
   - Select "Web Service"
   - Connect your GitHub repository `coronary-reconstruction-app`

3. **Configure the Service**
   - **Name**: `coronary-reconstruction-app`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python src/main.py`
   - **Instance Type**: Choose based on your needs (Free tier available)

4. **Environment Variables** (Optional)
   - `FLASK_ENV`: Set to `production` for production deployment
   - No other environment variables are required

5. **Deploy**
   - Click "Create Web Service"
   - Render will automatically build and deploy your application
   - You'll get a URL like `https://coronary-reconstruction-app.onrender.com`

## Step 3: Verify Deployment

1. **Health Check**
   - Visit `https://your-app-url.onrender.com/api/coronary/health`
   - Should return: `{"service": "Coronary Reconstruction API", "status": "healthy", "version": "1.0.0"}`

2. **Main Application**
   - Visit your main application URL
   - Test the image upload functionality
   - Verify the analysis features work correctly

## Troubleshooting

### Common Issues

1. **Build Failures**
   - Check that `requirements.txt` includes all dependencies
   - Ensure Python version compatibility

2. **Memory Issues**
   - The application uses image processing libraries that require memory
   - Consider upgrading to a paid Render plan for better performance

3. **Timeout Issues**
   - Image processing can take time
   - Render free tier has request timeout limits
   - Consider optimizing image processing or upgrading plan

### Performance Optimization

1. **Image Size Limits**
   - The app is configured with 50MB max file size
   - Consider reducing for better performance on free tier

2. **Processing Optimization**
   - The CoronaryReconstructor uses simplified algorithms for web demo
   - Full processing capabilities are available but may require more resources

## File Structure for Render

The application is structured to work seamlessly with Render:

```
coronary-reconstruction-app/
├── Procfile                    # Render process configuration
├── requirements.txt            # Python dependencies
├── src/
│   ├── main.py                # Flask app entry point (PORT env var ready)
│   ├── static/                # Frontend files served by Flask
│   └── ...                    # Other application files
└── README.md                  # Project documentation
```

## Security Notes

- The application uses CORS to allow cross-origin requests
- File uploads are limited to 50MB
- Only image files are processed
- No persistent data storage (uses in-memory processing)

## Support

If you encounter any issues during deployment:

1. Check Render's build logs for error messages
2. Verify all files are properly committed to GitHub
3. Ensure the repository is public (or configure private repo access)
4. Test the application locally first using `python src/main.py`

## Next Steps

After successful deployment:

1. **Custom Domain**: Configure a custom domain in Render settings
2. **SSL Certificate**: Render provides free SSL certificates
3. **Monitoring**: Set up monitoring and alerts in Render dashboard
4. **Scaling**: Configure auto-scaling based on usage
5. **Database**: Add persistent storage if needed for user data

Your coronary reconstruction application will be live and accessible worldwide!

