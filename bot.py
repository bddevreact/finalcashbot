#!/usr/bin/env python3
"""
Cash Points Telegram Bot
Features:
- Referral link detection and processing
- Group membership verification
- Automatic reward distribution
- Rejoin detection and prevention
- Firebase database integration
"""

import os
import logging
import requests
from datetime import datetime
from typing import Optional, Dict, Any
from flask import Flask, request, jsonify

# Telegram Bot imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters
)

# Firebase imports
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Flask app for Railway health checks
app = Flask(__name__)

# Load environment variables safely
try:
    load_dotenv()
except Exception as e:
    print(f"⚠️ Warning: Could not load .env file: {e}")
    print("📝 Continuing with system environment variables...")

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def safe_getenv(key, default=''):
    """Safely get environment variable, handling null characters"""
    try:
        value = os.getenv(key, default)
        if value and '\x00' in value:
            # Remove null characters
            value = value.replace('\x00', '')
        return value
    except Exception:
        return default

# Bot configuration
BOT_TOKEN = safe_getenv('BOT_TOKEN', '')
BOT_USERNAME = 'CashPoinntbot'

# Group configuration
REQUIRED_GROUP_ID = -1002963279317  # Bull Trading Community (BD)
REQUIRED_GROUP_LINK = "https://t.me/+IJgHDdrX1yZlZWRh"
REQUIRED_GROUP_NAME = "BT Learn & Earn Community BD"

# Mini App configuration
MINI_APP_URL = "https://cashpoinnts.netlify.app/"

# Reward configuration
REFERRAL_REWARD = 2  # 2 Taka per successful referral

# Initialize Firebase with better error handling
db = None
firebase_error_details = None

# Global bot instance
bot_instance = None

