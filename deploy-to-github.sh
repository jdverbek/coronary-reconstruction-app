#!/bin/bash

# Deploy Coronary Reconstruction App to GitHub
echo "🚀 Deploying Coronary Reconstruction App to GitHub..."

# Check if gh CLI is available
if command -v gh &> /dev/null; then
    echo "✅ GitHub CLI found"
    
    # Check if user is authenticated
    if gh auth status &> /dev/null; then
        echo "✅ GitHub CLI authenticated"
        
        # Create repository and push
        echo "📦 Creating GitHub repository..."
        gh repo create coronary-reconstruction-app --public --description "Professional web application for coronary artery 3D reconstruction from medical images" --push
        
        echo "🎉 Successfully deployed to GitHub!"
        echo "📋 Repository URL: $(gh repo view --json url -q .url)"
        echo ""
        echo "🌐 Next steps:"
        echo "1. Go to render.com"
        echo "2. Create a new Web Service"
        echo "3. Connect your GitHub repository"
        echo "4. Use these settings:"
        echo "   - Build Command: pip install -r requirements.txt"
        echo "   - Start Command: python src/main.py"
        echo ""
        echo "📖 See DEPLOYMENT.md for detailed instructions"
        
    else
        echo "❌ GitHub CLI not authenticated"
        echo "Please run: gh auth login"
        echo "Then run this script again"
    fi
    
else
    echo "❌ GitHub CLI not found"
    echo "Please install GitHub CLI first:"
    echo "https://cli.github.com/"
    echo ""
    echo "Or create repository manually:"
    echo "1. Go to github.com and create new repository 'coronary-reconstruction-app'"
    echo "2. Run these commands:"
    echo "   git remote add origin https://github.com/YOUR_USERNAME/coronary-reconstruction-app.git"
    echo "   git branch -M main"
    echo "   git push -u origin main"
fi

