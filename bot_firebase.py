import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Firebase Admin SDK
try:
    # Use service account key if available
    service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH')
    if service_account_path and os.path.exists(service_account_path):
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
    else:
        # Use default credentials (for production)
        firebase_admin.initialize_app()
    
    db = firestore.client()
    print("✅ Firebase Admin SDK initialized successfully")
except Exception as e:
    print(f"❌ Firebase initialization failed: {e}")
    db = None

def generate_referral_code(user_id: int) -> str:
    """Generate unique referral code for user"""
    try:
        if not db:
            return f"CP{str(user_id)}"  # Use full telegram ID with CP prefix
        
        user_id_str = str(user_id)
        
        # Check if user already has a referral code
        user_ref = db.collection('users').document(user_id_str)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            if user_data.get('referral_code'):
                return user_data['referral_code']
        
        # Generate new referral code
        referral_code = f"CP{str(user_id)}"  # Use full telegram ID with CP prefix
        
        # Create user document if doesn't exist
        user_data = {
            'telegram_id': user_id_str,
            'referral_code': referral_code,
            'balance': 0,
            'total_earnings': 0,
            'referral_count': 0,
            'is_active': True,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        user_ref.set(user_data, merge=True)
        
        # Create referral code document
        referral_data = {
            'user_id': user_id_str,
            'referral_code': referral_code,
            'is_active': True,
            'created_at': datetime.now(),
            'total_uses': 0,
            'total_earnings': 0
        }
        
        db.collection('referralCodes').document(referral_code).set(referral_data)
        print(f"✅ Referral code created: {referral_code} for user {user_id}")
        
        return referral_code
    except Exception as e:
        print(f"❌ Error generating referral code: {e}")
        return f"CP{str(user_id)}"  # Use full telegram ID with CP prefix

def ensure_user_referral_code(user_id: int, username: str = None) -> str:
    """Ensure user has a referral code, create if missing"""
    try:
        if not db:
            return f"CP{str(user_id)}"  # Use full telegram ID with CP prefix
        
        user_id_str = str(user_id)
        user_ref = db.collection('users').document(user_id_str)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            existing_code = user_data.get('referral_code')
            
            if existing_code:
                # Check if code exists in referralCodes collection
                code_doc = db.collection('referralCodes').document(existing_code).get()
                
                if not code_doc.exists:
                    # Code missing from referralCodes collection, create it
                    referral_data = {
                        'user_id': user_id_str,
                        'referral_code': existing_code,
                        'is_active': True,
                        'created_at': datetime.now(),
                        'total_uses': 0,
                        'total_earnings': 0
                    }
                    db.collection('referralCodes').document(existing_code).set(referral_data)
                    print(f"✅ Fixed missing referral code record: {existing_code} for user {user_id}")
                
                return existing_code
        
        # Create new user and referral code
        return generate_referral_code(user_id)
    except Exception as e:
        print(f"❌ Error ensuring user referral code: {e}")
        return f"CP{str(user_id)}"  # Use full telegram ID with CP prefix

def get_user_data(user_id: int):
    """Get user data from Firebase"""
    try:
        if not db:
            return None
        
        user_doc = db.collection('users').document(str(user_id)).get()
        if user_doc.exists:
            return user_doc.to_dict()
        return None
    except Exception as e:
        print(f"❌ Error getting user data: {e}")
        return None

def update_user_balance(user_id: int, new_balance: float):
    """Update user balance"""
    try:
        if not db:
            return False
        
        user_ref = db.collection('users').document(str(user_id))
        user_ref.update({
            'balance': new_balance,
            'updated_at': datetime.now()
        })
        return True
    except Exception as e:
        print(f"❌ Error updating user balance: {e}")
        return False

def process_referral(referrer_id: int, referred_id: int, reward_amount: int = 2):
    """Process referral and update balances"""
    try:
        if not db:
            return False
        
        referrer_id_str = str(referrer_id)
        referred_id_str = str(referred_id)
        
        # Get referrer data
        referrer_ref = db.collection('users').document(referrer_id_str)
        referrer_doc = referrer_ref.get()
        
        if not referrer_doc.exists:
            print(f"❌ Referrer {referrer_id} not found")
            return False
        
        referrer_data = referrer_doc.to_dict()
        current_balance = referrer_data.get('balance', 0)
        current_referral_count = referrer_data.get('referral_count', 0)
        current_total_earnings = referrer_data.get('total_earnings', 0)
        
        # Update referrer
        new_balance = current_balance + reward_amount
        new_referral_count = current_referral_count + 1
        new_total_earnings = current_total_earnings + reward_amount
        
        referrer_ref.update({
            'balance': new_balance,
            'referral_count': new_referral_count,
            'total_earnings': new_total_earnings,
            'updated_at': datetime.now()
        })
        
        # Update referral code usage
        referral_code = referrer_data.get('referral_code')
        if referral_code:
            code_ref = db.collection('referralCodes').document(referral_code)
            code_doc = code_ref.get()
            
            if code_doc.exists:
                code_data = code_doc.to_dict()
                current_uses = code_data.get('total_uses', 0)
                current_earnings = code_data.get('total_earnings', 0)
                
                code_ref.update({
                    'total_uses': current_uses + 1,
                    'total_earnings': current_earnings + reward_amount
                })
        
        print(f"✅ Referral processed: {referrer_id} earned {reward_amount} points from {referred_id}")
        return True
    except Exception as e:
        print(f"❌ Error processing referral: {e}")
        return False

def add_task_completion(user_id: int, task_type: str, reward_amount: int = 1):
    """Add task completion record"""
    try:
        if not db:
            return False
        
        task_data = {
            'user_id': str(user_id),
            'task_type': task_type,
            'completed_at': datetime.now(),
            'reward_amount': reward_amount
        }
        
        db.collection('taskCompletions').add(task_data)
        
        # Update user balance
        user_ref = db.collection('users').document(str(user_id))
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            current_balance = user_data.get('balance', 0)
            current_total_earnings = user_data.get('total_earnings', 0)
            
            user_ref.update({
                'balance': current_balance + reward_amount,
                'total_earnings': current_total_earnings + reward_amount,
                'updated_at': datetime.now()
            })
        
        print(f"✅ Task completion added: {task_type} for user {user_id}")
        return True
    except Exception as e:
        print(f"❌ Error adding task completion: {e}")
        return False

def check_user_exists(user_id: int) -> bool:
    """Check if user exists in database"""
    try:
        if not db:
            return False
        
        user_doc = db.collection('users').document(str(user_id)).get()
        return user_doc.exists
    except Exception as e:
        print(f"❌ Error checking user existence: {e}")
        return False

def create_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    """Create new user"""
    try:
        if not db:
            return False
        
        user_data = {
            'telegram_id': str(user_id),
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'balance': 0,
            'total_earnings': 0,
            'referral_count': 0,
            'is_active': True,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        db.collection('users').document(str(user_id)).set(user_data)
        
        # Generate referral code
        generate_referral_code(user_id)
        
        print(f"✅ User created: {user_id}")
        return True
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        return False

def get_all_users():
    """Get all users (for admin)"""
    try:
        if not db:
            return []
        
        users = []
        docs = db.collection('users').stream()
        for doc in docs:
            users.append(doc.to_dict())
        return users
    except Exception as e:
        print(f"❌ Error getting all users: {e}")
        return []

def get_all_referral_codes():
    """Get all referral codes (for admin)"""
    try:
        if not db:
            return []
        
        codes = []
        docs = db.collection('referralCodes').stream()
        for doc in docs:
            codes.append(doc.to_dict())
        return codes
    except Exception as e:
        print(f"❌ Error getting all referral codes: {e}")
        return []
