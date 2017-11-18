## Image: abacosamples/docker_ps ##

When executed, this image will attempt to interact with the local Docker installtion. It can be used
to test basic the basic functionality of a privileged actor.

### Executing the actor ###
You might consider passing different content types including JSON in the message to see the context is generated.
Here's an example where we pass JSON:

    ```shell
    $ curl -H "Content-Type: application/json" -d '{"key1": "value1", "key2": "value2" }' -H "Authorization: Bearer $tok" $base/actors/v2/$uuid/messages
    ```

