"""auth-api — owns users, credentials, and token issuing.

Other services do not share this database; they only trust the JWTs this service
issues (verified with the shared secret via `cplatform.auth`).
"""
