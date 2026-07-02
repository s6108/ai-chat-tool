from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY, validate_env


validate_env()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
