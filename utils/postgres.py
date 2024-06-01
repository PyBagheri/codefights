from django.db import connection

# We'll keep only one cursor.
cursor = connection.cursor()


def pg_try_advisory_xact_lock(i1: int, i2: int = None):
    if i2 is None:
        query = "SELECT pg_try_advisory_xact_lock( %s )"
        params = [i1]
    else:
        query = "SELECT pg_try_advisory_xact_lock( %s , %s )"
        params = [i1, i2]

    cursor.execute(query, params)
    
    return cursor.fetchone()[0]
        

def pg_advisory_xact_lock(i1: int, i2: int = None):
    if i2 is None:
        query = "SELECT pg_advisory_xact_lock( %s )"
        params = [i1]
    else:
        query = "SELECT pg_advisory_xact_lock( %s , %s )"
        params = [i1, i2]

    cursor.execute(query, params)
    
    cursor.fetchone()  # flush the cursor

