import os
from agavepy.actors import get_context, get_client


def main():
    context = get_context()
    print("Contents of context:")
    for k,v in context.items():
        print("key: {}. value: {}".format(k,v))
    print("Contents of env: {}".format(os.environ))

    # instantiate the agavepy client:
    ag = get_client()
    try:
        prof = ag.profiles.get()
        print("This actor was executed by the user with profile: {}".format(prof))
    except Exception as e:
        print("Got an exception trying to get the profile. Exception: {}".format(e))


if __name__ == '__main__':
    main()
