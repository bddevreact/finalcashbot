# 🚂 Railway Deployment Guide for Cash Points Bot

## 📋 **Prerequisites**

1. **Railway Account**: Sign up at [railway.app](https://railway.app)
2. **GitHub Repository**: Your bot code should be in a GitHub repository
3. **Telegram Bot Token**: Get from [@BotFather](https://t.me/BotFather)
4. **Firebase Service Account**: Download from Firebase Console

---

## 🚀 **Step-by-Step Deployment**

### **Step 1: Prepare Your Repository**

Make sure your repository has these files:
- ✅ `bot.py` - Main bot file
- ✅ `requirements.txt` - Python dependencies
- ✅ `Procfile` - Railway start command
- ✅ `runtime.txt` - Python version
- ✅ `.railwayignore` - Files to exclude

### **Step 2: Connect to Railway**

1. **Login to Railway**: Go to [railway.app](https://railway.app)
2. **Create New Project**: Click "New Project"
3. **Connect GitHub**: Select "Deploy from GitHub repo"
4. **Select Repository**: Choose your bot repository
5. **Select Branch**: Choose `main` or `master` branch

### **Step 3: Configure Environment Variables**

In Railway dashboard, go to **Variables** tab and add:

```env
# Bot Configuration
BOT_TOKEN=your_telegram_bot_token_here
BOT_USERNAME=your_bot_username

# Firebase Configuration
FIREBASE_TYPE=service_account
FIREBASE_PROJECT_ID=your_project_id
FIREBASE_PRIVATE_KEY_ID=your_private_key_id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYour Private Key Here\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=your_service_account_email
FIREBASE_CLIENT_ID=your_client_id
FIREBASE_AUTH_URI=https://accounts.google.com/o/oauth2/auth
FIREBASE_TOKEN_URI=https://oauth2.googleapis.com/token
FIREBASE_AUTH_PROVIDER_X509_CERT_URL=https://www.googleapis.com/oauth2/v1/certs
FIREBASE_CLIENT_X509_CERT_URL=your_cert_url

# Railway Configuration
RAILWAY_ENVIRONMENT=true
WEBHOOK_URL=https://your-app-name.railway.app
WEBHOOK_SECRET=your_secret_token_here

# Group Configuration
REQUIRED_GROUP_ID=-1002551110221
REQUIRED_GROUP_LINK=https://t.me/+GOIMwAc_R9RhZGVk
REQUIRED_GROUP_NAME=Bull Trading Community (BD)

# Mini App Configuration
MINI_APP_URL=https://helpful-khapse-deec27.netlify.app/

# Reward Configuration
REFERRAL_REWARD=2
```

### **Step 4: Deploy**

1. **Automatic Deployment**: Railway will automatically deploy when you push to GitHub
2. **Manual Deployment**: Click "Deploy" in Railway dashboard
3. **Check Logs**: Monitor deployment in the "Deployments" tab

### **Step 5: Set Webhook**

After successful deployment:

1. **Get Your App URL**: Railway will provide a URL like `https://your-app-name.railway.app`
2. **Set Webhook**: Visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://your-app-name.railway.app/webhook`
3. **Verify Webhook**: Visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo`

---

## 🔧 **Configuration Files**

### **requirements.txt**
```txt
python-telegram-bot==20.7
firebase-admin==6.4.0
python-dotenv==1.0.0
requests==2.31.0
python-dateutil==2.8.2
jsonschema==4.20.0
colorlog==6.8.0
aiohttp==3.9.1
ratelimit==2.2.1
Flask==3.0.0
gunicorn==21.2.0
```

### **Procfile**
```
web: gunicorn --bind 0.0.0.0:$PORT bot:app
```

### **runtime.txt**
```
python-3.11.7
```

### **railway.json**
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python bot.py",
    "healthcheckPath": "/",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

---

## 🧪 **Testing**

### **Health Check**
Visit your app URL: `https://your-app-name.railway.app/`

Expected response:
```json
{
  "status": "healthy",
  "bot": "Cash Points Bot",
  "database": "connected",
  "timestamp": "2024-01-01T12:00:00"
}
```

### **Bot Commands**
Test these commands in Telegram:
- `/start` - Start the bot
- `/help` - Show help
- `/status` - Check bot status

---

## 📊 **Monitoring**

### **Railway Dashboard**
- **Deployments**: Check deployment status
- **Logs**: Monitor bot logs
- **Metrics**: CPU, memory usage
- **Variables**: Environment variables

### **Bot Logs**
Check logs in Railway dashboard for:
- ✅ Bot startup messages
- ✅ Firebase connection status
- ✅ Webhook setup
- ❌ Error messages

---

## 🔄 **Updates**

### **Automatic Updates**
1. Push changes to GitHub
2. Railway automatically redeploys
3. Monitor deployment logs

### **Manual Updates**
1. Go to Railway dashboard
2. Click "Deploy" button
3. Wait for deployment to complete

---

## 🚨 **Troubleshooting**

### **Common Issues**

#### **1. Bot Not Responding**
- Check webhook URL is correct
- Verify bot token is valid
- Check Railway logs for errors

#### **2. Firebase Connection Failed**
- Verify Firebase credentials
- Check service account permissions
- Ensure project ID is correct

#### **3. Deployment Failed**
- Check `requirements.txt` syntax
- Verify Python version in `runtime.txt`
- Check Railway logs for build errors

#### **4. Webhook Not Working**
- Verify webhook URL format
- Check if port is accessible
- Ensure HTTPS is enabled

### **Debug Commands**

#### **Check Webhook Status**
```
https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo
```

#### **Delete Webhook (for polling)**
```
https://api.telegram.org/bot<BOT_TOKEN>/deleteWebhook
```

#### **Set Webhook Manually**
```
https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://your-app.railway.app/webhook
```

---

## 💰 **Costs**

Railway pricing:
- **Free Tier**: $5 credit/month
- **Pro Plan**: Pay-as-you-go
- **Team Plan**: $20/month per user

Bot typically uses:
- **CPU**: Low usage
- **Memory**: ~100-200MB
- **Bandwidth**: Minimal

---

## 🔒 **Security**

### **Environment Variables**
- ✅ Never commit secrets to GitHub
- ✅ Use Railway's secure variable storage
- ✅ Rotate tokens regularly

### **Webhook Security**
- ✅ Use HTTPS only
- ✅ Set secret token
- ✅ Validate webhook requests

### **Firebase Security**
- ✅ Use service account with minimal permissions
- ✅ Enable Firestore security rules
- ✅ Monitor database access

---

## 📞 **Support**

### **Railway Support**
- [Railway Documentation](https://docs.railway.app/)
- [Railway Discord](https://discord.gg/railway)
- [Railway Status](https://status.railway.app/)

### **Bot Issues**
- Check Railway logs
- Verify environment variables
- Test locally first

---

## ✅ **Success Checklist**

- [ ] Repository connected to Railway
- [ ] Environment variables configured
- [ ] Deployment successful
- [ ] Health check endpoint working
- [ ] Webhook set correctly
- [ ] Bot responding to commands
- [ ] Firebase connection working
- [ ] Logs showing no errors

---

**🎉 Your Cash Points Bot is now deployed on Railway!**
