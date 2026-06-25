from slowapi import Limiter
from slowapi.util import get_remote_address

# Singleton Limiter instance configured to use remote IP as key
limiter = Limiter(key_func=get_remote_address)
