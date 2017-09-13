import os
from agavepy.actors import get_context

def main():
    context = get_context()
    print("Contents of context:")
    for k,v in context.items():
        print("key: {}. value: {}".format(k,v))

    print("Contents of env: {}".format(os.environ))



if __name__ == '__main__':
    main()
