# Deploying to Vercel

This guide provides step-by-step instructions for deploying the Daily Rewards Report Generator to Vercel.

## Prerequisites

1. A Vercel account (create one at [vercel.com](https://vercel.com) if you don't have one)
2. Node.js installed on your local machine (for the Vercel CLI)
3. Git (if deploying from a repository)

## Option 1: Deploy from Local Directory Using Vercel CLI

### Step 1: Install Vercel CLI

```bash
npm install -g vercel
```

### Step 2: Login to Vercel

```bash
vercel login
```

Follow the prompts to authenticate your account.

### Step 3: Navigate to Project Directory

```bash
cd path/to/rewards-report-app
```

### Step 4: Deploy to Vercel

```bash
vercel
```

This command will start the deployment process. You'll be asked a series of questions about your project:

- Set up and deploy? Yes.
- Which scope? Select your account.
- Link to existing project? No.
- What's your project name? rewards-report-app (or your preferred name).
- In which directory is your code located? ./ (default).
- Want to override settings? No.

### Step 5: Add Environment Variables

1. After deployment, go to the [Vercel dashboard](https://vercel.com/dashboard)
2. Select your project
3. Go to "Settings" -> "Environment Variables"
4. Add a new variable:
   - NAME: `SECRET_KEY`
   - VALUE: Generate a random string (e.g., using `openssl rand -hex 24` in terminal)
5. Click "Save"

### Step 6: Deploy to Production

```bash
vercel --prod
```

This will deploy your application to production.

## Option 2: Deploy from a Git Repository

### Step 1: Push your code to a Git repository

Create a repository on GitHub, GitLab, or Bitbucket and push your code:

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repository-url>
git push -u origin main
```

### Step 2: Connect to Vercel

1. Go to the [Vercel dashboard](https://vercel.com/dashboard)
2. Click "New Project"
3. Import your Git repository
4. Configure the project:
   - Framework Preset: Other
   - Root Directory: ./
   - Build Command: leave empty
   - Output Directory: leave empty
5. Click "Deploy"

### Step 3: Add Environment Variables

1. After deployment, go to the project settings
2. Navigate to "Environment Variables"
3. Add a new variable:
   - NAME: `SECRET_KEY`
   - VALUE: Generate a random string (e.g., using `openssl rand -hex 24` in terminal)
4. Click "Save"
5. Redeploy your application for the changes to take effect

## Verifying Your Deployment

After deployment is complete, Vercel will provide you with a URL to access your application.

1. Visit the provided URL
2. Test the application by uploading a CSV file
3. Verify that the report is generated correctly

## Troubleshooting

If you encounter any issues during deployment:

1. Check the deployment logs in the Vercel dashboard
2. Ensure your `requirements.txt` file includes all necessary dependencies
3. Verify that the `vercel.json` file is configured correctly
4. Make sure the `SECRET_KEY` environment variable is set

## Updating Your Deployment

To update your deployment after making changes:

1. If using CLI: run `vercel` or `vercel --prod` again
2. If using Git: push changes to your repository, and Vercel will automatically redeploy

## Custom Domains

To use a custom domain:

1. Go to your project settings in the Vercel dashboard
2. Navigate to "Domains"
3. Add your domain and follow the verification steps 