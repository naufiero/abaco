## Image: abacosamples/py3_func ##

This actor will execute an arbitrary Python3 function that is passed to it after serialization via the cloudpickle
library.

### Executing the actor ###

    ```shell
    $ curl -H "Content-Type: application/json" -d '{"function": "serialized_", "key2": "value2" }' -H "Authorization: Bearer $tok" $base/actors/v2/$uuid/messages
    ```

