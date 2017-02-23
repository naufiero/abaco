# Status codes for actor objects

REQUESTED = 'REQUESTED'
COMPLETE = 'COMPLETE'
SUBMITTED = 'SUBMITTED'
READY = 'READY'
ERROR = 'ERROR'
BUSY = 'BUSY'

# order of permissions implies level; i.e. NONE < READ < EXECUTE < UPDATE
PERMISSION_LEVELS = ('NONE', 'READ', 'EXECUTE', 'UPDATE')