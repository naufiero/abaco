import getpass
import os
import sys
from agavepy.actors import get_context, get_client


def main():
    context = get_context()
    print("Contents of context:")
    for k,v in context.items():
        print("key: {}. value: {}".format(k,v))
    print("Contents of env: {}".format(os.environ))

    # check identity:
    print("*** Posix Identity Information ***")
    try:
        print("Posix username: {}".format(getpass.getuser()))
    except Exception as e:
        # it is possible to get an exception trying to look up the username because the uid may not
        # exist there. Swallow it and keep going.
        print("Got an exception trying to look up the username: {}".format(e))

    print("Posix uid: {}".format(os.getuid()))
    print("Posix gid: {}".format(os.getgid()))

    # instantiate the agavepy client:
    try:
        ag = get_client()
    except Exception as e:
        print("Got exception {} trying to get client.".format(e))
        sys.exit()

    try:
        prof = ag.profiles.get()
        print("This actor was executed by the user with profile: {}".format(prof))
    except Exception as e:
        print("Got an exception trying to get the profile. Exception: {}".format(e))


if __name__ == '__main__':
    main()