# Flask routes for Railway health checks
@app.route('/')
def health_check():
    """Health check endpoint for Railway"""
    return jsonify({
        'status': 'healthy',
        'bot': 'Cash Points Bot',
        'database': 'connected' if db else 'offline',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook endpoint for Telegram bot"""
    if request.method == 'POST':
        if bot_instance:
            # Forward the webhook to the bot
            update = Update.de_json(request.get_json(), bot_instance.application.bot)
            bot_instance.application.process_update(update)
            return jsonify({'status': 'ok'})
        else:
            return jsonify({'status': 'error', 'message': 'Bot not initialized'}), 500
    return jsonify({'status': 'error', 'message': 'Method not allowed'}), 405

def check_system_time():
    """Check if system time is reasonable (not too far off)"""
    try:
        import requests
        from datetime import datetime
        
        # Get current time from a reliable source
        response = requests.get('http://worldtimeapi.org/api/timezone/Etc/UTC', timeout=5)
        if response.status_code == 200:
            server_time = datetime.fromisoformat(response.json()['datetime'].replace('Z', '+00:00'))
            local_time = datetime.now()
            time_diff = abs((server_time - local_time).total_seconds())
            
            if time_diff > 300:  # More than 5 minutes difference
                return False, f"System time is {time_diff:.0f} seconds off from server time"
            return True, None
    except Exception as e:
        # If we can't check, assume it's fine
        return True, f"Could not verify time sync: {e}"
    
    return True, None

def validate_firebase_connection():
    """Test Firebase connection with a simple operation"""
    try:
        # Try a simple read operation to test connection
        test_ref = db.collection('_connection_test').limit(1)
        list(test_ref.stream())
        return True, None
    except Exception as e:
        error_str = str(e)
        print(f"❌ Firebase connection test failed: {error_str}")
        
        if "Invalid JWT Signature" in error_str or "invalid_grant" in error_str:
            print("🔍 JWT signature error detected. This usually means:")
            print("   - Service account key is corrupted")
            print("   - System time is incorrect")
            print("   - Private key format is wrong")
            
            # Try to wait and retry once for JWT issues
            print("⏳ Waiting 2 seconds and retrying...")
            import time
            time.sleep(2)
            try:
                list(test_ref.stream())
                print("✅ Retry successful!")
                return True, None
            except Exception as retry_e:
                print(f"❌ Retry failed: {str(retry_e)}")
                return False, f"Retry failed: {str(retry_e)}"
        
        return False, error_str

try:
    print("🔧 Initializing Firebase connection...")
    
    # Check system time first
    time_ok, time_msg = check_system_time()
    if not time_ok:
        print(f"⚠️ System time issue: {time_msg}")
        print("🔧 This may cause JWT signature errors")
    else:
        print("✅ System time check passed")
    
    # Prioritize environment variables for Railway deployment
    firebase_project_id = safe_getenv('FIREBASE_PROJECT_ID')
    firebase_private_key = safe_getenv('FIREBASE_PRIVATE_KEY')
    firebase_client_email = safe_getenv('FIREBASE_CLIENT_EMAIL')
    
    if firebase_project_id and firebase_private_key and firebase_client_email:
        print("🌍 Loading Firebase credentials from environment variables (Railway)")
        
        # Fix private key format for Railway
        private_key = firebase_private_key.strip()
        if private_key.startswith('"') and private_key.endswith('"'):
            private_key = private_key[1:-1]
        private_key = private_key.replace('\\n', '\n')
        
        firebase_config = {
            "type": "service_account",
            "project_id": firebase_project_id,
            "private_key_id": safe_getenv('FIREBASE_PRIVATE_KEY_ID', ''),
            "private_key": private_key,
            "client_email": firebase_client_email,
            "client_id": safe_getenv('FIREBASE_CLIENT_ID', ''),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": safe_getenv('FIREBASE_CLIENT_X509_CERT_URL', ''),
            "universe_domain": "googleapis.com"
        }
        
        print(f"🔑 Service Account: {firebase_client_email}")
        print(f"🏗️ Project ID: {firebase_project_id}")
        
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)
        
    elif os.path.exists('serviceAccountKey.json'):
        print("📄 Loading Firebase credentials from serviceAccountKey.json")
        
        # Fix the service account key format
        try:
            with open('serviceAccountKey.json', 'r') as f:
                import json
                key_data = json.load(f)
                
                # Fix private key format
                private_key = key_data.get('private_key', '')
                if private_key:
                    # Remove outer quotes if present
                    if private_key.startswith('"') and private_key.endswith('"'):
                        private_key = private_key[1:-1]
                    
                    # Replace \\n with \n
                    private_key = private_key.replace('\\n', '\n')
                    
                    # Update the key data
                    key_data['private_key'] = private_key
                    
                    # Write back the fixed data
                    with open('serviceAccountKey.json', 'w') as f:
                        json.dump(key_data, f, indent=2)
                    
                    print("✅ Fixed private key format in serviceAccountKey.json")
                
                required_fields = ['type', 'project_id', 'private_key', 'client_email']
                missing_fields = [field for field in required_fields if not key_data.get(field)]
                
                if missing_fields:
                    raise ValueError(f"Missing required fields in serviceAccountKey.json: {missing_fields}")
                
                print(f"🔑 Service Account: {key_data.get('client_email')}")
                print(f"🏗️ Project ID: {key_data.get('project_id')}")
                
                cred = credentials.Certificate('serviceAccountKey.json')
                firebase_admin.initialize_app(cred)
                
        except Exception as e:
            print(f"❌ Error loading serviceAccountKey.json: {e}")
            raise
        
    else:
        raise ValueError("No Firebase credentials found. Please set environment variables or provide serviceAccountKey.json")
    
    # Initialize Firestore client
    db = firestore.client()
    print(f"✅ Firebase Admin SDK initialized")
    print(f"🔗 Project ID: {db.project}")
    
    # Test the connection with actual database operation
    print("🧪 Testing Firebase connection...")
    is_connected, test_error = validate_firebase_connection()
    
    if is_connected:
        print("✅ Firebase database connection verified")
    else:
        print(f"⚠️ Firebase connection test failed: {test_error}")
        print("🔄 Bot will continue with limited functionality")
        firebase_error_details = test_error
        # Don't set db = None here, keep it for basic operations
    
except Exception as e:
    print(f"❌ Firebase initialization failed: {e}")
    firebase_error_details = str(e)
    
    # Check for specific error types
    if "Invalid JWT Signature" in str(e) or "invalid_grant" in str(e):
        print("🔧 JWT SIGNATURE ERROR TROUBLESHOOTING:")
        print("1. ⏰ Check system time synchronization")
        print("2. 🔑 Regenerate service account key from Firebase Console")
        print("3. 📄 Verify serviceAccountKey.json is complete and valid")
        print("4. 🌐 Check internet connectivity")
        print("5. 🏗️ Verify Firebase project is active and billing enabled")
        print("6. 🔐 Ensure service account has proper permissions")
        print("7. 💻 Try restarting the bot after 1-2 minutes")
    elif "ServiceUnavailable" in str(e):
        print("🔧 SERVICE UNAVAILABLE ERROR:")
        print("1. 🌐 Check internet connectivity")
        print("2. 🔄 Firebase services may be temporarily down")
        print("3. ⏳ Wait a few minutes and try again")
    elif "PermissionDenied" in str(e):
        print("🔧 PERMISSION DENIED ERROR:")
        print("1. 🔐 Check service account permissions")
        print("2. 🏗️ Verify Firestore is enabled in Firebase Console")
        print("3. 📋 Check Firestore security rules")
    
    print("⚠️ Bot will continue in offline mode")
    db = None


class CashPoinntBot:
    def __init__(self):
        self.db = db
        self.firebase_connected = db is not None
        self.fallback_mode = not self.firebase_connected
        self.firebase_error = firebase_error_details
        
    async def check_group_membership(self, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Check if user is member of required group"""
        try:
            chat_member = await context.bot.get_chat_member(REQUIRED_GROUP_ID, user_id)
            return chat_member.status in ['member', 'administrator', 'creator']
        except Exception as e:
            logger.error(f"Error checking group membership for {user_id}: {e}")
            return False
    
    def generate_referral_code(self, user_id: int) -> str:
        """Generate referral code for user"""
        try:
            # Use CP + full telegram ID (matching mini app and enhanced bot)
            return f"CP{str(user_id)}"
        except Exception as e:
            logger.error(f"Error generating referral code: {e}")
            return f"CP{str(user_id)}"
    
    async def get_user_from_db(self, telegram_id: str) -> Optional[Dict[str, Any]]:
        """Get user data from Firebase"""
        if not self.db:
            return None
            
        try:
            users_ref = self.db.collection('users')
            query = users_ref.where('telegram_id', '==', telegram_id).limit(1)
            docs = list(query.stream())
            
            if docs:
                return docs[0].to_dict()
            return None
        except Exception as e:
            logger.warning(f"Database query failed (continuing without DB): {e}")
            return None
    
    async def create_or_update_user(self, user_data: Dict[str, Any]) -> bool:
        """Create or update user in Firebase"""
        if not self.db:
            logger.info("📝 Database not connected, skipping user creation")
            return False
            
        try:
            users_ref = self.db.collection('users')
            telegram_id = str(user_data['telegram_id'])
            
            # Check if user exists
            existing_user = await self.get_user_from_db(telegram_id)
            
            if existing_user:
                # Update existing user
                query = users_ref.where('telegram_id', '==', telegram_id).limit(1)
                docs = list(query.stream())
                if docs:
                    docs[0].reference.update({
                        'username': user_data.get('username', ''),
                        'first_name': user_data.get('first_name', ''),
                        'last_name': user_data.get('last_name', ''),
                        'last_active': datetime.now(),
                        'updated_at': datetime.now()
                    })
                    logger.info(f"✅ Updated user {telegram_id} in database")
                    return True
            else:
                # Create new user
                new_user_data = {
                    'telegram_id': telegram_id,
                    'username': user_data.get('username', ''),
                    'first_name': user_data.get('first_name', ''),
                    'last_name': user_data.get('last_name', ''),
                    'balance': 0,
                    'total_earnings': 0,
                    'total_referrals': 0,
                    'referral_code': self.generate_referral_code(int(telegram_id)),
                    'is_verified': False,
                    'is_banned': False,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now(),
                    'last_active': datetime.now()
                }
                
                users_ref.add(new_user_data)
                logger.info(f"✅ Created new user {telegram_id} in database")
                return True
                
        except Exception as e:
            logger.warning(f"Database operation failed (continuing without DB): {e}")
            return False
    
    async def process_referral(self, referrer_id: str, referred_id: str, referral_code: str) -> bool:
        """Process referral and check for duplicates"""
        if not self.db:
            logger.info("📝 Database not connected, skipping referral processing")
            return False
            
        try:
            referrals_ref = self.db.collection('referrals')
            
            # Check if referral already exists (rejoin detection)
            # Check for both referrer_id and referred_id combination to prevent duplicates
            existing_query = referrals_ref.where('referred_id', '==', referred_id).where('referrer_id', '==', referrer_id).limit(1)
            existing_docs = list(existing_query.stream())
            
            if existing_docs:
                # This is a duplicate referral - update rejoin count but don't give reward
                existing_referral = existing_docs[0].to_dict()
                rejoin_count = existing_referral.get('rejoin_count', 0) + 1
                
                existing_docs[0].reference.update({
                    'rejoin_count': rejoin_count,
                    'last_rejoin_date': datetime.now(),
                    'updated_at': datetime.now()
                })
                
                logger.info(f"⚠️ Duplicate referral detected for user {referred_id} by referrer {referrer_id}. Count: {rejoin_count}")
                return False  # No reward for duplicate
            
            # Also check if user was referred by someone else before
            other_referral_query = referrals_ref.where('referred_id', '==', referred_id).limit(1)
            other_referral_docs = list(other_referral_query.stream())
            
            if other_referral_docs:
                # User was referred by someone else before
                other_referral = other_referral_docs[0].to_dict()
                other_referrer = other_referral['referrer_id']
                logger.warning(f"⚠️ User {referred_id} was already referred by {other_referrer}, ignoring new referral from {referrer_id}")
                return False  # No reward for second referrer
            
            # Create new referral record
            referral_data = {
                'referrer_id': referrer_id,
                'referred_id': referred_id,
                'referral_code': referral_code,
                'status': 'pending_group_join',
                'created_at': datetime.now(),
                'group_join_verified': False,
                'rejoin_count': 0,
                'reward_given': False
            }
            
            referrals_ref.add(referral_data)
            logger.info(f"✅ Created referral record: {referrer_id} → {referred_id}")
            return True
            
        except Exception as e:
            logger.warning(f"Referral processing failed (continuing without DB): {e}")
            return False
    
    async def verify_group_join_and_reward(self, user_id: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Verify group join and distribute reward to referrer"""
        if not self.db:
            logger.info("📝 Database not connected, skipping reward processing")
            return False
            
        try:
            # Check if user is actually a group member
            is_member = await self.check_group_membership(int(user_id), context)
            if not is_member:
                return False
            
            referrals_ref = self.db.collection('referrals')
            
            # Find pending referral for this user
            query = referrals_ref.where('referred_id', '==', user_id).where('status', '==', 'pending_group_join').limit(1)
            docs = list(query.stream())
            
            if not docs:
                logger.info(f"No pending referral found for user {user_id}")
                return False
            
            referral_doc = docs[0]
            referral_data = referral_doc.to_dict()
            referrer_id = referral_data['referrer_id']
            referral_code = referral_data['referral_code']
            
            # Update referral status
            referral_doc.reference.update({
                'status': 'verified',
                'group_join_verified': True,
                'group_join_date': datetime.now(),
                'reward_given': True,
                'updated_at': datetime.now()
            })
            
            # Update referrer's balance and stats
            users_ref = self.db.collection('users')
            referrer_query = users_ref.where('telegram_id', '==', referrer_id).limit(1)
            referrer_docs = list(referrer_query.stream())
            
            if referrer_docs:
                referrer_doc = referrer_docs[0]
                referrer_data = referrer_doc.to_dict()
                
                new_balance = referrer_data.get('balance', 0) + REFERRAL_REWARD
                new_total_earnings = referrer_data.get('total_earnings', 0) + REFERRAL_REWARD
                new_total_referrals = referrer_data.get('total_referrals', 0) + 1
                
                referrer_doc.reference.update({
                    'balance': new_balance,
                    'total_earnings': new_total_earnings,
                    'total_referrals': new_total_referrals,
                    'updated_at': datetime.now()
                })
                
                # Update referral_codes collection
                try:
                    referral_codes_ref = self.db.collection('referralCodes')
                    referral_code_query = referral_codes_ref.where('referral_code', '==', referral_code).limit(1)
                    referral_code_docs = list(referral_code_query.stream())
                    
                    if referral_code_docs:
                        referral_code_doc = referral_code_docs[0]
                        current_usage = referral_code_doc.to_dict().get('usage_count', 0)
                        referral_code_doc.reference.update({
                            'usage_count': current_usage + 1,
                            'last_used': datetime.now(),
                            'updated_at': datetime.now()
                        })
                        logger.info(f"✅ Updated referral code usage count: {referral_code}")
                except Exception as e:
                    logger.warning(f"Failed to update referral code usage: {e}")
                
                # Create earnings record
                earnings_ref = self.db.collection('earnings')
                earnings_data = {
                    'user_id': referrer_id,
                    'amount': REFERRAL_REWARD,
                    'type': 'referral',
                    'description': f'Referral reward from user {user_id}',
                    'referral_id': referral_doc.id,
                    'created_at': datetime.now()
                }
                earnings_ref.add(earnings_data)
                
                logger.info(f"✅ Rewarded {REFERRAL_REWARD} Taka to referrer {referrer_id}")
                return True
            
        except Exception as e:
            logger.warning(f"Reward processing failed (continuing without DB): {e}")
            return False
        
        return False


# Initialize bot instance
bot_instance = CashPoinntBot()


# Command Handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with referral detection"""
    user = update.effective_user
    user_id = str(user.id)
    user_name = user.first_name or user.username or f"User{user.id}"
    
    logger.info(f"👤 User {user_name} (ID: {user_id}) started bot")
    
    # Create or update user in database
    user_data = {
        'telegram_id': user.id,
        'username': user.username or '',
        'first_name': user.first_name or '',
        'last_name': user.last_name or ''
    }
    
    # Try to store user data
    user_stored = await bot_instance.create_or_update_user(user_data)
    
    # Add status indicator for database connection
    db_status = "🔥 Database: ✅ Connected" if bot_instance.firebase_connected else "⚠️ Database: ❌ Offline Mode"
    
    # Check for referral parameter
    referral_code = None
    referrer_id = None
    
    if context.args:
        referral_code = context.args[0]
        logger.info(f"🔗 Referral code detected: {referral_code}")
        
        # Extract referrer ID from referral code (CP format)
        if referral_code.startswith('CP') and len(referral_code) >= 3:
            # Find referrer by referral code
            if bot_instance.db:
                try:
                    # First try to find in users collection (primary method)
                    users_ref = bot_instance.db.collection('users')
                    user_query = users_ref.where('referral_code', '==', referral_code).limit(1)
                    user_docs = list(user_query.stream())
                    
                    if user_docs:
                        referrer_id = user_docs[0].to_dict()['telegram_id']
                        logger.info(f"✅ Found referrer {referrer_id} by referral code {referral_code}")
                    else:
                        # Fallback: try referral_codes collection
                        referral_codes_ref = bot_instance.db.collection('referralCodes')
                        query = referral_codes_ref.where('referral_code', '==', referral_code).where('is_active', '==', True).limit(1)
                        docs = list(query.stream())
                        
                        if docs:
                            referrer_id = docs[0].to_dict()['user_id']
                            logger.info(f"✅ Found referrer {referrer_id} in referral_codes collection")
                        else:
                            logger.warning(f"❌ No referrer found for code: {referral_code}")
                            # Try to create missing referral codes
                            await bot_instance.create_missing_referral_codes()
                            referrer_id = None
                    
                    if referrer_id and referrer_id != user_id:
                        # Process referral
                        await bot_instance.process_referral(referrer_id, user_id, referral_code)
                        logger.info(f"✅ Processed referral: {referrer_id} → {user_id}")
                    elif referrer_id == user_id:
                        logger.warning(f"⚠️ User {user_id} tried to use their own referral code")
                    else:
                        logger.info(f"⚠️ No valid referrer found for code: {referral_code}")
                        
                except Exception as e:
                    logger.error(f"Error processing referral code {referral_code}: {e}")
            else:
                logger.info("📝 Database not connected, skipping referral processing")
        else:
            logger.info(f"⚠️ Invalid referral code format: {referral_code}")
    
    # Check if user is already a group member
    is_member = await bot_instance.check_group_membership(user.id, context)
    
    if is_member:
        # User is already a member - show mini app directly
        welcome_text = (
            f"🎉 <b>স্বাগতম {user_name}!</b>\n\n"
            "✅ আপনি সফলভাবে আমাদের গ্রুপে যুক্ত হয়েছেন।\n\n"
            "📢 প্রতিদিন রাত ৯টায় আমাদের <b>লাইভ ক্লাসে</b> যোগ দেওয়ার সুযোগ পাচ্ছেন।\n"
            "👀 নিয়মিত চোখ রাখুন আমাদের গ্রুপে, যেন কোনো আপডেট মিস না হয়।\n\n"
            "🏆 <b>রিওয়ার্ড অর্জন এখন আরও সহজ!</b>\n"
            "💰 কোনো ইনভেস্টমেন্ট ছাড়াই প্রতিদিন জিতে নিন বিশেষ রিওয়ার্ড।\n"
            "🎁 <b>App ব্যবহার করে বন্ধুদের গ্রুপে আমন্ত্রণ জানান এবং জিতে নিন সর্বোচ্চ ৫,২০০ টাকা (BDT)!</b>\n\n"
            "👉 পাশের <b>Earn</b> বাটনে ট্যাপ করে এখনই <b>Mini App</b> ওপেন করুন এবং রিওয়ার্ড ক্লেইম করুন!"
        )

        
        keyboard = [
            [InlineKeyboardButton("Open and Earn 💰", url=MINI_APP_URL)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_photo(
            photo="https://i.postimg.cc/65Sx65jK/01.jpg",
            caption=welcome_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        # If this was a referral, verify and reward
        if referrer_id:
            await bot_instance.verify_group_join_and_reward(user_id, context)
        
    else:
        # User is not a member - show join requirement
        join_text = (
            f"🔒 <b>Group Join Required</b>\n\n"
            f"হ্যালো {user_name}! Mini App access পেতে আমাদের group এ join করতে হবে।\n\n"
            "📋 <b>Requirements:</b>\n"
            "✅ Group এ join করুন\n"
            "✅ তারপর 'Verify Membership' বাটনে ক্লিক করুন\n"
            "✅ Mini App access পাবেন\n\n"
            "💰 <b>Benefits:</b>\n"
            "🎁 Daily rewards\n"
            "🎯 Easy tasks\n"
            "🚀 Level up system\n"
            "💎 Real money earnings\n\n"
            "⚠️ <b>গুরুত্বপূর্ণ সতর্কতা:</b>\n"
            "🚫 Group এ join না করলে withdrawal দেওয়া হবে না\n"
            "💸 আপনার balance থাকলেও withdrawal করতে পারবেন না\n"
            "🔒 শুধুমাত্র group member রা withdrawal করতে পারবে\n\n"
            "👉 <b>Join the group now!</b>"
        )
        
        keyboard = [
            [InlineKeyboardButton(f"📱 Join {REQUIRED_GROUP_NAME}", url=REQUIRED_GROUP_LINK)],
            [InlineKeyboardButton("✅ Verify Membership", callback_data="verify_membership")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_photo(
            photo="https://i.postimg.cc/44DtvWyZ/43b0363d-525b-425c-bc02-b66f6d214445-1.jpg",
            caption=join_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries (button clicks)"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = str(user.id)
    user_name = user.first_name or user.username or f"User{user.id}"
    
    if query.data == "verify_membership":
        # Check if user is now a member
        is_member = await bot_instance.check_group_membership(user.id, context)
        
        if is_member:
            # User joined - show success message and mini app
            success_text = (
                f"🎉 <b>স্বাগতম {user_name}!</b>\n\n"
                "✅ আপনি সফলভাবে আমাদের গ্রুপে যোগদান করেছেন!\n\n"
                "🏆 <b>রিওয়ার্ড অর্জন এখন আরও সহজ!</b>\n"
                "💰 কোনো ইনভেস্টমেন্ট ছাড়াই প্রতিদিন জিতে নিন রিওয়ার্ড।\n"
                "👥 শুধু টেলিগ্রামে মেম্বার অ্যাড করুন,\n"
                "🎯 সহজ কিছু টাস্ক সম্পন্ন করুন আর\n"
                "🚀 লেভেল আপ করুন।\n\n"
                "👉 এখনই Mini App খুলুন এবং আপনার রিওয়ার্ড ক্লেইম করুন!"
            )
            
            keyboard = [
                [InlineKeyboardButton("🚀 Open Mini App", url=MINI_APP_URL)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Verify group join and reward referrer
            reward_given = await bot_instance.verify_group_join_and_reward(user_id, context)
            
            if reward_given:
                success_text += "\n\n🎁 <b>Bonus:</b> Your referrer has been rewarded!"
            
            # Add database status
            db_status = "🔥 Database: ✅ Connected" if bot_instance.firebase_connected else "⚠️ Database: ❌ Offline Mode"
            success_text += f"\n\n{db_status}"
            
            try:
                await query.edit_message_caption(
                    caption=success_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            except Exception:
                # If edit fails, send new message
                await query.message.reply_photo(
                    photo="https://i.postimg.cc/65Sx65jK/01.jpg",
                    caption=success_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
        
        else:
            # User is still not a member
            not_member_text = (
                f"❌ <b>Group Join Required</b>\n\n"
                f"হ্যালো {user_name}! আপনি এখনও group এ join করেননি।\n\n"
                "📋 <b>Please:</b>\n"
                f"1️⃣ Join {REQUIRED_GROUP_NAME}\n"
                "2️⃣ Then click 'Verify Membership' again\n\n"
                "🔒 Mini App access is only available for group members.\n\n"
                "⚠️ <b>গুরুত্বপূর্ণ সতর্কতা:</b>\n"
                "🚫 Group এ join না করলে withdrawal দেওয়া হবে না\n"
                "💸 আপনার balance থাকলেও withdrawal করতে পারবেন না\n"
                "🔒 শুধুমাত্র group member রা withdrawal করতে পারবে"
            )
            
            keyboard = [
                [InlineKeyboardButton(f"📱 Join {REQUIRED_GROUP_NAME}", url=REQUIRED_GROUP_LINK)],
                [InlineKeyboardButton("✅ Verify Membership", callback_data="verify_membership")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_caption(
                    caption=not_member_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            except Exception:
                # If edit fails, send new message
                await query.message.reply_text(
                    not_member_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - show bot and database status"""
    user = update.effective_user
    user_name = user.first_name or user.username or f"User{user.id}"
    
    # Check group membership
    is_member = await bot_instance.check_group_membership(user.id, context)
    
    status_text = (
        f"🤖 <b>Bot Status Report</b>\n\n"
        f"👤 <b>User:</b> {user_name}\n"
        f"🆔 <b>Telegram ID:</b> <code>{user.id}</code>\n"
        f"📱 <b>Group Member:</b> {'✅ Yes' if is_member else '❌ No'}\n\n"
        f"🔥 <b>Database:</b> {'✅ Connected' if db else '❌ Offline Mode'}\n"
        f"🤖 <b>Bot:</b> ✅ Online\n"
    )
    
    # Add error details if there are Firebase issues
    if bot_instance.firebase_error:
        if "Invalid JWT Signature" in bot_instance.firebase_error:
            status_text += f"⚠️ <b>Issue:</b> Firebase Authentication Problem\n"
            status_text += f"🔧 <b>Fix:</b> Service account key needs renewal\n\n"
        else:
            status_text += f"⚠️ <b>Error:</b> {bot_instance.firebase_error[:50]}...\n\n"
    
    status_text += f"📊 <b>Features:</b>\n"
    
    if db:
        status_text += (
            "   ✅ Referral tracking\n"
            "   ✅ Reward distribution\n"
            "   ✅ User data storage\n"
            "   ✅ Earnings history\n"
        )
    else:
        status_text += (
            "   ❌ Referral tracking (offline)\n"
            "   ❌ Reward distribution (offline)\n"
            "   ❌ User data storage (offline)\n"
            "   ✅ Group verification\n"
            "   ✅ Basic commands\n"
        )
    
    status_text += f"\n⏰ <b>Check Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    keyboard = [
        [InlineKeyboardButton("📱 Join Group", url=REQUIRED_GROUP_LINK)],
        [InlineKeyboardButton("🚀 Open Mini App", url=MINI_APP_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        status_text,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = (
        "🤖 <b>Cash Points Bot Commands</b>\n\n"
        "📋 <b>Available Commands:</b>\n"
        "/start - Start the bot and check group membership\n"
        "/help - Show this help message\n"
        "/status - Check bot and database status\n\n"
        "💰 <b>Referral System:</b>\n"
        "🔗 Share your referral link\n"
        "🎁 Earn ৳2 for each successful referral\n"
        "✅ Users must join group to earn you rewards\n\n"
        "⚠️ <b>গুরুত্বপূর্ণ নিয়ম:</b>\n"
        "🔒 Group এ join না করলে withdrawal দেওয়া হবে না\n"
        "💰 শুধুমাত্র group member রা withdrawal করতে পারবে\n\n"
        "📱 <b>Group:</b> Bull Trading Community (BD)\n"
        f"🔗 <b>Link:</b> {REQUIRED_GROUP_LINK}\n\n"
        "👉 Use /start to begin your journey!\n\n"
        f"🔥 Database Status: {'✅ Connected' if db else '❌ Offline Mode'}"
    )
    
    keyboard = [
        [InlineKeyboardButton("📱 Join Group", url=REQUIRED_GROUP_LINK)],
        [InlineKeyboardButton("🚀 Open Mini App", url=MINI_APP_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        help_text,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )


def main():
    """Main function to run the bot"""
    global bot_instance
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Create bot instance
    bot_instance = CashPoinntBot()
    bot_instance.application = application
    
    # Start the bot
    print("🤖 Cash Points Bot Starting...")
    print(f"🔗 Bot Username: @{BOT_USERNAME}")
    print(f"📱 Group: {REQUIRED_GROUP_NAME}")
    print(f"💰 Referral Reward: ৳{REFERRAL_REWARD}")
    print(f"🔥 Firebase: {'✅ Connected' if db else '❌ Not Connected'}")
    
    if not db:
        print("⚠️  FALLBACK MODE: Bot running without database")
        print("📝 Features available: Group verification, basic commands")
        print("🚫 Features disabled: Referral tracking, reward distribution")
    
    print("🚀 Bot is ready to receive commands!")
    
    # Check if running on Railway (production)
    port = int(os.environ.get('PORT', 8080))
    
    if os.environ.get('RAILWAY_ENVIRONMENT'):
        # Production mode - use webhook
        print(f"🚂 Railway Environment Detected - Using Webhook on port {port}")
        
        # Set webhook URL
        webhook_url = os.environ.get('WEBHOOK_URL')
        if webhook_url:
            application.bot.set_webhook(url=f"{webhook_url}/webhook")
            print(f"🔗 Webhook set to: {webhook_url}/webhook")
        
        # Start webhook
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=f"/webhook",
            secret_token=os.environ.get('WEBHOOK_SECRET', 'your-secret-token')
        )
    else:
        # Development mode - use polling
        print("🖥️  Development Environment - Using Polling")
        application.run_polling()


if __name__ == "__main__":
    main()
