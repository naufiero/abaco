# Status codes for actor objects

REQUESTED = 'REQUESTED'
COMPLETE = 'COMPLETE'
SUBMITTED = 'SUBMITTED'
READY = 'READY'
ERROR = 'ERROR'
BUSY = 'BUSY'

# order of permissions implies level; i.e. NONE < READ < EXECUTE < UPDATE
NONE = 'NONE'
READ = 'READ'
EXECUTE = 'EXECUTE'
UPDATE = 'UPDATE'
PERMISSION_LEVELS = (NONE, READ, EXECUTE, UPDATE)

# role set by agaveflask in case the access_control_type is none
ALL_ROLE = 'ALL'

# roles - only used when Agave's JWT Auth is activated.
# the admin role allows users full access to Abaco, including modifying workers assigned to actors.
ADMIN_ROLE = 'Internal/abaco-admin'

# the privileged role allows users to create privileged actors.
PRIVILEGED_ROLE = 'Internal/abaco-privileged'

# the base user role in Abaco. This role isn't authorized to create privileged containers or add workers but is not
# throttled in the number of requests they can make.
USER_ROLE = 'Internal/abaco-user'

# a role with limited (throttled) access -- must be implemented in the Agave APIM tenant.
LIMITED_ROLE = 'Internal/abaco-limited'

roles = [ALL_ROLE, ADMIN_ROLE, PRIVILEGED_ROLE, USER_ROLE, LIMITED_ROLE]