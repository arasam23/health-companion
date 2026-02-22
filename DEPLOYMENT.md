# Health Companion - GCP Deployment Guide

This guide outlines how to deploy the Health Companion system to Google Cloud Platform using **Cloud Run** and **Cloud Scheduler**.

## Prerequisites
1. A Google Cloud Platform (GCP) Account with Billing Enabled.
2. The `gcloud` CLI installed and authenticated (`gcloud auth login`).
3. Your `GEMINI_API_KEY`.

## 1. Deploy the Streamlit App to Cloud Run

We will use Google Cloud Build to containerize the app and deploy it to Cloud Run.

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"
gcloud config set project $PROJECT_ID

# Enable Required APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com cloudscheduler.googleapis.com

# Deploy to Cloud Run
gcloud run deploy health-companion \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="GEMINI_API_KEY=your_gemini_api_key_here"
```

Once deployed, the CLI will output the **Service URL** (e.g., `https://health-companion-xyz.a.run.app`).

### Using as a Progressive Web App (PWA) on Android
1. Open the Cloud Run Service URL in your Android Chrome browser.
2. Tap the three dots (menu) in the top right.
3. Tap **"Add to Home screen"**.
4. The app will now appear on your home screen and launch without the browser UI, functioning like a native app.

## 2. Deploy the Reporting Scheduler

The `scheduler.py` script needs to run periodically (e.g., hourly) to check the SQLite database for due reports. 
Because Cloud Run containers are stateless, you should ideally migrate the SQLite `.db` file to a **Cloud Storage FUSE mount** or **Cloud SQL (PostgreSQL)** to share state between the frontend container and the scheduler container.

Assuming you are using a shared state (like Cloud SQL or FUSE), you run the scheduler as a Cloud Run Job.

```bash
# Deploy as a Cloud Run Job
gcloud run jobs create health-scheduler \
  --source . \
  --region us-central1 \
  --command="python" \
  --args="scheduler.py" \
  --set-env-vars="GEMINI_API_KEY=your_gemini_api_key_here"
```

Create a Cloud Scheduler trigger to run exactly on the hour:

```bash
gcloud scheduler jobs create http trigger-health-scheduler \
  --location us-central1 \
  --schedule="0 * * * *" \
  --uri="https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/health-scheduler:run" \
  --http-method POST \
  --oauth-service-account-email="your-compute-service-account@$PROJECT_ID.iam.gserviceaccount.com"
```

## Summary
You now have:
- A serverless Streamlit UI serving as your PWA interface.
- A background chron scheduler executing LangGraph reports automatically based on user-defined UI inputs.
