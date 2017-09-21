## Image: abacosamples/py_test ##

When executed, this image will utilize the Abaco Python SDK and print the contents of the context. It can be used
to test basic the basic functionality of the Python SDK against an Abaco instance.

### Executing the actor ###
You might consider passing different content types including JSON in the message to see the context is generated.
Here's an example where we pass JSON:

    ```shell
    $ curl -H "Content-Type: application/json" -d '{"key1": "value1", "key2": "value2" }' -H "Authorization: Bearer $tok" $base/actors/v2/$uuid/messages
    ```

