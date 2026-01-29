# Railway Deployment Guide

Complete guide to deploy the Insurance Comparator application on Railway with MySQL database.

## Prerequisites

1. Railway account (sign up at [railway.app](https://railway.app))
2. GitHub account (to connect your repository)
3. Git installed on your local machine

## Step 1: Prepare Your Code

Make sure all files are ready in the `WebSite` folder:
- ✅ `app.py` - Main Flask application
- ✅ `requirements.txt` - Python dependencies
- ✅ `Dockerfile` - Docker configuration
- ✅ `.env.example` - Environment variables template
- ✅ `database/models.py` - MySQL database models
- ✅ All other application files

## Step 2: Push Code to GitHub

```bash
# Navigate to your WebSite folder
cd "g:\6-Python Scraping Code\FreelanceScraperSuite\67-Insurance Automation\WebSite"

# Initialize git if not already done
git init

# Add all files
git add .

# Create .gitignore to exclude sensitive files
echo ".env" > .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore
echo "*.db" >> .gitignore
echo "static/uploads/*" >> .gitignore

# Commit changes
git commit -m "Initial commit for Railway deployment"

# Create a new repository on GitHub and push
git remote add origin YOUR_GITHUB_REPO_URL
git branch -M main
git push -u origin main
```

## Step 3: Create Railway Project

1. Go to [railway.app](https://railway.app) and log in
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Select your repository
5. Railway will detect the Dockerfile automatically

## Step 4: Add MySQL Database

1. In your Railway project dashboard, click "New"
2. Select "Database" → "Add MySQL"
3. Railway will automatically create a MySQL database and provide connection details
4. The `MYSQL_URL` environment variable will be automatically set

## Step 5: Configure Environment Variables

In your Railway project:

1. Click on your service (the one running your app)
2. Go to "Variables" tab
3. Click "Raw Editor" and add the following:

```bash
# Flask Configuration
SECRET_KEY=generate-a-secure-random-key-here
FLASK_ENV=production

# Admin User Credentials (Change these!)
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=SecurePassword123!
ADMIN_NAME=Admin

# Railway automatically provides MYSQL_URL, but you can also set individual variables:
# MYSQL_HOST will be auto-set by Railway
# MYSQL_PORT will be auto-set by Railway
# MYSQL_USER will be auto-set by Railway
# MYSQL_PASSWORD will be auto-set by Railway
# MYSQL_DATABASE will be auto-set by Railway

# Port (Railway sets this automatically, but you can specify)
PORT=8080
```

**Important Security Notes:**
- Generate a strong `SECRET_KEY` using: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- Change `ADMIN_PASSWORD` to a strong, unique password
- Change `ADMIN_EMAIL` to your actual email

## Step 6: Configure Service Settings

1. In your service settings, verify:
   - **Root Directory**: Leave blank (or set to `/WebSite` if deploying from parent folder)
   - **Build Command**: Automatic (Docker build)
   - **Start Command**: Defined in Dockerfile
   - **Health Check Path**: `/api/health`

2. Under "Networking":
   - Enable "Public Networking"
   - Note your public domain (e.g., `your-app.up.railway.app`)

## Step 7: Deploy

1. Railway will automatically deploy when you push to GitHub
2. Monitor the deployment logs in the "Deployments" tab
3. Wait for the build to complete (may take 5-10 minutes for first deployment)

## Step 8: Verify Deployment

1. Once deployed, click on the public URL
2. You should see the login page
3. Log in with your admin credentials
4. Test the following:
   - ✅ User creation
   - ✅ Insurance comparison form
   - ✅ Database export (Download BDD button in admin panel)
   - ✅ All scrapers working

## Database Access

### Using Railway's MySQL Client

1. In Railway dashboard, click on your MySQL database
2. Go to "Connect" tab
3. Use the provided connection details

### Using External MySQL Client

You can connect using tools like MySQL Workbench or DBeaver:

```
Host: Available in Railway MySQL "Connect" tab
Port: Available in Railway MySQL "Connect" tab
Username: Available in Railway MySQL "Connect" tab
Password: Available in Railway MySQL "Connect" tab
Database: Available in Railway MySQL "Connect" tab
```

### Download Database Backup

From the admin panel:
1. Log in as admin
2. Click "Télécharger BDD" button in the header
3. Excel file with all tables will be downloaded

## Troubleshooting

### Deployment Fails

**Issue**: Build fails with dependency errors
- **Solution**: Check `requirements.txt` for correct package versions
- Run locally: `pip install -r requirements.txt` to verify

**Issue**: MySQL connection fails
- **Solution**: Verify MYSQL_URL is set in environment variables
- Check that MySQL service is running in Railway

### Application Errors

**Issue**: 500 Internal Server Error
- **Solution**: Check deployment logs in Railway
- Look for Python traceback errors
- Verify all environment variables are set correctly

**Issue**: Database tables not created
- **Solution**: The app creates tables automatically on first run
- Check logs for database initialization messages
- Verify MySQL credentials are correct

### Performance Issues

**Issue**: Slow response times
- **Solution**:
  - Consider upgrading Railway plan for more resources
  - Increase worker count in Dockerfile if needed
  - Check MySQL connection pool settings

## Continuous Deployment

Railway automatically deploys when you push to GitHub:

```bash
# Make changes to your code
git add .
git commit -m "Your commit message"
git push origin main

# Railway will automatically detect the push and deploy
```

## Scaling

To handle more traffic:

1. **Vertical Scaling** (Railway dashboard):
   - Upgrade your Railway plan for more CPU/RAM
   - Adjust in Settings → Resources

2. **Horizontal Scaling** (Code changes):
   - In `Dockerfile`, increase workers:
     ```dockerfile
     CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120", "app:app"]
     ```

## Monitoring

### Health Check
- Endpoint: `https://your-app.up.railway.app/api/health`
- Should return: `{"status": "healthy", "providers": [...]}`

### Logs
- Access logs in Railway dashboard → Your Service → "Logs" tab
- Monitor for errors and performance issues

## Backup Strategy

### Database Backups

1. **Manual Backup** (via admin panel):
   - Log in as admin
   - Click "Télécharger BDD"
   - Store Excel file securely

2. **Automated Backup** (Railway):
   - Railway Pro plans include automated database backups
   - Configure in MySQL service settings

### Code Backups
- Code is already backed up in GitHub
- Tag releases for important versions:
  ```bash
  git tag -a v1.0 -m "Production release 1.0"
  git push origin v1.0
  ```

## Cost Estimation

Railway pricing (as of 2024):
- **Hobby Plan**: $5/month - Good for testing
- **Pro Plan**: $20/month - Recommended for production
- **MySQL Database**: Included in plan
- Additional costs for high resource usage

## Security Best Practices

1. ✅ Never commit `.env` file to GitHub
2. ✅ Use strong passwords for admin account
3. ✅ Regularly update dependencies
4. ✅ Enable Railway's firewall rules if needed
5. ✅ Regular database backups
6. ✅ Monitor logs for suspicious activity

## Support

For issues with:
- **Railway Platform**: [Railway Documentation](https://docs.railway.app)
- **Application Code**: Check deployment logs and error messages
- **Database**: Use Railway's MySQL client for direct access

## Quick Commands Reference

```bash
# View logs
railway logs

# SSH into service (Railway CLI)
railway run bash

# Rollback to previous deployment
# Go to Railway dashboard → Deployments → Select previous → "Redeploy"

# Update environment variables
# Railway dashboard → Variables → Update → Redeploy
```

---

## Migration from SQLite to MySQL (Complete)

✅ Database models updated to use MySQL with connection pooling
✅ All queries converted from SQLite to MySQL syntax
✅ Support for both MYSQL_URL and individual connection parameters
✅ Excel export functionality added for complete database download
✅ Docker configuration optimized for MySQL
✅ Environment variables configured for Railway deployment

Your application is now ready for production deployment on Railway!
